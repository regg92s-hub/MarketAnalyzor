"""
v15: Posisjonering (COT) — første ekte sentiment/posisjoneringsakse i systemet.

CFTC Commitments of Traders, disaggregert futures-only, via Socrata-API
(publicreporting.cftc.gov, gratis, ingen nøkkel). Managed Money-netto som
persentil av rullerende 3 år — gratis DSI-erstatning for gull og sølv.

VIKTIG (ærlighet fra research-runden): fagfellevurdert litteratur finner at
posisjonering stort sett FØLGER pris, ikke leder den (Sanders m.fl. 2004/2009;
Bosch & Pradkhan 2015 for metaller). Dette er derfor en KONTEKST-/risiko-måler,
ALDRI en timing-trigger, og den endrer aldri beholdninger alene. Kun ekstreme
persentiler (>90 / <10) vises som tilstand.

Publisering: fredag 15:30 ET for tirsdagens posisjoner — 3 dagers lag, som
passer ukedisiplinen (signaler committes uansett på fredags-close).
"""
from __future__ import annotations

import pandas as pd

CONTRACTS = {
    "088691": {"name": "Gull (COMEX)", "iid": "GLD"},
    "084691": {"name": "Sølv (COMEX)", "iid": "SLV"},
}

_URL = ("https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
        "?$where=cftc_contract_market_code in('088691','084691')"
        "&$order=report_date_as_yyyy_mm_dd DESC&$limit=500")


def fetch_cot():
    """Hent rådata fra CFTC Socrata. Returnerer liste av dicts eller None."""
    try:
        import requests
        r = requests.get(_URL, timeout=30,
                         headers={"User-Agent": "MarketAnalyzor personal research"})
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  COT-henting feilet: {e}")
    return None


def build_positioning():
    """
    -> {contracts: [{name, iid, net_pct_oi, percentile, velocity, state, col}],
        note} eller {} ved feil. Persentil = MM-netto som % av OI mot
    rullerende 156 uker (3 år).
    """
    from .config import PALETTE
    raw = fetch_cot()
    if not raw:
        return {}
    try:
        df = pd.DataFrame(raw)
        need = ["cftc_contract_market_code", "report_date_as_yyyy_mm_dd",
                "m_money_positions_long_all", "m_money_positions_short_all",
                "open_interest_all"]
        if any(c not in df.columns for c in need):
            return {}
        df = df[need].copy()
        for c in need[2:]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"])
        out = []
        for code, meta in CONTRACTS.items():
            sub = (df[df["cftc_contract_market_code"] == code]
                   .dropna().sort_values("date"))
            if len(sub) < 60:  # trenger godt over ett år for meningsfull persentil
                continue
            net = sub["m_money_positions_long_all"] - sub["m_money_positions_short_all"]
            net_pct = 100 * net / sub["open_interest_all"].replace(0, pd.NA)
            net_pct = net_pct.dropna()
            if len(net_pct) < 60:
                continue
            window = net_pct.tail(156)
            cur = float(window.iloc[-1])
            pct_rank = float((window <= cur).mean() * 100)
            velo = float(window.iloc[-1] - window.iloc[-2]) if len(window) >= 2 else 0.0
            if pct_rank >= 90:
                state, col = "Overfylt long (sårbar)", PALETTE["warn"]
            elif pct_rank <= 10:
                state, col = "Utvasket (se etter bekreftelse)", PALETTE["up"]
            else:
                state, col = "Nøytral", PALETTE["neutral"]
            out.append({
                "name": meta["name"], "iid": meta["iid"],
                "net_pct_oi": round(cur, 1),
                "percentile": round(pct_rank, 0),
                "velocity": round(velo, 1),
                "state": state, "col": col,
                "asof": sub["date"].iloc[-1].strftime("%Y-%m-%d"),
            })
        if not out:
            return {}
        return {
            "contracts": out,
            "note": ("Managed Money-netto som % av åpen balanse, persentil mot 3 år. "
                     "Kontekst/risiko — IKKE timing: posisjonering følger stort sett pris "
                     "(Sanders 2009; Bosch & Pradkhan 2015). Publiseres fredager m/ 3d lag."),
        }
    except Exception as e:
        print(f"  COT-prosessering feilet: {e}")
        return {}
