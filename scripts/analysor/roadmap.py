"""
Auto-roadmap-motor (NSBC-stil).

NSBC lager roadmaps: store-bilde-charts (kvartal/måned) med support/resistance,
trend-kanaler, mål-nivåer og scenarioer (bull/base/bear) med klare
invaliderings-nivåer ("lines in the sand"). Denne modulen genererer det samme
algoritmisk fra OHLC:

  - Support/resistance fra klustrede swing-pivoter (indicators.support_resistance)
  - Trend-kanal via regresjon gjennom pivoter (+ R² som trend-kvalitet)
  - Mål via measured move (AB=CD) og Fibonacci-extension (1.0/1.272/1.618)
  - Scenarioer: BASE (kanal/measured move), BULL (over neste resistance),
    BEAR (tap av 36-MA/kanalgulv/sky -> neste support)
  - Invaliderings-nivå per scenario
  - Alt kan også regnes på instrument/gull-ratioen ("priced in gold")

Sannsynligheter fabrikkeres IKKE her — de forankres i hit-rate-motoren
(validation.py) når basen er stor nok. Her gir vi struktur og nivåer.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from . import indicators as ind


def _fib_levels(low: float, high: float) -> dict:
    rng = high - low
    return {
        "0.0": round(low, 4), "0.382": round(low + 0.382 * rng, 4),
        "0.5": round(low + 0.5 * rng, 4), "0.618": round(low + 0.618 * rng, 4),
        "1.0": round(high, 4),
        "1.272": round(high + 0.272 * rng, 4), "1.618": round(high + 0.618 * rng, 4),
    }


def _trend_channel(close: pd.Series, lookback: int = 120):
    """Regresjonskanal + R² (trend-kvalitet) over siste lookback barer."""
    c = close.dropna().tail(lookback)
    if len(c) < 20:
        return None
    x = np.arange(len(c), dtype=float)
    y = c.values
    a, b = np.polyfit(x, y, 1)
    fit = a * x + b
    resid = y - fit
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1e-9
    r2 = 1 - ss_res / ss_tot
    sd = float(np.std(resid))
    slope_pct = a / y.mean() * 100 if y.mean() else 0
    return {
        "slope_per_bar": float(a), "slope_pct": round(slope_pct, 3),
        "r2": round(float(r2), 3),
        "mid_now": round(float(fit[-1]), 4),
        "upper_now": round(float(fit[-1] + 2 * sd), 4),
        "lower_now": round(float(fit[-1] - 2 * sd), 4),
        "rising": bool(a > 0),
    }


def build_roadmap(df: pd.DataFrame, label: str, tf: str = "weekly") -> dict | None:
    """
    Bygg roadmap for ett instrument på gitt tidsramme (default ukentlig =
    NSBCs mellom-bilde). Returnerer nivåer, kanal, mål og scenarioer.
    """
    c = df["close_use"].dropna()
    if len(c) < 60:
        return None
    high = df["high"] if "high" in df else c
    low = df["low"] if "low" in df else c
    last = float(c.iloc[-1])

    sr = ind.support_resistance(high, low, c, left=3, right=3, tol=0.02, max_levels=5)
    chan = _trend_channel(c, 120)
    ich = ind.ichimoku(high, low, c)
    tn = ind.trend_navigator(c, 12, 36)
    dist = ind.dist_from_ma(c, 36)
    ma36 = float(c.rolling(36).mean().iloc[-1]) if len(c) >= 36 else None

    # Siste betydelige svingning for measured move / fib
    piv_h, piv_l = ind.swing_pivots(high, low, 3, 3)
    last_low = piv_l[-1][1] if piv_l else float(low.tail(60).min())
    last_high = piv_h[-1][1] if piv_h else float(high.tail(60).max())
    swing_lo = min(last_low, last_high)
    swing_hi = max(last_low, last_high)
    fib = _fib_levels(swing_lo, swing_hi)

    res_levels = [r["price"] for r in sr["resistance"]]
    sup_levels = [s["price"] for s in sr["support"]]
    nearest_res = res_levels[0] if res_levels else None
    nearest_sup = sup_levels[0] if sup_levels else None

    # Measured move: lengden på siste impuls lagt til breakout-punkt
    impulse = swing_hi - swing_lo
    measured_target = round(last + impulse, 4) if impulse > 0 else None

    # ── Scenarioer ────────────────────────────────────────────────
    # BASE: fortsettelse i kanal mot nærmeste mål
    base_target = nearest_res or measured_target or (fib["1.272"] if fib else None)
    # BULL: over nærmeste resistance -> neste nivå / fib-extension
    bull_target = None
    if len(res_levels) >= 2:
        bull_target = res_levels[1]
    elif fib:
        bull_target = fib["1.618"]
    # BEAR: tap av 36-MA / kanalgulv -> nærmeste support
    bear_target = nearest_sup or (chan["lower_now"] if chan else None)

    # Invaliderings-nivå: under 36-MA og nærmeste support = base-case død
    invalidation = None
    if ma36 and nearest_sup:
        invalidation = round(min(ma36, nearest_sup), 4)
    elif ma36:
        invalidation = round(ma36, 4)
    elif nearest_sup:
        invalidation = nearest_sup

    def pct(target):
        return round((target / last - 1) * 100, 1) if target else None

    return {
        "label": label, "tf": tf, "last": round(last, 4),
        "trend_state": tn["state"], "cloud": ich["position"],
        "dist36": dist["dist"], "stretched": dist["stretched"],
        "channel": chan,
        "support": sr["support"], "resistance": sr["resistance"],
        "fib": fib, "swing_low": round(swing_lo, 4), "swing_high": round(swing_hi, 4),
        "ma36": round(ma36, 4) if ma36 else None,
        "scenarios": {
            "bull": {"target": bull_target, "pct": pct(bull_target),
                     "trigger": nearest_res,
                     "note": "Breakout over nærmeste resistance åpner neste nivå"},
            "base": {"target": base_target, "pct": pct(base_target),
                     "note": "Fortsettelse i kanal mot nærmeste mål / measured move"},
            "bear": {"target": bear_target, "pct": pct(bear_target),
                     "trigger": invalidation,
                     "note": "Tap av 36-MA / support åpner nedside mot neste støtte"},
        },
        "measured_move": measured_target,
        "invalidation": invalidation,
    }


def build_all_roadmaps(raw: dict, assets_meta: dict, gld=None) -> dict:
    """
    Roadmaps for hele universet på ukentlig tidsramme, pluss priced-in-gold
    for de viktigste. Returnerer {id: {nominal, gold}}.
    """
    from . import data as datamod
    out = {}
    for iid, meta in assets_meta.items():
        df = raw.get(iid)
        if df is None:
            continue
        frames = datamod.resample_frames(df)
        wk = frames.get("weekly")
        if wk is None or len(wk) < 60:
            continue
        label = meta.get("symbol_label", iid)
        rm = build_roadmap(wk, label, "weekly")
        if rm is None:
            continue
        entry = {"nominal": rm}
        # priced in gold (ratio-roadmap) for ikke-gull
        if gld is not None and iid != "GLD":
            comb = pd.DataFrame({"n": df["close_use"], "g": gld["close_use"]}).dropna()
            if len(comb) > 300:
                ratio_df = pd.DataFrame({
                    "close_use": comb["n"] / comb["g"],
                    "high": comb["n"] / comb["g"],
                    "low": comb["n"] / comb["g"],
                })
                rframes = datamod.resample_frames(ratio_df)
                rwk = rframes.get("weekly")
                if rwk is not None and len(rwk) >= 60:
                    gold_rm = build_roadmap(rwk, f"{label}/GLD", "weekly")
                    if gold_rm:
                        entry["gold"] = gold_rm
        out[iid] = entry
    return out
