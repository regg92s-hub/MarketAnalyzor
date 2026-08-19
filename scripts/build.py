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
from analysor import config, data as datamod, scoring, analytics, regime as regimemod, render, portfolio  # noqa: E402
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
        score, parts = scoring.northstar_score(frames)
        a["northstar_score"] = score
        a["missing_data"] = False
        a["price_last"] = round(float(df["close_use"].iloc[-1]), 4)
        a["price_series"] = price_series_for_chart(df)
        a["risk"] = ind.risk_metrics(df["close_use"], config.RISK_LOOKBACK_DAYS, config.RISK_FREE_ANNUAL)
        # kvartals-indikatorer for porteføljens overkjøpt-sjekk
        q = parts.get("quarterly", {})
        a["rsi_q"] = q.get("rsi14"); a["macd_q"] = q.get("macd_hist"); a["d36_q"] = (q.get("dist_to_36MA") or 0)/100.0 if q.get("dist_to_36MA") is not None else None
        # weekly 50MA for sektor-trend
        w = parts.get("weekly", {})
        a["close_above_sma50_w"] = w.get("close_above_sma50")
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
        if tot and over / tot >= 0.5:
            ttxt, tcol = "Opptrend", PALETTE["up"]
        elif tot:
            ttxt, tcol = "Dipp i trend", PALETTE["warn"]
        else:
            ttxt, tcol = "Ingen data", PALETTE["neutral"]
        lab, scol = scoring.score_label(int(round(avg)))
        sector_summary[sec] = {
            "display": "Råvarer" if sec == "Rawarer" else sec,
            "avg_score": avg, "label": lab, "score_col": scol,
            "trend_txt": ttxt, "trend_col": tcol,
            "over_ma50": over, "total_ma50": tot, "n": len(iids),
        }

    # 4. Analyselag
    ranking_gold = analytics.build_ranking(raw, "GLD", "Gull (GLD)", assets_meta)
    ranking_dxy = analytics.build_ranking(raw, "UUP", "Dollar (UUP)", assets_meta)
    genres = analytics.genre_strength(raw, assets_meta)
    universe = [m["id"] for m in meta_list if not assets.get(m["id"], {}).get("missing_data")]
    breadth = analytics.breadth(raw, universe)
    pairs = analytics.cyclical_pairs(raw)
    flow = analytics.money_flow(raw)
    rot = analytics.rotation(raw, assets_meta)
    reg = regimemod.build_regime(os.environ.get("FRED_API_KEY", ""))

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
        "cyclical_pairs": pairs,
        "money_flow": flow,
        "rotation": rot,
        "regime": reg,
        "notes": {"instrument_count": len(universe)},
    }

    # 6. Skriv index.json (minifisert -> mindre payload, gzip på toppen via Pages)
    with open(DOCS / "index.json", "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, separators=(",", ":"))
    log(f"index.json skrevet ({(DOCS/'index.json').stat().st_size} bytes)")

    # 7. HTML-sider
    (DOCS / "index.html").write_text(render.render_trend(model), encoding="utf-8")
    (DOCS / "report.html").write_text(render.render_report(model), encoding="utf-8")
    (DOCS / "portfolio.html").write_text(portfolio.render_portfolio(model), encoding="utf-8")
    log("HTML-sider skrevet")

    # 8. Selvhost Lightweight Charts (last ned hvis mangler)
    ensure_lwc()

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


if __name__ == "__main__":
    main()
