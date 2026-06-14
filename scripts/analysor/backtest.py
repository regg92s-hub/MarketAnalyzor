"""
Walk-forward / out-of-sample backtest av rotasjonsregelen.

Rapportens Stage 3 (troverdighet): en score og en rotasjonsregel er kun
*påstander* til de er testet out-of-sample. Dette modulen tester en enkel,
økonomisk motivert regel (lav parameterrikdom = mindre overtilpasning):

  REGEL (månedlig rebalansering):
    - Beregn 3M+6M momentum (ROC) mot gull for hvert syklisk instrument.
    - Absolutt-momentum-filter (Antonacci dual momentum): hold kun instrumenter
      som også har positiv absolutt 12M-avkastning; ellers til cash/gull.
    - Eier topp-N (relativ styrke) som passerer filteret, likevektet.
    - Volatilitetsskalering (Daniel & Moskowitz): skaler eksponering ned i
      høyvol-regimer for å dempe momentum-krasj.

  WALK-FORWARD: ingen parameteroptimalisering på testdata. Regelen er fast og
  økonomisk begrunnet; vi rapporterer rullende out-of-sample-avkastning og
  sammenligner mot kjøp-og-hold SPY og gull. Look-ahead unngås ved å bruke
  forrige måneds signaler for inneværende måneds avkastning.

Dette er fortsatt IKKE en garanti for fremtidig avkastning — kun en ærlig test
av om regelen har historisk hold.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from . import indicators as ind


def _month_end_prices(raw: dict, ids: list) -> pd.DataFrame:
    """Månedssluttkurser for gitte instrumenter, justert og innrettet."""
    cols = {}
    for iid in ids:
        df = raw.get(iid)
        if df is None:
            continue
        m = df["close_use"].resample("ME").last()
        cols[iid] = m
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).dropna(how="all")


def run_backtest(raw: dict, cyclical_ids: list, top_n: int = 5,
                 start: str = "2012-01-01") -> dict:
    """
    Kjør rotasjonsbacktest. Returnerer ytelsesmål + ekvitykurver (månedlig).
    """
    gld = raw.get("GLD")
    spy = raw.get("SPY")
    if gld is None or spy is None:
        return {"available": False, "reason": "mangler GLD/SPY"}

    px = _month_end_prices(raw, cyclical_ids + ["GLD", "SPY"])
    if px.empty or len(px) < 40:
        return {"available": False, "reason": "for kort historikk"}
    px = px[px.index >= pd.Timestamp(start)]
    if len(px) < 36:
        return {"available": False, "reason": "for få måneder etter startdato"}

    rets = px.pct_change()
    gold_m = px["GLD"]

    from .config import (TX_COST_BPS, HYSTERESIS_Z, BT_VOL_TARGET,
                         VALUE_WEIGHT, VALUE_LOOKBACK_M,
                         PANIC_VOL_THRESHOLD, PANIC_EXPOSURE_CAP)
    cost_rate = TX_COST_BPS / 10000.0

    def _z(d: dict) -> dict:
        v = np.array(list(d.values()), dtype=float)
        if len(v) < 2 or np.std(v) == 0:
            return {k: 0.0 for k in d}
        mu, sd = float(np.mean(v)), float(np.std(v))
        return {k: (x - mu) / sd for k, x in d.items()}

    strat_curve = [1.0]
    spy_curve = [1.0]
    gold_curve = [1.0]
    dates = [px.index[0].strftime("%Y-%m")]
    n_hold_log = []
    exposure_log = []
    turnover_log = []
    panic_log = []
    prev_holds: list = []

    # iterer måned for måned; signaler fra t-1, avkastning i t (ingen look-ahead)
    for t in range(13, len(px)):
        sig_date = px.index[t - 1]
        # relativ styrke mot gull: 3M+6M ROC av ratioen + VALUE-TILT
        # (Asness 2013: value = negativ langtids relativ avkastning; mom+value
        # er negativt korrelert -> kombinasjonen demper krasj og turnover)
        mom_s, val_s = {}, {}
        for iid in cyclical_ids:
            if iid not in px.columns:
                continue
            ratio = (px[iid] / px["GLD"]).iloc[:t]  # kun data t.o.m. t-1
            r = ratio.dropna()
            if len(r) < 7:
                continue
            roc3 = (r.iloc[-1] / r.iloc[-4] - 1) if len(r) >= 4 else None
            roc6 = (r.iloc[-1] / r.iloc[-7] - 1) if len(r) >= 7 else None
            if roc3 is None or roc6 is None:
                continue
            rel = (roc3 + roc6) / 2
            # absolutt-momentum-filter: 12M absolutt avkastning > 0
            abs_series = px[iid].iloc[:t].dropna()
            abs12 = (abs_series.iloc[-1] / abs_series.iloc[-13] - 1) if len(abs_series) >= 13 else None
            if abs12 is None or abs12 <= 0:
                continue  # feiler filter -> ikke eid (til cash)
            if rel <= 0:
                continue
            mom_s[iid] = rel
            lb = min(VALUE_LOOKBACK_M, len(r) - 1)
            val_s[iid] = (-(r.iloc[-1] / r.iloc[-1 - lb] - 1)) if lb >= 24 else 0.0
        mz, vz = _z(mom_s), _z(val_s)
        scores = {k: mz[k] + VALUE_WEIGHT * vz.get(k, 0.0) for k in mom_s}

        # Utvalg med HYSTERESE: eierposisjoner beholdes så lenge de fortsatt
        # kvalifiserer; en utfordrer må slå svakeste eier med margin. Dette
        # senker turnover og gjør live-resultat likere backtest.
        incumbents = sorted([h for h in prev_holds if h in scores],
                            key=lambda k: -scores[k])
        challengers = sorted([k for k in scores if k not in incumbents],
                             key=lambda k: -scores[k])
        holds = incumbents[:top_n]
        for cand in challengers:
            if len(holds) < top_n:
                holds.append(cand)
                continue
            weakest = min(holds, key=lambda k: scores[k])
            if scores[cand] > scores[weakest] + HYSTERESIS_Z:
                holds.remove(weakest)
                holds.append(cand)
        n_hold_log.append(len(holds))

        # Kontinuerlig volatilitetsskalering (Moreira & Muir): eksponering =
        # vol-mål / realisert vol, klippet til [0.3, 1.0]. Erstatter trappetrinn.
        exposure = 1.0
        try:
            basket = holds if holds else ["GLD"]
            recent = rets[basket].iloc[t - 6:t].mean(axis=1).dropna()
            if len(recent) >= 4:
                rvol = float(recent.std() * np.sqrt(12))
                if rvol > 0:
                    exposure = float(np.clip(BT_VOL_TARGET / rvol, 0.3, 1.0))
        except Exception:
            pass
        # PANIKK-DEMPER (Daniel & Moskowitz 2016): SPY 12m < 0 OG høy vol ->
        # cap eksponering. Krasjene kommer i rebound etter bear-marked.
        panic = False
        try:
            spy12 = float(px["SPY"].iloc[t - 1] / px["SPY"].iloc[t - 13] - 1)
            spyv = float(rets["SPY"].iloc[t - 6:t].std() * np.sqrt(12))
            panic = (spy12 < 0) and (spyv > PANIC_VOL_THRESHOLD)
            if panic:
                exposure = min(exposure, PANIC_EXPOSURE_CAP)
        except Exception:
            pass
        panic_log.append(panic)
        exposure_log.append(exposure)

        # Transaksjonskostnader: kostnad på handlet notional (likevekts-vekter).
        w_prev = {h: 1.0 / len(prev_holds) for h in prev_holds} if prev_holds else {}
        w_new = {h: 1.0 / len(holds) for h in holds} if holds else {}
        all_ids = set(w_prev) | set(w_new)
        turnover = sum(abs(w_new.get(i, 0.0) - w_prev.get(i, 0.0)) for i in all_ids)
        turnover_log.append(turnover)
        cost = turnover * cost_rate

        # månedens avkastning
        if holds:
            port_ret = float(rets[holds].iloc[t].mean())
        else:
            port_ret = float(rets["GLD"].iloc[t])  # ingen leder -> gull
        port_ret = port_ret * exposure - cost  # resten i cash (0 % antatt)
        prev_holds = holds

        strat_curve.append(strat_curve[-1] * (1 + (port_ret if np.isfinite(port_ret) else 0)))
        spy_curve.append(spy_curve[-1] * (1 + (float(rets["SPY"].iloc[t]) if np.isfinite(rets["SPY"].iloc[t]) else 0)))
        gold_curve.append(gold_curve[-1] * (1 + (float(rets["GLD"].iloc[t]) if np.isfinite(rets["GLD"].iloc[t]) else 0)))
        dates.append(px.index[t].strftime("%Y-%m"))

    def stats(curve):
        c = pd.Series(curve)
        months = len(c) - 1
        if months < 12:
            return {}
        total = c.iloc[-1] / c.iloc[0] - 1
        cagr = (c.iloc[-1] / c.iloc[0]) ** (12 / months) - 1
        mret = c.pct_change().dropna()
        vol = mret.std() * np.sqrt(12)
        sharpe = (mret.mean() * 12 - 0.04) / vol if vol > 0 else None
        roll_max = c.cummax()
        maxdd = float((c / roll_max - 1).min())
        return {
            "total_return": round(total * 100, 1),
            "cagr": round(cagr * 100, 1),
            "vol": round(float(vol) * 100, 1),
            "sharpe": round(float(sharpe), 2) if sharpe is not None else None,
            "max_dd": round(maxdd * 100, 1),
        }

    return {
        "available": True,
        "start": dates[0], "end": dates[-1], "months": len(dates),
        "top_n": top_n,
        "avg_holdings": round(float(np.mean(n_hold_log)), 1) if n_hold_log else 0,
        "tx_cost_bps": TX_COST_BPS,
        "hysteresis_z": HYSTERESIS_Z,
        "avg_exposure": round(float(np.mean(exposure_log)), 2) if exposure_log else 1.0,
        "annual_turnover": round(float(np.mean(turnover_log)) * 12 * 100) if turnover_log else 0,
        "value_weight": VALUE_WEIGHT,
        "panic_months": int(sum(panic_log)),
        "dates": dates,
        "strategy": {"curve": [round(v, 4) for v in strat_curve], **stats(strat_curve)},
        "spy": {"curve": [round(v, 4) for v in spy_curve], **stats(spy_curve)},
        "gold": {"curve": [round(v, 4) for v in gold_curve], **stats(gold_curve)},
    }
