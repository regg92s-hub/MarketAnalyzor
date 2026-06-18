"""
Hit-rate / signal-validering.

Fra akkumulert score-historikk: "når signal X inntraff, hva ble fremtidig
1/3/6-måneders avkastning vs gull og vs cash, og hvor ofte var den positiv?"

Streng metodikk (rapportens krav):
  - INGEN look-ahead: signal måles på data t.o.m. t-1, avkastning på t+horisont.
  - BASE-RATE: signalets avkastning vises ALLTID mot ubetinget avkastning for
    samme univers/periode. "Edge" = differansen, ikke råtallet.
  - SMÅ UTVALG: n vises alltid; n<20 flagges "lav tillit". Databasen er ung.
  - Ingen kurvetilpasning: vi optimaliserer ikke vekter mot historisk hit-rate.

Bruker score-historikk (docs/history/score_history.json) + dagens priser for
fremtidig avkastning. Kjøres i bygget; resultat lagres i docs/validation.json
og vises på en egen seksjon.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def _monthly_close(df: pd.DataFrame) -> pd.Series:
    return df["close_use"].resample("ME").last().dropna()


def forward_returns(raw: dict, gld, score_history: dict,
                    horizons=(1, 3, 6)) -> dict:
    """
    For hvert instrument: koble historiske score-snapshots til fremtidig
    avkastning. Beregn hit-rate for "score >= 70" (lavrisiko-entry) og
    sammenlign mot base-rate (alle perioder).

    score_history: {dato: {instrument_id: score}}  (ukentlige snapshots)
    Returnerer aggregert statistikk per horisont + per signaltype.
    """
    if not score_history:
        return {"available": False, "reason": "ingen score-historikk ennå"}

    # Bygg månedlige pris-serier
    monthly = {}
    for iid, df in raw.items():
        if df is None:
            continue
        m = _monthly_close(df)
        if len(m) > 12:
            monthly[iid] = m
    gold_m = _monthly_close(gld) if gld is not None else None
    if not monthly:
        return {"available": False, "reason": "ingen prisdata"}

    # Sorter snapshot-datoer
    dates = sorted(score_history.keys())
    if len(dates) < 8:
        return {"available": False, "reason": f"for få snapshots ({len(dates)}) — trenger flere ukers historikk",
                "snapshots": len(dates)}

    # For hver horisont, samle (signal_ret, base_ret) par
    results = {}
    for h in horizons:
        sig_rets, base_rets, sig_beat_gold, base_beat_gold = [], [], [], []
        for d in dates:
            try:
                d0 = pd.Timestamp(d)
            except Exception:
                continue
            snap = score_history[d]
            for iid, m in monthly.items():
                # finn pris ved/etter snapshot og h måneder frem
                idx = m.index[m.index <= d0]
                if len(idx) < 1:
                    continue
                p0 = float(m.loc[idx[-1]])
                fut_idx = m.index[m.index > idx[-1]]
                if len(fut_idx) < h:
                    continue
                p1 = float(m.loc[fut_idx[h - 1]])
                if p0 <= 0:
                    continue
                ret = (p1 / p0 - 1) * 100
                # gull-relativ
                gbeat = None
                if gold_m is not None:
                    gidx = gold_m.index[gold_m.index <= idx[-1]]
                    gfut = gold_m.index[gold_m.index > (gidx[-1] if len(gidx) else d0)]
                    if len(gidx) and len(gfut) >= h:
                        g0 = float(gold_m.loc[gidx[-1]]); g1 = float(gold_m.loc[gfut[h - 1]])
                        if g0 > 0:
                            gret = (g1 / g0 - 1) * 100
                            gbeat = ret > gret
                # base-rate: alle observasjoner
                base_rets.append(ret)
                if gbeat is not None:
                    base_beat_gold.append(gbeat)
                # signal: score >= 70 ved snapshot
                sc = snap.get(iid)
                if isinstance(sc, (int, float)) and sc >= 70:
                    sig_rets.append(ret)
                    if gbeat is not None:
                        sig_beat_gold.append(gbeat)

        def stats(arr):
            if not arr:
                return None
            a = np.array(arr, dtype=float)
            return {"n": len(a), "mean": round(float(a.mean()), 2),
                    "median": round(float(np.median(a)), 2),
                    "hit_rate": round(float((a > 0).mean()) * 100, 1)}

        s_sig = stats(sig_rets)
        s_base = stats(base_rets)
        edge = None
        if s_sig and s_base:
            edge = round(s_sig["mean"] - s_base["mean"], 2)
        results[f"{h}m"] = {
            "signal": s_sig, "base": s_base, "edge_mean": edge,
            "signal_beat_gold": (round(float(np.mean(sig_beat_gold)) * 100, 1) if sig_beat_gold else None),
            "base_beat_gold": (round(float(np.mean(base_beat_gold)) * 100, 1) if base_beat_gold else None),
            "low_confidence": bool(not s_sig or s_sig["n"] < 20),
        }

    return {"available": True, "snapshots": len(dates),
            "signal": "NSBC-score ≥ 70 (lavrisiko-entry)",
            "horizons": results,
            "note": "Edge = signalets snittavkastning minus base-rate. n<20 = lav tillit."}


def kelly_fraction(hit_rate_pct: float | None, mean_win: float | None,
                   mean_loss: float | None, cap: float = 0.25) -> float | None:
    """
    Kvart-Kelly posisjonsguide fra målt edge. Konservativ (cap 25%).
    Kun ment som tak/guide, aldri ved n<30. Returnerer fraksjon 0-cap.
    """
    if hit_rate_pct is None or mean_win is None or mean_loss is None:
        return None
    p = hit_rate_pct / 100.0
    q = 1 - p
    b = abs(mean_win / mean_loss) if mean_loss else None
    if not b or b <= 0:
        return None
    full = p - q / b           # Kelly
    quarter = max(0.0, full * 0.25)
    return round(min(quarter, cap), 3)
