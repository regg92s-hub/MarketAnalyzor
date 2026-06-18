"""
Tekniske indikatorer og risikometrikker.

Nøkkelendring fra forrige versjon: relativ styrke måles med ROC (momentum)
på ratioen mot baseline, ikke MA-kryssing. ROC krever ikke 12,5 års historikk
slik en 50-perioders MA på kvartalsratio gjør, og snur raskere – bedre for
"lavrisiko-entry"-timing.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


# ── Grunnindikatorer ──────────────────────────────────────────────
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(s, fast) - ema(s, slow)
    sig = ema(macd_line, signal)
    hist = macd_line - sig
    return macd_line, sig, hist


def roc(s: pd.Series, periods: int) -> float | None:
    """Rate-of-change i prosent over N perioder. None hvis for kort historikk."""
    s = s.dropna()
    if len(s) <= periods:
        return None
    past = s.iloc[-periods - 1]
    last = s.iloc[-1]
    if past == 0 or pd.isna(past) or pd.isna(last):
        return None
    return float((last / past - 1.0) * 100.0)


# ── Relativ styrke (momentum-basert) ──────────────────────────────
def relative_roc(num: pd.Series, den: pd.Series, horizons: dict) -> dict:
    """
    Multi-horisont ROC på ratioen num/den.
    Returnerer {horisont: roc_pct|None} pluss vektet kompositt.
    """
    comb = pd.DataFrame({"n": num, "d": den}).dropna()
    out = {"roc": {}, "composite": None, "available": []}
    if len(comb) < 30:
        return out
    ratio = comb["n"] / comb["d"]
    from .config import ROC_WEIGHTS
    wsum, vsum = 0.0, 0.0
    for name, p in horizons.items():
        v = roc(ratio, p)
        out["roc"][name] = v
        if v is not None:
            out["available"].append(name)
            w = ROC_WEIGHTS.get(name, 0.0)
            wsum += w
            vsum += w * v
    out["composite"] = (vsum / wsum) if wsum > 0 else None
    return out


def beats_baseline(num: pd.Series, den: pd.Series, horizons_check: list,
                   all_horizons: dict) -> dict:
    """
    'Slår' baseline (gull/dollar) hvis positiv ROC på minst én av de
    spesifiserte horisontene (typisk 1M eller 3M). Momentum-basert, så
    unge instrumenter får signal uten 12 års historikk.
    """
    rr = relative_roc(num, den, all_horizons)
    rocs = rr["roc"]
    checks = {h: rocs.get(h) for h in horizons_check}
    avail = [h for h, v in checks.items() if v is not None]
    beats = any((checks[h] or 0) > 0 for h in avail) if avail else None
    loses = all((checks[h] or 0) <= 0 for h in avail) if avail else None
    tf_over = [h for h in avail if (checks[h] or 0) > 0]
    return {
        "beats": (bool(beats) if beats is not None else None),
        "loses": (bool(loses) if loses is not None else None),
        "tf_over": tf_over,
        "roc": rocs,
        "composite": rr["composite"],
    }


# ── Risikometrikker ───────────────────────────────────────────────
def daily_returns(close: pd.Series) -> pd.Series:
    return close.pct_change().dropna()


def annualized_vol(close: pd.Series, lookback: int = 252) -> float | None:
    r = daily_returns(close).tail(lookback)
    if len(r) < 20:
        return None
    return float(r.std() * np.sqrt(252) * 100.0)


def max_drawdown(close: pd.Series, lookback: int = 252) -> float | None:
    c = close.dropna().tail(lookback)
    if len(c) < 20:
        return None
    roll_max = c.cummax()
    dd = (c / roll_max - 1.0)
    return float(dd.min() * 100.0)


def sharpe(close: pd.Series, lookback: int = 252, rf_annual: float = 0.04) -> float | None:
    r = daily_returns(close).tail(lookback)
    if len(r) < 20:
        return None
    excess = r - (rf_annual / 252)
    sd = r.std()
    if sd == 0 or pd.isna(sd):
        return None
    return float(excess.mean() / sd * np.sqrt(252))


def sortino(close: pd.Series, lookback: int = 252, rf_annual: float = 0.04) -> float | None:
    r = daily_returns(close).tail(lookback)
    if len(r) < 20:
        return None
    excess = r - (rf_annual / 252)
    downside = r[r < 0]
    dd = downside.std()
    if dd == 0 or pd.isna(dd) or len(downside) < 5:
        return None
    return float(excess.mean() / dd * np.sqrt(252))


def risk_metrics(close: pd.Series, lookback: int = 252, rf_annual: float = 0.04) -> dict:
    return {
        "vol": annualized_vol(close, lookback),
        "max_dd": max_drawdown(close, lookback),
        "sharpe": sharpe(close, lookback, rf_annual),
        "sortino": sortino(close, lookback, rf_annual),
    }


def correlation_matrix(closes: dict, lookback: int = 252) -> dict:
    """Korrelasjonsmatrise av daglige avkastninger for gitte serier."""
    rets = {}
    for iid, c in closes.items():
        r = daily_returns(c).tail(lookback)
        if len(r) >= 60:
            rets[iid] = r
    if len(rets) < 2:
        return {"ids": [], "matrix": []}
    df = pd.DataFrame(rets).dropna()
    if len(df) < 60:
        df = pd.DataFrame(rets)  # behold det vi har
    corr = df.corr()
    ids = list(corr.columns)
    matrix = [[round(float(corr.iloc[i, j]), 2) for j in range(len(ids))] for i in range(len(ids))]
    return {"ids": ids, "matrix": matrix}


# ── Posisjonsstørrelse: volatilitetsmål ──────────────────────────
def vol_target_weight(vol_pct: float | None, target_annual: float = 0.12) -> float | None:
    """
    Invers-volatilitet vekt-faktor mot et årlig vol-mål.
    1.0 = posisjon med vol lik målet; <1 hvis mer volatil.
    """
    if vol_pct is None or vol_pct <= 0:
        return None
    return float(target_annual / (vol_pct / 100.0))


# ── RRG: Relative Rotation Graph (JdK RS-Ratio / RS-Momentum) ─────
def rrg_point(num: pd.Series, den: pd.Series, window: int = 63) -> dict | None:
    """
    Forenklet JdK RS-Ratio/RS-Momentum for ett instrument vs baseline.

    RS-Ratio  = normalisert relativ styrke (trend i ratioen, sentrert på 100).
    RS-Momentum = normalisert endringstakt i RS-Ratio (sentrert på 100).

    Kvadranter (klokka rundt): Leading (x>100,y>100) -> Weakening (x>100,y<100)
    -> Lagging (x<100,y<100) -> Improving (x<100,y>100).
    Returnerer None ved for kort historikk.
    """
    comb = pd.DataFrame({"n": num, "d": den}).dropna()
    if len(comb) < window * 2 + 5:
        return None
    rs = (comb["n"] / comb["d"]) * 100.0
    # RS-Ratio: hvor langt RS ligger over/under eget glidende snitt, z-skåret
    rs_sma = rs.rolling(window).mean()
    rs_std = rs.rolling(window).std()
    rs_ratio = 100 + (rs - rs_sma) / rs_std.replace(0, np.nan)
    rs_ratio = rs_ratio.dropna()
    if len(rs_ratio) < window + 5:
        return None
    # RS-Momentum: endringstakt i RS-Ratio, z-skåret
    roc_rr = rs_ratio.diff(int(window / 3))
    mom = 100 + (roc_rr - roc_rr.rolling(window).mean()) / roc_rr.rolling(window).std().replace(0, np.nan)
    mom = mom.dropna()
    if mom.empty or rs_ratio.empty:
        return None
    x = float(rs_ratio.iloc[-1])
    y = float(mom.iloc[-1])
    if not (np.isfinite(x) and np.isfinite(y)):
        return None
    if x >= 100 and y >= 100:
        quad = "Leading"
    elif x >= 100 and y < 100:
        quad = "Weakening"
    elif x < 100 and y < 100:
        quad = "Lagging"
    else:
        quad = "Improving"
    # liten hale (siste 5 punkter) for retning
    tail = [[round(float(a), 2), round(float(b), 2)]
            for a, b in zip(rs_ratio.tail(5), mom.tail(5))
            if np.isfinite(a) and np.isfinite(b)]
    return {"rs_ratio": round(x, 2), "rs_momentum": round(y, 2), "quadrant": quad, "tail": tail}


# ════════════════════════════════════════════════════════════════
# NSBC-METODIKK (Northstar & Badcharts)
# Bygget direkte fra deres dokumenter:
#  - 12 & 36 SMA "Trend Navigator" (over begge + golden cross = bull)
#  - Ichimoku Cloud 9/26/52 (over sky = bull, under = bear)
#  - Distance % from 36 SMA: 0-linje = nøytral, +10% = stretched/FOMO-sone
#  - Stochastic RSI (ikke vanlig RSI)
#  - Lavrisiko-entry = IKKE stretched + nettopp brutt ut av konsolidering
# ════════════════════════════════════════════════════════════════

def ichimoku(high: pd.Series, low: pd.Series, close: pd.Series,
             conv=9, base=26, span_b=52):
    """
    Ichimoku Cloud (Hosodas originale 9/26/52). Returnerer dict med
    tenkan, kijun, span_a, span_b (forskjøvet 26 frem), og om close er
    over/under skyen NÅ (det NSBC bryr seg om: bull over, bear under).
    """
    conv_line = (high.rolling(conv).max() + low.rolling(conv).min()) / 2
    base_line = (high.rolling(base).max() + low.rolling(base).min()) / 2
    span_a = ((conv_line + base_line) / 2)
    span_b_line = (high.rolling(span_b).max() + low.rolling(span_b).min()) / 2
    # Skyen som gjelder NÅ ble projektert for 26 perioder siden
    cloud_top_now = pd.concat([span_a.shift(base), span_b_line.shift(base)], axis=1).max(axis=1)
    cloud_bot_now = pd.concat([span_a.shift(base), span_b_line.shift(base)], axis=1).min(axis=1)
    last = float(close.iloc[-1])
    ct = cloud_top_now.iloc[-1]
    cb = cloud_bot_now.iloc[-1]
    if pd.isna(ct) or pd.isna(cb):
        pos = None
    elif last > ct:
        pos = "above"     # bull
    elif last < cb:
        pos = "below"     # bear
    else:
        pos = "inside"    # nøytral/i skyen
    # Fremtidssky-retning (grønn/stigende = bull-struktur)
    future_green = None
    if not pd.isna(span_a.iloc[-1]) and not pd.isna(span_b_line.iloc[-1]):
        future_green = bool(span_a.iloc[-1] >= span_b_line.iloc[-1])
    return {"position": pos, "future_bull": future_green,
            "cloud_top": float(ct) if not pd.isna(ct) else None,
            "cloud_bot": float(cb) if not pd.isna(cb) else None}


def stoch_rsi(close: pd.Series, rsi_len=14, stoch_len=14, k=3, d=3):
    """Stochastic RSI (NSBC bruker denne, ikke vanlig RSI). Returnerer (K, D)."""
    r = rsi(close, rsi_len)
    rmin = r.rolling(stoch_len).min()
    rmax = r.rolling(stoch_len).max()
    denom = (rmax - rmin).replace(0, np.nan)
    stoch = (r - rmin) / denom * 100
    kline = stoch.rolling(k).mean()
    dline = kline.rolling(d).mean()
    kv = float(kline.iloc[-1]) if pd.notna(kline.iloc[-1]) else None
    dv = float(dline.iloc[-1]) if pd.notna(dline.iloc[-1]) else None
    kprev = float(kline.iloc[-2]) if len(kline) > 1 and pd.notna(kline.iloc[-2]) else None
    return {"k": kv, "d": dv, "k_prev": kprev,
            "turning_up": (kv is not None and kprev is not None and kv > kprev),
            "oversold": (kv is not None and kv < 20),
            "overbought": (kv is not None and kv > 80)}


def dist_from_ma(close: pd.Series, n: int = 36) -> dict:
    """
    Distance % fra n-SMA (NSBC: 36). 0 = nøytral, +10% = stretched/FOMO-sone.
    Returnerer nåverdi, om den nettopp krysset opp over 0 (momentum gjenvunnet),
    og om den er i stretched-sonen (>= +10%, dårlig lavrisiko-entry).
    """
    ma = close.rolling(n).mean()
    dist = (close - ma) / ma * 100
    d = dist.dropna()
    if len(d) < 2:
        return {"dist": None, "crossed_up": False, "stretched": False, "series": []}
    last = float(d.iloc[-1])
    prev = float(d.iloc[-2])
    return {
        "dist": round(last, 2),
        "crossed_up": bool(prev <= 0 < last),       # momentum gjenvunnet
        "stretched": bool(last >= 10.0),            # FOMO / profit-taking-sone
        "below_zero": bool(last < 0),
        "series": [(idx.strftime("%Y-%m-%d"), round(float(v), 2)) for idx, v in d.tail(180).items()],
    }


def trend_navigator(close: pd.Series, short=12, long=36) -> dict:
    """
    NSBC Trend Navigator: 12 & 36 SMA. Bull = close over BEGGE og 12>36.
    Golden cross = 12 krysser over 36. Death cross = motsatt.
    """
    s = close.rolling(short).mean()
    l = close.rolling(long).mean()
    if pd.isna(s.iloc[-1]) or pd.isna(l.iloc[-1]):
        return {"state": None, "above_both": False, "s_over_l": False,
                "golden_cross": False, "death_cross": False}
    last = float(close.iloc[-1])
    above_both = bool(last > s.iloc[-1] and last > l.iloc[-1])
    s_over_l = bool(s.iloc[-1] > l.iloc[-1])
    gc = dc = False
    if len(s) > 1 and pd.notna(s.iloc[-2]) and pd.notna(l.iloc[-2]):
        gc = bool(s.iloc[-2] <= l.iloc[-2] and s.iloc[-1] > l.iloc[-1])
        dc = bool(s.iloc[-2] >= l.iloc[-2] and s.iloc[-1] < l.iloc[-1])
    if above_both and s_over_l:
        state = "bull"
    elif last < s.iloc[-1] and last < l.iloc[-1] and not s_over_l:
        state = "bear"
    else:
        state = "neutral"   # NSBC: sidelengs = agnostisk, ikke bearish
    return {"state": state, "above_both": above_both, "s_over_l": s_over_l,
            "golden_cross": gc, "death_cross": dc}


# ── Support/resistance-motor (swing-pivoter klustret til nivåer) ──
def swing_pivots(high: pd.Series, low: pd.Series, left=3, right=3):
    """Finn swing-topper/-bunner (fraktaler). Returnerer (highs, lows) som lister."""
    h = high.values
    l = low.values
    n = len(h)
    highs, lows = [], []
    for i in range(left, n - right):
        if all(h[i] >= h[i - j] for j in range(1, left + 1)) and \
           all(h[i] >= h[i + j] for j in range(1, right + 1)):
            highs.append((i, float(h[i])))
        if all(l[i] <= l[i - j] for j in range(1, left + 1)) and \
           all(l[i] <= l[i + j] for j in range(1, right + 1)):
            lows.append((i, float(l[i])))
    return highs, lows


def support_resistance(high: pd.Series, low: pd.Series, close: pd.Series,
                       left=3, right=3, tol=0.02, max_levels=6) -> dict:
    """
    Klustre swing-pivoter til horisontale nivåer (NSBC: support/resistance-linjer).
    Nivåer scores på antall berøringer og nærhet til dagens pris.
    Returnerer support (under pris) og resistance (over pris), nærmest først.
    """
    highs, lows = swing_pivots(high, low, left, right)
    pts = [p for _, p in highs] + [p for _, p in lows]
    if not pts:
        return {"support": [], "resistance": [], "all": []}
    pts.sort()
    clusters = []
    cur = [pts[0]]
    for p in pts[1:]:
        if abs(p - cur[-1]) / cur[-1] <= tol:
            cur.append(p)
        else:
            clusters.append(cur)
            cur = [p]
    clusters.append(cur)
    levels = [{"price": round(sum(c) / len(c), 4), "touches": len(c)} for c in clusters]
    last = float(close.iloc[-1])
    support = sorted([lv for lv in levels if lv["price"] < last],
                     key=lambda x: -x["price"])
    resistance = sorted([lv for lv in levels if lv["price"] > last],
                        key=lambda x: x["price"])
    return {"support": support[:max_levels], "resistance": resistance[:max_levels],
            "all": sorted(levels, key=lambda x: x["price"])}


def breakout_state(high: pd.Series, low: pd.Series, close: pd.Series,
                   lookback=60) -> dict:
    """
    Bryter prisen ut av en konsolidering? NSBC-lavrisiko-entry krever dette.
    Konsolidering = pris har ligget i et relativt smalt bånd; breakout = close
    over båndets tak (resistance) etter å ha vært inne i det.
    """
    c = close.tail(lookback)
    h = high.tail(lookback)
    l = low.tail(lookback)
    if len(c) < 20:
        return {"breakout": False, "consolidating": False, "range_pct": None}
    hi = float(h.max())
    lo = float(l.min())
    rng = (hi - lo) / lo * 100 if lo > 0 else 999
    last = float(c.iloc[-1])
    prev_hi = float(h.iloc[:-1].max())
    # breakout = ny høyde over forrige periodes tak, og båndet var ikke altfor bredt
    breakout = bool(last >= prev_hi and rng < 60)
    # konsolidering = siste 20 barer innenfor < 15% bånd
    recent = c.tail(20)
    cons_rng = (recent.max() - recent.min()) / recent.min() * 100 if recent.min() > 0 else 999
    consolidating = bool(cons_rng < 15)
    return {"breakout": breakout, "consolidating": consolidating,
            "range_pct": round(rng, 1), "recent_range_pct": round(cons_rng, 1)}
