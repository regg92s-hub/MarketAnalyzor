"""
Makro-regime (NFTRH-stil): yield-kurve (2s10s + 10y-3m), Fed-likviditet
(WALCL), og kredittspreader (HY OAS) for et multi-faktor regime-signal.

Forskning (NY Fed) bruker 10y-3m term-spread for resesjonssannsynlighet;
nyere arbeid viser at kredittspreader bør bekrefte yield-kurve-signalet.
"""
from __future__ import annotations
import os
import pandas as pd

try:
    import requests
except Exception:
    requests = None

FRED_SERIES = {
    "DGS2": "2yr Treasury",
    "DGS10": "10yr Treasury",
    "DGS3MO": "3mo Treasury",
    "WALCL": "Fed balanse",
    "BAMLH0A0HYM2": "HY OAS (kredittspread)",
}


def _log(m):
    print(m, flush=True)


def fetch_fred_series(series_id: str, api_key: str) -> pd.Series | None:
    if requests is None or not api_key:
        return None
    url = "https://api.stlouisfed.org/fred/series/observations"
    try:
        r = requests.get(url, params={
            "series_id": series_id, "api_key": api_key, "file_type": "json",
            "observation_start": "2003-01-01",
        }, timeout=30)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        idx, vals = [], []
        for o in obs:
            v = o.get("value")
            if v in (".", "", None):
                continue
            idx.append(pd.to_datetime(o["date"]))
            vals.append(float(v))
        if not vals:
            return None
        _log(f"  fred ok: {series_id}")
        return pd.Series(vals, index=idx)
    except Exception as e:
        _log(f"  fred feil {series_id}: {e}")
        return None


def build_regime(api_key: str) -> dict:
    from .config import PALETTE
    regime = {}
    s2 = fetch_fred_series("DGS2", api_key)
    s10 = fetch_fred_series("DGS10", api_key)
    s3m = fetch_fred_series("DGS3MO", api_key)
    walcl = fetch_fred_series("WALCL", api_key)
    hy = fetch_fred_series("BAMLH0A0HYM2", api_key)

    # 2s10s
    if s2 is not None and s10 is not None:
        df = pd.DataFrame({"s2": s2, "s10": s10}).dropna()
        spread = (df["s10"] - df["s2"]).iloc[-1]
        inverted = spread < 0
        regime["yield_curve"] = {
            "label": f"2s10s: {spread:+.2f}%",
            "col": PALETTE["down"] if inverted else PALETTE["up"],
            "note": "Invertert – historisk resesjonsvarsel" if inverted else "Normal helning",
            "value": round(float(spread), 2),
            "series": [(d.strftime("%Y-%m-%d"), round(float(v), 3))
                       for d, v in (df["s10"] - df["s2"]).tail(180).items()],
        }

    # 10y-3m (NY Fed-modellens foretrukne spread)
    if s10 is not None and s3m is not None:
        df = pd.DataFrame({"s10": s10, "s3m": s3m}).dropna()
        spread = (df["s10"] - df["s3m"]).iloc[-1]
        regime["term_spread_10y3m"] = {
            "label": f"10y-3m: {spread:+.2f}%",
            "col": PALETTE["down"] if spread < 0 else PALETTE["up"],
            "note": "NY Fed resesjonsmodell-spread",
            "value": round(float(spread), 2),
        }

    # Fed-balanse (QE/QT)
    if walcl is not None:
        w = walcl.dropna()
        chg_13w = (w.iloc[-1] / w.iloc[-14] - 1.0) * 100 if len(w) > 14 else 0
        qt = chg_13w < 0
        regime["fed_liquidity"] = {
            "label": f"Fed-balanse 13u: {chg_13w:+.1f}%",
            "col": PALETTE["down"] if qt else PALETTE["up"],
            "note": "QT pågår – likviditet ut" if qt else "Stimulativ – likviditet inn",
            "series": [(d.strftime("%Y-%m-%d"), round(float(v) / 1e6, 3))
                       for d, v in w.tail(180).items()],
        }

    # Kredittspread (HY OAS)
    if hy is not None:
        h = hy.dropna()
        last = h.iloc[-1]
        chg_4w = last - h.iloc[-21] if len(h) > 21 else 0
        widening = chg_4w > 0.3
        regime["credit_spread"] = {
            "label": f"HY OAS: {last:.2f}% ({chg_4w:+.2f})",
            "col": PALETTE["down"] if (widening or last > 5.0) else PALETTE["up"],
            "note": "Spreader utvider – risiko-aversjon stiger" if widening else "Spreader stabile/strammer",
            "value": round(float(last), 2),
        }

    # Multi-faktor regime-score (0-100): høyere = mer risk-on
    factors = []
    if "yield_curve" in regime:
        factors.append(1.0 if regime["yield_curve"]["value"] > 0 else 0.0)
    if "fed_liquidity" in regime:
        factors.append(1.0 if "Stimulativ" in regime["fed_liquidity"]["note"] else 0.0)
    if "credit_spread" in regime:
        factors.append(0.0 if "utvider" in regime["credit_spread"]["note"] else 1.0)
    if factors:
        score = round(sum(factors) / len(factors) * 100)
        if score >= 66:
            st, col = "Risk-on", PALETTE["up"]
        elif score >= 34:
            st, col = "Nøytral / overgang", PALETTE["warn"]
        else:
            st, col = "Risk-off / defensiv", PALETTE["down"]
        regime["composite"] = {"score": score, "state": st, "col": col,
                               "label": f"Regime: {st} ({score}/100)"}
    return regime
