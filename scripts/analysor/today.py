"""
"I dag"-motor: vekt-av-bevis-rangering på tvers av instrument + sjanger + makro.

Northstar-filosofi: et instrument flyter til toppen bare når DETS eget oppsett
(NSBC-score), DETS sjanger (medvind), OG makrobildet alle peker samme vei.
En sterk graf i en svak sjanger eller i risk-off-makro rabatteres deretter.

Produserer:
  - leaderboard: alle instrumenter med felter for sorterbar tabell
  - buys: kjøp-kandidater (ekte lavrisiko-entry + medvind)
  - avoids: skaler av / unngå (stretched FOMO eller Stage 4 nedtrend)
  - verdict: én linje øverst (regime + hva som gjelder i dag)
"""
from __future__ import annotations


def _genre_lookup(genre_strength):
    """sektor/sjanger -> medvind-multiplikator (0.7-1.15)."""
    out = {}
    for g in genre_strength or []:
        # strength er % som slår gull; medvind hvis >= terskel
        s = g.get("strength", 50)
        if g.get("medvind"):
            mult = 1.0 + min((s - 70) / 100.0, 0.15)   # opp til +15%
        elif g.get("state") == "Nedadgående":
            mult = 0.7
        else:
            mult = 0.88
        out[g.get("genre")] = {"mult": mult, "state": g.get("state"), "strength": s}
    return out


def _macro_mult(regime):
    """Makro-regime -> global multiplikator. Risk-on løfter sykliske, risk-off demper."""
    comp = (regime or {}).get("composite", {})
    score = comp.get("score")
    if score is None:
        return 1.0, "ukjent"
    if score >= 66:
        return 1.10, "risk-on"
    if score >= 34:
        return 1.0, "nøytral"
    return 0.82, "risk-off"


def build_today(assets, genre_strength, regime, sector_summary,
                user_portfolio=None, roadmaps=None, money_flow=None, sector_flow=None):
    macro_mult, macro_state = _macro_mult(regime)
    genre = _genre_lookup(genre_strength)
    # sektor (norsk visningsnavn) -> sjanger-info via assets[].sector
    leaderboard = []
    for iid, a in assets.items():
        if a.get("missing_data"):
            continue
        score = a.get("northstar_score", 0)
        sec = a.get("sector")
        gi = genre.get(sec, {"mult": 0.9, "state": "?", "strength": None})
        gmult = gi["mult"]
        # Vekt-av-bevis-kompositt: score × sjanger × makro
        composite = round(score * gmult * macro_mult, 1)
        gb = a.get("gold_beat") or {}
        leaderboard.append({
            "id": iid,
            "name": a.get("display_name", iid),
            "sym": a.get("symbol_label", iid),
            "sector": sec,
            "score": score,
            "composite": composite,
            "stage": a.get("stage"),
            "stage_label": a.get("stage_label", ""),
            "lt": a.get("lt_state"), "kt": a.get("st_state"),
            "beats_gold": gb.get("beats"),
            "mansfield": gb.get("mansfield"),
            "roc3m": gb.get("roc3m"),
            "dist36": a.get("dist36_w"),
            "stretched": a.get("stretched", False),
            "breakout": a.get("breakout", False),
            "genre_state": gi["state"],
            "genre_mult": round(gmult, 2),
            "spark": [p[1] for p in (a.get("price_series") or [])[-30:]],
        })
    # Standard sortering: kompositt synkende
    leaderboard.sort(key=lambda r: -r["composite"])

    # Kjøp-kandidater: ekte lavrisiko-entry (score>=70, ikke stretched, breakout
    # eller konstruktiv) OG sjanger ikke nedadgående OG makro ikke risk-off
    buys = []
    for r in leaderboard:
        if (r["score"] >= 65 and not r["stretched"]
                and r["stage"] in (1, 2)
                and r["genre_state"] != "Nedadgående"
                and macro_state != "risk-off"):
            why = []
            if r["breakout"]:
                why.append("breakout")
            if r["beats_gold"]:
                why.append("slår gull")
            if r["genre_state"] == "I medvind":
                why.append("sjanger-medvind")
            r2 = dict(r); r2["why"] = ", ".join(why) or "konstruktivt oppsett"
            buys.append(r2)
    buys = buys[:8]

    # Skaler av / unngå: stretched FOMO eller Stage 4 nedtrend
    avoids = []
    for r in leaderboard:
        if r["stretched"] and r["stage"] == 2:
            r2 = dict(r); r2["reason"] = f"Strukket {r['dist36']:+.0f}% fra 36-MA (FOMO)" if r["dist36"] is not None else "Strukket (FOMO)"
            avoids.append(r2)
        elif r["stage"] == 4:
            r2 = dict(r); r2["reason"] = "Nedtrend (Stage 4) — unngå nye kjøp"
            avoids.append(r2)
    # sorter: stretched først (eier-relevans), så nedtrender
    avoids.sort(key=lambda r: (r["stage"] != 2, -(r.get("dist36") or -999)))
    avoids = avoids[:8]

    # Pengestrøm-sammendrag for kommando-båndet
    mf = money_flow or {}
    sf = sector_flow or {}
    flows = sf.get("flows", [])
    inflow = [f for f in flows if f.get("dir") == "Innstrømning"][:3]
    outflow = [f for f in flows if f.get("dir") == "Utstrømning"][-3:]
    flow_summary = {
        "state": mf.get("state"), "col": mf.get("col"), "note": mf.get("note"),
        "inflow": [{"sector": f["display"], "roc_3m": f["roc_3m"], "accel": f.get("accel")} for f in inflow],
        "outflow": [{"sector": f["display"], "roc_3m": f["roc_3m"]} for f in outflow],
    }

    # Verdikt-linje (nå med pengestrøm)
    n_buys = len(buys)
    top_sym = buys[0]["sym"] if buys else None
    flow_txt = ""
    if mf.get("state") and mf["state"] != "Ingen data":
        flow_txt = f" Pengestrøm: {mf['state'].lower()}."
    if macro_state == "risk-off":
        verdict = (f"Makro risk-off — vær defensiv.{flow_txt} {n_buys} kvalifiserte kjøp-kandidater "
                   "tross motvind. Vurder gull/kontanter og lav beta.")
    elif n_buys == 0:
        verdict = (f"Ingen instrumenter i ekte lavrisiko-entry akkurat nå.{flow_txt} "
                   "Tålmodighet er en posisjon — vent på breakout fra base.")
    else:
        lead = f"Ledende: {top_sym}." if top_sym else ""
        verdict = (f"Makro {macro_state}.{flow_txt} {n_buys} kjøp-kandidater i lavrisiko-entry med "
                   f"sjanger-/makro-medvind. {lead}")

    return {
        "verdict": verdict,
        "macro_state": macro_state,
        "macro_score": (regime or {}).get("composite", {}).get("score"),
        "flow": flow_summary,
        "buys": buys,
        "avoids": avoids,
        "leaderboard": leaderboard,
        "n_total": len(leaderboard),
    }
