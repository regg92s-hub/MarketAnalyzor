"""
v17: Aksje-screener — motor.

Kjøres UKENTLIG (egen workflow, screener.yml), ikke i det daglige bygget.
Henter fundamentaldata per aksje i stock_universe.UNIVERSE via yfinance
(defensivt, hopper over enkeltaksjer som feiler i stedet for å velte hele
kjøringen — samme mønster som resten av siden), beregner:
  - Omsetningsvekst YoY og QoQ
  - EPS-vekst YoY og QoQ
  - Profit margin (netto)
  - D/E (total gjeld / egenkapital)
  - Innsidekjøp siste 90 dager (KUN USA, via SEC Form 4 — se _sec_insider_buy)

Rangerer mot brukerens skjermer:
  VEKST:            omsetningsvekst YoY > 50%  OG  QoQ > 40%
  VALUE:            EPS-vekst YoY > 50%  OG  QoQ > 40%  OG  margin > 10%  OG  D/E < 1,2
  VEKST MED OPPSIDE (v20): blant aksjene med reell omsetningsvekst (minst ett
                    vekstkrav oppfylt) — rangert etter tre fremoverskuende mål:
                    PEG-ratio < 2 (prisen er fornuftig relativt til inntjeningsveksten),
                    avstand fra 200-dagers snitt < 25% (ikke allerede strukket),
                    analytikernes kursmål > 10% over dagens kurs (markedet ser
                    fortsatt oppside). Svarer på "har vokst OG har mer å gå på" —
                    Vekst/Value over svarer kun på "har vokst". Alle tre feltene
                    hentes fra samme yfinance .info-kall som resten av
                    fundamentaldataene, altså ingen ekstra nettverkskostnad.

TEKNISK/NORTHSTAR-LAG (v21): fundamentaldata svarer på HVA som er bra å eie —
den sier ingenting om NÅR. Hver aksje kjøres derfor gjennom akkurat samme
NSBC-metodikk (scoring.nsbc_score) som resten av siden bruker på ETF-ene i
det daglige bygget — Trend Navigator (12/36-SMA), Ichimoku-sky, Stage-analyse,
distance-fra-36-SMA (stretched/FOMO-sjekk) og breakout-fra-konsolidering — på
aksjens egen ukentlige/månedlige/kvartalsvise prishistorikk (data.resample_frames,
hentet via samme yf.Ticker-objekt som fundamentaldataene, altså kun ÉN ekstra
forespørsel per aksje). Resultatet ("Northstar-score" 0-100 + stage) brukes
som sekundært sorteringskriterium i alle tre listene — blant ellers like
kandidater rangeres den med bedre teknisk oppsett (lavrisiko-entry) foran en
som er strukket eller i nedtrend. Degraderer grasiøst til "ukjent" for aksjer
med for kort historikk (typisk nylige børsnoteringer) til at kvartals-/
månedsrammene gir mening — samme filosofi som PEG/analytiker-mål over.

Kravene over er bevisst strenge (se README) — de fleste reelle kandidater vil
oppfylle NOEN, ikke alle, kriteriene. Vi rangerer derfor etter en dekningsgrad
("hvor mange av kravene er oppfylt") i stedet for en hard alt-eller-ingenting-
filtrering som ofte ville gitt tomme lister. Hvert krav vises eksplisitt per
aksje slik at du selv ser nøyaktig hva som er oppfylt.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from .stock_universe import SEED_UNIVERSE, REGIONS


def build_universe():
    """v18: kombinerer håndplukket seed-liste med dynamisk hentede
    indekser (Wikipedia) — se universe_fetch.py. Kjøres identisk i hver
    parallelle chunk-jobb (deterministisk rekkefølge) slik at chunk-index
    peker på samme skive av universet i alle jobbene."""
    from . import universe_fetch
    return universe_fetch.build_expanded_universe(SEED_UNIVERSE)


def _safe_float(x):
    try:
        if x is None:
            return None
        v = float(x)
        return v if v == v else None  # NaN-sjekk
    except Exception:
        return None


def _pct_growth(new, old):
    if new is None or old is None or old == 0:
        return None
    try:
        return (new / old - 1) * 100 if old > 0 else None
    except Exception:
        return None


# v21: NSBC/Northstar-teknisk lag — se moduldocstringen. Ukjent-verdier for
# aksjer med for kort/manglende historikk til at rammene gir mening.
_TA_UNKNOWN = {
    "ta_score": None, "ta_stage": None, "ta_stage_label": None,
    "ta_long_term": None, "ta_short_term": None,
    "ta_stretched": False, "ta_breakout": False, "ta_dist36": None,
}


def _fetch_technical(t):
    """Kjør NSBC-metodikken (scoring.nsbc_score) på aksjens egen prishistorikk.
    Gjenbruker det allerede instansierte yf.Ticker-objektet `t` — én ekstra
    forespørsel (.history), ingen ny Ticker-instansiering. Aldri fatal: enhver
    feil eller for kort historikk gir _TA_UNKNOWN, ikke et krasj som velter
    hele fundamentalhentingen for aksjen."""
    try:
        from . import data as datamod, scoring
        hist = t.history(period="5y", auto_adjust=True)
        if hist is None or hist.empty or len(hist) < 60:
            return _TA_UNKNOWN
        df = pd.DataFrame(index=hist.index)
        df["close_use"] = hist["Close"]
        df["high"] = hist["High"] if "High" in hist else hist["Close"]
        df["low"] = hist["Low"] if "Low" in hist else hist["Close"]
        df["open"] = hist["Open"] if "Open" in hist else hist["Close"]
        df["volume"] = hist["Volume"] if "Volume" in hist else np.nan
        df = df.dropna(subset=["close_use"])
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        frames = datamod.resample_frames(df)
        score, meta = scoring.nsbc_score(frames)
        if not meta or meta.get("stage") is None:
            return _TA_UNKNOWN
        return {
            "ta_score": score,
            "ta_stage": meta.get("stage"),
            "ta_stage_label": meta.get("stage_label"),
            "ta_long_term": meta.get("long_term"),
            "ta_short_term": meta.get("short_term"),
            "ta_stretched": bool(meta.get("stretched")),
            "ta_breakout": bool(meta.get("breakout")),
            "ta_dist36": meta.get("dist36"),
        }
    except Exception:
        return _TA_UNKNOWN


def fetch_fundamentals(ticker: str):
    """Hent kvartalsvise/årlige fundamentaltall for én aksje via yfinance.
    Returnerer dict eller None ved feil (hoppes over av kalleren)."""
    try:
        import yfinance as yf
    except Exception:
        return None
    for attempt in range(3):
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            qfin = t.quarterly_financials  # kolonner = kvartaler, nyest først
            afin = t.financials
            qbs = t.quarterly_balance_sheet
            bs = t.balance_sheet

            def _row(df, *names):
                if df is None or df.empty:
                    return None
                for n in names:
                    if n in df.index:
                        return df.loc[n]
                return None

            rev_q = _row(qfin, "Total Revenue", "TotalRevenue")
            ni_q = _row(qfin, "Net Income", "NetIncome")
            rev_a = _row(afin, "Total Revenue", "TotalRevenue")

            rev_yoy = rev_qoq = eps_yoy = eps_qoq = None
            if rev_q is not None and len(rev_q) >= 5:
                rev_yoy = _pct_growth(float(rev_q.iloc[0]), float(rev_q.iloc[4]))
            if rev_q is not None and len(rev_q) >= 2:
                rev_qoq = _pct_growth(float(rev_q.iloc[0]), float(rev_q.iloc[1]))

            eps_q = info.get("trailingEps")  # fallback hvis kvartals-EPS-serie mangler
            # Bruk nettoresultat-vekst som EPS-proxy når kvartalsvis EPS-serie
            # ikke er tilgjengelig direkte fra yfinance (vanlig for ikke-US).
            if ni_q is not None and len(ni_q) >= 5:
                eps_yoy = _pct_growth(float(ni_q.iloc[0]), float(ni_q.iloc[4]))
            if ni_q is not None and len(ni_q) >= 2:
                eps_qoq = _pct_growth(float(ni_q.iloc[0]), float(ni_q.iloc[1]))

            margin = _safe_float(info.get("profitMargins"))
            margin = margin * 100 if margin is not None else None

            de = _safe_float(info.get("debtToEquity"))
            if de is not None:
                de = de / 100.0 if de > 10 else de  # yfinance gir ofte % (f.eks 120 = 1.2)

            # v20: tre fremoverskuende oppside-mål — samme .info-kall som over,
            # ingen ekstra nettverkskostnad. Mer konsistent tilgjengelig for
            # amerikanske/store europeiske aksjer enn for mindre nordiske
            # selskaper i yfinances gratis-data; vises ærlig som "ukjent" der
            # den mangler i stedet for å late som vi vet.
            price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
            ma200 = _safe_float(info.get("twoHundredDayAverage"))
            dist200 = None
            if price is not None and ma200:
                dist200 = (price / ma200 - 1) * 100

            target_mean = _safe_float(info.get("targetMeanPrice"))
            target_upside = None
            if price is not None and target_mean is not None and price:
                target_upside = (target_mean / price - 1) * 100

            peg = _safe_float(info.get("trailingPegRatio"))
            if peg is None:
                peg = _safe_float(info.get("pegRatio"))

            ta = _fetch_technical(t)

            return {
                "ticker": ticker,
                "name": info.get("shortName") or info.get("longName") or ticker,
                "sector_yf": info.get("sector"),
                "market_cap": _safe_float(info.get("marketCap")),
                "currency": info.get("currency"),
                "price": round(price, 2) if price is not None else None,
                "rev_yoy": round(rev_yoy, 1) if rev_yoy is not None else None,
                "rev_qoq": round(rev_qoq, 1) if rev_qoq is not None else None,
                "eps_yoy": round(eps_yoy, 1) if eps_yoy is not None else None,
                "eps_qoq": round(eps_qoq, 1) if eps_qoq is not None else None,
                "margin": round(margin, 1) if margin is not None else None,
                "de": round(de, 2) if de is not None else None,
                "peg": round(peg, 2) if peg is not None else None,
                "dist200": round(dist200, 1) if dist200 is not None else None,
                "target_upside": round(target_upside, 1) if target_upside is not None else None,
                **ta,
            }
        except Exception:
            time.sleep(1.5)
    return None


# ── Innsidekjøp (SEC Form 4, KUN USA) ────────────────────────────────
_UA = {"User-Agent": "MarketAnalyzor personal-research contact@example.com"}
_CIK_CACHE = None


def _sec_cik_map():
    """Ticker -> CIK, hele markedet i én gratis fil (ingen nøkkel)."""
    global _CIK_CACHE
    if _CIK_CACHE is not None:
        return _CIK_CACHE
    try:
        import requests
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers=_UA, timeout=20)
        if r.status_code == 200:
            data = r.json()
            _CIK_CACHE = {v["ticker"].upper(): str(v["cik_str"]).zfill(10)
                         for v in data.values()}
            return _CIK_CACHE
    except Exception as e:
        print(f"  SEC CIK-kart feilet: {e}")
    _CIK_CACHE = {}
    return _CIK_CACHE


def sec_insider_buy(ticker: str, days: int = 90) -> bool | None:
    """True hvis minst ett åpent-marked-kjøp (transactionCode 'P') av innsider
    er meldt siste `days` dager. None hvis data ikke kunne hentes (ikke samme
    som False — kalleren skal vise 'ukjent', ikke 'nei'). KUN amerikanske
    tickere (ingen suffiks) — SEC dekker ikke utenlandske børser."""
    if "." in ticker:  # ikke-US suffiks (.DE/.OL/.ST/.CO/.HE/.TO)
        return None
    cik_map = _sec_cik_map()
    cik = cik_map.get(ticker.upper())
    if not cik:
        return None
    try:
        import requests
        from datetime import datetime, timedelta, timezone
        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                         headers=_UA, timeout=20)
        if r.status_code != 200:
            return None
        recent = (r.json().get("filings") or {}).get("recent") or {}
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accns = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        for i, form in enumerate(forms):
            if form != "4":
                continue
            try:
                fdate = datetime.strptime(dates[i], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if fdate < cutoff:
                continue
            accn_nodash = accns[i].replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn_nodash}/{docs[i]}"
            time.sleep(0.15)  # SEC-grense: 10 kall/sek
            xr = requests.get(url, headers=_UA, timeout=15)
            if xr.status_code == 200 and "<transactionCode>P</transactionCode>" in xr.text:
                return True
        return False
    except Exception as e:
        print(f"  SEC Form 4-sjekk feilet for {ticker}: {e}")
        return None


# ── Rangering ─────────────────────────────────────────────────────────
def _score_growth(f):
    """Dekningsgrad 0-2 for vekst-kravene (omsetning YoY>50, QoQ>40)."""
    hits, total = 0, 2
    if f.get("rev_yoy") is not None:
        total_ok = f["rev_yoy"] > 50
        hits += 1 if total_ok else 0
    if f.get("rev_qoq") is not None:
        hits += 1 if f["rev_qoq"] > 40 else 0
    return hits


def _score_value(f):
    """Dekningsgrad 0-4 for value-kravene."""
    hits = 0
    if f.get("eps_yoy") is not None and f["eps_yoy"] > 50:
        hits += 1
    if f.get("eps_qoq") is not None and f["eps_qoq"] > 40:
        hits += 1
    if f.get("margin") is not None and f["margin"] > 10:
        hits += 1
    if f.get("de") is not None and f["de"] < 1.2:
        hits += 1
    return hits


def _score_upside(f):
    """v20: Dekningsgrad 0-3 for "Vekst med oppside" — de tre fremoverskuende
    målene (er prisen fornuftig, er den allerede strukket, ser markedet fortsatt
    oppside). Brukes KUN på aksjer som allerede har reell vekst (se
    rank_and_select) — dette scorer om den veksten fortsatt er kjøpbar."""
    hits = 0
    if f.get("peg") is not None and 0 < f["peg"] < 2:
        hits += 1
    if f.get("dist200") is not None and f["dist200"] < 25:
        hits += 1
    if f.get("target_upside") is not None and f["target_upside"] > 10:
        hits += 1
    return hits


def fetch_universe_chunk(universe, chunk_index: int, chunk_total: int):
    """Henter fundamentaler for KUN denne chunk-jobbens skive av universet.
    Brukes av de parallelle fetch-jobbene i screener.yml — hver jobb tar en
    ~1/chunk_total-del, holder seg innenfor trygge rate-limit-grenser per
    jobb selv når totaluniverset er stort (hundrevis-tusenvis av tickere)."""
    my_slice = [t for i, t in enumerate(universe) if i % chunk_total == chunk_index]
    rows = []
    for ticker, name, region, sector in my_slice:
        f = fetch_fundamentals(ticker)
        if f is None:
            continue
        f["region"] = region
        f["region_label"] = REGIONS.get(region, {}).get("label", region)
        f["exchange"] = REGIONS.get(region, {}).get("exchange", "")
        f["ask_eligible"] = REGIONS.get(region, {}).get("ask_eligible", False)
        f["sector"] = sector if sector != "—" else (f.get("sector_yf") or "Ukjent")
        f["display_name"] = name or f.get("name") or ticker
        rows.append(f)
    return {"chunk_index": chunk_index, "chunk_total": chunk_total,
           "n_slice": len(my_slice), "n_ok": len(rows), "rows": rows}


def rank_and_select(rows, top_n=20, insider_check_limit=40):
    """Ren rangeringsfunksjon: tar en FERDIG SAMMENSLÅTT liste av
    fundamental-dicter (fra alle chunks) og returnerer topp-N per skjerm.
    Innsidesjekk (SEC) kjøres KUN på de endelige topp-40(+) radene på tvers av
    alle tre skjermene, uansett hvor stort råuniverset var — holder
    SEC-kallbudsjettet konstant.

    v21: Northstar-teknisk score (`ta_score`, se _fetch_technical) brytes inn
    som SISTE tiebreaker — ETTER dekningsgrad og ETTER selve vekstmagnituden.
    En aksje med reelt ekstrem vekst skal fortsatt trone øverst i Vekst-listen
    selv om timingen ikke er perfekt akkurat nå (det er nettopp derfor
    Teknisk-kolonnen og ⭐-merket finnes — for å vise DEG hvem av de allerede
    beste som også har god timing, ikke for å gjemme bort de sterkeste
    vekstnavnene fordi de er midlertidig strukket)."""
    growth_ranked = sorted(
        rows, key=lambda r: (-_score_growth(r), -(r.get("rev_yoy") or -999), -(r.get("ta_score") or 0)))
    value_ranked = sorted(
        rows, key=lambda r: (-_score_value(r), -(r.get("eps_yoy") or -999), -(r.get("ta_score") or 0)))
    growth_top = growth_ranked[:top_n]
    value_top = value_ranked[:top_n]

    # v20: "Vekst med oppside" — kun blant aksjer med minst ett vekstkrav
    # oppfylt (reell vekst), rangert etter dekning på de tre oppside-målene,
    # så (v21) teknisk score som siste tiebreaker.
    upside_pool = [r for r in rows if _score_growth(r) >= 1]
    upside_ranked = sorted(
        upside_pool,
        key=lambda r: (-_score_upside(r), -_score_growth(r),
                       -(r.get("rev_yoy") or -999), -(r.get("ta_score") or 0)))
    upside_top = upside_ranked[:top_n]

    checked = 0
    seen_tickers = set()
    all_top = growth_top + value_top + upside_top
    for r in all_top:
        if r["ticker"] in seen_tickers:
            continue
        seen_tickers.add(r["ticker"])
        if checked >= insider_check_limit:
            r["insider_buy"] = None
            continue
        r["insider_buy"] = sec_insider_buy(r["ticker"])
        checked += 1
    # Kopier insider-resultat til evt. duplikat-forekomst (samme aksje i flere lister)
    by_ticker = {r["ticker"]: r.get("insider_buy") for r in all_top if r["ticker"] in seen_tickers}
    for r in all_top:
        if "insider_buy" not in r:
            r["insider_buy"] = by_ticker.get(r["ticker"])

    for r in growth_top:
        r["growth_score"] = _score_growth(r)
        r["growth_qualified"] = r["growth_score"] == 2
    for r in value_top:
        r["value_score"] = _score_value(r)
        r["value_qualified"] = r["value_score"] == 4
    for r in upside_top:
        r["growth_score"] = _score_growth(r)
        r["upside_score"] = _score_upside(r)
        r["upside_qualified"] = r["upside_score"] == 3

    from datetime import datetime, timezone
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "n_scanned": len(rows),
        "growth": growth_top,
        "value": value_top,
        "growth_upside": upside_top,
    }


def run_screener(universe=None, top_n=20, insider_check_limit=40):
    """Enkeltprosess-variant (ingen chunking) — brukt av CI-testen og for
    lokal kjøring uten matrix. Produksjon bruker fetch_universe_chunk +
    rank_and_select via de parallelle jobbene i screener.yml."""
    universe = universe if universe is not None else SEED_UNIVERSE
    chunk = fetch_universe_chunk(universe, 0, 1)
    result = rank_and_select(chunk["rows"], top_n, insider_check_limit)
    result["n_universe"] = len(universe)
    return result
