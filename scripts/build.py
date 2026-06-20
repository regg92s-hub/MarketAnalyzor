#!/usr/bin/env python3
"""
Hovedbygg for market-analysor.

Kjører hele pipelinen:
  1. Hent priser (yfinance) for alle instrumenter + NOK for TV-lenker
  2. Beregn Northstar-score, risikometrikker, prisserier
  3. Leadership ranking (ROC vs gull/dollar), sjanger-styrke, bredde, regime, par, money flow
  4. Skriv index.json (minifisert) + tre HTML-sider (Lightweight Charts)
  5. Last ned/­selvhost Lightweight Charts-biblioteket

Kjør lokalt:  python scripts/build.py
GitHub Actions kjører dette daglig og deployer docs/ til gh-pages.
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Gjør pakken importerbar uansett arbeidskatalog
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import numpy as np  # noqa: E402


def _json_default(o):
    """Gjør numpy-typer (bool_, int64, float64) JSON-serialiserbare."""
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

from analysor import config, data as datamod, scoring, analytics, regime as regimemod, render, portfolio, backtest as backtestmod, benchmarks as benchmarksmod, paper, roadmap as roadmapmod, validation as validationmod  # noqa: E402
from analysor.config import VERSION, PALETTE  # noqa: E402
from analysor.layout import LWC_CDN, LWC_LOCAL  # noqa: E402
from analysor import indicators as ind  # noqa: E402

OSLO = timezone(timedelta(hours=2))
NOW = datetime.now(OSLO)
DOCS = Path(__file__).resolve().parent.parent / "docs"
CHARTS_HISTORY_DAYS = 400  # antall dagspunkter i prisgrafen


def log(m):
    print(m, flush=True)


def price_series_for_chart(df: pd.DataFrame, days: int = CHARTS_HISTORY_DAYS):
    """[(YYYY-MM-DD, close)] for Lightweight Charts."""
    c = df["close_use"].dropna().tail(days)
    return [(idx.strftime("%Y-%m-%d"), round(float(v), 4)) for idx, v in c.items()]


def chart_data_nsbc(df: pd.DataFrame, days: int = 350) -> dict:
    """
    Rik chart-data med NSBC-indikatorer (beregnet i pandas, sendt som serier):
    candles (OHLC), 12 & 36 SMA, Ichimoku-sky (span A/B). Tegnes på ukentlig
    oppløsning (NSBCs mellom-bilde). Payload-trimmet: ~70 uker, 2-3 desimaler.
    """
    import numpy as np
    d = df.dropna(subset=["close_use"])
    if len(d) < 60:
        return {}
    wk = pd.DataFrame()
    wk["close"] = d["close_use"].resample("W-FRI").last()
    wk["high"] = (d["high"] if "high" in d else d["close_use"]).resample("W-FRI").max()
    wk["low"] = (d["low"] if "low" in d else d["close_use"]).resample("W-FRI").min()
    wk["open"] = (d["open"] if "open" in d else d["close_use"]).resample("W-FRI").first()
    wk = wk.dropna()
    if len(wk) < 60:
        return {}
    weeks = min(len(wk), days // 5)
    wk = wk.tail(weeks + 60)

    sma12 = wk["close"].rolling(12).mean()
    sma36 = wk["close"].rolling(36).mean()
    conv = (wk["high"].rolling(9).max() + wk["low"].rolling(9).min()) / 2
    base = (wk["high"].rolling(26).max() + wk["low"].rolling(26).min()) / 2
    span_a = ((conv + base) / 2)
    span_b = (wk["high"].rolling(52).max() + wk["low"].rolling(52).min()) / 2

    # Adaptiv presisjon: små priser (ratioer) trenger flere desimaler
    lastv = float(wk["close"].iloc[-1])
    nd = 2 if lastv >= 10 else (4 if lastv >= 0.1 else 6)

    def ser(s):
        s = s.dropna().tail(weeks)
        return [(idx.strftime("%y-%m-%d"), round(float(v), nd)) for idx, v in s.items()]

    def candle_ser():
        out = []
        for idx, row in wk.tail(weeks).iterrows():
            out.append({"t": idx.strftime("%y-%m-%d"),
                        "o": round(float(row["open"]), nd), "h": round(float(row["high"]), nd),
                        "l": round(float(row["low"]), nd), "c": round(float(row["close"]), nd)})
        return out

    return {
        "candles": candle_ser(),
        "sma12": ser(sma12), "sma36": ser(sma36),
        "cloud_a": ser(span_a), "cloud_b": ser(span_b),
    }


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "charts").mkdir(exist_ok=True)
    force = os.environ.get("FORCE_RUN", "").lower() in ("1", "true", "yes")
    log(f"market-analysor {VERSION} — start {NOW.isoformat()} (force={force})")

    meta_list = config.all_instruments()
    assets_meta = {m["id"]: m for m in meta_list}

    # 1. Hent priser
    raw = {}
    for m in meta_list:
        log(f"Henter {m['id']}...")
        df, resolved = datamod.fetch_one(m["candidates"])
        if df is None:
            log(f"  MANGLER: {m['id']}")
            continue
        raw[m["id"]] = df
    # NOK for TV-lenker/rotasjon (ikke et scoret instrument)
    nok_df, _ = datamod.fetch_one(["NOK=X"])
    if nok_df is not None:
        raw["NOK"] = nok_df

    # 2. Score + risiko + prisserie per instrument
    assets = {}
    gld = raw.get("GLD")
    for m in meta_list:
        iid = m["id"]
        a = {
            "id": iid, "display_name": m["label"], "symbol_label": m["symbol_label"],
            "sector": m["sector"], "subclass": m["subclass"],
            "category_title": m["category_title"],
        }
        df = raw.get(iid)
        if df is None:
            a["missing_data"] = True
            assets[iid] = a
            continue
        frames = datamod.resample_frames(df)
        score, meta = scoring.nsbc_score(frames)
        a["northstar_score"] = score
        a["missing_data"] = False
        a["price_last"] = round(float(df["close_use"].iloc[-1]), 4)
        a["price_series"] = price_series_for_chart(df)
        a["chart_nsbc"] = chart_data_nsbc(df)
        a["risk"] = ind.risk_metrics(df["close_use"], config.RISK_LOOKBACK_DAYS, config.RISK_FREE_ANNUAL)
        # NSBC-tilstand: langtid (regime) × korttid (timing) + evidens
        a["lt_state"] = meta.get("long_term")
        a["st_state"] = meta.get("short_term")
        a["evidence"] = meta.get("evidence", [])
        a["ticks"] = meta.get("ticks", 0)
        a["stretched"] = meta.get("stretched", False)
        a["breakout"] = meta.get("breakout", False)
        a["dist36_w"] = meta.get("dist36")
        a["state_label"] = scoring.state_label(meta.get("long_term"), meta.get("short_term"))
        a["stage"] = meta.get("stage")
        a["stage_label"] = meta.get("stage_label")
        a["stage_reason"] = meta.get("stage_reason")
        wf = meta.get("frames", {}).get("weekly", {})
        qf = meta.get("frames", {}).get("quarterly", {})
        mf = meta.get("frames", {}).get("monthly", {})
        # Avstand fra 12 & 36 MA på ukentlig OG månedlig (NSBC distance-gauge)
        a["dist_w"] = {"d12": wf.get("dist12"), "d36": wf.get("dist36")}
        a["dist_m"] = {"d12": mf.get("dist12"), "d36": mf.get("dist36")}
        # porteføljens overkjøpt/stretched-sjekk bruker nå NSBC-evidens
        a["rsi_q"] = qf.get("srsi_k")
        a["overbought_w"] = bool(wf.get("srsi_overbought"))
        a["stretched_w"] = bool(wf.get("stretched"))
        # sektor-trend: over 12&36 MA (ukentlig) = NSBC bull-gate
        a["close_above_sma50_w"] = wf.get("above_both_ma")
        # slår gull (ROC 1M/3M)
        if gld is not None and iid != "GLD":
            b = ind.beats_baseline(df["close_use"], gld["close_use"],
                                   config.BEATS_ROC_HORIZONS, config.ROC_HORIZONS)
            a["gold_beat"] = {"beats": b["beats"], "tf_over": b["tf_over"]} if b["beats"] is not None else None
        else:
            a["gold_beat"] = None
        assets[iid] = a
        log(f"  OK {iid}: score={score}")

    # 3. Sektorscore + trend (weekly 50MA)
    sector_summary = {}
    sec_scores = {}
    for iid, a in assets.items():
        if a.get("missing_data"):
            continue
        sec_scores.setdefault(a["sector"], []).append(iid)
    for sec, iids in sec_scores.items():
        vals = [assets[i]["northstar_score"] for i in iids]
        avg = round(sum(vals) / len(vals), 1)
        over = sum(1 for i in iids if assets[i].get("close_above_sma50_w") is True)
        tot = sum(1 for i in iids if assets[i].get("close_above_sma50_w") is not None)
        pct_over = round(over / tot * 100) if tot else None
        # Aggreger stage: hvor mange medlemmer i nedtrend (Stage 4) vs opptrend (Stage 2)
        stages = [assets[i].get("stage") for i in iids if assets[i].get("stage")]
        n_down = sum(1 for s in stages if s == 4)
        n_up = sum(1 for s in stages if s == 2)
        n_stretch = sum(1 for i in iids if assets[i].get("stretched"))
        if tot and over / tot >= 0.5:
            ttxt, tcol = f"Opptrend — {pct_over}% over 30-ukers MA (ukentlig)", PALETTE["up"]
        elif tot:
            ttxt, tcol = f"Svak — bare {pct_over}% over 30-ukers MA (ukentlig)", PALETTE["warn"]
        else:
            ttxt, tcol = "Ingen data", PALETTE["neutral"]
        # KORRIGERT etikett: skiller nedtrend fra strukket på sektornivå
        if stages and n_down >= len(stages) * 0.5:
            lab, scol = "Nedtrend (Stage 4)", PALETTE["down"]
        elif n_stretch >= max(1, len(iids) * 0.5):
            lab, scol = "Strukket (FOMO-sone)", PALETTE["warn"]
        else:
            lab, scol = scoring.score_label(int(round(avg)))
        # Plain-language forklaring i boksen
        if lab.startswith("Nedtrend"):
            explain = (f"{n_down} av {len(iids)} instrumenter er i nedtrend (under fallende 12&36-MA). "
                       "Lav score = ingen bullish bevis, IKKE strukket. Unngå nye kjøp; vent på base.")
        elif lab.startswith("Strukket"):
            explain = ("Sektoren er i opptrend, men flere medlemmer er strukket fra 36-MA (FOMO-sone). "
                       "Eiere kan holde; nye kjøp har høy risiko. Vent på tilbaketrekk/konsolidering.")
        elif avg >= 70:
            explain = "Flere medlemmer i ekte lavrisiko-entry (over trend, ikke strukket, bryter ut)."
        else:
            explain = (f"Snittscore {avg}/100 over ukentlig/månedlig/kvartal. "
                       f"{n_up} i opptrend, {n_down} i nedtrend. Se enkeltinstrumenter for detaljer.")
        sector_summary[sec] = {
            "display": "Råvarer" if sec == "Rawarer" else sec,
            "avg_score": avg, "label": lab, "score_col": scol,
            "trend_txt": ttxt, "trend_col": tcol,
            "over_ma50": over, "total_ma50": tot, "pct_over": pct_over, "n": len(iids),
            "n_down": n_down, "n_up": n_up, "explain": explain,
        }

    # 4. Analyselag
    ranking_gold = analytics.build_ranking(raw, "GLD", "Gull (GLD)", assets_meta)
    ranking_dxy = analytics.build_ranking(raw, "UUP", "Dollar (UUP)", assets_meta)
    genres = analytics.genre_strength(raw, assets_meta)
    universe = [m["id"] for m in meta_list if not assets.get(m["id"], {}).get("missing_data")]
    breadth = analytics.breadth(raw, universe)
    glob_breadth = analytics.global_breadth(raw, config.BREADTH_GLOBAL_IDS)
    pairs = analytics.cyclical_pairs(raw)
    flow = analytics.money_flow(raw)
    rot = analytics.rotation(raw, assets_meta)
    rrg = analytics.build_rrg(raw, assets_meta)
    corr = analytics.build_correlation(raw)
    bt = backtestmod.run_backtest(raw, config.CYCLICAL_IDS, top_n=5)
    # Anbefalings-backtest: "hvis alle NSBC-anbefalinger var fulgt"
    rec_bt = backtestmod.run_recommendation_backtest(raw, config.CYCLICAL_IDS)
    # Auto-roadmaps (NSBC-stil) for hele universet
    roadmaps = roadmapmod.build_all_roadmaps(raw, assets_meta, gld=raw.get("GLD"))
    # Hit-rate-validering fra score-historikk
    score_hist = load_score_history()
    validation = validationmod.forward_returns(raw, raw.get("GLD"), score_hist)
    reg = regimemod.build_regime(os.environ.get("FRED_API_KEY", ""))
    # Panikk-tilstand (Daniel & Moskowitz) inn i regimet
    pstate = analytics.panic_state(raw)
    if pstate:
        reg["panic"] = pstate

    # Benchmarks: norsk KPI (SSB), USDNOK/NOWA (Norges Bank), US CPI, gull
    bench = benchmarksmod.build_benchmarks(
        raw, regimemod.fetch_fred_series, os.environ.get("FRED_API_KEY", ""))

    # Regime-historikk: append dagens composite-score -> tidslinje-stripe
    today = NOW.strftime("%Y-%m-%d")
    rhist = load_prev_json("regime_history.json") or {"dates": [], "scores": [], "states": []}
    comp = reg.get("composite") or {}
    if comp.get("score") is not None and (not rhist["dates"] or rhist["dates"][-1] != today):
        rhist["dates"].append(today)
        rhist["scores"].append(comp["score"])
        rhist["states"].append(comp.get("state", ""))
        for k in ("dates", "scores", "states"):
            rhist[k] = rhist[k][-365:]
    with open(DOCS / "regime_history.json", "w", encoding="utf-8") as f:
        json.dump(rhist, f, separators=(",", ":"), default=_json_default)

    # Paper-ledger ("regelen vs deg") + brukerens synkede portefølje
    usdnok_now = (round(float(raw["NOK"]["close_use"].iloc[-1]), 4)
                  if raw.get("NOK") is not None else None)
    ledger = paper.update_paper_ledger(
        load_prev_json("paper_ledger.json"), raw, config.CYCLICAL_IDS, usdnok_now, today)
    user_pf_raw = load_user_portfolio()
    user_val = paper.value_user_portfolio(user_pf_raw, raw, usdnok_now, assets)
    if user_val:
        ledger["actual_curve"] = (ledger.get("actual_curve") or [])[-730:]
        if not ledger["actual_curve"] or ledger["actual_curve"][-1][0] != today:
            ledger["actual_curve"].append((today, user_val["total_nok"]))
    with open(DOCS / "paper_ledger.json", "w", encoding="utf-8") as f:
        json.dump(ledger, f, separators=(",", ":"), default=_json_default)

    # 5. Samlet datamodell
    model = {
        "version": VERSION,
        "generated_local": NOW.isoformat(),
        "assets": assets,
        "sector_summary": sector_summary,
        "ranking_gold": ranking_gold,
        "ranking_dxy": ranking_dxy,
        "genre_strength": genres,
        "breadth": breadth,
        "global_breadth": glob_breadth,
        "cyclical_pairs": pairs,
        "money_flow": flow,
        "rotation": rot,
        "rrg": rrg,
        "correlation": corr,
        "backtest": bt,
        "rec_backtest": rec_bt,
        "roadmaps": roadmaps,
        "validation": validation,
        "regime": reg,
        "benchmarks": bench,
        "regime_history": rhist,
        "paper": {"curve": ledger.get("curve", [])[-400:],
                  "actual_curve": ledger.get("actual_curve", [])[-400:],
                  "events": ledger.get("events", [])[-6:],
                  "positions": sorted(ledger.get("positions", {}).keys()),
                  "start_nok": ledger.get("start_nok")},
        "user_portfolio": user_val,
        "notes": {"instrument_count": len(universe)},
        "usdnok": (round(float(raw["NOK"]["close_use"].iloc[-1]), 4)
                   if raw.get("NOK") is not None else None),
    }

    # 5b. Signal-snapshot + diff mot forrige bygg + Discord-varsel
    snapshot = signals_snapshot(model)
    prev = load_prev_signals()
    changes = compute_changes(prev, snapshot)
    model["changes"] = changes
    with open(DOCS / "signals.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, separators=(",", ":"), default=_json_default)
    log(f"signals.json skrevet ({len(changes)} endringer siden forrige bygg)")
    notify_discord(changes, user_val)

    # 5c. Append dagens NSBC-scorer til historikk (for hit-rate-validering)
    append_score_history(assets)

    # AI-morgenbrief (valgfri, krever ANTHROPIC_API_KEY) — strengt grunnet
    # i beregnede signaler, aldri egne tall.
    model["ai_brief"] = build_ai_brief(model)

    # 6. Skriv index.json (minifisert). Strip tunge chart-data — trend-siden
    # rendrer ikke per-instrument-charts, og report/roadmap-sidene embedder
    # sine egne chart-data direkte i HTML. Dette holder index.json liten.
    import copy as _copy
    slim = dict(model)
    slim_assets = {}
    for iid, a in model.get("assets", {}).items():
        a2 = {k: v for k, v in a.items() if k not in ("chart_nsbc", "price_series")}
        slim_assets[iid] = a2
    slim["assets"] = slim_assets
    # Roadmaps: dropp candle-arrays fra index.json (kun HTML trenger dem)
    slim_rm = {}
    for iid, entry in model.get("roadmaps", {}).items():
        e2 = {}
        for variant, rm in entry.items():
            if isinstance(rm, dict):
                e2[variant] = {k: v for k, v in rm.items() if k != "chart"}
            else:
                e2[variant] = rm
        slim_rm[iid] = e2
    slim["roadmaps"] = slim_rm
    with open(DOCS / "index.json", "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, separators=(",", ":"), default=_json_default)
    log(f"index.json skrevet ({(DOCS/'index.json').stat().st_size} bytes)")

    # 7. HTML-sider
    (DOCS / "index.html").write_text(render.render_trend(model), encoding="utf-8")
    (DOCS / "report.html").write_text(render.render_report(model), encoding="utf-8")
    (DOCS / "roadmap.html").write_text(render.render_roadmap(model), encoding="utf-8")
    (DOCS / "portfolio.html").write_text(portfolio.render_portfolio(model), encoding="utf-8")
    (DOCS / "backtest.html").write_text(render.render_backtest(model), encoding="utf-8")
    log("HTML-sider skrevet")

    # 8. Selvhost Lightweight Charts (last ned hvis mangler)
    ensure_lwc()

    # 8b. PWA-ressurser (manifest, service worker, ikoner) — installerbar
    # hjemskjerm + offline. Push krever server -> Discord forblir varselkanal.
    write_pwa_assets()

    # 9. .nojekyll så GitHub Pages ikke prosesserer
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    log(f"FERDIG — {len(universe)} instrumenter, versjon={VERSION}")


def ensure_lwc():
    """Last ned Lightweight Charts til docs/ for selvhosting (én gang)."""
    dest = DOCS / LWC_LOCAL
    if dest.exists() and dest.stat().st_size > 50000:
        log("Lightweight Charts allerede selvhostet")
        return
    try:
        import urllib.request
        log("Laster ned Lightweight Charts for selvhosting...")
        urllib.request.urlretrieve(LWC_CDN, dest)
        log(f"  lagret {dest.stat().st_size} bytes")
    except Exception as e:
        log(f"  ADVARSEL: klarte ikke laste ned LWC ({e}). Grafer vil ikke vises før filen finnes.")


# ── Signal-diff + Discord-varsling ───────────────────────────────
def signals_snapshot(model: dict) -> dict:
    """Kompakt snapshot av dagens signaler for diff mot neste bygg."""
    snap = {"date": NOW.strftime("%Y-%m-%d")}
    snap["genres"] = {g["genre"]: g["state"] for g in model.get("genre_strength", [])}
    snap["gold_beat"] = {
        iid: (a.get("gold_beat") or {}).get("beats")
        for iid, a in model.get("assets", {}).items()
        if not a.get("missing_data") and a.get("gold_beat") is not None
    }
    rot = model.get("rotation") or {}
    snap["rotation_beats"] = sorted(x["id"] for x in rot.get("beats", []))
    comp = (model.get("regime") or {}).get("composite") or {}
    snap["regime_state"] = comp.get("state")
    br = model.get("breadth") or {}
    snap["breadth50"] = br.get("pct_over_50ma")
    return snap


def load_score_history() -> dict:
    """Score-historikk (snapshots) for hit-rate-validering."""
    hist = load_prev_json("history/score_history.json") or {}
    return hist if isinstance(hist, dict) else {}


def append_score_history(assets: dict):
    """Append dagens scorer til docs/history/score_history.json (en per dag)."""
    hist = load_score_history()
    today = NOW.strftime("%Y-%m-%d")
    row = {iid: a["northstar_score"] for iid, a in assets.items()
           if not a.get("missing_data") and a.get("northstar_score") is not None}
    row["_real"] = True
    hist[today] = row
    keys = sorted(hist.keys())
    if len(keys) > 520:
        for k in keys[:-520]:
            hist.pop(k, None)
    hdir = DOCS / "history"
    hdir.mkdir(parents=True, exist_ok=True)
    with open(hdir / "score_history.json", "w", encoding="utf-8") as f:
        json.dump(hist, f, separators=(",", ":"), default=_json_default)
    log(f"score_history.json: {len(hist)} datoer")


def load_prev_json(name: str) -> dict | None:
    """Hent en JSON-fil fra forrige bygg: lokal docs/<name>, ellers gh-pages rå-URL."""
    local = DOCS / name
    if local.exists():
        try:
            return json.loads(local.read_text(encoding="utf-8"))
        except Exception:
            pass
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if repo:
        try:
            import requests
            url = f"https://raw.githubusercontent.com/{repo}/gh-pages/{name}"
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            log(f"  klarte ikke hente forrige {name}: {e}")
    return None


def load_prev_signals() -> dict | None:
    """Forrige byggs signaler (spesialtilfelle av load_prev_json)."""
    return load_prev_json("signals.json")


def load_user_portfolio() -> dict | None:
    """
    Brukerens synkede portefølje fra docs/portfolio.json (committet via
    eksport-knappen på porteføljesiden). Leses kun fra repoet (main-branch
    checkout under bygg) — aldri fra klienten. Mangler den, kjøres alt uten.
    """
    p = DOCS.parent / "docs" / "portfolio.json"
    # docs/portfolio.json ligger i repoet (ikke generert) -> sjekk repo-roten
    candidates = [DOCS / "portfolio.json", Path(__file__).resolve().parent.parent / "docs" / "portfolio.json"]
    for c in candidates:
        if c.exists():
            try:
                return json.loads(c.read_text(encoding="utf-8"))
            except Exception:
                pass
    return None


def build_ai_brief(model: dict) -> dict | None:
    """
    AI-morgenbrief på norsk (~150-220 ord), strengt grunnet i beregnede signaler.
    Krever ANTHROPIC_API_KEY. Modell via ANTHROPIC_MODEL (default haiku).
    Degraderer til None uten nøkkel eller ved enhver feil.
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        log("AI-brief: ingen ANTHROPIC_API_KEY (hopper over)")
        return None
    try:
        import requests
        reg = model.get("regime", {})
        comp = reg.get("composite", {})
        # Kompakt, FAKTISK signal-subsett — modellen får KUN disse tallene
        facts = {
            "regime": {"state": comp.get("state"), "score": comp.get("score"),
                       "kort": {k: v.get("label") for k, v in reg.items()
                                if isinstance(v, dict) and "label" in v}},
            "endringer": model.get("changes", []),
            "ledere_mot_gull": [r["label"] for r in model.get("ranking_gold", {}).get("rows", [])[:5]
                                if r.get("beats")],
            "sjangrer_medvind": [g["genre"] for g in model.get("genre_strength", [])
                                 if g.get("medvind")],
            "bredde_50": model.get("breadth", {}).get("pct_over_50ma"),
            "paper_vs_start": {
                "start": model.get("paper", {}).get("start_nok"),
                "naa": (model.get("paper", {}).get("curve") or [[None, None]])[-1][1]},
        }
        sys_prompt = (
            "Du er en nøktern norsk markedsanalytiker. Skriv en morgenbrief på 150-220 ord "
            "basert UTELUKKENDE på de oppgitte tallene. Ikke finn på tall, priser eller "
            "hendelser. Si 'ukjent' hvis noe mangler. Vev regime, endringer, ledere mot gull "
            "og bredde til en sammenhengende tekst. Avslutt med 'Ikke finansrådgivning.' "
            "Ingen punktlister, kun prosa.")
        payload = {
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5"),
            "max_tokens": 600,
            "system": sys_prompt,
            "messages": [{"role": "user",
                          "content": "Signaler i dag (JSON):\n" + json.dumps(facts, ensure_ascii=False)}],
        }
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"},
                          json=payload, timeout=40)
        if r.status_code != 200:
            log(f"AI-brief: API {r.status_code} (hopper over)")
            return None
        text = "".join(b.get("text", "") for b in r.json().get("content", [])
                       if b.get("type") == "text").strip()
        if not text:
            return None
        log(f"AI-brief: generert ({len(text)} tegn)")
        return {"text": text, "model": payload["model"], "date": NOW.strftime("%Y-%m-%d")}
    except Exception as e:
        log(f"AI-brief: feil ({e})")
        return None


def compute_changes(prev: dict | None, cur: dict) -> list:
    """Menneskelesbare endringer siden forrige bygg (norsk)."""
    if not prev:
        return []
    ch = []
    pg, cg = prev.get("genres", {}), cur.get("genres", {})
    for genre, state in cg.items():
        old = pg.get(genre)
        if old is not None and old != state:
            icon = "▲" if state == "I medvind" else ("▼" if state == "Nedadgående" else "•")
            ch.append(f"{icon} Sjanger {genre}: {old} → {state}")
    pb, cb = prev.get("gold_beat", {}), cur.get("gold_beat", {})
    flipped_up = [i for i, v in cb.items() if v is True and pb.get(i) is False]
    flipped_dn = [i for i, v in cb.items() if v is False and pb.get(i) is True]
    if flipped_up:
        ch.append("▲ Slår gull nå: " + ", ".join(sorted(flipped_up)))
    if flipped_dn:
        ch.append("▼ Taper mot gull nå: " + ", ".join(sorted(flipped_dn)))
    if prev.get("regime_state") and cur.get("regime_state") and \
            prev["regime_state"] != cur["regime_state"]:
        ch.append(f"⚠ Regime: {prev['regime_state']} → {cur['regime_state']}")
    p50, c50 = prev.get("breadth50"), cur.get("breadth50")
    if p50 is not None and c50 is not None:
        if p50 >= 50 > c50:
            ch.append(f"▼ Bredde under 50% (over 50d-MA: {p50}% → {c50}%)")
        elif p50 < 50 <= c50:
            ch.append(f"▲ Bredde over 50% (over 50d-MA: {p50}% → {c50}%)")
    return ch


def notify_discord(changes: list, user_val: dict | None = None):
    """Send endringer + dine posisjons-verdikter til Discord (DISCORD_WEBHOOK_URL)."""
    url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        log("Discord: ingen webhook satt (hopper over)")
        return
    # Posisjoner som krever handling (SKALER AV / VURDER SKALER AV)
    action_lines = []
    if user_val:
        for r in user_val.get("rows", []):
            if r["verdict"] in ("SKALER AV", "VURDER SKALER AV"):
                action_lines.append(f"• {r['sym']}: {r['verdict']} ({r['why']})")
    if not changes and not action_lines:
        log("Discord: ingen endringer å varsle")
        return
    try:
        import requests
        body = "**📊 Market Analysor — " + NOW.strftime("%d.%m.%Y") + "**\n"
        if changes:
            body += "\n".join(changes)
        if action_lines:
            body += "\n\n**Dine posisjoner:**\n" + "\n".join(action_lines)
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if repo:
            owner, name = repo.split("/", 1)
            body += f"\n<https://{owner}.github.io/{name}/>"
        r = requests.post(url, json={"content": body[:1950]}, timeout=20)
        log(f"Discord: varsel sendt ({r.status_code})")
    except Exception as e:
        log(f"Discord: feil ved sending ({e})")


def write_pwa_assets():
    """Skriv manifest, service worker og to ikoner (PWA-installasjon + offline)."""
    manifest = {
        "name": "MarketAnalyzor", "short_name": "Analysor",
        "start_url": ".", "scope": ".", "display": "standalone",
        "background_color": "#0b0d10", "theme_color": "#0b0d10",
        "description": "Gull-relativt, regime-basert markeds-dashboard",
        "icons": [
            {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    (DOCS / "manifest.webmanifest").write_text(json.dumps(manifest), encoding="utf-8")

    # Service worker: network-first for data (.json), cache-first for resten.
    sw = """const CACHE = 'analysor-v5';
const CORE = ['./','./index.html','./report.html','./roadmap.html','./portfolio.html','./backtest.html',
  './lightweight-charts.standalone.production.js','./manifest.webmanifest'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(
    ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = e.request.url;
  if (url.endsWith('.json')) {                       // data: network-first
    e.respondWith(fetch(e.request).then(r => {
      const cp = r.clone(); caches.open(CACHE).then(c => c.put(e.request, cp)); return r;
    }).catch(() => caches.match(e.request)));
  } else {                                           // shell: cache-first
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});
"""
    (DOCS / "sw.js").write_text(sw, encoding="utf-8")

    # Ikoner: ren-Python PNG (ingen Pillow). Mørk bakgrunn + blå trekant (opp).
    _write_icon_png(DOCS / "icon-192.png", 192)
    _write_icon_png(DOCS / "icon-512.png", 512)
    log("PWA-ressurser skrevet (manifest, sw.js, ikoner)")


def _write_icon_png(path: Path, size: int):
    """Skriv en enkel PNG uten eksterne biblioteker (zlib + struct + CRC)."""
    import struct
    import zlib
    bg = (11, 13, 16)       # --bg
    blue = (0, 114, 178)    # Okabe-Ito blå
    cx = size / 2
    # Trekant (pilspiss opp) sentrert
    top_y, base_y = size * 0.26, size * 0.74
    half = size * 0.26
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # filter-byte per rad
        for x in range(size):
            r, g, b = bg
            if top_y <= y <= base_y:
                frac = (y - top_y) / (base_y - top_y)
                w = half * frac
                if (cx - w) <= x <= (cx + w):
                    r, g, b = blue
            rows += bytes((r, g, b))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    idat = zlib.compress(bytes(rows), 9)
    png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    path.write_bytes(png)


if __name__ == "__main__":
    main()
