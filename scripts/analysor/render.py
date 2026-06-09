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

    # Regime-stripe
    reg = data.get("regime", {})
    out.append('<section class="section"><h2>Makro-regime</h2>'
               '<p class="sub">NFTRH-kontekst: renteregime, Fed-likviditet og kredittspreader. '
               'Regime-score = andel risk-on-faktorer (yield-kurve positiv, likviditet inn, spreader stramme).</p>'
               '<div class="sector-grid">')
    comp = reg.get("composite")
    if comp:
        out.append(_regime_card("Samlet regime", comp.get("label"), comp.get("col"), comp.get("state", "")))
    for key, title in [("yield_curve", "Yield-kurve 2s10s"), ("term_spread_10y3m", "10y-3m spread"),
                       ("fed_liquidity", "Fed-likviditet"), ("credit_spread", "Kredittspread")]:
        r = reg.get(key)
        if r:
            out.append(_regime_card(title, r.get("label"), r.get("col"), r.get("note", "")))
    out.append('</div></section>')

    # Kapitalrotasjon
    rot = data.get("rotation")
    if rot:
        out.append('<section class="section"><h2>Kapitalrotasjon — hovedinstrumenter vs gull</h2>'
                   f'<p class="sub">{html.escape(rot["note"])} '
                   'Slår gull = positiv ROC på 1M eller 3M. Klikk 📊 for ratioen i TradingView.</p>')
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
                chips.append(f'<a class="tag" href="{_tv(it["sym"],"GLD")}" target="_blank" rel="noopener">'
                             f'{html.escape(it["sym"])} {tf} 📊</a>')
            out.append(f'<div style="margin:4px 0"><span class="{cls}" style="font-weight:600;font-size:12px">'
                       f'{icon} {lab}:</span> {" ".join(chips) or "<span class=muted>ingen</span>"}</div>')
        out.append('</div></section>')

    # Leadership ranking (vs gull + vs dollar)
    out.append('<section class="section"><h2>🏆 Leadership ranking (relativ styrke)</h2>'
               '<p class="sub">Sykliske instrumenter rangert etter vektet ROC mot gull og dollar. '
               'Leder = positiv ROC på 1M eller 3M (vises i Trend-kolonnen).</p>'
               '<div class="grid grid2">')
    out.append(_ranking_table(data.get("ranking_gold", {}), "🥇 vs Gull (GLD)", "GLD"))
    out.append(_ranking_table(data.get("ranking_dxy", {}), "💵 vs Dollar (UUP)", "UUP"))
    out.append('</div></section>')

    # Bredde
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

    # Money flow
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


def _regime_card(title, label, col, note):
    return (f'<div class="sc" style="border-color:{col}55">'
            f'<div class="sc-name">{html.escape(title)}</div>'
            f'<div style="font-size:15px;font-weight:700;color:{col}">{html.escape(label or "–")}</div>'
            f'<div class="sc-label muted">{html.escape(note or "")}</div></div>')


def _ranking_table(rk, title, den):
    rows = rk.get("rows", [])
    if not rows:
        return f'<div><h3>{title}</h3><p class="muted">Ingen data.</p></div>'
    out = [f'<div><h3>{title}</h3>',
           '<table><thead><tr><th>#</th><th>Ratio</th><th>Sjanger</th>'
           '<th style="text-align:right">1M</th><th style="text-align:right">3M</th>'
           '<th>Trend</th><th>TV</th></tr></thead><tbody>']
    for i, r in enumerate(rows, 1):
        tf = r.get("tf_over") or []
        trend = _arrow(r.get("beats"))
        if r.get("beats") and tf:
            trend = f'<span class="up">▲ Leder ({"+".join(tf)})</span>'
        out.append(f'<tr><td class="muted">{i}</td>'
                   f'<td><strong>{html.escape(r["label"])}/{den}</strong></td>'
                   f'<td class="muted">{html.escape(r.get("subclass",""))}</td>'
                   f'{_roc_cell(r.get("roc_1m"))}{_roc_cell(r.get("roc_3m"))}'
                   f'<td>{trend}</td>'
                   f'<td><a class="tv" href="{_tv(r["label"],den)}" target="_blank" rel="noopener">📊</a></td></tr>')
    out.append('</tbody></table></div>')
    return "".join(out)


# ── Market Daily Report ───────────────────────────────────────────
def render_report(data) -> str:
    P = layout.head("Market Daily Report", 1)
    out = [P, '<h1>📊 Market Daily Report</h1>',
           '<p class="sub">Northstar-score 0–100 (høyere = lavere risiko / bedre entry), '
           'snitt av RSI, MACD og MA-avstand over ukentlig/månedlig/kvartal. '
           'Sektorscore = snitt av medlemmenes score; trend = andel over 50MA (ukentlig).</p>']

    # Sektorscore
    sec = data.get("sector_summary", {})
    out.append('<section class="section"><h2>Sektorscore</h2><div class="sector-grid">')
    for s in sorted(sec.values(), key=lambda x: -x["avg_score"]):
        c = s["score_col"]
        tcol = s["trend_col"]
        out.append(f'<div class="sc" style="border-color:{c}55">'
                   f'<div class="sc-name">{html.escape(s["display"])}</div>'
                   f'<div class="sc-score" style="color:{c}">{s["avg_score"]}</div>'
                   f'<div class="sc-label" style="color:{c}">{html.escape(s["label"])}</div>'
                   f'<div class="sc-label" style="color:{tcol}">{html.escape(s["trend_txt"])} '
                   f'<span class="muted">({s["over_ma50"]}/{s["total_ma50"]} over 50MA)</span></div>'
                   f'<div class="sc-label muted">{s["n"]} instr.</div></div>')
    out.append('</div></section>')

    # Per-instrument
    out.append('<section class="section"><h2>Instrumenter</h2>'
               '<p class="sub">Sortert etter score. Hvert instrument viser om det slår gull '
               '(ROC 1M/3M) med lenke til TradingView, og en interaktiv prisgraf.</p>')
    assets = data["assets"]
    order = sorted([a for a in assets.values() if not a.get("missing_data")],
                   key=lambda a: -a.get("northstar_score", 0))
    chart_init = []
    for a in order:
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
    out.append('</section>')

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
