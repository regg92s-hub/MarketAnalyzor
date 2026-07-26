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

from . import config


def _genre_lookup(genre_strength):
    """sektor/sjanger -> {strength 0-100, state}.

    v13: Bayesiansk krymping mot nøytral (50) for små sjangre. En 2-medlems
    sjanger (crypto) kan bare gi 0/50/100 — rå bruk gir småutvalgs-forvrengning.
    Krympefaktor n/(n+4): 2 medl. -> 33% av avviket, 10 medl. -> 71%."""
    out = {}
    for g in genre_strength or []:
        s = g.get("strength")
        n = g.get("n") or 1
        raw = s if s is not None else 50
        shrunk = 50 + (raw - 50) * n / (n + 4)
        out[g.get("genre")] = {"strength": round(shrunk, 1),
                               "state": g.get("state")}
    return out


def _macro_state(regime):
    """Makro-regime -> (score 0-100, tilstand)."""
    comp = (regime or {}).get("composite", {})
    score = comp.get("score")
    if score is None:
        return 50, "ukjent"
    if score >= 66:
        return score, "risk-on"
    if score >= 34:
        return score, "nøytral"
    return score, "risk-off"


def build_today(assets, genre_strength, regime, sector_summary,
                user_portfolio=None, roadmaps=None, money_flow=None, sector_flow=None,
                capital_flows=None):
    macro_score, macro_state = _macro_state(regime)
    genre = _genre_lookup(genre_strength)
    leaderboard = []
    for iid, a in assets.items():
        if a.get("missing_data"):
            continue
        score = a.get("northstar_score", 0)
        sec = a.get("sector")
        gi = genre.get(sec, {"strength": 50, "state": "?"})
        gstr = gi["strength"] if gi["strength"] is not None else 50
        # Vekt-av-bevis-kompositt: NORMALISERT VEKTET SUM (ikke multiplikativ —
        # multiplikasjon dobbeltstraffer og kollapser skalaen). Eget oppsett
        # veier tyngst (65%); sjanger (20%) og makro (15%) er kontekst.
        composite = round(0.65 * score + 0.20 * gstr + 0.15 * macro_score, 1)
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
            "from52wh": a.get("pct_from_52wh"),
            "vol_ratio": a.get("vol_ratio"),
            "stretched": a.get("stretched", False),
            "breakout": a.get("breakout", False),
            "genre_state": gi["state"],
            "genre_strength": gstr,
            "no_access": config.no_access(iid),
            "spark": [p[1] for p in (a.get("price_series") or [])[-30:]],
        })
    leaderboard.sort(key=lambda r: -r["composite"])

    # Kjøp-kandidater: ekte lavrisiko-entry + sjanger/makro-medvind.
    # NYTT (volum-evidens): breakout uten volum-bekreftelse (RVOL < 1.0)
    # kvalifiserer ikke — volumløse brudd feiler oftere.
    buys = []
    for r in leaderboard:
        if (r["score"] >= 65 and not r["stretched"]
                and r["stage"] in (1, 2)
                and r["genre_state"] != "Nedadgående"
                and macro_state != "risk-off"):
            vr = r.get("vol_ratio")
            if r["breakout"] and vr is not None and vr < 1.0:
                continue  # volumløst brudd — vent på bekreftelse
            why = []
            if r["breakout"]:
                why.append("breakout" + (" m/volum" if vr and vr >= 1.2 else ""))
            if r["beats_gold"]:
                why.append("slår gull")
            if r["genre_state"] == "I medvind":
                why.append("sjanger-medvind")
            f52 = r.get("from52wh")
            if f52 is not None and f52 >= -5:
                why.append("nær 52u-topp")
            r2 = dict(r); r2["why"] = ", ".join(why) or "konstruktivt oppsett"
            buys.append(r2)
    buys = buys[:8]
    # v13 Weinstein-disiplin: NSBC-signalene er ukentlige. Midtuke er kandidatene
    # FORELØPIGE — de bekreftes først på fredagens close. Flagges i UI og Discord.
    import datetime as _dt
    provisional = _dt.datetime.now().weekday() < 4
    for b in buys:
        b["provisional"] = provisional

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
    # Kapitalstrøm (Armstrong-stil, datapunkt): hvor internasjonal kapital søker seg
    cf = capital_flows or {}
    cap_summary = None
    if cf.get("verdict"):
        cap_summary = {
            "verdict": cf["verdict"], "col": cf.get("col"),
            "destinations": cf.get("destinations", [])[:3],
            "dollar": cf.get("dollar", {}).get("state"),
            "us_concentration": cf.get("us_concentration", {}).get("state"),
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
        "capital": cap_summary,
        "buys": buys,
        "avoids": avoids,
        "leaderboard": leaderboard,
        "n_total": len(leaderboard),
    }
