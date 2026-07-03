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
from . import glossary
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
def render_today(data) -> str:
    """🎯 I dag — landingssiden. Tre lag: kommando-bånd (én skjerm),
    sorterbar leaderboard, og lenker til detaljer."""
    P = layout.head("I dag", 0)
    td = data.get("today", {})
    out = [P, '<h1>🎯 I dag</h1>']

    # ── LAG 1: Kommando-bånd ──────────────────────────────────────
    macro_state = td.get("macro_state", "ukjent")
    macro_score = td.get("macro_score")
    mcol = (PALETTE["up"] if macro_state == "risk-on"
            else PALETTE["down"] if macro_state == "risk-off" else PALETTE["warn"])
    out.append('<section class="section" style="border:2px solid var(--accent)">')
    out.append(f'<div style="font-size:16px;font-weight:700;margin-bottom:4px">'
               f'Makro: <span style="color:{mcol}">{html.escape(macro_state)}'
               f'{f" ({macro_score}/100)" if macro_score is not None else ""}</span></div>')
    out.append(f'<p style="font-size:14px;line-height:1.5;margin:0 0 12px">{html.escape(td.get("verdict",""))}</p>')

    # Pengestrøm-stripe: retning + hvor kapital strømmer inn/ut
    flow = td.get("flow", {})
    if flow.get("state"):
        fcol = flow.get("col", PALETTE["warn"])
        inflow = flow.get("inflow", [])
        outflow = flow.get("outflow", [])
        in_s = ", ".join(f'{html.escape(f["sector"])} ({f["roc_3m"]:+.0f}%{"⚡" if f.get("accel") else ""})'
                         for f in inflow) or "ingen klar"
        out_s = ", ".join(f'{html.escape(f["sector"])} ({f["roc_3m"]:+.0f}%)' for f in outflow) or "ingen klar"
        out.append(f'<div style="background:var(--panel2);border-radius:8px;padding:10px 12px;margin-bottom:12px">'
                   f'<div style="font-weight:700;color:{fcol};margin-bottom:4px">💧 Pengestrøm: {html.escape(flow["state"])}</div>'
                   f'<div style="font-size:12.5px;line-height:1.6">'
                   f'<span style="color:{PALETTE["up"]}">▲ Inn:</span> {in_s}<br>'
                   f'<span style="color:{PALETTE["down"]}">▼ Ut:</span> {out_s}</div></div>')

    # Kapitalstrøm (Armstrong-stil datapunkt): hvor internasjonal kapital søker seg
    cap = td.get("capital") or {}
    if cap.get("verdict"):
        ccol = cap.get("col", PALETTE["warn"])
        dests = cap.get("destinations", [])
        dest_s = " · ".join(f'{html.escape(d["region"])} ({d["roc_3m"]:+.1f}%{"⚡" if d.get("accel") else ""})'
                            for d in dests) or "n/a"
        extra = []
        if cap.get("us_concentration"):
            extra.append(html.escape(cap["us_concentration"]))
        out.append(f'<div style="background:var(--panel2);border-radius:8px;padding:10px 12px;margin-bottom:12px">'
                   f'<div style="font-weight:700;color:{ccol};margin-bottom:4px">🌍 Kapitalstrøm (land, målt i gull)</div>'
                   f'<div style="font-size:12.5px;line-height:1.6">{html.escape(cap["verdict"])}<br>'
                   f'<span class="muted">Topp-destinasjoner: {dest_s}'
                   f'{" · " + " · ".join(extra) if extra else ""}</span></div></div>')

    # Hva er nytt siden forrige bygg (diff)
    changes = data.get("changes", [])
    if changes:
        out.append('<div style="background:var(--panel2);border-radius:8px;padding:10px 12px;margin-bottom:12px">'
                   '<div style="font-weight:700;margin-bottom:4px">🔔 Endret siden forrige bygg</div>')
        for c in changes[:6]:
            cls = "up" if c.startswith(("▲", "🎯")) else ("down" if c.startswith(("▼", "⚠")) else "muted")
            out.append(f'<div class="{cls}" style="font-size:12.5px;padding:2px 0">{html.escape(c)}</div>')
        out.append('</div>')

    # Tre kolonner: kjøp / skaler av / dine posisjoner
    out.append('<div class="today-cols">')

    # Kjøp-kandidater
    buys = td.get("buys", [])
    out.append(f'<div class="today-col"><h3 style="color:{PALETTE["up"]};margin-top:0">▲ Kjøp-kandidater</h3>')
    if buys:
        for b in buys:
            out.append(f'<div class="today-item"><a href="report.html#{b["id"]}" style="font-weight:700;color:var(--text);text-decoration:none">{html.escape(b["sym"])}</a> '
                       f'<span class="pill" style="background:{PALETTE["up"]}22;color:{PALETTE["up"]}">{b["score"]}</span>'
                       f'<div class="muted" style="font-size:11px">{html.escape(b.get("why",""))} · {html.escape(b.get("sector",""))}</div></div>')
    else:
        out.append('<p class="muted" style="font-size:12px">Ingen kvalifiserte i lavrisiko-entry nå. Tålmodighet.</p>')
    out.append('</div>')

    # Skaler av / unngå
    avoids = td.get("avoids", [])
    out.append(f'<div class="today-col"><h3 style="color:{PALETTE["down"]};margin-top:0">▼ Skaler av / unngå</h3>')
    if avoids:
        for av in avoids:
            ac = PALETTE["warn"] if av.get("stage") == 2 else PALETTE["down"]
            out.append(f'<div class="today-item"><a href="report.html#{av["id"]}" style="font-weight:700;color:var(--text);text-decoration:none">{html.escape(av["sym"])}</a> '
                       f'<div class="muted" style="font-size:11px;color:{ac}">{html.escape(av.get("reason",""))}</div></div>')
    else:
        out.append('<p class="muted" style="font-size:12px">Ingen stretched/nedtrend-varsler nå.</p>')
    out.append('</div>')

    # Dine posisjoner
    uv = data.get("user_portfolio")
    out.append(f'<div class="today-col"><h3 style="margin-top:0">💼 Dine posisjoner</h3>')
    if uv and uv.get("rows"):
        actions = [r for r in uv["rows"] if r["verdict"] in ("SKALER AV", "VURDER SKALER AV")]
        if actions:
            for r in actions:
                rc = PALETTE["down"] if r["verdict"] == "SKALER AV" else PALETTE["warn"]
                out.append(f'<div class="today-item"><span style="font-weight:700">{html.escape(r["sym"])}</span> '
                           f'<span style="color:{rc};font-size:11px">{html.escape(r["verdict"])}</span>'
                           f'<div class="muted" style="font-size:11px">{html.escape(r.get("why",""))} · {r["pnl_pct"]:+.1f}%</div></div>')
        else:
            out.append(f'<p class="muted" style="font-size:12px">Ingen posisjoner krever handling. '
                       f'Total {uv.get("total_nok",0):,.0f} kr.</p>')
    else:
        out.append('<p class="muted" style="font-size:12px">Synk porteføljen din for å se posisjons-varsler her.</p>')
    out.append('</div>')

    out.append('</div></section>')

    # ── LAG 2: Sorterbar leaderboard ──────────────────────────────
    lb = td.get("leaderboard", [])
    # Guidet arbeidsflyt (Start her)
    out.append('<details class="section" style="padding:10px 14px"><summary style="cursor:pointer;font-weight:700">'
               '🧭 Start her — slik bruker du verktøyet</summary>'
               '<div style="font-size:13px;line-height:1.7;margin-top:8px">'
               '1. Sjekk <strong>makro-verdikt og pengestrøm</strong> øverst — er det medvind eller motvind?<br>'
               '2. Se <strong>kjøp-kandidatene</strong> — bare instrumenter i ekte lavrisiko-entry med sjanger-medvind kvalifiserer.<br>'
               '3. Sorter <strong>leaderboarden</strong> for å se hva som gjør det bra/dårlig — kompositt vekter oppsett + sjanger + makro.<br>'
               '4. Åpne <a href="roadmap.html">roadmapen</a> for kandidaten — sjekk mål, støtte og invalideringsnivå FØR du kjøper.<br>'
               '5. Bruk <a href="portfolio.html">porteføljesiden</a> for posisjonsstørrelse (vol-justert) og loggfør beslutningen.<br>'
               '6. <a href="backtest.html">Backtesten</a> viser ærlig om systemet faktisk har edge — sjekk før du stoler blindt på det.'
               '</div></details>')

    out.append('<section class="section"><h2>📊 Leaderboard — hele universet</h2>'
               '<p class="sub">Klikk en kolonne for å sortere. <strong>Kompositt</strong> = '
               'NSBC-score × sjanger-medvind × makro (vekt-av-bevis): et instrument flyter til '
               'toppen bare når oppsett, sjanger OG makro peker samme vei. '
               'Grønn = sterk, rød = svak. Klikk symbol for detaljer.</p>')
    out.append(_leaderboard_table(lb))
    out.append('</section>')

    out.append('<p class="sub" style="margin-top:16px">Mer detaljer: '
               '<a href="trend.html">Trend-oversikt</a> · '
               '<a href="report.html">Daily Report</a> · '
               '<a href="roadmap.html">Roadmaps</a></p>')
    out.append(layout.foot())
    return "".join(out)


def _leaderboard_table(lb) -> str:
    """Sorterbar HTML-tabell. Sortering gjøres klientside i JS."""
    if not lb:
        return '<p class="muted">Ingen data.</p>'
    import json as _json
    head_cols = [
        ("composite", "Kompositt"), ("sym", "Symbol"), ("score", "Score"),
        ("stage", "Stage"), ("trend", "LT/KT"), ("beats", "Slår gull"),
        ("mansfield", "Mansfield"), ("roc3m", "3M %"), ("dist36", "Fra 36-MA"),
        ("from52wh", "Fra 52u-topp"), ("sector", "Sjanger"),
    ]
    th = "".join(f'<th data-k="{k}" style="cursor:pointer;user-select:none">{lbl} <span class="sort-ar"></span></th>'
                 for k, lbl in head_cols)
    return (f'<input id="lbFilter" type="text" placeholder="Filtrer på symbol eller sjanger..." '
            f'style="width:100%;max-width:340px;padding:7px 10px;margin:0 0 8px;background:var(--panel2);'
            f'border:1px solid var(--border);border-radius:7px;color:var(--text);font-size:13px">'
            f'<div style="overflow-x:auto"><table id="lbTable" class="lb"><thead><tr>{th}</tr></thead>'
            f'<tbody></tbody></table></div>'
            f'<script>const LB={_json.dumps(lb)};{_leaderboard_js()}</script>')


def _leaderboard_js() -> str:
    return r"""
(function(){
  let sortK='composite', sortDir=-1, filt='';
  const tb=document.querySelector('#lbTable tbody');
  const fEl=document.getElementById('lbFilter');
  if(fEl) fEl.addEventListener('input',()=>{ filt=fEl.value.toLowerCase(); render(); });
  const upC='#009E73',downC='#D55E00',warnC='#E69F00',mutC='#7d8a99';
  function scoreColor(s){ if(s>=70)return upC; if(s>=55)return '#56B4E9'; if(s>=40)return warnC; return downC; }
  function stageLabel(st){ return {1:'1 Basing',2:'2 Opptrend',3:'3 Distrib.',4:'4 Nedtrend'}[st]||'–'; }
  function stageColor(st){ return {1:'#56B4E9',2:upC,3:warnC,4:downC}[st]||mutC; }
  function spark(arr){ if(!arr||arr.length<2)return ''; const w=60,h=18,mn=Math.min(...arr),mx=Math.max(...arr);
    const rng=(mx-mn)||1; const pts=arr.map((v,i)=>`${(i/(arr.length-1)*w).toFixed(1)},${(h-(v-mn)/rng*h).toFixed(1)}`).join(' ');
    const up=arr[arr.length-1]>=arr[0]; return `<svg width="${w}" height="${h}" style="vertical-align:middle"><polyline points="${pts}" fill="none" stroke="${up?upC:downC}" stroke-width="1.3"/></svg>`; }
  function cell(v,c){ return `<td style="${c||''}">${v}</td>`; }
  function render(){
    const rows=[...LB].filter(r=>!filt||(r.sym||'').toLowerCase().includes(filt)||(r.sector||'').toLowerCase().includes(filt)||(r.name||'').toLowerCase().includes(filt)).sort((a,b)=>{ let x=a[sortK],y=b[sortK];
      if(sortK==='sym'||sortK==='sector'){ x=(x||'');y=(y||''); return sortDir*x.localeCompare(y); }
      if(sortK==='trend'){ x=(a.lt||'')+(a.kt||'');y=(b.lt||'')+(b.kt||''); return sortDir*x.localeCompare(y); }
      if(sortK==='beats'){ x=a.beats_gold?1:0;y=b.beats_gold?1:0; }
      x=(x==null?-9999:x); y=(y==null?-9999:y); return sortDir*(x-y); });
    tb.innerHTML=rows.map(r=>{
      const tr=v=>v==null?'<span style="color:'+mutC+'">–</span>':v;
      const sb=v=>({'bull':'<span style="color:'+upC+'">bull</span>','bear':'<span style="color:'+downC+'">bear</span>'}[v]||'<span style="color:'+mutC+'">nøy</span>');
      const beats=r.beats_gold==null?tr(null):(r.beats_gold?'<span style="color:'+upC+'">▲ ja</span>':'<span style="color:'+downC+'">▼ nei</span>');
      const mans=r.mansfield==null?tr(null):`<span style="color:${r.mansfield>0?upC:downC}">${r.mansfield>0?'+':''}${r.mansfield}</span>`;
      const roc=r.roc3m==null?tr(null):`<span style="color:${r.roc3m>=0?upC:downC}">${r.roc3m>=0?'+':''}${r.roc3m.toFixed(1)}%</span>`;
      const dist=r.dist36==null?tr(null):`<span style="color:${r.dist36>=10?warnC:(r.dist36>=0?upC:downC)}">${r.dist36>=0?'+':''}${r.dist36.toFixed(1)}%</span>`;
      const f52=r.from52wh==null?tr(null):`<span style="color:${r.from52wh>=-5?upC:(r.from52wh>=-15?warnC:downC)}">${r.from52wh.toFixed(1)}%</span>`;
      return `<tr>
        <td style="font-weight:700;color:${scoreColor(r.composite)}">${r.composite} ${spark(r.spark)}</td>
        <td><a href="report.html#${r.id}" style="color:var(--text);font-weight:600;text-decoration:none">${r.sym}</a></td>
        <td style="color:${scoreColor(r.score)};font-weight:600">${r.score}</td>
        <td style="color:${stageColor(r.stage)};font-size:12px">${stageLabel(r.stage)}</td>
        <td style="font-size:11px">${sb(r.lt)}/${sb(r.kt)}</td>
        ${cell(beats)}${cell(mans)}${cell(roc)}${cell(dist)}${cell(f52)}
        <td class="muted" style="font-size:11px">${r.sector||''}</td></tr>`;
    }).join('');
    document.querySelectorAll('#lbTable th').forEach(th=>{
      const ar=th.querySelector('.sort-ar'); if(ar) ar.textContent = th.dataset.k===sortK?(sortDir<0?'▼':'▲'):''; });
  }
  document.querySelectorAll('#lbTable th').forEach(th=>{
    th.addEventListener('click',()=>{ const k=th.dataset.k;
      if(k===sortK) sortDir*=-1; else { sortK=k; sortDir=(k==='sym'||k==='sector')?1:-1; }
      render(); }); });
  render();
})();
"""


def render_trend(data) -> str:
    P = layout.head("Trend-oversikt", 1)
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

    # 🎯 Triage: hva bør jeg vurdere i dag (én handlingsliste)
    out.append(_triage_view(data))

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
            out.append(_regime_card("Samlet regime", comp.get("label"), comp.get("col"),
                                    comp.get("state", ""), "regime_composite"))
        ex_keys = {"yield_curve": "yield_curve", "net_liquidity": "net_liquidity",
                   "global_liquidity": "global_liquidity", "real_rate": "real_rate",
                   "breakeven": "breakeven", "nfci": "nfci", "credit_spread": "credit_spread",
                   "panic": "panic", "gpr": "gpr"}
        for key, title in [("yield_curve", "Yield-kurve 2s10s"), ("term_spread_10y3m", "10y-3m spread"),
                           ("net_liquidity", "Net liquidity (WALCL−TGA−RRP)"),
                           ("global_liquidity", "G3-likviditet (Fed+ECB+BoJ)"),
                           ("real_rate", "Realrente 10y (TIPS)"), ("breakeven", "Inflasjonsforv. 10y"),
                           ("fed_liquidity", "Fed-likviditet"), ("credit_spread", "Kredittspread"),
                           ("nfci", "NFCI (Chicago Fed)"), ("panic", "Momentum-regime"),
                           ("gpr", "Geopolitisk risiko (GPR)")]:
            r = reg.get(key)
            if r:
                out.append(_regime_card(title, r.get("label"), r.get("col"), r.get("note", ""),
                                        ex_keys.get(key)))
        out.append('</div>')
        # Samlet forklaring av regimet i klartekst
        if comp:
            out.append(f'<div class="explain" style="margin-top:8px"><span class="ex-what">'
                       f'{html.escape(glossary.regime_one_liner(comp.get("score")))}</span></div>')
    out.append('</section>')

    # Markedsbredde (flyttet opp – overordnet markedstilstand først)
    br = data.get("breadth", {})
    gb = data.get("global_breadth", {})
    if br:
        out.append('<section class="section"><h2>📐 Markedsbredde</h2>'
                   '<p class="sub">Andel av universet over 50- og 200-dagers MA (daglig). '
                   'Bred deltakelse bekrefter trend; smal bredde varsler svekkelse.</p>'
                   '<div class="sector-grid">')
        for ma in (50, 200):
            v = br.get(f"pct_over_{ma}ma")
            n = br.get(f"n_{ma}ma", 0)
            col = PALETTE["up"] if (v or 0) >= 50 else PALETTE["down"]
            icon = "▲" if (v or 0) >= 50 else "▼"
            out.append(f'<div class="sc"><div class="sc-name">Over {ma}-dagers MA (daglig)</div>'
                       f'<div class="sc-score" style="color:{col}">{icon} {v if v is not None else "–"}%</div>'
                       f'<div class="sc-label muted">{n} instrumenter</div></div>')
        # Global bredde (land + sektorer over 200d)
        if gb and gb.get("pct_over_200d") is not None:
            out.append(f'<div class="sc" style="border-color:{gb["col"]}55">'
                       f'<div class="sc-name">Global bredde: land+sektorer over 200-dagers MA (daglig)</div>'
                       f'<div class="sc-score" style="color:{gb["col"]}">{gb["pct_over_200d"]}%</div>'
                       f'<div class="sc-label" style="color:{gb["col"]}">{html.escape(gb["state"])} · {gb["over"]}/{gb["n"]}</div></div>')
        out.append('</div>')
        out.append(glossary.box("breadth"))
        out.append('</section>')

    # Money flow (flyttet opp)
    mf = data.get("money_flow", {})
    pairs = mf.get("pairs", []) if isinstance(mf, dict) else (mf or [])
    if pairs:
        verdict = ""
        if isinstance(mf, dict) and mf.get("state"):
            verdict = (f'<div class="explain" style="margin-bottom:10px;border-left-color:{mf["col"]}">'
                       f'<span class="ex-what" style="color:{mf["col"]};font-weight:700">Pengestrøm: {html.escape(mf["state"])}</span> '
                       f'<span class="ex-do">{html.escape(mf.get("note",""))}</span></div>')
        out.append('<section class="section"><h2>💧 Money flow &amp; likviditet</h2>'
                   '<p class="sub">Hvor strømmer kapitalen — risikovillig vs trygg havn. '
                   '3M/1M = ROC av forholdstallet; Over 50MA = ratio over 50-dagers snitt (daglig). '
                   'Risk-on krever begge positive.</p>'
                   + verdict + '<div class="sector-grid">')
        for f in pairs:
            o = f.get("over_50ma")
            ostr = "▲ over 50MA (daglig)" if o else ("▼ under 50MA (daglig)" if o is False else "50MA: n/a")
            r3 = f.get("roc_3m")
            r3s = f"{r3:+.1f}% 3M" if r3 is not None else "n/a"
            out.append(f'<div class="sc" style="border-color:{f["col"]}55">'
                       f'<div class="sc-name">{html.escape(f["label"])}</div>'
                       f'<div style="font-size:15px;font-weight:700;color:{f["col"]}">{html.escape(f["state"])} ({r3s})</div>'
                       f'<div class="sc-label" style="color:{f["col"]}">{ostr}</div>'
                       f'<div class="sc-label muted">{html.escape(f["note"])}</div></div>')
        out.append('</div>')
        out.append(glossary.box("money_flow"))
        out.append('</section>')

    # Sektor-rotasjon: hvor strømmer pengene på sjanger-nivå
    sf = data.get("sector_flow", {})
    flows = sf.get("flows", []) if isinstance(sf, dict) else []
    if flows:
        out.append('<section class="section"><h2>🔀 Sektor-rotasjon — hvor strømmer pengene</h2>'
                   f'<p class="sub">Hver sektor målt på relativ momentum mot bredt marked '
                   f'({html.escape(sf.get("baseline","ACWI"))}), priced relativt. Innstrømning øverst, '
                   'utstrømning nederst. ⚡ = akselererende (1M leder 3M).</p>'
                   '<table><thead><tr><th>Sektor</th><th>Retning</th>'
                   '<th style="text-align:right">1M</th><th style="text-align:right">3M</th></tr></thead><tbody>')
        for f in flows:
            r1 = f.get("roc_1m"); r3 = f.get("roc_3m")
            accel = " ⚡" if f.get("accel") else ""
            out.append(f'<tr><td><strong>{html.escape(f["display"])}</strong>{accel}</td>'
                       f'<td style="color:{f["col"]};font-weight:600">{html.escape(f["dir"])}</td>'
                       f'<td style="text-align:right;color:{f["col"]}">{r1:+.1f}%</td>'
                       f'<td style="text-align:right;color:{f["col"]};font-weight:600">{r3:+.1f}%</td></tr>')
        out.append('</tbody></table></section>')

    # 🌍 Kapitalstrøm (Armstrong-stil datapunkt)
    cf = data.get("capital_flows", {})
    if cf.get("destinations"):
        out.append('<section class="section"><h2>🌍 Kapitalstrøm — hvor internasjonal kapital søker seg</h2>'
                   '<p class="sub">Land/regioner rangert på relativ styrke <strong>målt i gull</strong> '
                   '(felles nøytral valuta) — proxy for hvor kapital strømmer. 3M/1M = ratio-ROC. '
                   '⚡ = akselererende (1M leder 3M). Pluss dollartrend og USA-konsentrasjon (SPY/ACWI). '
                   'Kun et datapunkt, ikke en tese alene.</p>')
        v = cf.get("verdict", "")
        vcol = cf.get("col", PALETTE["warn"])
        out.append(f'<div class="explain" style="border-left-color:{vcol};margin-bottom:8px">'
                   f'<span class="ex-what" style="color:{vcol};font-weight:700">{html.escape(v)}</span></div>')
        out.append('<table><thead><tr><th>Region</th><th style="text-align:right">1M</th>'
                   '<th style="text-align:right">3M (i gull)</th></tr></thead><tbody>')
        for d in cf["destinations"]:
            c = PALETTE["up"] if d["roc_3m"] > 0 else PALETTE["down"]
            acc = " ⚡" if d.get("accel") else ""
            r1 = f'{d["roc_1m"]:+.1f}%' if d.get("roc_1m") is not None else "–"
            out.append(f'<tr><td><strong>{html.escape(d["region"])}</strong>{acc}</td>'
                       f'<td style="text-align:right;color:{c}">{r1}</td>'
                       f'<td style="text-align:right;color:{c};font-weight:600">{d["roc_3m"]:+.1f}%</td></tr>')
        out.append('</tbody></table>')
        cards = []
        dd = cf.get("dollar")
        if dd:
            r3s = f' ({dd["roc_3m"]:+.1f}%)' if dd.get("roc_3m") is not None else ""
            cards.append(f'<div class="sc" style="border-color:{dd["col"]}55"><div class="sc-name">Dollartrend (UUP, 3M)</div>'
                         f'<div style="font-size:15px;font-weight:700;color:{dd["col"]}">{html.escape(dd["state"])}{r3s}</div></div>')
        uc = cf.get("us_concentration")
        if uc:
            cards.append(f'<div class="sc" style="border-color:{uc["col"]}55"><div class="sc-name">USA-konsentrasjon (SPY/ACWI, 3M)</div>'
                         f'<div style="font-size:15px;font-weight:700;color:{uc["col"]}">{html.escape(uc["state"])} ({uc["roc_3m"]:+.1f}%)</div></div>')
        if cards:
            out.append('<div class="sector-grid" style="margin-top:8px">' + "".join(cards) + '</div>')
        out.append(glossary.box("capital_flows"))
        out.append('</section>')

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

    # 📊 Hit-rate-validering (treffsikkerhet over tid)
    out.append(_hitrate_section(data.get("validation", {})))

    out.append(layout.foot())
    return "".join(out)


def _triage_view(data) -> str:
    """🎯 Hva bør jeg vurdere i dag — én fusjonert handlingsliste.
    Nye lavrisiko-entries, stretched/FOMO-exit-kandidater, og dine posisjoner."""
    assets = data.get("assets", {})
    uv = data.get("user_portfolio")
    roadmaps = data.get("roadmaps", {})

    entries, exits, holds_action = [], [], []
    for iid, a in assets.items():
        if a.get("missing_data"):
            continue
        sc = a.get("northstar_score", 0)
        sym = a.get("symbol_label", iid)
        # Nye lavrisiko-entries: høy score + breakout + ikke stretched + LT konstruktiv
        if sc >= 70 and a.get("breakout") and not a.get("stretched"):
            entries.append((sc, sym, iid, a.get("state_label", "")))
        # Exit-kandidater: stretched i FOMO-sonen
        if a.get("stretched") and a.get("st_state") != "bear":
            exits.append((a.get("dist36_w") or 0, sym, iid))

    # Dine posisjoner som krever handling
    if uv and uv.get("rows"):
        for r in uv["rows"]:
            if r["verdict"] in ("SKALER AV", "VURDER SKALER AV"):
                holds_action.append(r)

    if not (entries or exits or holds_action):
        return ('<section class="section"><h2>🎯 Hva bør jeg vurdere i dag</h2>'
                '<p class="sub">Ingen nye lavrisiko-entries, FOMO-exit-kandidater eller '
                'posisjons-varsler akkurat nå. Tålmodighet er en posisjon.</p></section>')

    parts = ['<section class="section" style="border:2px solid var(--good)">'
             '<h2>🎯 Hva bør jeg vurdere i dag</h2>'
             '<p class="sub">Fusjonert handlingsliste: nye lavrisiko-entries (NSBC: breakout + '
             'ikke stretched), FOMO-exit-kandidater, og dine posisjoner. '
             'Hver rad lenker til roadmap-nivåene. <strong>Ikke finansrådgivning.</strong></p>']

    if entries:
        entries.sort(reverse=True)
        parts.append(f'<h3 style="color:{PALETTE["up"]};margin-top:8px">▲ Nye lavrisiko-entries</h3>')
        for sc, sym, iid, state in entries[:8]:
            rm = roadmaps.get(iid, {}).get("nominal", {})
            tgt = ""
            if rm and rm.get("scenarios", {}).get("base", {}).get("target"):
                b = rm["scenarios"]["base"]
                pct = b.get("pct")
                pct_s = f' ({pct:+.0f}%)' if isinstance(pct, (int, float)) else ""
                tgt = f' <span class="muted">base-mål {b["target"]:g}{pct_s}</span>'
            parts.append(f'<div style="padding:3px 0"><strong>{html.escape(sym)}</strong> '
                         f'<span class="pill" style="background:{PALETTE["up"]}22;color:{PALETTE["up"]}">score {sc}</span> '
                         f'<span class="muted" style="font-size:12px">{html.escape(state)}</span>{tgt}</div>')

    if exits:
        exits.sort(reverse=True)
        parts.append(f'<h3 style="color:{PALETTE["warn"]};margin-top:10px">⚠ FOMO-sone (vurder å skalere av)</h3>')
        for dist, sym, iid in exits[:8]:
            parts.append(f'<div style="padding:3px 0"><strong>{html.escape(sym)}</strong> '
                         f'<span class="warn">stretched {dist:+.1f}% fra 36-MA</span> '
                         f'<span class="muted" style="font-size:12px">— høy risiko å gå inn, vurder profittsikring</span></div>')

    if holds_action:
        parts.append(f'<h3 style="color:{PALETTE["down"]};margin-top:10px">💼 Dine posisjoner</h3>')
        for r in holds_action:
            col = PALETTE["down"] if r["verdict"] == "SKALER AV" else PALETTE["warn"]
            parts.append(f'<div style="padding:3px 0;color:{col};font-weight:600">'
                         f'{html.escape(r["sym"])}: {html.escape(r["verdict"])} '
                         f'<span class="muted" style="font-weight:400">({html.escape(r["why"])}, '
                         f'{r["pnl_pct"]:+.1f}%)</span></div>')

    parts.append('</section>')
    return "".join(parts)


def _hitrate_section(val) -> str:
    """📊 Hit-rate-validering: når NSBC-score ≥70, hva ble fremtidig avkastning?"""
    if not val or not val.get("available"):
        reason = (val or {}).get("reason", "bygger opp historikk")
        snaps = (val or {}).get("snapshots", 0)
        return ('<section class="section"><h2>📊 Hit-rate-validering</h2>'
                f'<p class="sub">Treffsikkerhet måles fra akkumulert score-historikk: '
                f'«når score ≥ 70, hva ble fremtidig avkastning vs base-rate?» '
                f'Status: {html.escape(reason)} ({snaps} snapshots). '
                f'Statistikken blir meningsfull etter noen måneders daglige bygg.</p></section>')

    parts = ['<section class="section"><h2>📊 Hit-rate-validering</h2>',
             f'<p class="sub">{html.escape(val.get("signal",""))} — fremtidig avkastning vs '
             f'<strong>base-rate</strong> (alle perioder). Edge = signal minus base. '
             f'{html.escape(val.get("note",""))} ({val.get("snapshots")} snapshots.)</p>',
             '<table><thead><tr><th>Horisont</th><th style="text-align:right">Signal snitt</th>'
             '<th style="text-align:right">Base-rate</th><th style="text-align:right">Edge</th>'
             '<th style="text-align:right">Hit-rate</th><th style="text-align:right">n</th>'
             '<th>Tillit</th></tr></thead><tbody>']
    for h, r in val.get("horizons", {}).items():
        sig = r.get("signal"); base = r.get("base")
        if not sig or not base:
            continue
        edge = r.get("edge_mean")
        ecol = PALETTE["up"] if (edge or 0) > 0 else PALETTE["down"]
        conf = ('<span class="down">lav (n<20)</span>' if r.get("low_confidence")
                else '<span class="up">ok</span>')
        parts.append(f'<tr><td><strong>{h}</strong></td>'
                     f'<td style="text-align:right">{sig["mean"]:+.1f}%</td>'
                     f'<td style="text-align:right" class="muted">{base["mean"]:+.1f}%</td>'
                     f'<td style="text-align:right;color:{ecol};font-weight:700">{edge:+.1f} pp</td>'
                     f'<td style="text-align:right">{sig["hit_rate"]:.0f}%</td>'
                     f'<td style="text-align:right">{sig["n"]}</td>'
                     f'<td>{conf}</td></tr>')
    parts.append('</tbody></table>'
                 '<p class="sub" style="margin-top:8px">⚠ Databasen er ung — behandle lave-tillit-tall '
                 'som foreløpige. En positiv edge over base-rate, med n≥20, er det som teller — ikke '
                 'råtallet alene. Sizing bør ikke styres av et lite utvalg.</p></section>')
    return "".join(parts)


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


def _regime_card(title, label, col, note, explain_key=None):
    ex = glossary.box(explain_key) if explain_key else ""
    return (f'<div class="sc" style="border-color:{col}55">'
            f'<div class="sc-name">{html.escape(title)}</div>'
            f'<div style="font-size:15px;font-weight:700;color:{col}">{html.escape(label or "–")}</div>'
            f'<div class="sc-label muted">{html.escape(note or "")}</div>{ex}</div>')


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
def _dist_display(a) -> str:
    """Avstand fra 12 & 36 SMA, ukentlig OG månedlig — alltid med tidsramme.
    Farge: grønn nær/over, oransje strukket (>+10%), rød under."""
    dw = a.get("dist_w", {}) or {}
    dm = a.get("dist_m", {}) or {}

    def cell(val):
        if val is None:
            return '<span class="muted">n/a</span>'
        if val >= 10:
            c = PALETTE["warn"]      # strukket / FOMO
        elif val >= 0:
            c = PALETTE["up"]        # sunn, over snitt
        else:
            c = PALETTE["down"]      # under snitt
        return f'<span style="color:{c};font-weight:600">{val:+.1f}%</span>'

    return ('<div style="font-size:11.5px;margin:3px 0;color:var(--muted)">'
            'Avstand fra MA — '
            f'<strong>ukentlig:</strong> 12MA {cell(dw.get("d12"))} · 36MA {cell(dw.get("d36"))} &nbsp; '
            f'<strong>månedlig:</strong> 12MA {cell(dm.get("d12"))} · 36MA {cell(dm.get("d36"))} '
            '<span class="muted">(0% = ved snittet, +10% = strukket/FOMO-sone)</span></div>')


def render_report(data) -> str:
    P = layout.head("Market Daily Report", 2)
    out = [P, '<h1 id="top">📊 Market Daily Report</h1>',
           '<p class="sub">NSBC-score 0–100 (høyere = ekte lavrisiko-entry slik Northstar '
           'definerer det: <strong>ikke stretched fra 36-MA + nettopp brutt ut av base + over trend</strong>). '
           'Bygget på evidens-klynge: 12&amp;36 SMA, Ichimoku-sky (9/26/52), distance-fra-36MA, StochRSI og breakout — '
           'over ukentlig/månedlig/kvartal. Stretched pris i FOMO-sonen gir LAV score (høy risiko), ikke høy. '
           'LT = langtidsregime (M/Q), KT = korttidstiming (W) — du kan være bull på én og bear på en annen.</p>'
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
            lab, col = score_label(sc, a)
            gb = a.get("gold_beat")
            if gb is None:
                gb_html = '<span class="muted">vs gull: n/a</span>'
            else:
                roc3 = (gb.get("roc") or {}).get("3M")
                mans = gb.get("mansfield")
                mans_s = ""
                if mans is not None:
                    mc = PALETTE["up"] if mans > 0 else PALETTE["down"]
                    mans_s = f' · <span style="color:{mc}">Mansfield {mans:+.0f}</span>'
                if gb.get("beats"):
                    r3s = f" {roc3:+.1f}%" if roc3 is not None else ""
                    gb_html = (f'<span class="up">▲ slår gull (pris/gull-forhold,{" ".join(gb.get("tf_over") or [])}'
                               f'{r3s})</span>{mans_s}')
                else:
                    r3s = f" {roc3:+.1f}%" if roc3 is not None else ""
                    gb_html = f'<span class="down">▼ taper mot gull (3M{r3s})</span>{mans_s}'
            sym = a.get("symbol_label", iid)
            rm = a.get("risk", {})
            risk_str = ""
            if rm.get("vol") is not None:
                risk_str = (f'<span class="muted">vol {rm["vol"]:.0f}% · '
                            f'maxDD {rm["max_dd"]:.0f}% · Sharpe {rm["sharpe"]:.2f}</span>'
                            if rm.get("sharpe") is not None else
                            f'<span class="muted">vol {rm["vol"]:.0f}%</span>')
            # NSBC-tilstand + evidens-badges
            lt = a.get("lt_state"); st = a.get("st_state")
            def _sb(s):
                return ('<span class="up">bull</span>' if s == "bull"
                        else '<span class="down">bear</span>' if s == "bear"
                        else '<span class="muted">nøytral</span>')
            state_html = f'<span class="tag">LT {_sb(lt)} · KT {_sb(st)}</span>'
            ev = a.get("evidence", [])
            ticks = a.get("ticks", 0)
            ev_html = (f'<span class="tag" style="color:{PALETTE["good"]}">✓ {ticks} bevis</span>'
                       if ticks else "")
            # Stage-badge (Weinstein) — skiller nedtrend fra strukket
            stg = a.get("stage"); stg_lab = a.get("stage_label", "")
            stg_col = {4: PALETTE["down"], 3: PALETTE["warn"], 2: PALETTE["up"],
                       1: PALETTE["accent"]}.get(stg, PALETTE["muted"])
            stage_html = (f'<span class="pill" style="background:{stg_col}22;color:{stg_col}">{html.escape(stg_lab)}</span>'
                          if stg_lab else "")
            brk_html = ('<span class="pill" style="background:#0072B222;color:#0072B2">▲ breakout</span>'
                        if a.get("breakout") else "")
            ev_detail = (f'<div class="muted" style="font-size:11px;margin:2px 0">Evidens: {", ".join(ev)}</div>'
                         if ev else "")
            # Avstand fra 12 & 36 MA — ukentlig OG månedlig (alltid med tidsramme)
            dist_html = _dist_display(a)
            # Forklaring (stage-reason) i klartekst
            reason = a.get("stage_reason", "")
            reason_html = (f'<div class="explain"><span class="ex-what">{html.escape(reason)}</span> '
                           f'<span class="ex-do">→ {html.escape(glossary.detail("nsbc_score"))}</span></div>'
                           if reason else "")
            chart_id = f"ch_{iid}"
            chart_init.append({"el": chart_id, "series": a.get("price_series", []),
                               "nsbc": a.get("chart_nsbc", {})})
            out.append(
                f'<div class="section" style="margin:10px 0">'
                f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:baseline">'
                f'<h3>{html.escape(a.get("display_name", iid))}</h3>'
                f'<span class="tag">{html.escape(sym)}</span>'
                f'<span class="pill" style="background:{col}22;color:{col}">Score {sc} · {html.escape(lab)}</span>'
                f'{stage_html}{state_html}{ev_html}{brk_html}'
                f'{gb_html}'
                f'<a class="tv" href="{_tv(sym,"GLD")}" target="_blank" rel="noopener">📊 {html.escape(sym)}/GLD</a>'
                f'</div>'
                f'{ev_detail}{dist_html}{reason_html}'
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
  if(!el || !window.LightweightCharts) return;
  const n = c.nsbc || {};
  const hasNsbc = n.candles && n.candles.length > 20;
  const chart = LightweightCharts.createChart(el, {
    height: hasNsbc ? 300 : 240, layout:{background:{color:'transparent'}, textColor:'#9aa7b5'},
    grid:{vertLines:{color:'#1a1f26'}, horzLines:{color:'#1a1f26'}},
    rightPriceScale:{borderColor:'#262d36'}, timeScale:{borderColor:'#262d36'},
    crosshair:{mode:0}
  });
  if(hasNsbc){
    // Ichimoku-sky: tegn span A og B som linjer; fyll mellom via baseline-triks.
    // To area-serier (A topp, B bunn) gir en visuell sky.
    try {
      const cloudA = chart.addLineSeries({color:'rgba(0,158,115,0.55)', lineWidth:1, priceLineVisible:false, lastValueVisible:false});
      const cloudB = chart.addLineSeries({color:'rgba(213,94,0,0.55)', lineWidth:1, priceLineVisible:false, lastValueVisible:false});
      cloudA.setData((n.cloud_a||[]).map(p=>({time:'20'+p[0],value:p[1]})));
      cloudB.setData((n.cloud_b||[]).map(p=>({time:'20'+p[0],value:p[1]})));
    } catch(e){}
    // Candlesticks (kompakte nøkler t/o/h/l/c -> Lightweight Charts-format)
    const candle = chart.addCandlestickSeries({
      upColor:'#009E73', downColor:'#D55E00', borderVisible:false,
      wickUpColor:'#009E73', wickDownColor:'#D55E00'});
    candle.setData(n.candles.map(k=>({time:'20'+k.t, open:k.o, high:k.h, low:k.l, close:k.c})));
    // 12 & 36 SMA (NSBC Trend Navigator)
    const ma12 = chart.addLineSeries({color:'#56B4E9', lineWidth:1, priceLineVisible:false, lastValueVisible:false, title:'12'});
    const ma36 = chart.addLineSeries({color:'#E69F00', lineWidth:2, priceLineVisible:false, lastValueVisible:false, title:'36'});
    ma12.setData((n.sma12||[]).map(p=>({time:'20'+p[0],value:p[1]})));
    ma36.setData((n.sma36||[]).map(p=>({time:'20'+p[0],value:p[1]})));
  } else if(c.series && c.series.length) {
    const s = chart.addAreaSeries({lineColor:'#0072B2', topColor:'rgba(0,114,178,0.30)',
      bottomColor:'rgba(0,114,178,0.02)', lineWidth:2});
    s.setData(c.series.map(p => ({time:p[0], value:p[1]})));
  } else { return; }
  chart.timeScale().fitContent();
  new ResizeObserver(()=>chart.applyOptions({width:el.clientWidth})).observe(el);
}
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
    P = layout.head("Backtest", 5)
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

    # ── ANBEFALINGS-BACKTEST: "hvis alle anbefalinger var fulgt" ──
    rb = data.get("rec_backtest", {})
    out.append(_rec_backtest_section(rb))

    # ── LIVE anbefalings-logg: akkumulerer faktiske anbefalinger fremover ──
    out.append(_rec_log_section(data.get("rec_log")))

    out.append(layout.foot())
    return "".join(out)


def _rec_log_section(rl) -> str:
    if not rl or not rl.get("curve"):
        return ('<section class="section"><h2>📈 Live anbefalings-portefølje</h2>'
                '<p class="sub">Følger de faktiske kjøp-anbefalingene fra «I dag» framover i tid, '
                'likevektet. Kurven starter når historikken begynner å bygge seg opp — kom tilbake '
                'etter noen dager med kjøringer. Dette er forskjellig fra anbefalings-backtesten over, '
                'som rekonstruerer fortiden.</p></section>')
    curve = rl["curve"]
    val = curve[-1][1] if curve else 100
    ret = val - 100
    rcol = PALETTE["up"] if ret >= 0 else PALETTE["down"]
    parts = ['<section class="section" style="border:2px solid var(--up)">',
             '<h2>📈 Live anbefalings-portefølje (akkumulerer framover)</h2>',
             f'<p class="sub">Følger de faktiske kjøp-anbefalingene fra «I dag»-siden, likevektet, '
             f'fra oppstart {html.escape(rl.get("inception",""))}. Hver dag kjøpes nye anbefalinger og '
             f'de som faller ut selges. Indeksert til 100 ved start. '
             f'<strong>Forskjellig fra backtesten over</strong> — denne bygger seg opp i sanntid.</p>',
             f'<div style="font-size:24px;font-weight:700;color:{rcol};margin:6px 0">'
             f'{val:.1f} <span style="font-size:14px">({ret:+.1f}% siden start)</span></div>',
             f'<p class="muted" style="font-size:12px">{rl.get("n_active",0)} aktive posisjoner: '
             f'{html.escape(", ".join(rl.get("active",[])[:20]))}</p>']
    if len(curve) >= 2:
        parts.append('<div class="lwc" id="reclog_chart" style="height:300px"></div>')
        rser = [[c[0], c[1]] for c in curve]
        parts.append('<script>\nconst RECLOG = ' + json.dumps(rser) + ';\n'
                     '(function(){function initRL(){var el=document.getElementById("reclog_chart");'
                     'if(!el||!window.LightweightCharts)return;'
                     'var chart=LightweightCharts.createChart(el,{height:300,'
                     'layout:{background:{color:"transparent"},textColor:"#9aa7b5"},'
                     'grid:{vertLines:{color:"#1a1f26"},horzLines:{color:"#1a1f26"}},'
                     'rightPriceScale:{borderColor:"#262d36"},timeScale:{borderColor:"#262d36"}});'
                     'var s=chart.addAreaSeries({lineColor:"#009E73",topColor:"rgba(0,158,115,0.3)",'
                     'bottomColor:"rgba(0,158,115,0.02)",lineWidth:2});'
                     's.setData(RECLOG.map(function(p){return {time:p[0],value:p[1]};}));'
                     'chart.timeScale().fitContent();'
                     'new ResizeObserver(function(){chart.applyOptions({width:el.clientWidth});}).observe(el);}'
                     'if(window.LightweightCharts)initRL();else window.addEventListener("load",initRL);})();'
                     '\n</script>')
    # Nylige hendelser
    ev = rl.get("recent_events", [])
    if ev:
        parts.append('<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--accent)">'
                     'Nylige kjøp/salg</summary><table><thead><tr><th>Dato</th><th>Handling</th>'
                     '<th>Instrument</th></tr></thead><tbody>')
        for e in reversed(ev):
            ac = PALETTE["up"] if e["action"] == "KJØP" else PALETTE["down"]
            parts.append(f'<tr><td>{html.escape(e["date"])}</td>'
                         f'<td style="color:{ac};font-weight:600">{html.escape(e["action"])}</td>'
                         f'<td>{html.escape(e["id"])}</td></tr>')
        parts.append('</tbody></table></details>')
    parts.append('<p class="sub" style="margin-top:8px">Forenklet modell: likevektet, ingen '
                 'transaksjonskostnad, daglig verdsetting. Bygger ekte sporing av anbefalingene '
                 'over tid. <strong>Ikke finansrådgivning.</strong></p></section>')
    return "".join(parts)


def _rec_backtest_section(rb) -> str:
    if not rb or not rb.get("available"):
        reason = (rb or {}).get("reason", "ikke tilgjengelig")
        return ('<section class="section"><h2>📋 Anbefalings-backtest</h2>'
                f'<p class="sub">«Hvis alle NSBC-anbefalinger var fulgt» — {html.escape(reason)}.</p></section>')
    sysd, sp, g = rb["system"], rb["spy"], rb["gold"]
    parts = ['<section class="section" style="border:2px solid var(--accent)">',
             '<h2>📋 Anbefalings-backtest: «hvis alle anbefalinger var fulgt»</h2>',
             '<p class="sub">Dette er forskjellig fra rotasjons-regelen over. Her rekonstrueres '
             '<strong>NSBC-scoren punkt-for-punkt historisk</strong>, og porteføljen eier alle '
             f'instrumenter som var i konstruktiv tilstand (score ≥ {rb.get("score_threshold",60)}) '
             'OG slo gull 3M — likevektet, månedlig. Signal på månedsslutt → kjøp neste måned '
             '(ingen look-ahead), 15bps kostnad. '
             f'Periode {rb["start"]} → {rb["end"]} ({rb["months"]} mnd), snitt {rb["avg_holdings"]} posisjoner.</p>']
    parts.append('<table><thead><tr><th>Strategi</th><th style="text-align:right">CAGR</th>'
                 '<th style="text-align:right">Vol</th><th style="text-align:right">Sharpe</th>'
                 '<th style="text-align:right">Max DD</th></tr></thead><tbody>')
    for name, d, col in [("Anbefalingssystem", sysd, PALETTE["up"]),
                         ("Kjøp-og-hold SPY", sp, PALETTE["accent"]),
                         ("Kjøp-og-hold gull", g, PALETTE["warn"])]:
        parts.append(f'<tr><td style="color:{col};font-weight:600">{name}</td>'
                     f'<td style="text-align:right">{d.get("cagr","–")}%</td>'
                     f'<td style="text-align:right">{d.get("vol","–")}%</td>'
                     f'<td style="text-align:right">{d.get("sharpe","–")}</td>'
                     f'<td style="text-align:right" class="down">{d.get("max_dd","–")}%</td></tr>')
    parts.append('</tbody></table>')
    parts.append('<div class="lwc" id="recbt_chart" style="height:340px"></div>')
    # Ærlig vurdering
    sys_sharpe = sysd.get("sharpe") or 0
    spy_sharpe = sp.get("sharpe") or 0
    if rb.get("suspicious_lookahead"):
        verdict = ('<div class="warn" style="font-weight:600">⚠ Mistenkelig høy ytelse '
                   '(Sharpe>1,5 eller CAGR>15%) — kan tyde på residual look-ahead. Tolk med skepsis.</div>')
    elif sys_sharpe > spy_sharpe:
        verdict = (f'<div class="up" style="font-weight:600">✓ Anbefalingssystemet slår kjøp-og-hold SPY '
                   f'risikojustert (Sharpe {sys_sharpe} vs {spy_sharpe}).</div>')
    else:
        verdict = (f'<div style="font-weight:600;color:var(--warn)">Anbefalingssystemet slår IKKE kjøp-og-hold SPY '
                   f'risikojustert (Sharpe {sys_sharpe} vs {spy_sharpe}). Da bør det brukes som '
                   'beslutnings-støtte, ikke som mekanisk «bruk dette»-signal.</div>')
    parts.append(verdict)
    parts.append('<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--accent)">Metodikk &amp; forbehold</summary>'
                 '<p class="sub" style="margin-top:8px">NSBC-score beregnes kun på data t.o.m. forrige måned '
                 '(.iloc-snitt, ingen look-ahead). Signal på månedsslutt → fyll neste måned. Dette er en '
                 '<strong>simulering av mekanisk fulgte signaler</strong>, ikke en logg over faktisk gjennomførte '
                 'handler — reell diskresjonær timing ville avvike. Cash-avkastning antas 0%. '
                 '<strong>Ikke finansrådgivning.</strong></p></details>')
    parts.append('</section>')
    # chart-data
    rseries = {
        "sys": [[rb["dates"][i], sysd["curve"][i]] for i in range(len(rb["dates"]))],
        "spy": [[rb["dates"][i], sp["curve"][i]] for i in range(len(rb["dates"]))],
        "gold": [[rb["dates"][i], g["curve"][i]] for i in range(len(rb["dates"]))],
    }
    parts.append('<script>\nconst RECBT = ' + json.dumps(rseries) + ';\n'
                 '(function(){function initR(){var el=document.getElementById("recbt_chart");'
                 'if(!el||!window.LightweightCharts)return;'
                 'var chart=LightweightCharts.createChart(el,{height:340,'
                 'layout:{background:{color:"transparent"},textColor:"#9aa7b5"},'
                 'grid:{vertLines:{color:"#1a1f26"},horzLines:{color:"#1a1f26"}},'
                 'rightPriceScale:{borderColor:"#262d36"},timeScale:{borderColor:"#262d36"}});'
                 'var mk=function(d,c){var s=chart.addLineSeries({color:c,lineWidth:2});'
                 's.setData(d.map(function(p){return {time:p[0]+"-01",value:p[1]};}));};'
                 'mk(RECBT.sys,"#009E73");mk(RECBT.spy,"#56B4E9");mk(RECBT.gold,"#E69F00");'
                 'chart.timeScale().fitContent();'
                 'new ResizeObserver(function(){chart.applyOptions({width:el.clientWidth});}).observe(el);}'
                 'if(window.LightweightCharts)initR();else window.addEventListener("load",initR);})();'
                 '\n</script>')
    return "".join(parts)


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


# ── Roadmap-side (NSBC-stil auto-roadmaps) ────────────────────────
def render_roadmap(data) -> str:
    P = layout.head("Roadmaps", 3)
    roadmaps = data.get("roadmaps", {})
    assets = data.get("assets", {})
    out = [P, '<h1>🗺️ Roadmaps</h1>',
           '<p class="sub">Auto-genererte roadmaps i NSBC-stil: support/resistance, '
           'trend-kanal, mål (measured move + Fibonacci) og scenarioer (bull/base/bear) '
           'med invaliderings-nivå. Bygget fra ukentlig OHLC. '
           '<strong>Ikke finansrådgivning.</strong></p>']

    if not roadmaps:
        out.append('<section class="section"><p class="muted">Ingen roadmaps tilgjengelig ennå.</p></section>')
        out.append(layout.foot())
        return "".join(out)

    # Sorter etter score (sterkest oppsett først)
    order = sorted(roadmaps.keys(),
                   key=lambda i: -(assets.get(i, {}).get("northstar_score", 0)))

    # Toggle nominal/gull
    out.append('<div style="margin:8px 0"><button class="btn secondary" id="tgGold" '
               'onclick="toggleGold()">Vis priced-in-gold</button></div>')

    rm_charts = []
    for iid in order:
        entry = roadmaps[iid]
        a = assets.get(iid, {})
        sym = a.get("symbol_label", iid)
        score = a.get("northstar_score", "–")
        lab, col = score_label(score, a) if isinstance(score, int) else ("", PALETTE["muted"])
        nominal = entry.get("nominal", {})
        out.append(f'<section class="section roadmap-card" data-id="{iid}">')
        out.append(f'<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:baseline">'
                   f'<h2 style="margin:0">{html.escape(a.get("display_name", iid))}</h2>'
                   f'<span class="tag">{html.escape(sym)}</span>'
                   f'<span class="pill" style="background:{col}22;color:{col}">Score {score} · {html.escape(lab)}</span>'
                   f'<span class="muted" style="font-size:12px">{html.escape(a.get("state_label",""))}</span>'
                   f'</div>')
        # Tegnet roadmap-chart (candles + 12/36 MA + S/R + mål + scenarioer)
        chart = nominal.get("chart")
        if chart and chart.get("candles"):
            cid = f"rm_{iid}"
            rm_charts.append({"el": cid, "chart": chart})
            out.append(f'<div class="lwc" id="{cid}" style="height:340px"></div>')
            out.append('<div style="font-size:11px;color:var(--muted);margin:2px 0 6px">'
                       '🟦 12-MA · 🟧 36-MA · grønne linjer = motstand/mål · '
                       'røde linjer = støtte/invalidering (ukentlig)</div>')
        # Scenario-sammendrag (alltid synlig)
        out.append(f'<div class="rm-nominal">{_roadmap_scenarios(nominal)}</div>')
        # Detaljer i utvidbar seksjon (progressiv avsløring)
        out.append('<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--accent);font-size:13px">'
                   'Vis tall-detaljer (nivåer, kanal, fib)</summary>'
                   f'<div class="rm-nominal">{_roadmap_block(nominal, sym)}</div>')
        if entry.get("gold"):
            out.append(f'<div class="rm-gold" style="display:none">'
                       f'<p class="sub">Priced in gold ({html.escape(sym)}/GLD):</p>'
                       f'{_roadmap_block(entry.get("gold"), sym + "/GLD")}</div>')
        out.append('</details></section>')

    out.append('<script>function toggleGold(){'
               'var g=document.querySelectorAll(".rm-gold"),n=document.querySelectorAll(".rm-nominal");'
               'var show=g.length&&g[0].style.display==="none";'
               'g.forEach(e=>e.style.display=show?"block":"none");'
               'n.forEach(e=>e.style.display=show?"none":"block");'
               'document.getElementById("tgGold").textContent=show?"Vis nominell":"Vis priced-in-gold";}'
               '</script>')
    out.append(layout.lwc_script())
    out.append('<script>\n' + _roadmap_chart_js(rm_charts) + '\n</script>')
    out.append(layout.foot())
    return "".join(out)


def _roadmap_scenarios(rm) -> str:
    """Kompakt scenario-sammendrag (alltid synlig over detaljene)."""
    if not rm:
        return ""
    sc = rm.get("scenarios", {})
    last = rm.get("last")

    def row(name, d, color):
        t = d.get("target")
        if t is None:
            return ""
        p = d.get("pct")
        psign = f"{p:+.1f}%" if isinstance(p, (int, float)) else ""
        return (f'<div style="padding:2px 0"><span style="color:{color};font-weight:700">{name}</span> '
                f'<strong>{t:g}</strong> <span style="color:{color}">{psign}</span></div>')

    inval = rm.get("invalidation")
    inval_s = (f'<div style="padding:2px 0;color:{PALETTE["down"]}">⛔ Invalidering: <strong>{inval:g}</strong></div>'
               if inval else "")
    return ('<div style="display:flex;flex-wrap:wrap;gap:16px;margin:6px 0;font-size:13px">'
            + row("🟢 Bull", sc.get("bull", {}), PALETTE["up"])
            + row("⚪ Base", sc.get("base", {}), PALETTE["accent"])
            + row("🔴 Bear", sc.get("bear", {}), PALETTE["down"])
            + inval_s + '</div>')


def _roadmap_chart_js(charts) -> str:
    payload = json.dumps(charts)
    return """
const RMCHARTS = %s;
function mkRm(c){
  const el = document.getElementById(c.el);
  if(!el || !window.LightweightCharts) return;
  const d = c.chart;
  const chart = LightweightCharts.createChart(el, {
    height: 340, layout:{background:{color:'transparent'}, textColor:'#9aa7b5'},
    grid:{vertLines:{color:'#1a1f26'}, horzLines:{color:'#1a1f26'}},
    rightPriceScale:{borderColor:'#262d36'}, timeScale:{borderColor:'#262d36'}, crosshair:{mode:0}
  });
  const candle = chart.addCandlestickSeries({upColor:'#009E73', downColor:'#D55E00',
    borderVisible:false, wickUpColor:'#009E73', wickDownColor:'#D55E00'});
  candle.setData(d.candles.map(k=>({time:'20'+k.t, open:k.o, high:k.h, low:k.l, close:k.c})));
  const ma12 = chart.addLineSeries({color:'#56B4E9', lineWidth:1, priceLineVisible:false, lastValueVisible:false});
  const ma36 = chart.addLineSeries({color:'#E69F00', lineWidth:2, priceLineVisible:false, lastValueVisible:false});
  ma12.setData((d.sma12||[]).map(p=>({time:'20'+p[0],value:p[1]})));
  ma36.setData((d.sma36||[]).map(p=>({time:'20'+p[0],value:p[1]})));
  const lv = d.levels || {};
  const pl = (price,color,title,style)=>{ if(price==null) return;
    candle.createPriceLine({price:price, color:color, lineWidth:1,
      lineStyle:(style||2), axisLabelVisible:true, title:title}); };
  (lv.resistance||[]).forEach((r,i)=>pl(r,'#009E73','R'+(i+1)));
  (lv.support||[]).forEach((s,i)=>pl(s,'#D55E00','S'+(i+1)));
  pl(lv.bull,'#009E73','BULL',0);
  pl(lv.base,'#56B4E9','BASE',0);
  pl(lv.bear,'#D55E00','BEAR',0);
  pl(lv.invalidation,'#CC0000','⛔ INVAL',3);
  chart.timeScale().fitContent();
  new ResizeObserver(()=>chart.applyOptions({width:el.clientWidth})).observe(el);
}
const rio = new IntersectionObserver((entries,obs)=>{
  entries.forEach(e=>{ if(e.isIntersecting){ const c=RMCHARTS.find(x=>x.el===e.target.id);
    if(c){ mkRm(c); obs.unobserve(e.target);} } });
}, {rootMargin:'200px'});
RMCHARTS.forEach(c=>{ const el=document.getElementById(c.el); if(el) rio.observe(el); });
""" % payload


def _roadmap_block(rm, sym) -> str:
    if not rm:
        return '<p class="muted">For lite data.</p>'
    last = rm["last"]
    sc = rm["scenarios"]

    def level_row(name, sc_data, color):
        t = sc_data.get("target")
        p = sc_data.get("pct")
        if t is None:
            return ""
        psign = f"{p:+.1f}%" if p is not None else ""
        trig = sc_data.get("trigger")
        trig_s = f' <span class="muted">trigger {trig:g}</span>' if trig else ""
        return (f'<tr><td style="color:{color};font-weight:700">{name}</td>'
                f'<td style="text-align:right">{t:g}</td>'
                f'<td style="text-align:right;color:{color}">{psign}</td>'
                f'<td class="muted" style="font-size:11px">{html.escape(sc_data.get("note",""))}{trig_s}</td></tr>')

    rows = (level_row("🟢 BULL", sc["bull"], PALETTE["up"]) +
            level_row("⚪ BASE", sc["base"], PALETTE["accent"]) +
            level_row("🔴 BEAR", sc["bear"], PALETTE["down"]))

    # støtte/motstand-nivåer
    res = " · ".join(f'{r["price"]:g}' for r in rm.get("resistance", [])[:3]) or "–"
    sup = " · ".join(f'{s["price"]:g}' for s in rm.get("support", [])[:3]) or "–"
    chan = rm.get("channel") or {}
    r2 = chan.get("r2")
    trend_q = ("sterk" if (r2 or 0) > 0.7 else "moderat" if (r2 or 0) > 0.4 else "svak")
    inval = rm.get("invalidation")
    stretched = rm.get("stretched")

    extra = ""
    if stretched:
        extra = (f'<div class="warn" style="font-weight:600;margin:6px 0">'
                 f'⚠ Stretched fra 36-MA ({rm.get("dist36")}%) — IKKE et lavrisiko-entry (FOMO-sone)</div>')

    inval_s = f"{inval:g}" if inval else "–"
    return (
        f'<table style="margin-top:8px"><thead><tr><th>Scenario</th><th style="text-align:right">Mål</th>'
        f'<th style="text-align:right">Avstand</th><th>Kommentar</th></tr></thead><tbody>{rows}</tbody></table>'
        f'{extra}'
        f'<div class="kpi" style="margin-top:8px">'
        f'<div class="k"><div class="lbl">Pris nå</div><div class="val">{last:g}</div></div>'
        f'<div class="k"><div class="lbl">Motstand over</div><div class="val" style="font-size:14px">{res}</div></div>'
        f'<div class="k"><div class="lbl">Støtte under</div><div class="val" style="font-size:14px">{sup}</div></div>'
        f'<div class="k"><div class="lbl">Invalidering</div><div class="val" style="font-size:15px;color:{PALETTE["down"]}">{inval_s}</div></div>'
        f'<div class="k"><div class="lbl">Trend-kvalitet (R²)</div><div class="val" style="font-size:15px">{r2 if r2 is not None else "–"} <span class="muted" style="font-size:11px">{trend_q}</span></div></div>'
        f'</div>')
