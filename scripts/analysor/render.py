"""
HTML-render for Trend-oversikt og Market Daily Report.
Bruker Lightweight Charts (interaktivt) i stedet for matplotlib-PNG.
Colorblind-trygg: blå=opp, vermillion=ned, oransje=avvent; alltid ikon+tekst.
"""
from __future__ import annotations
import html
import json
from .config import PALETTE, tv_symbol
from . import layout
from .scoring import score_label


def _tv(sym, den=None):
    s = tv_symbol(sym) + (f"/{tv_symbol(den)}" if den else "")
    return f'https://www.tradingview.com/chart/?symbol={html.escape(s)}'


def _arrow(beats):
    """Ikon + tekst, aldri farge alene (colorblind-trygt)."""
    if beats is True:
        return f'<span class="up">▲ Leder</span>'
    if beats is False:
        return f'<span class="down">▼ Taper</span>'
    return '<span class="muted">— n/a</span>'


def _roc_cell(v):
    if v is None:
        return '<td class="muted">–</td>'
    cls = "up" if v > 0 else "down"
    sign = "+" if v >= 0 else ""
    return f'<td class="{cls}" style="text-align:right">{sign}{v:.1f}%</td>'


# ── Trend-oversikt ────────────────────────────────────────────────
def render_trend(data) -> str:
    P = layout.head("Trend-oversikt", 0)
    out = [P, '<h1>📈 Trend-oversikt</h1>',
           '<p class="sub">All analyse er relativ til gull (XAU) som baseline. '
           'Relativ styrke måles med <strong>ROC/momentum</strong> på ratioen, ikke MA-kryssing — '
           'det krever ikke lang historikk og snur raskere.</p>']

    # 🎯 DAGENS BESLUTNINGSBILDE — alt du trenger på én skjerm
    out.append(_decision_dashboard(data))

    # 🤖 AI-morgenbrief (valgfri, grunnet i signalene)
    brief = data.get("ai_brief")
    if brief and brief.get("text"):
        out.append('<section class="section">'
                   '<h2>🤖 Morgenbrief</h2>'
                   f'<p style="font-size:14px;line-height:1.6">{html.escape(brief["text"])}</p>'
                   f'<p class="sub" style="margin-top:6px">Generert av {html.escape(brief.get("model","AI"))} '
                   'fra dagens beregnede signaler. Kan inneholde feil — ikke finansrådgivning.</p>'
                   '</section>')

    # 🔔 Hva endret seg siden forrige bygg (diff av signaler)
    changes = data.get("changes") or []
    if changes:
        out.append('<section class="section" style="border-color:var(--accent)">'
                   '<h2>🔔 Endringer siden forrige bygg</h2>'
                   '<p class="sub">Signal-flips oppdaget av generatoren — det eneste du '
                   'trenger å vurdere i dag. Sendes også til Discord hvis webhook er satt.</p>')
        for c in changes:
            cls = "up" if c.startswith("▲") else ("down" if c.startswith("▼") else "warn")
            out.append(f'<div class="{cls}" style="padding:4px 0;font-weight:600;font-size:14px">{html.escape(c)}</div>')
        out.append('</section>')

    # Regime-stripe
    reg = data.get("regime", {})
    out.append('<section class="section"><h2>Makro-regime</h2>'
               '<p class="sub">NFTRH-kontekst: renteregime, likviditet (net + global), realrente, '
               'kredittspreader, finansielle forhold og geopolitikk. '
               'Regime-score = andel risk-on-faktorer.</p>')
    if not reg:
        out.append('<div class="sc" style="border-color:#E69F0055">'
                   '<div class="sc-name warn">⚠ Makro-regime mangler data</div>'
                   '<div class="sc-label muted">Krever <strong>FRED_API_KEY</strong> som repo-secret '
                   '(gratis nøkkel fra fredaccount.stlouisfed.org/apikeys). '
                   'Legg den til i Settings → Secrets → Actions og kjør workflowen på nytt.</div></div>')
    else:
        out.append('<div class="sector-grid">')
        comp = reg.get("composite")
        if comp:
            out.append(_regime_card("Samlet regime", comp.get("label"), comp.get("col"), comp.get("state", "")))
        for key, title in [("yield_curve", "Yield-kurve 2s10s"), ("term_spread_10y3m", "10y-3m spread"),
                           ("net_liquidity", "Net liquidity (WALCL−TGA−RRP)"),
                           ("global_liquidity", "G3-likviditet (Fed+ECB+BoJ)"),
                           ("real_rate", "Realrente 10y (TIPS)"), ("breakeven", "Inflasjonsforv. 10y"),
                           ("fed_liquidity", "Fed-likviditet"), ("credit_spread", "Kredittspread"),
                           ("nfci", "NFCI (Chicago Fed)"), ("panic", "Momentum-regime"),
                           ("gpr", "Geopolitisk risiko (GPR)")]:
            r = reg.get(key)
            if r:
                out.append(_regime_card(title, r.get("label"), r.get("col"), r.get("note", "")))
        out.append('</div>')
    out.append('</section>')

    # Markedsbredde (flyttet opp – overordnet markedstilstand først)
    br = data.get("breadth", {})
    if br:
        out.append('<section class="section"><h2>📐 Markedsbredde</h2>'
                   '<p class="sub">Andel av universet over 50- og 200-dagers MA. '
                   'Bred deltakelse bekrefter trend; smal bredde varsler svekkelse.</p>'
                   '<div class="sector-grid">')
        for ma in (50, 200):
            v = br.get(f"pct_over_{ma}ma")
            n = br.get(f"n_{ma}ma", 0)
            col = PALETTE["up"] if (v or 0) >= 50 else PALETTE["down"]
            icon = "▲" if (v or 0) >= 50 else "▼"
            out.append(f'<div class="sc"><div class="sc-name">Over {ma}-dagers MA</div>'
                       f'<div class="sc-score" style="color:{col}">{icon} {v if v is not None else "–"}%</div>'
                       f'<div class="sc-label muted">{n} instrumenter</div></div>')
        out.append('</div></section>')

    # Money flow (flyttet opp)
    mf = data.get("money_flow", [])
    if mf:
        out.append('<section class="section"><h2>💧 Money flow &amp; likviditet</h2>'
                   '<p class="sub">Risikoappetitt og vekstforventning. 3M = ROC siste kvartal; '
                   'Over 50MA = ratio over 50-dagers snitt. Risk-on krever begge positive.</p>'
                   '<div class="sector-grid">')
        for f in mf:
            o = f.get("over_50ma")
            ostr = "▲ over 50MA" if o else ("▼ under 50MA" if o is False else "50MA: n/a")
            r3 = f.get("roc_3m")
            r3s = f"{r3:+.1f}% 3M" if r3 is not None else "n/a"
            out.append(f'<div class="sc" style="border-color:{f["col"]}55">'
                       f'<div class="sc-name">{html.escape(f["label"])}</div>'
                       f'<div style="font-size:15px;font-weight:700;color:{f["col"]}">{html.escape(f["state"])} ({r3s})</div>'
                       f'<div class="sc-label" style="color:{f["col"]}">{ostr}</div>'
                       f'<div class="sc-label muted">{html.escape(f["note"])}</div></div>')
        out.append('</div></section>')

    # Kapitalrotasjon
    rot = data.get("rotation")
    if rot:
        out.append('<section class="section"><h2>Kapitalrotasjon — hovedinstrumenter vs gull</h2>'
                   f'<p class="sub">{html.escape(rot["note"])} '
                   'Slår gull = positiv ROC på 1M eller 3M. Klikk for ratioen i TradingView.</p>')
        out.append(f'<p style="font-size:15px;font-weight:700;color:{rot["col"]}">{html.escape(rot["label"])}</p>')
        out.append('<div style="margin:6px 0">')
        for grp, beat in [("beats", True), ("loses", False)]:
            items = rot.get(grp, [])
            lab = "Slår gull" if beat else "Taper mot gull"
            icon = "▲" if beat else "▼"
            cls = "up" if beat else "down"
            chips = []
            for it in items:
                tf = "+".join(it.get("tf_over", [])) or ("" if beat else "—")
                chips.append(f'<a class="chip" href="{_tv(it["sym"],"GLD")}" target="_blank" rel="noopener">'
                             f'{html.escape(it["sym"])}<span class="chip-tf">{tf}</span> 📊</a>')
            out.append(f'<div style="margin:6px 0"><span class="{cls}" style="font-weight:600;font-size:13px">'
                       f'{icon} {lab}:</span> {" ".join(chips) or "<span class=muted>ingen</span>"}</div>')
        out.append('</div></section>')

    # Leadership ranking (vs gull + vs dollar)
    out.append('<section class="section"><h2>🏆 Leadership ranking (relativ styrke)</h2>'
               '<p class="sub">Sykliske instrumenter rangert etter vektet ROC mot gull og dollar. '
               '<strong>Leder %</strong> = hvor mye ratioen har steget (3M ROC) — altså hvor kraftig '
               'det slår, ikke bare at det slår.</p>'
               '<div class="grid grid2">')
    out.append(_ranking_table(data.get("ranking_gold", {}), "🥇 vs Gull (GLD)", "GLD"))
    out.append(_ranking_table(data.get("ranking_dxy", {}), "💵 vs Dollar (UUP)", "UUP"))
    out.append('</div></section>')

    # RRG-scatter (leadership som rotasjonsgraf)
    out.append(_rrg_section(data.get("rrg", {})))

    # Korrelasjonsmatrise
    out.append(_corr_section(data.get("correlation", {})))

    # Sykliske par
    cp = data.get("cyclical_pairs", [])
    if cp:
        out.append('<section class="section"><h2>⚖️ Sykliske par (intern rotasjon)</h2>'
                   '<p class="sub">Instrument vs instrument — hvem leder innad. Composite = vektet ROC.</p>'
                   '<table><thead><tr><th>Par</th><th style="text-align:right">1M</th>'
                   '<th style="text-align:right">3M</th><th>Leder</th></tr></thead><tbody>')
        for p in cp:
            comp = p.get("composite") or 0
            leader = p["a"] if comp > 0 else p["b"]
            lcls = "up" if comp > 0 else "down"
            out.append(f'<tr><td><strong>{html.escape(p["label"])}</strong> '
                       f'<span class="muted">{html.escape(p["a"])}/{html.escape(p["b"])}</span></td>'
                       f'{_roc_cell(p.get("roc_1m"))}{_roc_cell(p.get("roc_3m"))}'
                       f'<td class="{lcls}">{html.escape(leader)}</td></tr>')
        out.append('</tbody></table></section>')

    out.append(layout.foot())
    return "".join(out)


def _decision_dashboard(data) -> str:
    """🎯 Dagens beslutningsbilde: regime + tidslinje + endringer + dine posisjoner
    + paper-vs-deg + benchmark-snapshot. Alt på én skjerm, øverst."""
    reg = data.get("regime", {})
    comp = reg.get("composite", {})
    panic = reg.get("panic", {})
    changes = data.get("changes") or []
    uv = data.get("user_portfolio")
    paper = data.get("paper", {})
    bench = data.get("benchmarks", {})

    parts = ['<section class="section" style="border:2px solid var(--accent)">'
             '<h2>🎯 Dagens beslutningsbilde</h2>']

    # Rad 1: regime-status + momentum-regime + endringsteller
    score = comp.get("score")
    scol = comp.get("col", PALETTE["muted"])
    sstate = comp.get("state", "ukjent")
    n_chg = len(changes)
    chg_col = PALETTE["warn"] if n_chg else PALETTE["good"]
    pflag = panic.get("panic")
    pstr = ("⚠ PANIKK" if pflag else "Normalt") if panic else "n/a"
    pcol = PALETTE["down"] if pflag else PALETTE["up"]
    parts.append('<div class="kpi">'
                 f'<div class="k"><div class="lbl">Makro-regime</div>'
                 f'<div class="val" style="color:{scol}">{html.escape(sstate)}</div>'
                 f'<div class="sc-label muted">{score if score is not None else "–"}/100</div></div>'
                 f'<div class="k"><div class="lbl">Momentum-regime</div>'
                 f'<div class="val" style="color:{pcol};font-size:16px">{pstr}</div>'
                 f'<div class="sc-label muted">D&amp;M krasj-vakt</div></div>'
                 f'<div class="k"><div class="lbl">Endringer i dag</div>'
                 f'<div class="val" style="color:{chg_col}">{n_chg}</div>'
                 f'<div class="sc-label muted">signal-flips</div></div>')
    # Benchmark-snapshot
    if bench:
        kpi_no = bench.get("kpi_no_yoy")
        cpi_us = bench.get("cpi_us_yoy")
        nowa = bench.get("nowa")
        ux = bench.get("usdnok")
        fx = ux[-1][1] if ux else None
        if kpi_no is not None:
            parts.append(f'<div class="k"><div class="lbl">Norsk KPI (12m)</div>'
                         f'<div class="val">{kpi_no:.1f}%</div>'
                         f'<div class="sc-label muted">realavk.-hinder</div></div>')
        if cpi_us is not None:
            parts.append(f'<div class="k"><div class="lbl">US CPI (12m)</div>'
                         f'<div class="val">{cpi_us:.1f}%</div></div>')
        if fx is not None:
            parts.append(f'<div class="k"><div class="lbl">USDNOK</div>'
                         f'<div class="val">{fx:.2f}</div></div>')
        if nowa is not None:
            parts.append(f'<div class="k"><div class="lbl">NOWA (risikofri)</div>'
                         f'<div class="val">{nowa:.2f}%</div></div>')
    parts.append('</div>')

    # Regime-tidslinje (stripe over tid)
    parts.append(_regime_timeline(data.get("regime_history", {})))

    # Rad 2: dine posisjoner som krever handling
    if uv and uv.get("rows"):
        actions = [r for r in uv["rows"] if r["verdict"] in ("SKALER AV", "VURDER SKALER AV")]
        parts.append('<h3 style="margin-top:14px">Dine posisjoner</h3>')
        if actions:
            parts.append('<p class="sub">Krever vurdering i dag:</p>')
            for r in actions:
                col = PALETTE["down"] if r["verdict"] == "SKALER AV" else PALETTE["warn"]
                parts.append(f'<div style="padding:3px 0;font-weight:600;color:{col}">'
                             f'{html.escape(r["sym"])}: {html.escape(r["verdict"])} '
                             f'<span class="muted" style="font-weight:400">({html.escape(r["why"])}, '
                             f'verdi {r["value_nok"]:,.0f} kr, {r["pnl_pct"]:+.1f}%)</span></div>')
        else:
            parts.append('<p class="sub">Ingen posisjoner krever handling i dag '
                         f'(total {uv.get("total_nok",0):,.0f} kr).</p>')
    else:
        parts.append('<p class="sub" style="margin-top:14px">💡 Synk porteføljen din '
                     '(docs/portfolio.json) for å se posisjons-varsler her og i Discord.</p>')

    # Rad 3: regelen vs deg
    curve = paper.get("curve") or []
    actual = paper.get("actual_curve") or []
    if curve:
        start = paper.get("start_nok") or 100000
        rule_now = curve[-1][1]
        rule_ret = (rule_now / start - 1) * 100
        line = (f'Regelen (paper): <strong style="color:{PALETTE["up"] if rule_ret>=0 else PALETTE["down"]}">'
                f'{rule_ret:+.1f}%</strong> siden {curve[0][0]}')
        if actual and uv:
            # felles startpunkt-sammenligning er upresis; vis bare nivåer
            line += f' · din portefølje nå: {uv.get("total_nok",0):,.0f} kr'
        parts.append(f'<h3 style="margin-top:14px">Regelen vs. deg</h3>'
                     f'<p class="sub">{line}. Hypotetisk regelportefølje som rebalanserer '
                     'mekanisk månedlig — speil for din egen disiplin.</p>')

    parts.append('</section>')
    return "".join(parts)


def _regime_timeline(rhist) -> str:
    """Fargestripe av composite regime-score over tid (grønn/oransje/rød bånd)."""
    scores = (rhist or {}).get("scores", [])
    dates = (rhist or {}).get("dates", [])
    if len(scores) < 3:
        return ('<p class="sub" style="margin-top:8px">Regime-tidslinje bygges opp '
                'etter hvert som daglige bygg kjører.</p>')
    n = len(scores)
    W, H = 100.0, 26.0
    bw = W / n
    bars = []
    for i, s in enumerate(scores):
        col = PALETTE["up"] if s >= 66 else (PALETTE["warn"] if s >= 34 else PALETTE["down"])
        x = i * bw
        bars.append(f'<rect x="{x:.3f}" y="0" width="{bw+0.5:.3f}" height="{H}" fill="{col}"/>')
    d0 = html.escape(dates[0]) if dates else ""
    d1 = html.escape(dates[-1]) if dates else ""
    return ('<h3 style="margin-top:14px">Regime-tidslinje</h3>'
            f'<svg viewBox="0 0 {W} {H}" width="100%" height="26" preserveAspectRatio="none" '
            f'style="border-radius:6px;display:block">{"".join(bars)}</svg>'
            f'<div style="display:flex;justify-content:space-between" class="sub">'
            f'<span>{d0}</span><span class="muted">grønn=risk-on · oransje=overgang · rød=risk-off</span>'
            f'<span>{d1}</span></div>')


def _regime_card(title, label, col, note):
    return (f'<div class="sc" style="border-color:{col}55">'
            f'<div class="sc-name">{html.escape(title)}</div>'
            f'<div style="font-size:15px;font-weight:700;color:{col}">{html.escape(label or "–")}</div>'
            f'<div class="sc-label muted">{html.escape(note or "")}</div></div>')


def _ranking_table(rk, title, den):
    rows = rk.get("rows", [])
    if not rows:
        return f'<div><h3>{title}</h3><p class="muted">Ingen data.</p></div>'
    # maks composite for skalering av styrke-bar
    comps = [abs(r.get("composite") or 0) for r in rows]
    maxc = max(comps) if comps else 1
    out = [f'<div><h3>{title}</h3>',
           '<table><thead><tr><th>#</th><th>Ratio</th><th>Sjanger</th>'
           '<th style="text-align:right">1M</th><th style="text-align:right">3M</th>'
           '<th>Leder-styrke</th><th>TV</th></tr></thead><tbody>']
    for i, r in enumerate(rows, 1):
        tf = r.get("tf_over") or []
        comp = r.get("composite")
        beats = r.get("beats")
        # Styrke-celle: ikon + tall + proporsjonal bar
        if beats and comp is not None:
            barw = int(min(abs(comp) / maxc * 100, 100)) if maxc else 0
            tfs = "+".join(tf) if tf else ""
            strength = (f'<div style="font-size:12px;font-weight:700;color:{PALETTE["up"]}">'
                        f'▲ +{comp:.1f}% <span class="muted" style="font-weight:400">{tfs}</span></div>'
                        f'<div style="height:5px;background:#1a1f26;border-radius:3px;margin-top:2px">'
                        f'<div style="height:5px;width:{barw}%;background:{PALETTE["up"]};border-radius:3px"></div></div>')
        elif beats is False and comp is not None:
            strength = f'<div style="font-size:12px;font-weight:700;color:{PALETTE["down"]}">▼ {comp:.1f}%</div>'
        else:
            strength = '<span class="muted">— n/a</span>'
        out.append(f'<tr><td class="muted">{i}</td>'
                   f'<td><strong>{html.escape(r["label"])}/{den}</strong></td>'
                   f'<td class="muted">{html.escape(r.get("subclass",""))}</td>'
                   f'{_roc_cell(r.get("roc_1m"))}{_roc_cell(r.get("roc_3m"))}'
                   f'<td style="min-width:120px">{strength}</td>'
                   f'<td><a class="tv" href="{_tv(r["label"],den)}" target="_blank" rel="noopener">📊</a></td></tr>')
    out.append('</tbody></table></div>')
    return "".join(out)


# ── Market Daily Report ───────────────────────────────────────────
def render_report(data) -> str:
    P = layout.head("Market Daily Report", 1)
    out = [P, '<h1 id="top">📊 Market Daily Report</h1>',
           '<p class="sub">Northstar-score 0–100 (høyere = lavere risiko / bedre entry), '
           'snitt av RSI, MACD og MA-avstand over ukentlig/månedlig/kvartal. '
           'Sektorscore = snitt av medlemmenes score; trend = andel over 50MA (ukentlig).</p>']

    # Sektorscore — kort lenker til sin seksjon lenger ned
    sec = data.get("sector_summary", {})
    # stabil anker-nøkkel per sektor (rå sektornavn -> slug)
    def _slug(name):
        return "sec-" + "".join(ch if ch.isalnum() else "-" for ch in name.lower())
    out.append('<section class="section"><h2>Sektorscore</h2>'
               '<p class="sub">Klikk på et kort for å hoppe til instrumentene i sektoren.</p>'
               '<div class="sector-grid">')
    sec_items = sorted(sec.items(), key=lambda kv: -kv[1]["avg_score"])
    for raw_sec, s in sec_items:
        c = s["score_col"]; tcol = s["trend_col"]
        out.append(f'<a class="sc" href="#{_slug(raw_sec)}" style="border-color:{c}55">'
                   f'<div class="sc-name">{html.escape(s["display"])} <span class="muted" style="font-weight:400">→</span></div>'
                   f'<div class="sc-score" style="color:{c}">{s["avg_score"]}</div>'
                   f'<div class="sc-label" style="color:{c}">{html.escape(s["label"])}</div>'
                   f'<div class="sc-label" style="color:{tcol}">{html.escape(s["trend_txt"])} '
                   f'<span class="muted">({s["over_ma50"]}/{s["total_ma50"]} over 50MA)</span></div>'
                   f'<div class="sc-label muted">{s["n"]} instr.</div></a>')
    out.append('</div></section>')

    # Per-instrument — gruppert etter sektor (sektorer sortert etter score,
    # instrumenter innen hver sektor sortert etter score)
    out.append('<section class="section"><h2>Instrumenter</h2>'
               '<p class="sub">Gruppert etter sektor. Hvert instrument viser om det slår gull '
               '(ROC 1M/3M) med lenke til TradingView, og en interaktiv prisgraf.</p></section>')
    assets = data["assets"]
    chart_init = []
    for raw_sec, s in sec_items:
        members = [a for a in assets.values()
                   if not a.get("missing_data") and a.get("sector") == raw_sec]
        members.sort(key=lambda a: -a.get("northstar_score", 0))
        if not members:
            continue
        c = s["score_col"]
        out.append(f'<h2 id="{_slug(raw_sec)}" style="scroll-margin-top:70px;border-bottom:2px solid {c}55;padding-bottom:4px">'
                   f'{html.escape(s["display"])} '
                   f'<span style="font-size:14px;color:{c}">snitt {s["avg_score"]} · {html.escape(s["label"])}</span> '
                   f'<a href="#top" class="tv" style="font-size:11px;float:right">↑ topp</a></h2>')
        for a in members:
            iid = a["id"]
            sc = a["northstar_score"]
            lab, col = score_label(sc)
            gb = a.get("gold_beat")
            if gb is None:
                gb_html = '<span class="muted">vs gull: n/a</span>'
            elif gb.get("beats"):
                gb_html = f'<span class="up">▲ slår gull ({"+".join(gb.get("tf_over") or [])})</span>'
            else:
                gb_html = '<span class="down">▼ taper mot gull</span>'
            sym = a.get("symbol_label", iid)
            rm = a.get("risk", {})
            risk_str = ""
            if rm.get("vol") is not None:
                risk_str = (f'<span class="muted">vol {rm["vol"]:.0f}% · '
                            f'maxDD {rm["max_dd"]:.0f}% · Sharpe {rm["sharpe"]:.2f}</span>'
                            if rm.get("sharpe") is not None else
                            f'<span class="muted">vol {rm["vol"]:.0f}%</span>')
            chart_id = f"ch_{iid}"
            chart_init.append({"el": chart_id, "series": a.get("price_series", [])})
            out.append(
                f'<div class="section" style="margin:10px 0">'
                f'<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:baseline">'
                f'<h3>{html.escape(a.get("display_name", iid))}</h3>'
                f'<span class="tag">{html.escape(sym)}</span>'
                f'<span class="tag" style="color:{PALETTE["accent"]}">{html.escape(a.get("subclass",""))}</span>'
                f'<span class="pill" style="background:{col}22;color:{col}">Score {sc} · {html.escape(lab)}</span>'
                f'{gb_html}'
                f'<a class="tv" href="{_tv(sym,"GLD")}" target="_blank" rel="noopener">📊 {html.escape(sym)}/GLD</a>'
                f'</div>'
                f'<div style="margin:4px 0">{risk_str}</div>'
                f'<div class="lwc" id="{chart_id}"></div>'
                f'</div>')

    # Charts-init (Lightweight Charts)
    out.append(layout.lwc_script())
    out.append('<script>\n' + _lwc_init_js(chart_init) + '\n</script>')
    out.append(layout.foot())
    return "".join(out)


def _lwc_init_js(charts) -> str:
    payload = json.dumps(charts)
    return """
const CHARTS = %s;
function mkChart(c){
  const el = document.getElementById(c.el);
  if(!el || !window.LightweightCharts || !c.series.length) return;
  const chart = LightweightCharts.createChart(el, {
    height: 240, layout:{background:{color:'transparent'}, textColor:'#9aa7b5'},
    grid:{vertLines:{color:'#1a1f26'}, horzLines:{color:'#1a1f26'}},
    rightPriceScale:{borderColor:'#262d36'}, timeScale:{borderColor:'#262d36'},
    crosshair:{mode:0}
  });
  const s = chart.addAreaSeries({lineColor:'#0072B2', topColor:'rgba(0,114,178,0.30)',
    bottomColor:'rgba(0,114,178,0.02)', lineWidth:2});
  s.setData(c.series.map(p => ({time:p[0], value:p[1]})));
  chart.timeScale().fitContent();
  new ResizeObserver(()=>chart.applyOptions({width:el.clientWidth})).observe(el);
}
// Lazy-init nar synlig (ytelse: ikke alle grafer pa en gang)
const io = new IntersectionObserver((entries,obs)=>{
  entries.forEach(e=>{ if(e.isIntersecting){ const c=CHARTS.find(x=>x.el===e.target.id);
    if(c){ mkChart(c); obs.unobserve(e.target);} } });
}, {rootMargin:'200px'});
CHARTS.forEach(c=>{ const el=document.getElementById(c.el); if(el) io.observe(el); });
""" % payload


# ── RRG-scatter (SVG, ingen ekstern lib) ──────────────────────────
def _rrg_section(rrg) -> str:
    pts = (rrg or {}).get("points", [])
    if not pts:
        return ""
    # Skala: finn min/max rundt 100, med marginer
    xs = [p["rs_ratio"] for p in pts]
    ys = [p["rs_momentum"] for p in pts]
    xmin, xmax = min(94, min(xs) - 1), max(106, max(xs) + 1)
    ymin, ymax = min(94, min(ys) - 1), max(106, max(ys) + 1)
    W, H, pad = 680, 460, 44

    def sx(v):
        return pad + (v - xmin) / (xmax - xmin) * (W - 2 * pad)

    def sy(v):
        return H - pad - (v - ymin) / (ymax - ymin) * (H - 2 * pad)

    x100, y100 = sx(100), sy(100)
    # Kvadrant-farger (colorblind-trygge, lav metning)
    quad_cols = {"Leading": "#0072B2", "Weakening": "#E69F00",
                 "Lagging": "#D55E00", "Improving": "#56B4E9"}
    svg = [f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:700px;background:var(--panel2);border-radius:10px">']
    # kvadrant-bakgrunner
    svg.append(f'<rect x="{x100}" y="{pad}" width="{W-pad-x100}" height="{y100-pad}" fill="#0072B215"/>')
    svg.append(f'<rect x="{x100}" y="{y100}" width="{W-pad-x100}" height="{H-pad-y100}" fill="#E69F0015"/>')
    svg.append(f'<rect x="{pad}" y="{y100}" width="{x100-pad}" height="{H-pad-y100}" fill="#D55E0015"/>')
    svg.append(f'<rect x="{pad}" y="{pad}" width="{x100-pad}" height="{y100-pad}" fill="#56B4E915"/>')
    # akse-kryss
    svg.append(f'<line x1="{x100}" y1="{pad}" x2="{x100}" y2="{H-pad}" stroke="#3a4452" stroke-dasharray="4 4"/>')
    svg.append(f'<line x1="{pad}" y1="{y100}" x2="{W-pad}" y2="{y100}" stroke="#3a4452" stroke-dasharray="4 4"/>')
    # kvadrant-etiketter
    svg.append(f'<text x="{W-pad-6}" y="{pad+16}" fill="#0072B2" font-size="12" text-anchor="end" font-weight="700">LEADING</text>')
    svg.append(f'<text x="{W-pad-6}" y="{H-pad-6}" fill="#E69F00" font-size="12" text-anchor="end" font-weight="700">WEAKENING</text>')
    svg.append(f'<text x="{pad+6}" y="{H-pad-6}" fill="#D55E00" font-size="12" font-weight="700">LAGGING</text>')
    svg.append(f'<text x="{pad+6}" y="{pad+16}" fill="#56B4E9" font-size="12" font-weight="700">IMPROVING</text>')
    # akse-titler
    svg.append(f'<text x="{W/2}" y="{H-8}" fill="var(--muted)" font-size="11" text-anchor="middle">RS-Ratio (relativ styrke) →</text>')
    svg.append(f'<text x="14" y="{H/2}" fill="var(--muted)" font-size="11" text-anchor="middle" transform="rotate(-90 14 {H/2})">RS-Momentum →</text>')
    # punkter med haler
    for p in pts:
        col = quad_cols.get(p["quadrant"], "#999")
        px, py = sx(p["rs_ratio"]), sy(p["rs_momentum"])
        tail = p.get("tail", [])
        if len(tail) >= 2:
            pl = " ".join(f"{sx(a)},{sy(b)}" for a, b in tail)
            svg.append(f'<polyline points="{pl}" fill="none" stroke="{col}" stroke-width="1.5" opacity="0.45"/>')
        svg.append(f'<circle cx="{px}" cy="{py}" r="5" fill="{col}" stroke="#0b0d10" stroke-width="1.5"/>')
        svg.append(f'<text x="{px+8}" y="{py+4}" fill="var(--text)" font-size="11" font-weight="600">{html.escape(p["label"])}</text>')
    svg.append('</svg>')
    return ('<section class="section"><h2>🔄 RRG — Relative Rotation Graph (vs gull)</h2>'
            '<p class="sub">RS-Ratio (relativ styrke) på x-aksen, RS-Momentum (endringstakt) på y-aksen, '
            'sentrert på 100. Instrumenter roterer mot klokka: Improving → Leading → Weakening → Lagging. '
            'Halen viser de siste punktene (retning). Ett blikk gir hele lederskapsbildet.</p>'
            + "".join(svg) +
            '<details><summary>Hvordan lese RRG</summary>'
            '<p class="sub" style="margin-top:8px">Øvre høyre (Leading, blå) = slår gull med positivt momentum — '
            'sterkest. Nedre høyre (Weakening, oransje) = fortsatt over, men momentum avtar. Nedre venstre '
            '(Lagging, vermillion) = svakest. Øvre venstre (Improving, lyseblå) = under gull, men på vei opp — '
            'tidlige vendingskandidater. En sunn opptrend roterer Improving → Leading.</p></details>'
            '</section>')


# ── Korrelasjonsmatrise (SVG heatmap) ─────────────────────────────
def _corr_section(corr) -> str:
    ids = (corr or {}).get("ids", [])
    mat = (corr or {}).get("matrix", [])
    if not ids or not mat:
        return ""
    n = len(ids)
    cell = 34
    label_pad = 46
    W = label_pad + n * cell + 10
    H = label_pad + n * cell + 10

    def color(v):
        # Divergerende, colorblind-trygt: blå (negativ) — grå (0) — vermillion (positiv)
        if v >= 0:
            t = min(v, 1.0)
            return f'rgba(213,94,0,{0.12 + 0.6*t:.2f})'   # vermillion
        t = min(-v, 1.0)
        return f'rgba(0,114,178,{0.12 + 0.6*t:.2f})'       # blå

    svg = [f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:{W}px;background:var(--panel2);border-radius:10px">']
    for j, lab in enumerate(ids):
        x = label_pad + j * cell + cell / 2
        svg.append(f'<text x="{x}" y="{label_pad-6}" fill="var(--muted)" font-size="10" text-anchor="middle" transform="rotate(-45 {x} {label_pad-6})">{html.escape(lab)}</text>')
        y = label_pad + j * cell + cell / 2 + 3
        svg.append(f'<text x="{label_pad-6}" y="{y}" fill="var(--muted)" font-size="10" text-anchor="end">{html.escape(lab)}</text>')
    for i in range(n):
        for j in range(n):
            v = mat[i][j]
            x = label_pad + j * cell
            y = label_pad + i * cell
            tcol = "#e6edf3" if abs(v) > 0.45 else "#9aa7b5"
            svg.append(f'<rect x="{x}" y="{y}" width="{cell-2}" height="{cell-2}" rx="3" fill="{color(v)}"/>')
            svg.append(f'<text x="{x+cell/2-1}" y="{y+cell/2+3}" fill="{tcol}" font-size="9" text-anchor="middle">{v:.2f}</text>')
    svg.append('</svg>')
    return ('<section class="section"><h2>🔗 Korrelasjonsmatrise (252 dager)</h2>'
            '<p class="sub">Daglig-avkastnings-korrelasjon mellom hovedaktivaklasser. '
            'Vermillion = positiv samvariasjon, blå = negativ. Lav/negativ korrelasjon mellom '
            'posisjoner = ekte diversifisering; høy korrelasjon = skjult konsentrasjonsrisiko.</p>'
            + "".join(svg) + '</section>')


# ── Backtest-side ─────────────────────────────────────────────────
def render_backtest(data) -> str:
    P = layout.head("Backtest", 3)
    bt = data.get("backtest", {})
    out = [P, '<h1>🧪 Backtest — walk-forward</h1>',
           '<p class="sub">Ærlig out-of-sample-test av en enkel, økonomisk motivert rotasjonsregel: '
           'eier topp-N sykliske mot gull (3M+6M momentum), med absolutt-momentum-filter (dual momentum) '
           'og volatilitetsskalering mot momentum-krasj. Ingen parameteroptimalisering på testdata.</p>']

    if not bt.get("available"):
        out.append(f'<section class="section"><p class="down">Backtest utilgjengelig: '
                   f'{html.escape(bt.get("reason","ukjent"))}.</p></section>')
        out.append(layout.foot())
        return "".join(out)

    s, sp, g = bt["strategy"], bt["spy"], bt["gold"]
    out.append('<section class="section"><h2>Resultater</h2>'
               f'<p class="sub">Periode {bt["start"]} → {bt["end"]} ({bt["months"]} måneder), '
               f'topp-{bt["top_n"]}, snitt {bt["avg_holdings"]} posisjoner. Månedlig rebalansering med '
               f'<strong>value-tilt</strong> (vekt {bt.get("value_weight","–")} på reversal, Asness), '
               f'<strong>hysterese</strong> (z-margin {bt.get("hysteresis_z","–")}), '
               f'<strong>transaksjonskostnad {bt.get("tx_cost_bps","–")} bps</strong> '
               f'(årlig turnover ~{bt.get("annual_turnover","–")}%), <strong>kontinuerlig vol-skalering</strong> '
               f'(snitt eksp. {bt.get("avg_exposure","–")}) og <strong>panikk-demper</strong> '
               f'({bt.get("panic_months","–")} måneder dempet, Daniel &amp; Moskowitz).</p>'
               '<table><thead><tr><th>Strategi</th><th style="text-align:right">Total</th>'
               '<th style="text-align:right">CAGR</th><th style="text-align:right">Vol</th>'
               '<th style="text-align:right">Sharpe</th><th style="text-align:right">Max DD</th></tr></thead><tbody>')
    for name, d, col in [("Rotasjon (regel)", s, PALETTE["up"]),
                         ("Kjøp-og-hold SPY", sp, PALETTE["accent"]),
                         ("Kjøp-og-hold gull", g, PALETTE["warn"])]:
        out.append(f'<tr><td style="color:{col};font-weight:600">{name}</td>'
                   f'<td style="text-align:right">{d.get("total_return","–")}%</td>'
                   f'<td style="text-align:right">{d.get("cagr","–")}%</td>'
                   f'<td style="text-align:right">{d.get("vol","–")}%</td>'
                   f'<td style="text-align:right">{d.get("sharpe","–")}</td>'
                   f'<td style="text-align:right" class="down">{d.get("max_dd","–")}%</td></tr>')
    out.append('</tbody></table>')
    out.append('<div class="lwc" id="bt_chart" style="height:340px"></div></section>')

    # ekvitykurve via Lightweight Charts (3 serier)
    series = {
        "strat": [[bt["dates"][i], bt["strategy"]["curve"][i]] for i in range(len(bt["dates"]))],
        "spy": [[bt["dates"][i], bt["spy"]["curve"][i]] for i in range(len(bt["dates"]))],
        "gold": [[bt["dates"][i], bt["gold"]["curve"][i]] for i in range(len(bt["dates"]))],
    }
    out.append('<section class="section"><h2>Tolkning &amp; forbehold</h2>'
               '<p class="sub">En clean walk-forward kan fortsatt smigre en regel. Sammenlign '
               '<strong>out-of-sample Sharpe</strong> mot kjøp-og-hold: hvis rotasjonsregelen ikke '
               'slår en enkel SPY-/gull-posisjon på risikojustert basis, er den ikke verdt kompleksiteten. '
               'Momentum krasjer sjelden, men hardt, i skarpe vendinger etter bear-marked (Daniel &amp; '
               'Moskowitz 2016) — derfor volatilitetsskaleringen. <strong>Ikke finansrådgivning.</strong></p>'
               '<details><summary>Metodikk</summary>'
               '<p class="sub" style="margin-top:8px">Signaler beregnes fra data t.o.m. forrige måned og '
               'brukes på inneværende måneds avkastning (ingen look-ahead). Cash-avkastning antas 0%. '
               'Transaksjonskostnader er ikke modellert — reell avkastning ville vært noe lavere. '
               'Universet er dagens sykliske instrumenter; instrumenter uten nok historikk faller naturlig ut '
               'tidlig i perioden (en mild survivorship-effekt).</p></details></section>')

    out.append(layout.lwc_script())
    out.append('<script>\nconst BT = ' + json.dumps(series) + ';\n' + _bt_chart_js() + '\n</script>')
    out.append(layout.foot())
    return "".join(out)


def _bt_chart_js() -> str:
    return """
function initBt(){
  const el = document.getElementById('bt_chart');
  if(!el || !window.LightweightCharts) return;
  const chart = LightweightCharts.createChart(el, {
    height:340, layout:{background:{color:'transparent'}, textColor:'#9aa7b5'},
    grid:{vertLines:{color:'#1a1f26'}, horzLines:{color:'#1a1f26'}},
    rightPriceScale:{borderColor:'#262d36'}, timeScale:{borderColor:'#262d36'}
  });
  const mk = (data,color)=>{ const s=chart.addLineSeries({color,lineWidth:2});
    s.setData(data.map(p=>({time:p[0]+'-01', value:p[1]}))); return s; };
  mk(BT.strat, '#0072B2'); mk(BT.spy, '#56B4E9'); mk(BT.gold, '#E69F00');
  chart.timeScale().fitContent();
  new ResizeObserver(()=>chart.applyOptions({width:el.clientWidth})).observe(el);
}
if(window.LightweightCharts) initBt(); else window.addEventListener('load', initBt);
"""
