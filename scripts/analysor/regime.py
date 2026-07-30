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
    dfii = fetch_fred_series("DFII10", api_key)       # 10y TIPS-realrente
    bei = fetch_fred_series("T10YIE", api_key)        # 10y inflasjonsforventning
    ecb = fetch_fred_series("ECBASSETSW", api_key)    # ECB-balanse (EUR mn)
    boj = fetch_fred_series("JPNASSETS", api_key)     # BoJ-balanse (100 mn yen)
    eurusd = fetch_fred_series("DEXUSEU", api_key)    # USD per EUR
    jpyusd = fetch_fred_series("DEXJPUS", api_key)    # JPY per USD

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

    # Realrente (10y TIPS) — direkte relevant for gull-baseline: gull følger
    # realrenter invers. Fallende realrente = medvind for gull/hard assets.
    if dfii is not None:
        d = dfii.dropna()
        last = float(d.iloc[-1])
        chg_3m = last - float(d.iloc[-63]) if len(d) > 63 else 0.0
        falling = chg_3m < 0
        regime["real_rate"] = {
            "label": f"Realrente 10y: {last:.2f}% ({chg_3m:+.2f} 3m)",
            "col": PALETTE["warn"] if falling else PALETTE["up"],
            "note": ("Fallende realrente — medvind for gull/hard assets" if falling
                     else "Stigende realrente — motvind for gull, støtte for USD"),
            "value": round(last, 2),
        }

    # Inflasjonsforventning (10y breakeven)
    if bei is not None:
        b = bei.dropna()
        last = float(b.iloc[-1])
        chg_3m = last - float(b.iloc[-63]) if len(b) > 63 else 0.0
        regime["breakeven"] = {
            "label": f"Breakeven 10y: {last:.2f}% ({chg_3m:+.2f} 3m)",
            "col": PALETTE["warn"] if last > 2.5 else PALETTE["up"],
            "note": ("Inflasjonsforventninger over komfortsonen" if last > 2.5
                     else "Forankrede inflasjonsforventninger"),
            "value": round(last, 2),
        }

    # Global sentralbanklikviditet (G3: Fed + ECB + BoJ i USD). Dokumentert
    # ~1 kvartals ledelse på risikoaktiva historisk, MEN forholdet brøt sammen
    # 2023–2025 (TGA/RRP dominerte) — presenteres som én input, ikke orakel.
    if walcl is not None and ecb is not None and eurusd is not None:
        try:
            fed_tn = walcl.dropna() / 1e6            # mn USD -> tn USD
            ecb_tn = (ecb.dropna() / 1e6)            # mn EUR -> tn EUR
            eu = eurusd.dropna()
            comb = pd.DataFrame({"f": fed_tn, "e": ecb_tn, "x": eu}).ffill().dropna()
            g = comb["f"] + comb["e"] * comb["x"]
            if boj is not None and jpyusd is not None:
                bj = (boj.dropna() * 100 / 1e6)      # 100mn JPY -> tn JPY
                jp = jpyusd.dropna()
                c2 = pd.DataFrame({"g": g, "b": bj, "j": jp}).ffill().dropna()
                g = c2["g"] + c2["b"] / c2["j"]
            gw = g.resample("W-WED").last().dropna()
            if len(gw) > 27:
                chg_6m = (float(gw.iloc[-1]) / float(gw.iloc[-27]) - 1.0) * 100
                rising = chg_6m > 0
                regime["global_liquidity"] = {
                    "label": f"G3-likviditet: {gw.iloc[-1]:.1f} tn$ ({chg_6m:+.1f}% 6m)",
                    "col": PALETTE["up"] if rising else PALETTE["down"],
                    "note": ("Global sentralbanklikviditet ekspanderer (~1 kvartals ledelse "
                             "historisk — men brøt sammen 2023–25, vekt deretter)" if rising
                             else "Global likviditet krymper — strukturell motvind"),
                    "chg_6m": round(chg_6m, 2),
                    "series": [(d.strftime("%Y-%m-%d"), round(float(v), 2))
                               for d, v in gw.tail(180).items()],
                }
        except Exception as e:
            _log(f"  global likviditet feil: {e}")

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
    if "global_liquidity" in regime:
        factors.append(1.0 if regime["global_liquidity"]["chg_6m"] > 0 else 0.0)

    # v15 (rec 3): USD basing-watch — strukturelt varsel FØR en dollar-rip.
    # 2014 og 2022: flermåneders base på/over månedlig 200-EMA -> voldsom
    # USD-styrking som knuste gull, råvarer OG aksjer samtidig. Momentum-mål
    # (3M ROC) ser ikke oppsettet — dette gjør det. FRED DTWEXBGS (bred USD).
    try:
        usd = fetch_fred_series("DTWEXBGS", api_key)
        if usd is not None and len(usd.dropna()) > 100:
            usd = usd.dropna()
            m = usd.resample("ME").last().dropna()
            if len(m) >= 60:
                span = min(200, len(m))
                ema200m = m.ewm(span=span, adjust=False).mean()
                dist = float(m.iloc[-1] / ema200m.iloc[-1] - 1) * 100
                # konsolideringsvarighet: uker innenfor ±3%-bånd rundt 26u-snitt
                w = usd.resample("W-FRI").last().dropna()
                band = w.rolling(26).mean()
                inband = (abs(w / band - 1) <= 0.03)
                dur = 0
                for v in reversed(inband.dropna().tolist()):
                    if v:
                        dur += 1
                    else:
                        break
                near_low = float(usd.iloc[-1] / usd.tail(252).min() - 1) * 100
                basing = (dist > -2) and (dur >= 12) and (near_low < 6)
                regime["usd_watch"] = {
                    "dist_200m_ema": round(dist, 1),
                    "consol_weeks": dur,
                    "above_12m_low_pct": round(near_low, 1),
                    "basing": basing,
                    "note": ("BASE-VARSEL: flermåneders konsolidering på/over månedlig "
                             "200-EMA — historisk forløper for USD-styrking som rammer "
                             "gull, råvarer og aksjer samtidig (2014, 2022)." if basing
                             else "Ingen basing-struktur nå."),
                }
                # Eskalering (rec 3): bekreftet base bidrar som risk-off-tick
                if basing:
                    factors.append(0.0)
    except Exception as e:
        print(f"  usd_watch feilet: {e}")

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
