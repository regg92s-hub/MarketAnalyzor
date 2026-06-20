"""
Analyselag: leadership ranking (vs gull/dollar), sjanger-styrke, bredde,
makro-regime, sykliske par, money flow. Alt momentum-/ROC-basert.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from . import indicators as ind
from .config import (ROC_HORIZONS, BEATS_ROC_HORIZONS, CYCLICAL_IDS, CYCLICAL_PAIRS,
                     ROTATION_MAIN, GENRE_TAILWIND_PCT, GENRE_DOWNTREND_PCT,
                     ASSET_SUBCLASS, BREADTH_MA, PALETTE)


def build_ranking(raw, den_id, den_label, assets_meta):
    """
    Leadership ranking: hvert syklisk instrument vs baseline (gull/dollar).
    'Leder' = positiv ROC (momentum) på 1M eller 3M. tf_over viser hvilke.
    """
    den = raw.get(den_id)
    rows = []
    if den is None:
        return {"den": den_label, "rows": []}
    for iid in CYCLICAL_IDS:
        num = raw.get(iid)
        if num is None:
            continue
        b = ind.beats_baseline(num["close_use"], den["close_use"],
                               BEATS_ROC_HORIZONS, ROC_HORIZONS)
        meta = assets_meta.get(iid, {})
        rows.append({
            "id": iid,
            "label": meta.get("symbol_label", iid),
            "subclass": ASSET_SUBCLASS.get(iid, ""),
            "roc_1m": b["roc"].get("1M"),
            "roc_3m": b["roc"].get("3M"),
            "roc_6m": b["roc"].get("6M"),
            "roc_12m": b["roc"].get("12M"),
            "composite": b["composite"],
            "beats": b["beats"],
            "loses": b["loses"],
            "tf_over": b["tf_over"],
        })
    rows.sort(key=lambda r: (r["composite"] if r["composite"] is not None else -999), reverse=True)
    return {"den": den_label, "rows": rows}


def genre_strength(raw, assets_meta):
    """
    Sjanger-score = % av medlemmene som slår BÅDE gull og dollar (ROC 1M/3M).
    >=70% -> medvind, >=70% taper -> nedadgående, ellers avventende.
    Sjangrer = sektorer (samme som sektorscore).
    """
    gld = raw.get("GLD")
    uup = raw.get("UUP")
    # bygg per-instrument beats-mot-gull og beats-mot-dollar
    gold_beat, dxy_beat, gold_lose, dxy_lose = {}, {}, {}, {}
    for iid, num in raw.items():
        if iid in ("GLD",):
            continue
        if gld is not None:
            bg = ind.beats_baseline(num["close_use"], gld["close_use"], BEATS_ROC_HORIZONS, ROC_HORIZONS)
            gold_beat[iid] = bg["beats"]; gold_lose[iid] = bg["loses"]
        if uup is not None:
            bd = ind.beats_baseline(num["close_use"], uup["close_use"], BEATS_ROC_HORIZONS, ROC_HORIZONS)
            dxy_beat[iid] = bd["beats"]; dxy_lose[iid] = bd["loses"]

    # grupper etter sektor
    members = {}
    for iid, meta in assets_meta.items():
        if iid == "GLD":
            continue
        sec = meta.get("sector", "")
        if not sec:
            continue
        disp = "Råvarer" if sec == "Rawarer" else sec
        members.setdefault(disp, []).append(iid)

    out = []
    for genre, iids in members.items():
        beats = loses = total = 0
        for iid in iids:
            gb, db = gold_beat.get(iid), dxy_beat.get(iid)
            if gb is None and db is None:
                continue
            total += 1
            if gb and db:
                beats += 1
            elif gold_lose.get(iid) and dxy_lose.get(iid):
                loses += 1
        if total == 0:
            out.append({"genre": genre, "strength": 0, "medvind": False,
                        "state": "Ingen data", "n": len(iids),
                        "members": [assets_meta[i].get("symbol_label", i) for i in iids],
                        "member_ids": iids})
            continue
        pct_beat = beats / total * 100
        pct_lose = loses / total * 100
        if pct_beat >= GENRE_TAILWIND_PCT:
            state, medvind = "I medvind", True
        elif pct_lose >= GENRE_DOWNTREND_PCT:
            state, medvind = "Nedadgående", False
        else:
            state, medvind = "Avventende", False
        out.append({
            "genre": genre, "strength": round(pct_beat), "medvind": medvind,
            "state": state, "n": len(iids),
            "members": [assets_meta[i].get("symbol_label", i) for i in iids],
            "member_ids": iids,
        })
    out.sort(key=lambda x: -x["strength"])
    for rank, g in enumerate(out):
        g["rank"] = rank + 1
    return out


def breadth(raw, universe_ids):
    """
    Bredde: % av universet over 50- og 200-dagers MA (daglig).
    Bekrefter om en bevegelse er bred eller smal.
    """
    res = {}
    for ma in BREADTH_MA:
        over = total = 0
        for iid in universe_ids:
            df = raw.get(iid)
            if df is None or len(df) < ma + 5:
                continue
            c = df["close_use"]
            m = c.rolling(ma).mean()
            if pd.isna(m.iloc[-1]):
                continue
            total += 1
            if c.iloc[-1] > m.iloc[-1]:
                over += 1
        res[f"pct_over_{ma}ma"] = round(over / total * 100) if total else None
        res[f"n_{ma}ma"] = total
    return res


def global_breadth(raw, ids):
    """
    Global bredde: % av land/sektor-ETF-er over 200-dagers MA (daglig).
    Kjent regime-filter — bredt over 200d = risk-on, smalt = risk-off.
    Returnerer også per-instrument-status for et heatmap.
    """
    over = total = 0
    members = []
    for iid in ids:
        df = raw.get(iid)
        if df is None or len(df) < 205:
            continue
        c = df["close_use"]
        m200 = c.rolling(200).mean()
        if pd.isna(m200.iloc[-1]):
            continue
        total += 1
        is_over = bool(c.iloc[-1] > m200.iloc[-1])
        if is_over:
            over += 1
        dist = round(float((c.iloc[-1] / m200.iloc[-1] - 1) * 100), 1)
        members.append({"id": iid, "over": is_over, "dist": dist})
    pct = round(over / total * 100) if total else None
    members.sort(key=lambda x: -x["dist"])
    if pct is None:
        state, col = "Ingen data", PALETTE["neutral"]
    elif pct >= 60:
        state, col = "Bred risk-on", PALETTE["up"]
    elif pct >= 40:
        state, col = "Blandet", PALETTE["warn"]
    else:
        state, col = "Smal / risk-off", PALETTE["down"]
    return {"pct_over_200d": pct, "n": total, "over": over,
            "state": state, "col": col, "members": members}


def cyclical_pairs(raw):
    out = []
    for a_id, b_id, label in CYCLICAL_PAIRS:
        a, b = raw.get(a_id), raw.get(b_id)
        if a is None or b is None:
            continue
        rr = ind.relative_roc(a["close_use"], b["close_use"], ROC_HORIZONS)
        out.append({
            "label": label, "a": a_id, "b": b_id,
            "roc_1m": rr["roc"].get("1M"), "roc_3m": rr["roc"].get("3M"),
            "composite": rr["composite"],
        })
    out.sort(key=lambda x: (x["composite"] if x["composite"] is not None else -999), reverse=True)
    return out


def money_flow(raw):
    """Risk-appetitt-signaler med ROC (3M) + 50-dagers MA-status."""
    defs = [
        ("HYG", "TLT", "Kreditt-appetitt (HYG/TLT)", "Høy = risikovillig kapital søker yield"),
        ("COPX", "GLD", "Vekst vs frykt (kobber/gull)", "Høy = vekstforventning over sikkerhet"),
        ("EEM", "ACWI", "EM-ledelse (EM/verden)", "Høy = risk-on, likviditet til periferien"),
    ]
    out = []
    for n_id, d_id, label, note in defs:
        n, d = raw.get(n_id), raw.get(d_id)
        if n is None or d is None:
            continue
        comb = pd.DataFrame({"n": n["close_use"], "d": d["close_use"]}).dropna()
        if len(comb) < 70:
            continue
        ratio = comb["n"] / comb["d"]
        r3 = ind.roc(ratio, 63)
        ma50 = ratio.rolling(50).mean()
        over = bool(ratio.iloc[-1] > ma50.iloc[-1]) if pd.notna(ma50.iloc[-1]) else None
        risk_on = (r3 or 0) > 0 and bool(over)
        from .config import PALETTE
        out.append({
            "label": label, "roc_3m": round(r3, 1) if r3 is not None else None,
            "over_50ma": over,
            "state": "Risk-on" if risk_on else ("Nøytral" if (r3 or 0) > -2 else "Risk-off"),
            "col": PALETTE["up"] if risk_on else (PALETTE["warn"] if (r3 or 0) > -2 else PALETTE["down"]),
            "note": note,
        })
    return out


def rotation(raw, assets_meta):
    """Kapitalrotasjon: hovedinstrumenter vs gull (ROC 1M/3M)."""
    gld = raw.get("GLD")
    beats, loses = [], []
    if gld is None:
        return None
    for iid in ROTATION_MAIN:
        num = raw.get(iid)
        if num is None:
            continue
        b = ind.beats_baseline(num["close_use"], gld["close_use"], BEATS_ROC_HORIZONS, ROC_HORIZONS)
        if b["beats"] is None:
            continue
        sym = assets_meta.get(iid, {}).get("symbol_label", iid)
        entry = {"id": iid, "sym": sym, "tf_over": b["tf_over"]}
        (beats if b["beats"] else loses).append(entry)
    tot = len(beats) + len(loses)
    if tot == 0:
        return None
    from .config import PALETTE
    frac = len(beats) / tot
    if frac == 0:
        col, note = PALETTE["down"], "Alle hovedinstrumenter under gull – kraftig rotasjon mot hard assets."
    elif frac < 0.5:
        col, note = PALETTE["warn"], "Få hovedinstrumenter slår gull – rotasjon mot hard assets pågår."
    else:
        col, note = PALETTE["up"], "Flertallet slår gull – risk-on holder følge."
    return {"label": f"{len(beats)}/{tot} slår gull (ROC 1M eller 3M)",
            "col": col, "note": note, "beats": beats, "loses": loses}


def build_rrg(raw, assets_meta):
    """RRG-punkter (RS-Ratio/RS-Momentum) for RRG_SET vs gull."""
    from .config import RRG_SET
    gld = raw.get("GLD")
    if gld is None:
        return {"baseline": "GLD", "points": []}
    points = []
    for iid in RRG_SET:
        num = raw.get(iid)
        if num is None:
            continue
        pt = ind.rrg_point(num["close_use"], gld["close_use"])
        if pt is None:
            continue
        pt["id"] = iid
        pt["label"] = assets_meta.get(iid, {}).get("symbol_label", iid)
        points.append(pt)
    return {"baseline": "GLD", "points": points}


def build_correlation(raw):
    """Korrelasjonsmatrise for det kuraterte settet."""
    from .config import CORR_SET
    closes = {iid: raw[iid]["close_use"] for iid in CORR_SET if iid in raw}
    return ind.correlation_matrix(closes)


def panic_state(raw):
    """
    Panikk-regime (Daniel & Moskowitz 2016): momentum krasjer i rebound etter
    bear-marked med høy volatilitet. Flagg = SPY 12M-avkastning < 0 OG
    realisert 6M-vol > terskel. Når flagget er på, dempes rotasjons-
    aggressivitet (eksponering caps).
    """
    from .config import (PANIC_RET_LOOKBACK_M, PANIC_VOL_LOOKBACK_M,
                         PANIC_VOL_THRESHOLD, PALETTE)
    spy = raw.get("SPY")
    if spy is None:
        return None
    c = spy["close_use"].dropna()
    m = c.resample("ME").last().dropna()
    if len(m) < PANIC_RET_LOOKBACK_M + 2:
        return None
    ret12 = float(m.iloc[-1] / m.iloc[-1 - PANIC_RET_LOOKBACK_M] - 1)
    daily = c.pct_change().dropna().tail(PANIC_VOL_LOOKBACK_M * 21)
    if len(daily) < 40:
        return None
    vol = float(daily.std() * (252 ** 0.5))
    panic = (ret12 < 0) and (vol > PANIC_VOL_THRESHOLD)
    return {
        "label": (f"PANIKK-REGIME (SPY 12m {ret12*100:+.0f}%, vol {vol*100:.0f}%)" if panic
                  else f"Normalt (SPY 12m {ret12*100:+.0f}%, vol {vol*100:.0f}%)"),
        "col": PALETTE["down"] if panic else PALETTE["up"],
        "note": ("Bear + høy vol: momentum-krasj-fare — eksponering dempes til 50% "
                 "(Daniel & Moskowitz 2016)" if panic
                 else "Ikke panikk-tilstand — full regelstyrt eksponering"),
        "panic": panic, "ret_12m": round(ret12 * 100, 1), "vol_6m": round(vol * 100, 1),
    }
