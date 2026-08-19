"""
NSBC-score (Northstar & Badcharts evidens-klynge), 0-100.

KORRIGERT i v6 for å matche NSBCs faktiske metodikk (fra deres dokumenter):
  - IKKE MACD (de bruker det ikke), IKKE "lav RSI = bra entry" (mean-reversion).
  - JA: 12 & 36 SMA Trend Navigator (over begge = bull), Ichimoku Cloud 9/26/52
    (over sky = bull), distance % fra 36-SMA (0 = nøytral, +10% = stretched/FOMO),
    Stochastic RSI (snur opp fra oversold), og breakout fra konsolidering.

NSBCs definisjon av LAVRISIKO-ENTRY (verbatim fra dokumentene):
  "Low risk entry points are found when price is not stretched and has just
   broken out of a pullback/consolidation pattern."
  Altså: IKKE stretched fra langtids-MA + nettopp brutt ut av base + over trend.
  En stretched pris i FOMO-sonen er HØY risiko å gå inn på (selv om trenden er opp).

Multi-tidsramme (NSBC): høyere tidsramme gir med-/motvind til lavere. Vi skiller
derfor LANGTID (M/Q: regime) fra KORTTID (W: timing) i stedet for å blande alt.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from . import indicators as ind
from .config import PALETTE


def frame_evidence(df: pd.DataFrame) -> dict:
    """
    Samle NSBC-evidens for én tidsramme fra OHLC.
    Returnerer 'ticks' (tente bevis), trend-tilstand, og om stretched.
    """
    c = df["close_use"].dropna()
    if len(c) < 12:
        return {}
    high = df["high"] if "high" in df else c
    low = df["low"] if "low" in df else c

    tn = ind.trend_navigator(c, 12, 36)
    ich = ind.ichimoku(high, low, c)
    dist = ind.dist_from_ma(c, 36)
    dist12 = ind.dist_from_ma(c, 12)
    srsi = ind.stoch_rsi(c)
    brk = ind.breakout_state(high, low, c)

    return {
        "trend": tn.get("state"),            # bull / neutral / bear
        "above_both_ma": tn.get("above_both", False),
        "golden_cross": tn.get("golden_cross", False),
        "death_cross": tn.get("death_cross", False),
        "cloud": ich.get("position"),        # above / inside / below
        "future_bull": ich.get("future_bull"),
        "dist36": dist["dist"],
        "dist12": dist12["dist"],
        "dist_crossed_up": dist["crossed_up"],
        "stretched": dist["stretched"],
        "below_zero": dist.get("below_zero"),
        "srsi_k": srsi["k"],
        "srsi_turning_up": srsi["turning_up"],
        "srsi_oversold": srsi["oversold"],
        "srsi_overbought": srsi["overbought"],
        "breakout": brk["breakout"],
        "consolidating": brk["consolidating"],
        "last": float(c.iloc[-1]),
    }


def timeframe_state(fe: dict) -> str | None:
    """NSBC trend-bias for tidsrammen: bull / neutral / bear."""
    if not fe:
        return None
    # Vekt av evidens: trend-navigator + sky
    if fe["trend"] == "bull" and fe["cloud"] in ("above", "inside"):
        return "bull"
    if fe["trend"] == "bear" and fe["cloud"] in ("below", "inside"):
        return "bear"
    if fe["above_both_ma"] and fe["cloud"] == "above":
        return "bull"
    if fe["trend"] == "bear" or fe["cloud"] == "below":
        return "bear"
    return "neutral"   # sidelengs = agnostisk (NSBC: ikke bearish)


def entry_quality(weekly: dict, monthly: dict, quarterly: dict) -> tuple[int, dict]:
    """
    NSBC lavrisiko-entry-score 0-100. Høyt = ekte lavrisiko-entry slik NSBC
    definerer det: langtid konstruktiv + korttid breakout fra base + IKKE stretched.

    Bygger på 'weight of evidence' (teller tente bevis), ikke oscillator-snitt.
    """
    if not weekly:
        return 50, {}

    # Langtidsregime (M+Q): gir med-/motvind
    lt_states = [timeframe_state(monthly), timeframe_state(quarterly)]
    lt_bull = sum(1 for s in lt_states if s == "bull")
    lt_bear = sum(1 for s in lt_states if s == "bear")
    if lt_bull >= 1 and lt_bear == 0:
        lt = "bull"
    elif lt_bear >= 1 and lt_bull == 0:
        lt = "bear"
    else:
        lt = "neutral"

    # Korttidstiming (W)
    st = timeframe_state(weekly)

    # Evidens-ticks for entry-kvalitet (maks 6)
    ticks = 0
    detail = []
    # 1. Over 12 & 36 MA (ukentlig)
    if weekly.get("above_both_ma"):
        ticks += 1; detail.append("over 12&36 SMA")
    # 2. Over Ichimoku-sky
    if weekly.get("cloud") == "above":
        ticks += 1; detail.append("over sky")
    # 3. Momentum gjenvunnet (distance krysset opp over 0) ELLER golden cross
    if weekly.get("dist_crossed_up") or weekly.get("golden_cross"):
        ticks += 1; detail.append("momentum snudd opp")
    # 4. StochRSI snur opp (helst fra oversold)
    if weekly.get("srsi_turning_up"):
        ticks += 1; detail.append("StochRSI snur opp")
    # 5. Breakout fra konsolidering (NSBCs kjernekriterium)
    if weekly.get("breakout"):
        ticks += 2; detail.append("breakout fra base")  # teller dobbelt
    elif weekly.get("consolidating"):
        ticks += 1; detail.append("bygger base")

    # Score: basis fra ticks (maks ~7 -> skaler til 100)
    raw = min(ticks / 7.0, 1.0) * 100

    # Langtidsregime justerer: medvind løfter, motvind senker
    if lt == "bull":
        raw = raw * 1.0 + 10
    elif lt == "bear":
        raw = raw * 0.6      # motvind: selv en breakout er høyere risiko

    # STRETCHED-STRAFF (NSBCs viktigste poeng): pris i FOMO-sonen =
    # HØY risiko entry, ikke lav. Caps scoren hardt.
    if weekly.get("stretched"):
        raw = min(raw, 45)
        detail.append("⚠ stretched (FOMO-sone)")
    if monthly and monthly.get("stretched"):
        raw = min(raw, 55)

    # Fallende kniv-vakt: under alle MA + sky = ikke lavrisiko uansett RSI
    if st == "bear" and not weekly.get("breakout"):
        raw = min(raw, 30)

    score = int(np.clip(round(raw), 0, 100))
    stage = classify_stage(weekly, monthly)
    return score, {
        "long_term": lt, "short_term": st, "ticks": ticks,
        "evidence": detail,
        "stretched": bool(weekly.get("stretched")),
        "dist36": weekly.get("dist36"),
        "breakout": bool(weekly.get("breakout")),
        "stage": stage["stage"],
        "stage_label": stage["label"],
        "stage_reason": stage["reason"],
    }


def classify_stage(weekly: dict, monthly: dict) -> dict:
    """
    Weinstein stage-analyse (1-4) — løser tvetydigheten stretched vs nedtrend.
    NSBC nedstammer fra Weinstein (Karim siterer 'Stan Weinstein's Secrets').

      Stage 1 — Basing/akkumulering: flat MA, pris pendler rundt 36-MA.
      Stage 2 — Opptrend: over stigende 12&36 MA + over sky.
      Stage 3 — Topping/distribusjon: flat MA etter opptur, momentum avtar.
      Stage 4 — Nedtrend: UNDER fallende MA + under sky. (= lav score, IKKE stretched)

    Stretched/FOMO er en UNDER-tilstand av Stage 2 (opptrend, men strukket) —
    aldri det samme som Stage 4 (nedtrend). Det er kjernen i feilrettingen.
    """
    if not weekly:
        return {"stage": None, "label": "Ukjent", "reason": "for lite data"}

    trend = weekly.get("trend")          # bull / neutral / bear
    cloud = weekly.get("cloud")          # above / inside / below
    above_ma = weekly.get("above_both_ma")
    below_zero = weekly.get("below_zero")
    stretched = weekly.get("stretched")
    dist = weekly.get("dist36")
    breakout = weekly.get("breakout")
    s_over_l = weekly.get("s_over_l", None)

    # Stage 4: nedtrend — under MA og sky, fallende
    if trend == "bear" and cloud == "below":
        return {"stage": 4, "label": "Nedtrend (Stage 4)",
                "reason": f"under 12&36-MA og under sky, momentum {dist:+.0f}% under null"
                          if dist is not None else "under 12&36-MA og under sky"}
    if (not above_ma) and below_zero and cloud in ("below", "inside"):
        return {"stage": 4, "label": "Nedtrend (Stage 4)",
                "reason": "under glidende snitt, negativ momentum"}

    # Stage 2: opptrend — over stigende MA + over sky
    if above_ma and cloud == "above" and trend == "bull":
        if stretched:
            return {"stage": 2, "label": "Strukket (FOMO-sone)",
                    "reason": f"opptrend, men {dist:+.0f}% over 36-MA — høy risiko å gå inn, "
                              "eier kan holde" if dist is not None else "opptrend men strukket"}
        if breakout:
            return {"stage": 2, "label": "Opptrend – breakout",
                    "reason": "over stigende 12&36-MA, over sky, bryter ut av base"}
        return {"stage": 2, "label": "Opptrend (Stage 2)",
                "reason": "over stigende 12&36-MA og over sky"}

    # Stage 3: distribusjon — var over, men momentum faller / under én MA
    if (s_over_l or cloud == "above") and (below_zero or trend == "neutral"):
        return {"stage": 3, "label": "Distribusjon (Stage 3)",
                "reason": "momentum avtar etter opptur — vær varsom"}

    # Stage 1: basing — flatt, rundt MA, ingen klar retning
    return {"stage": 1, "label": "Basing (Stage 1)",
            "reason": "pendler rundt glidende snitt — bygger mulig base"}


def nsbc_score(frames: dict) -> tuple[int, dict]:
    """Hovedinngang: bygg evidens per tidsramme og regn entry-kvalitet."""
    w = frame_evidence(frames.get("weekly", pd.DataFrame()))
    m = frame_evidence(frames.get("monthly", pd.DataFrame()))
    q = frame_evidence(frames.get("quarterly", pd.DataFrame()))
    score, meta = entry_quality(w, m, q)
    meta["frames"] = {"weekly": w, "monthly": m, "quarterly": q}
    return score, meta


# Bakoverkompatibelt alias (build.py kaller northstar_score)
def northstar_score(frames: dict) -> tuple[int, dict]:
    return nsbc_score(frames)


def score_label(score: int, meta: dict | None = None) -> tuple[str, str]:
    """
    (tekst, farge). KORRIGERT: skiller nedtrend fra strukket.
    Lav score kan bety enten Stage 4 (nedtrend) ELLER strukket — aldri begge.
    Bruk stage-etiketten når meta er tilgjengelig.
    """
    if meta and meta.get("stage_label"):
        sl = meta["stage_label"]
        if score >= 70:
            return "Lavrisiko-entry", PALETTE["up"]
        if "Strukket" in sl:
            return sl, PALETTE["warn"]          # opptrend men FOMO
        if "Nedtrend" in sl:
            return sl, PALETTE["down"]          # Stage 4 — IKKE stretched
        if score >= 55:
            return sl, PALETTE["accent"]
        if score >= 40:
            return sl, PALETTE["warn"]
        return sl, PALETTE["down"]
    # Fallback uten meta
    if score >= 70:
        return "Lavrisiko-entry", PALETTE["up"]
    if score >= 55:
        return "Konstruktiv", PALETTE["accent"]
    if score >= 40:
        return "Avvent base/breakout", PALETTE["warn"]
    return "Svakt oppsett", PALETTE["down"]


def state_label(lt: str, st: str) -> str:
    """Langtid × korttid som lesbar etikett (NSBC kan være bull+bear samtidig)."""
    m = {"bull": "bull", "bear": "bear", "neutral": "nøytral", None: "n/a"}
    return f"LT {m.get(lt,'n/a')} / KT {m.get(st,'n/a')}"
