"""
Northstar-score: 0-100, høyere = lavere risiko / bedre lavrisiko-entry.

Tre tidsrammer (ukentlig/månedlig/kvartal), 33% hver. Hver tidsramme
kombinerer RSI (lavere = bedre entry), MACD-histogram-retning og avstand
til 36-perioders MA. Kontinuerlige delscorer (ikke terskel-hopp).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from . import indicators as ind


def _rsi_subscore(rsi_val: float | None) -> float:
    """Lav RSI = bedre entry. 30->1.0, 70->0.0, lineært, klippet."""
    if rsi_val is None or pd.isna(rsi_val):
        return 0.5
    return float(np.clip((70 - rsi_val) / 40.0, 0.0, 1.0))


def _macd_subscore(hist: float | None, prev_hist: float | None) -> float:
    """Positiv og stigende histogram = momentum opp."""
    if hist is None or pd.isna(hist):
        return 0.5
    base = 0.6 if hist > 0 else 0.4
    if prev_hist is not None and not pd.isna(prev_hist):
        if hist > prev_hist:
            base += 0.2
        else:
            base -= 0.1
    return float(np.clip(base, 0.0, 1.0))


def _ma_subscore(dist_pct: float | None) -> float:
    """
    Nær MA (liten |avstand|) = lavrisiko entry. Langt over = strukket (dårlig
    entry men ikke null). Under MA = svakt.
    """
    if dist_pct is None or pd.isna(dist_pct):
        return 0.5
    d = dist_pct / 100.0
    if d >= 0:
        return float(np.clip(1.0 - d / 0.25, 0.2, 1.0))   # 0% over=1.0, 25% over=0.2
    return float(np.clip(0.5 + d / 0.20, 0.0, 0.5))        # under MA faller mot 0


def frame_summary(df: pd.DataFrame) -> dict:
    """Indikatorer for én tidsramme."""
    c = df["close_use"].dropna()
    if len(c) < 5:
        return {}
    rsi_s = ind.rsi(c, 14)
    macd_line, sig, hist = ind.macd(c)
    sma36 = ind.sma(c, 36)
    sma50 = ind.sma(c, 50)
    last = float(c.iloc[-1])
    dist36 = float((last - sma36.iloc[-1]) / sma36.iloc[-1] * 100) if pd.notna(sma36.iloc[-1]) else None
    return {
        "last": last,
        "rsi14": float(rsi_s.iloc[-1]) if pd.notna(rsi_s.iloc[-1]) else None,
        "macd_hist": float(hist.iloc[-1]) if pd.notna(hist.iloc[-1]) else None,
        "macd_hist_prev": float(hist.iloc[-2]) if len(hist) > 1 and pd.notna(hist.iloc[-2]) else None,
        "dist_to_36MA": dist36,
        "sma50": float(sma50.iloc[-1]) if pd.notna(sma50.iloc[-1]) else None,
        "close_above_sma50": bool(last > sma50.iloc[-1]) if pd.notna(sma50.iloc[-1]) else None,
    }


def timeframe_score(fs: dict) -> float | None:
    if not fs:
        return None
    rs = _rsi_subscore(fs.get("rsi14"))
    ms = _macd_subscore(fs.get("macd_hist"), fs.get("macd_hist_prev"))
    mas = _ma_subscore(fs.get("dist_to_36MA"))
    return (rs + ms + mas) / 3.0 * 100.0


def northstar_score(frames: dict) -> tuple[int, dict]:
    """Vektet snitt over weekly/monthly/quarterly (33% hver)."""
    parts = {}
    vals = []
    for tf in ("weekly", "monthly", "quarterly"):
        fs = frame_summary(frames.get(tf, pd.DataFrame()))
        parts[tf] = fs
        s = timeframe_score(fs)
        if s is not None:
            vals.append(s)
    score = round(sum(vals) / len(vals)) if vals else 50
    return int(np.clip(score, 0, 100)), parts


def score_label(score: int) -> tuple[str, str]:
    """(tekst, farge) – colorblind-trygg (blå/oransje/vermillion)."""
    from .config import PALETTE
    if score >= 70:
        return "Lav risiko (god entry)", PALETTE["up"]
    if score >= 55:
        return "Moderat", PALETTE["accent"]
    if score >= 40:
        return "Avventende", PALETTE["warn"]
    return "Høy risiko / svak", PALETTE["down"]
