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


GPR_URLS = [
    "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls",
]


def fetch_gpr() -> dict | None:
    """
    Caldara-Iacoviello Geopolitical Risk Index (manedlig, oppdateres ~10. i mnd).
    Sammenligner siste verdi mot 12-mnd snitt; deler i Threats/Acts der mulig.
    Robust: returnerer None ved enhver feil (nettverk, format, manglende deps).
    """
    from .config import PALETTE
    if requests is None:
        return None
    for url in GPR_URLS:
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            import io
            df = pd.read_excel(io.BytesIO(r.content))
            cols = {c.lower(): c for c in df.columns}
            gcol = cols.get("gpr")
            mcol = cols.get("month") or list(df.columns)[0]
            if gcol is None:
                continue
            df = df[[mcol, gcol] + [cols[k] for k in ("gprt", "gpra") if k in cols]].dropna(subset=[gcol])
            df[mcol] = pd.to_datetime(df[mcol], errors="coerce")
            df = df.dropna(subset=[mcol]).sort_values(mcol)
            if len(df) < 13:
                continue
            last = float(df[gcol].iloc[-1])
            avg12 = float(df[gcol].tail(13).iloc[:-1].mean())
            ratio = last / avg12 if avg12 else 1.0
            if ratio >= 1.5:
                col, note = PALETTE["down"], "GPR-spike vs 12m-snitt - de-risk-signal HVIS kredittspreader samtidig utvider"
            elif ratio >= 1.2:
                col, note = PALETTE["warn"], "Forhoyet geopolitisk risiko - folg kredittspreader"
            else:
                col, note = PALETTE["up"], "Geopolitisk risiko naer/under normalen"
            extra = ""
            tcol_ = cols.get("gprt"); acol_ = cols.get("gpra")
            if tcol_ and acol_:
                extra = f" | Threats {float(df[tcol_].iloc[-1]):.0f} / Acts {float(df[acol_].iloc[-1]):.0f}"
            _log(f"  gpr ok: {last:.0f} (12m snitt {avg12:.0f})")
            return {
                "label": f"GPR: {last:.0f} ({ratio:+.0%} av 12m-snitt){extra}",
                "col": col, "note": note + " (kontekst, ikke timing-signal)",
                "value": round(last, 1), "ratio_12m": round(ratio, 2),
            }
        except Exception as e:
            _log(f"  gpr feil: {e}")
    return None


def build_regime(api_key: str) -> dict:
    from .config import PALETTE
    regime = {}
    s2 = fetch_fred_series("DGS2", api_key)
    s10 = fetch_fred_series("DGS10", api_key)
    s3m = fetch_fred_series("DGS3MO", api_key)
    walcl = fetch_fred_series("WALCL", api_key)
    hy = fetch_fred_series("BAMLH0A0HYM2", api_key)
    tga = fetch_fred_series("WTREGEN", api_key)       # Treasury General Account
    rrp = fetch_fred_series("RRPONTSYD", api_key)     # Overnight Reverse Repo
    nfci = fetch_fred_series("NFCI", api_key)         # Chicago Fed Financial Conditions

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

    # Net liquidity = Fed-balanse − TGA − RRP (alt på FRED). Bedre proxy for
    # dollar-likviditet "i spill" for risikoaktiva enn balansen alene; sterk
    # korrelat til risikoaktiva siden 2020.
    if walcl is not None and tga is not None:
        def _bn(s):  # normaliser til milliarder (WALCL er i millioner)
            s = s.dropna()
            return s / 1000.0 if float(s.iloc[-1]) > 200000 else s
        parts_nl = {"w": _bn(walcl), "t": _bn(tga)}
        if rrp is not None:
            parts_nl["r"] = _bn(rrp)
        dfn = pd.DataFrame(parts_nl).ffill().dropna()
        net = dfn["w"] - dfn["t"] - (dfn["r"] if "r" in dfn else 0.0)
        netw = net.resample("W-WED").last().dropna()
        if len(netw) > 14:
            chg_13w = (float(netw.iloc[-1]) / float(netw.iloc[-14]) - 1.0) * 100
            rising = chg_13w > 0
            regime["net_liquidity"] = {
                "label": f"Net liquidity: {netw.iloc[-1]/1000:.2f} bn$ ({chg_13w:+.1f}% 13u)",
                "col": PALETTE["up"] if rising else PALETTE["down"],
                "note": ("Likviditet inn i risikoaktiva (WALCL − TGA − RRP stiger)" if rising
                         else "Likviditet trekkes ut (TGA/RRP/QT) – motvind for risikoaktiva"),
                "value": round(float(netw.iloc[-1]), 1),
                "chg_13w": round(chg_13w, 2),
                "series": [(d.strftime("%Y-%m-%d"), round(float(v), 1))
                           for d, v in netw.tail(180).items()],
            }

    # NFCI (Chicago Fed): bred finansiell stress-indikator. >0 = strammere
    # forhold enn historisk snitt (risk-off), <0 = løsere (risk-on).
    if nfci is not None:
        n = nfci.dropna()
        last = float(n.iloc[-1])
        chg_4w = last - float(n.iloc[-5]) if len(n) > 5 else 0.0
        if last < 0:
            col, note = PALETTE["up"], "Løsere finansielle forhold enn snittet – støttende"
        elif last < 0.5:
            col, note = PALETTE["warn"], "Litt strammere enn snittet – nøytral/varsom"
        else:
            col, note = PALETTE["down"], "Klart stramme forhold – risk-off-press"
        regime["nfci"] = {
            "label": f"NFCI: {last:+.2f} ({chg_4w:+.2f} 4u)",
            "col": col, "note": note, "value": round(last, 3),
        }

    # Geopolitisk risiko (Caldara-Iacoviello GPR, månedlig, gratis nedlasting).
    # Kontekst-kort, ikke timing-signal: brukes som forsterker sammen med
    # kredittspreader, ikke alene.
    gpr = fetch_gpr()
    if gpr:
        regime["gpr"] = gpr

    # Multi-faktor regime-score (0-100): høyere = mer risk-on
    factors = []
    if "yield_curve" in regime:
        factors.append(1.0 if regime["yield_curve"]["value"] > 0 else 0.0)
    # Likviditet: foretrekk net liquidity (WALCL−TGA−RRP) over balansen alene
    if "net_liquidity" in regime:
        factors.append(1.0 if regime["net_liquidity"]["chg_13w"] > 0 else 0.0)
    elif "fed_liquidity" in regime:
        factors.append(1.0 if "Stimulativ" in regime["fed_liquidity"]["note"] else 0.0)
    if "credit_spread" in regime:
        factors.append(0.0 if "utvider" in regime["credit_spread"]["note"] else 1.0)
    if "nfci" in regime:
        factors.append(1.0 if regime["nfci"]["value"] < 0 else 0.0)
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
