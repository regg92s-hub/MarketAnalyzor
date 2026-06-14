"""
Paper-trading-ledger: "regelen vs deg".

En hypotetisk portefølje som mekanisk følger rotasjonsregelen (samme utvalg
som backtesten: 3M+6M momentum vs gull + value-tilt + absolutt-momentum-
filter), rebalansert månedlig, verdsatt daglig i NOK. Hvis docs/portfolio.json
er synket fra porteføljesiden, verdsettes også DINE faktiske posisjoner daglig
— så du kan se om du slår ditt eget regelverk eller taper mot det.

State persisteres i docs/paper_ledger.json (lastes fra forrige bygg via
gh-pages, samme mønster som signals.json). Ingen ekte penger, ingen megler —
det tryggeste mulige automatiseringssteget og et kraftig adferdsspeil.
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

from .config import PAPER_TOP_N, PAPER_START_NOK, VALUE_WEIGHT, VALUE_LOOKBACK_M


def _log(m):
    print(m, flush=True)


def _zscore_dict(d: dict) -> dict:
    vals = np.array(list(d.values()), dtype=float)
    if len(vals) < 2 or np.std(vals) == 0:
        return {k: 0.0 for k in d}
    mu, sd = float(np.mean(vals)), float(np.std(vals))
    return {k: (v - mu) / sd for k, v in d.items()}


def rule_selection(raw: dict, cyclical_ids: list, top_n: int = PAPER_TOP_N) -> list:
    """
    Dagens regel-utvalg (samme logikk som backtesten, på live data):
    momentum (3M+6M ROC vs gull) + value-tilt (negativ 5-års relativ avkastning,
    Asness-kombinasjon) + absolutt 12M-momentumfilter. Returnerer topp-N ids.
    """
    gld = raw.get("GLD")
    if gld is None:
        return []
    mom, val = {}, {}
    for iid in cyclical_ids:
        df = raw.get(iid)
        if df is None:
            continue
        comb = pd.DataFrame({"n": df["close_use"], "g": gld["close_use"]}).dropna()
        if len(comb) < 200:
            continue
        ratio = (comb["n"] / comb["g"]).resample("ME").last().dropna()
        if len(ratio) < 7:
            continue
        roc3 = ratio.iloc[-1] / ratio.iloc[-4] - 1 if len(ratio) >= 4 else None
        roc6 = ratio.iloc[-1] / ratio.iloc[-7] - 1 if len(ratio) >= 7 else None
        if roc3 is None or roc6 is None:
            continue
        # Absolutt-momentumfilter (12M abs avkastning > 0)
        absr = comb["n"].resample("ME").last().dropna()
        if len(absr) < 13 or absr.iloc[-1] / absr.iloc[-13] - 1 <= 0:
            continue
        m = (roc3 + roc6) / 2
        if m <= 0:
            continue
        mom[iid] = m
        # Value-proxy: negativ langtids relativ avkastning (reversal)
        lb = min(VALUE_LOOKBACK_M, len(ratio) - 1)
        if lb >= 24:
            val[iid] = -(ratio.iloc[-1] / ratio.iloc[-1 - lb] - 1)
        else:
            val[iid] = 0.0
    if not mom:
        return []
    mz, vz = _zscore_dict(mom), _zscore_dict(val)
    combined = {k: mz[k] + VALUE_WEIGHT * vz.get(k, 0.0) for k in mom}
    ranked = sorted(combined, key=lambda k: -combined[k])
    return ranked[:top_n]


def _price(raw: dict, iid: str) -> float | None:
    df = raw.get(iid)
    if df is None or df.empty:
        return None
    return float(df["close_use"].iloc[-1])


def update_paper_ledger(prev: dict | None, raw: dict, cyclical_ids: list,
                        usdnok: float | None, today: str) -> dict:
    """
    Oppdater ledgeren: månedlig rebalansering (første bygg i ny måned),
    daglig mark-to-market i NOK. Likevekt blant valgte; cash om <N valgt.
    """
    fx = usdnok or 1.0
    led = prev if isinstance(prev, dict) and prev.get("positions") is not None else {
        "start_date": today, "start_nok": PAPER_START_NOK,
        "cash_nok": PAPER_START_NOK, "positions": {},
        "last_rebal_month": "", "curve": [], "actual_curve": [], "events": [],
    }
    if led["curve"] and led["curve"][-1][0] == today:
        return led  # allerede oppdatert i dag

    month = today[:7]
    if month != led.get("last_rebal_month"):
        # Selg alt til dagens kurs, kjøp regel-utvalget likevektet
        total = led["cash_nok"]
        for iid, units in led["positions"].items():
            p = _price(raw, iid)
            if p:
                total += units * p * fx
        picks = rule_selection(raw, cyclical_ids)
        led["positions"] = {}
        if picks:
            alloc = total / len(picks)
            for iid in picks:
                p = _price(raw, iid)
                if p and p > 0:
                    led["positions"][iid] = alloc / (p * fx)
            led["cash_nok"] = total - sum(
                led["positions"][i] * _price(raw, i) * fx for i in led["positions"])
        else:
            led["cash_nok"] = total
        led["last_rebal_month"] = month
        led["events"] = (led.get("events") or [])[-23:] + [
            {"date": today, "picks": picks}]
        _log(f"  paper rebalansert ({month}): {picks or 'kun cash'}")

    # Daglig mark-to-market
    value = led["cash_nok"]
    for iid, units in led["positions"].items():
        p = _price(raw, iid)
        if p:
            value += units * p * fx
    led["curve"] = (led.get("curve") or [])[-730:] + [(today, round(value, 2))]
    return led


def value_user_portfolio(user_pf: dict | None, raw: dict, usdnok: float | None,
                         assets: dict) -> dict | None:
    """
    Verdsett brukerens synkede posisjoner (docs/portfolio.json) i NOK i dag,
    og lag handlings-verdikt per posisjon for dashboard + Discord.
    """
    if not user_pf or not isinstance(user_pf.get("positions"), dict):
        return None
    fx = usdnok or 1.0
    total, rows = 0.0, []
    for iid, p in user_pf["positions"].items():
        cost = float(p.get("cost") or 0)
        if cost <= 0:
            continue
        cur = _price(raw, iid)
        ep, efx = p.get("entryPrice"), p.get("entryFx")
        v = cost
        if cur and ep:
            v = cost * (cur / float(ep))
        if efx:
            v = v * (fx / float(efx))
        total += v
        a = assets.get(iid, {})
        verdict = "HOLD"
        why = []
        sc = a.get("northstar_score")
        rsi = a.get("rsi_q")
        gb = (a.get("gold_beat") or {})
        if sc is not None and sc < 35:
            verdict = "SKALER AV"; why.append(f"score {sc}")
        elif rsi is not None and rsi >= 70:
            verdict = "VURDER SKALER AV"; why.append(f"RSI {round(rsi)}")
        elif gb.get("beats") is False:
            verdict = "HOLD (svak)"; why.append("taper mot gull")
        rows.append({"id": iid, "sym": a.get("symbol_label", iid),
                     "value_nok": round(v, 0), "pnl_pct": round((v / cost - 1) * 100, 1),
                     "verdict": verdict, "why": ", ".join(why)})
    if not rows:
        return None
    rows.sort(key=lambda r: -r["value_nok"])
    return {"total_nok": round(total, 0), "rows": rows,
            "updated": user_pf.get("updated", "")}
