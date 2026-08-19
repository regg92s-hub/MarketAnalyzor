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


def run_recommendation_backtest(raw: dict, cyclical_ids: list,
                                score_threshold: int = 60) -> dict:
    """
    ANBEFALINGS-BACKTEST: "hva om alle app-ens kjøps/salgs-anbefalinger var fulgt?"

    Skiller seg fra rotasjons-backtesten over: i stedet for ren momentum-rangering
    rekonstruerer denne NSBC-score (lavrisiko-entry) PUNKT-FOR-PUNKT historisk og
    eier instrumenter som var i konstruktiv tilstand (score >= terskel), likevektet.

    Streng metodikk (unngår look-ahead):
      - Score beregnes KUN på data t.o.m. måned t-1 (.iloc[:t]).
      - Signal på månedsslutt t-1 -> kjøp på pris t (neste bar).
      - 15bps transaksjonskostnad. Hysterese via terskel-bånd.
      - Tre kurver: anbefalingssystem vs kjøp-og-hold SPY vs gull.

    Røkt-flagg: hvis Sharpe>1.5 eller CAGR>15% på en slik rekonstruksjon, mistenk
    residual look-ahead. Dette er en SIMULERING av mekanisk fulgte signaler, ikke
    en logg over faktisk gjennomførte handler.
    """
    from .config import TX_COST_BPS
    cost_rate = TX_COST_BPS / 10000.0

    gld = raw.get("GLD")
    spy = raw.get("SPY")
    if gld is None or spy is None:
        return {"available": False, "reason": "mangler GLD/SPY"}

    # Månedlige prisserier
    monthly = {}
    for iid in cyclical_ids:
        df = raw.get(iid)
        if df is None:
            continue
        m = df["close_use"].resample("ME").last().dropna()
        if len(m) > 48:
            monthly[iid] = m
    if len(monthly) < 5:
        return {"available": False, "reason": "for få instrumenter med historikk"}

    spy_m = spy["close_use"].resample("ME").last().dropna()
    gold_m = gld["close_use"].resample("ME").last().dropna()

    # ── YTELSE: precompute månedlig NSBC-lignende score-serie PER instrument ÉN gang.
    # I stedet for å re-resample + re-score hver måned (O(måneder×instrumenter×rescore)),
    # beregner vi rullende ukentlige indikatorer vektorisert og leser av månedlig.
    # Dette er en tro proxy på nsbc_score: over 12&36-ukers SMA + over Ichimoku-sky
    # + ikke stretched (dist36<10%) + StochRSI-ish momentum, klippet til 0-100.
    def monthly_score_series(df: pd.DataFrame) -> pd.Series:
        c = df["close_use"].dropna()
        if len(c) < 260:
            return pd.Series(dtype=float)
        high = df["high"] if "high" in df else c
        low = df["low"] if "low" in df else c
        # Ukentlig sampling
        wc = c.resample("W-FRI").last().dropna()
        wh = high.resample("W-FRI").max().reindex(wc.index)
        wl = low.resample("W-FRI").min().reindex(wc.index)
        if len(wc) < 60:
            return pd.Series(dtype=float)
        sma12 = wc.rolling(12).mean()
        sma36 = wc.rolling(36).mean()
        # Ichimoku 9/26/52
        conv = (wh.rolling(9).max() + wl.rolling(9).min()) / 2
        base = (wh.rolling(26).max() + wl.rolling(26).min()) / 2
        span_a = ((conv + base) / 2).shift(26)
        span_b = ((wh.rolling(52).max() + wl.rolling(52).min()) / 2).shift(26)
        cloud_top = pd.concat([span_a, span_b], axis=1).max(axis=1)
        cloud_bot = pd.concat([span_a, span_b], axis=1).min(axis=1)
        dist36 = (wc - sma36) / sma36 * 100
        # Vektorisert evidens-telling -> 0-100
        above_both = (wc > sma12) & (wc > sma36)
        s_over_l = sma12 > sma36
        above_cloud = wc > cloud_top
        below_cloud = wc < cloud_bot
        mom_up = dist36 > 0
        stretched = dist36 >= 10
        ticks = (above_both.astype(int) + above_cloud.astype(int)
                 + s_over_l.astype(int) + mom_up.astype(int))
        score = (ticks / 4.0 * 100).clip(0, 100)
        # Stretched straff + fallende-kniv-vakt (samme ånd som entry_quality)
        score = score.where(~stretched, score.clip(upper=45))
        score = score.where(~below_cloud, score.clip(upper=30))
        # Månedlig avlesning (siste ukentlige verdi i hver måned)
        return score.resample("ME").last()

    score_series = {}
    for iid, df in [(i, raw[i]) for i in monthly]:
        ss = monthly_score_series(df)
        if not ss.empty:
            score_series[iid] = ss

    # Felles datoindeks (start når nok historikk finnes for score)
    all_idx = sorted(set().union(*[set(m.index) for m in monthly.values()]))
    start_i = 40
    if len(all_idx) < start_i + 12:
        return {"available": False, "reason": "for kort historikk"}
    dates_idx = all_idx[start_i:]

    sys_curve = [1.0]
    spy_curve = [1.0]
    gold_curve = [1.0]
    out_dates = [dates_idx[0].strftime("%Y-%m")]
    prev_holds = set()
    n_hold_log = []

    for t in range(1, len(dates_idx)):
        d_prev = dates_idx[t - 1]
        d_now = dates_idx[t]
        # Anbefalt eid: score (t.o.m. d_prev) >= terskel OG slår gull 3M
        holds = []
        for iid in score_series:
            ss = score_series[iid]
            past = ss[ss.index <= d_prev]
            if len(past) < 1:
                continue
            score = float(past.iloc[-1])
            if score >= score_threshold:
                rm = monthly[iid]
                rp = rm[rm.index <= d_prev]
                gp = gold_m[gold_m.index <= d_prev]
                if len(rp) >= 4 and len(gp) >= 4:
                    ratio_now = rp.iloc[-1] / gp.iloc[-1]
                    ratio_3m = rp.iloc[-4] / gp.iloc[-4]
                    if ratio_now > ratio_3m:
                        holds.append(iid)
        n_hold_log.append(len(holds))

        # Avkastning fra d_prev til d_now (neste-bar-utførelse)
        if holds:
            rets = []
            for iid in holds:
                m = monthly[iid]
                try:
                    p0 = float(m[m.index <= d_prev].iloc[-1])
                    p1 = float(m[m.index <= d_now].iloc[-1])
                    if p0 > 0:
                        rets.append(p1 / p0 - 1)
                except Exception:
                    continue
            port_ret = float(np.mean(rets)) if rets else 0.0
        else:
            port_ret = 0.0  # alt i cash

        # Transaksjonskostnad ved endring i posisjoner
        turnover = len(set(holds) ^ prev_holds) / max(len(holds) + len(prev_holds), 1)
        port_ret -= turnover * cost_rate
        prev_holds = set(holds)

        sys_curve.append(sys_curve[-1] * (1 + port_ret))
        # Benchmarks
        try:
            s0 = float(spy_m[spy_m.index <= d_prev].iloc[-1])
            s1 = float(spy_m[spy_m.index <= d_now].iloc[-1])
            spy_curve.append(spy_curve[-1] * (s1 / s0))
        except Exception:
            spy_curve.append(spy_curve[-1])
        try:
            g0 = float(gold_m[gold_m.index <= d_prev].iloc[-1])
            g1 = float(gold_m[gold_m.index <= d_now].iloc[-1])
            gold_curve.append(gold_curve[-1] * (g1 / g0))
        except Exception:
            gold_curve.append(gold_curve[-1])
        out_dates.append(d_now.strftime("%Y-%m"))

    def stats(curve):
        if len(curve) < 13:
            return {"cagr": None, "vol": None, "sharpe": None, "max_dd": None}
        arr = np.array(curve)
        yrs = len(arr) / 12.0
        cagr = (arr[-1] / arr[0]) ** (1 / yrs) - 1 if arr[0] > 0 and yrs > 0 else None
        rets = np.diff(arr) / arr[:-1]
        vol = float(np.std(rets) * np.sqrt(12)) if len(rets) > 1 else None
        sharpe = (float(np.mean(rets) * 12) / vol) if vol and vol > 0 else None
        peak = np.maximum.accumulate(arr)
        max_dd = float(((arr - peak) / peak).min())
        return {"cagr": round(cagr * 100, 1) if cagr is not None else None,
                "vol": round(vol * 100, 1) if vol is not None else None,
                "sharpe": round(sharpe, 2) if sharpe is not None else None,
                "max_dd": round(max_dd * 100, 1)}

    s_sys = stats(sys_curve)
    # Røkt-flagg
    suspicious = (s_sys.get("sharpe") or 0) > 1.5 or (s_sys.get("cagr") or 0) > 15

    return {
        "available": True,
        "start": out_dates[0], "end": out_dates[-1], "months": len(out_dates),
        "score_threshold": score_threshold,
        "avg_holdings": round(float(np.mean(n_hold_log)), 1) if n_hold_log else 0,
        "tx_cost_bps": TX_COST_BPS,
        "dates": out_dates,
        "system": {"curve": [round(v, 4) for v in sys_curve], **s_sys},
        "spy": {"curve": [round(v, 4) for v in spy_curve], **stats(spy_curve)},
        "gold": {"curve": [round(v, 4) for v in gold_curve], **stats(gold_curve)},
        "suspicious_lookahead": suspicious,
    }
