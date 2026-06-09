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
