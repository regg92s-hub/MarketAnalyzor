"""
Portefølje-side: klientside-manager med kr-kostbasis-modell og daglig
rebalansering (verdi = kostbasis × dagens pris / inngangspris).

Rapportforbedringer innebygd:
  - Volatilitetsjustert posisjonsstørrelse (mål-vekt)
  - JSON eksport/import backup (mot datatap — størst reell risiko)
  - Valgfri Web Crypto AES-GCM-kryptering (PBKDF2) av lagret state
  - Risikometrikker per posisjon + portefølje (vol, maxDD, Sharpe)
  - Endringslogg med full historikk
"""
from __future__ import annotations
import json
from . import layout
from .config import (PALETTE, CASH_THRESHOLD, MAX_POSITIONS, OVERBOUGHT_RSI,
                     OVERBOUGHT_MACD, STRETCH_36, VOL_TARGET_ANNUAL)


def render_portfolio(data) -> str:
    P = layout.head("Portefølje", 2)
    # Data porteføljen trenger: per-instrument score, sektor, pris, risiko, sjanger-medvind
    pdata = {
        "version": data.get("version"),
        "generated": data.get("generated_local"),
        "assets": {},
        "genres": data.get("genre_strength", []),
        "fx": data.get("usdnok"),
        "regime": ((data.get("regime") or {}).get("composite") or {}).get("state"),
        "benchmarks": data.get("benchmarks"),
    }
    for iid, a in data["assets"].items():
        if a.get("missing_data"):
            continue
        pdata["assets"][iid] = {
            "name": a.get("display_name", iid),
            "sym": a.get("symbol_label", iid),
            "score": a.get("northstar_score"),
            "sector": "Råvarer" if a.get("sector") == "Rawarer" else a.get("sector", ""),
            "subclass": a.get("subclass", ""),
            "price": a.get("price_last"),
            "rsi": a.get("rsi_q"),
            "macd": a.get("macd_q"),
            "d36": a.get("d36_q"),
            "vol": (a.get("risk") or {}).get("vol"),
        }
    payload = json.dumps(pdata, ensure_ascii=False)

    body = P + """
<h1>💼 Portefølje</h1>
<p class="sub">Ditt eget regelbaserte rammeverk. To trinn: (1) sjanger-rangering finner sektorer
i medvind (≥70% slår gull og dollar), (2) lavrisiko-entry-instrumenter innenfor dem anbefales.
Verdien følger kursutviklingen daglig. <strong>Ikke finansrådgivning.</strong></p>

<section class="section">
  <h2>Kapital &amp; innstillinger</h2>
  <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">
    <div><label class="sub">Startkapital (kr)</label><br><input id="startCap" type="number" step="1000" value="100000"></div>
    <div><label class="sub">Nytt innskudd (kr)</label><br><input id="addCap" type="number" step="1000" placeholder="0"></div>
    <div><label class="sub">Cash-mål (%)</label><br><input id="cashTarget" type="number" step="1" value="15"></div>
    <div><label class="sub">Maks vekt/posisjon (%)</label><br><input id="maxPos" type="number" step="1" value="25"></div>
  </div>
  <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
    <button class="btn" id="applyCap">Oppdater</button>
    <button class="btn secondary" id="rebalance">Foreslå omfordeling</button>
    <button class="btn secondary" id="exportBtn">⬇ Eksporter backup</button>
    <button class="btn secondary" id="syncBtn">⬆ Synk til GitHub</button>
    <button class="btn secondary" id="importBtn">⬆ Importer backup</button>
    <input id="importFile" type="file" accept="application/json" style="display:none">
    <button class="btn secondary" id="encBtn">🔒 Kryptering</button>
  </div>
  <p class="sub" id="encStatus" style="margin-top:8px"></p>
</section>

<section class="section">
  <div class="kpi">
    <div class="k"><div class="lbl">Total kapital</div><div class="val" id="kTotal">–</div></div>
    <div class="k"><div class="lbl">Investert</div><div class="val" id="kInvested">–</div></div>
    <div class="k"><div class="lbl">Cash</div><div class="val" id="kCash">–</div></div>
    <div class="k"><div class="lbl">Cash %</div><div class="val" id="kCashPct">–</div></div>
    <div class="k"><div class="lbl">Portef.-trend (vektet score)</div><div class="val" id="kTrend">–</div></div>
    <div class="k"><div class="lbl">Andel i medvind</div><div class="val" id="kMedvind">–</div></div>
    <div class="k"><div class="lbl">Portef.-vol (est.)</div><div class="val" id="kVol">–</div></div>
    <div class="k"><div class="lbl">USDNOK</div><div class="val" id="kFx">–</div></div>
  </div>
</section>

<section class="section">
  <h2>🏆 Trinn 1: Sjanger-rangering</h2>
  <p class="sub">Score = % av instrumentene i sektoren som slår både gull og dollar (ROC 1M/3M).
  ≥70% = i medvind (blå ▲), 40–70% = avventende (oransje), ≤30% = nedadgående (vermillion ▼).</p>
  <div class="sector-grid" id="genreBox"></div>
</section>

<div class="grid grid2">
  <section class="section">
    <h2>🥧 Fordeling</h2>
    <p class="sub">Faktisk markedsverdi i dag (drifter med kurs). Cash-buffer holdes igjen.</p>
    <div id="pieWrap"></div>
    <div id="pieLegend" style="margin-top:10px"></div>
  </section>
  <section class="section">
    <h2>📝 Trinn 2: Posisjoner &amp; anbefaling</h2>
    <p class="sub">Skriv inn investert beløp (kr) — verdien endrer seg daglig med kursen, og
    andel + kake oppdateres automatisk. 0 = selg. KJØP/LEGG TIL kun i medvind-sjangrer.
    Volatilitetsjustert mål-vekt vises. SKALER AV sorteres over AVVENT.</p>
    <table id="posTable"><thead><tr><th>Instrument</th><th>Sjanger</th><th>Score</th>
      <th>Investert (kr)</th><th>Andel nå</th><th>Mål-vekt</th><th>Anbefaling</th></tr></thead>
      <tbody id="posBody"></tbody></table>
  </section>
</div>

<section class="section">
  <h2>📐 Realavkastning (fire spor)</h2>
  <p class="sub">Avkastningen din målt mot det som faktisk teller for en norsk investor:
  nominell NOK, <strong>real NOK</strong> (deflatert med norsk KPI), <strong>USD</strong>
  (uten valutaeffekt) og <strong>gull-unser</strong> (din baseline). Per posisjon brukes
  inngangsmåneden mot benchmark-seriene. Mangler KPI/FX-data, vises "ukjent".</p>
  <div id="realBox"></div>
</section>

<section class="section">
  <h2>📜 Endringslogg</h2>
  <p class="sub">Hvert kjøp, salg, justering, innskudd og omfordeling logges med tidspunkt —
  full historikk over alle endringer (lagret lokalt i nettleseren).</p>
  <div id="histBox" style="max-height:320px;overflow:auto;font-size:12px"></div>
  <button class="btn secondary" id="clearHist" style="margin-top:10px">Tøm logg</button>
</section>
"""
    body += layout.lwc_script()
    body += "<script>\nconst DATA = " + payload + ";\n" + _portfolio_js() + "\n</script>"
    body += layout.foot()
    return body


def _portfolio_js() -> str:
    tpl = r"""
const LS_KEY = "analysor_portfolio_v1";
const CASH_THRESHOLD = __CASH__, MAX_POSITIONS = __MAXPOS__, OVERBOUGHT_RSI = __OBRSI__,
      OVERBOUGHT_MACD = __OBMACD__, STRETCH_36 = __STRETCH__, VOL_TARGET = __VOLT__;

let STATE = null, CRYPTO_KEY = null;

// ---------- State load/save (med valgfri kryptering) ----------
function defaultState(){ return {startCap:100000, cash:100000, positions:{}, history:[], cashTarget:15, maxPos:25, encrypted:false}; }

async function loadState(){
  let raw = localStorage.getItem(LS_KEY);
  if(!raw){ STATE = defaultState(); return; }
  try {
    const obj = JSON.parse(raw);
    if(obj && obj.__enc){
      const pass = prompt("Passord for å låse opp porteføljen:");
      if(pass){ try { STATE = await decryptState(obj, pass); CRYPTO_KEY = pass; return; }
                catch(e){ alert("Feil passord — starter tom."); } }
      STATE = defaultState(); return;
    }
    STATE = obj;
  } catch(e){ STATE = defaultState(); }
}
async function saveState(){
  if(CRYPTO_KEY){ const enc = await encryptState(STATE, CRYPTO_KEY);
                  localStorage.setItem(LS_KEY, JSON.stringify(enc)); }
  else localStorage.setItem(LS_KEY, JSON.stringify(STATE));
}

// ---------- Web Crypto AES-GCM + PBKDF2 ----------
async function deriveKey(pass, salt){
  const enc = new TextEncoder();
  const base = await crypto.subtle.importKey("raw", enc.encode(pass), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({name:"PBKDF2", salt, iterations:200000, hash:"SHA-256"},
    base, {name:"AES-GCM", length:256}, false, ["encrypt","decrypt"]);
}
async function encryptState(state, pass){
  const enc = new TextEncoder();
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(pass, salt);
  const ct = await crypto.subtle.encrypt({name:"AES-GCM", iv}, key, enc.encode(JSON.stringify(state)));
  return {__enc:true, salt:[...salt], iv:[...iv], ct:[...new Uint8Array(ct)]};
}
async function decryptState(obj, pass){
  const key = await deriveKey(pass, new Uint8Array(obj.salt));
  const pt = await crypto.subtle.decrypt({name:"AES-GCM", iv:new Uint8Array(obj.iv)}, key,
    new Uint8Array(obj.ct));
  return JSON.parse(new TextDecoder().decode(pt));
}

// ---------- Helpers ----------
const kr = n => Math.round(n).toLocaleString("no-NO")+" kr";
const pct = n => n.toFixed(1)+"%";
const nowStr = () => new Date().toLocaleString("no-NO");
function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }
function priceOf(id){ const a=DATA.assets[id]; return (a && a.price>0)? a.price : null; }
function fxNow(){ return (DATA.fx && DATA.fx>0)? DATA.fx : null; }
// Verdi i NOK = kostbasis × (USD-prisutvikling) × (USDNOK-utvikling siden kjøp).
// Uten valutaleddet er kr-verdien feil for en norsk investor — USDNOK svinger 10-15%/år.
function valueOf(id){ const p=STATE.positions[id]; if(!p||!p.cost) return 0;
  const cur=priceOf(id); let v=p.cost;
  if(cur!=null && p.entryPrice) v = p.cost*(cur/p.entryPrice);
  const fx=fxNow();
  if(fx!=null && p.entryFx) v = v*(fx/p.entryFx);
  return v; }
function investedValue(){ return Object.keys(STATE.positions).reduce((s,id)=>s+valueOf(id),0); }
function totalValue(){ return STATE.cash + investedValue(); }
function owns(id){ const p=STATE.positions[id]; return !!(p&&p.cost>0); }
function ownPctOf(id){ const t=totalValue(); return t>0? valueOf(id)/t*100 : 0; }
function scoreColor(s){ if(s>=70)return '#0072B2'; if(s>=55)return '#56B4E9'; if(s>=40)return '#E69F00'; return '#D55E00'; }
function tvSymbol(s){ return ({BTC:'BTCUSD',ETH:'ETHUSD',ETHA:'ETHUSD',NOK:'USDNOK'})[s]||s; }
function logHist(msg){ STATE.history.unshift({t:nowStr(), msg}); if(STATE.history.length>500) STATE.history.pop(); }

// ---------- Sjanger / medvind ----------
function medvindGenres(){ return new Set((DATA.genres||[]).filter(g=>g.medvind).map(g=>g.genre)); }
function candidates(){
  const mv = medvindGenres(); const arr=[];
  Object.keys(DATA.assets).forEach(id=>{
    const a=DATA.assets[id]; if(a.score==null) return;
    arr.push({id, label:`${a.name} (${a.sym})`, ticker:a.sym, score:a.score,
      sector:a.sector, subclass:a.subclass, vol:a.vol, rsi:a.rsi, macd:a.macd, d36:a.d36,
      inMedvind:mv.has(a.sector)});
  });
  arr.sort((x,y)=>y.score-x.score); return arr;
}

// ---------- Mål-vekter (volatilitetsjustert) ----------
function targetWeights(cands){
  const cashTarget = clamp(parseFloat(document.getElementById("cashTarget").value)||15,0,100);
  const maxPos = clamp(parseFloat(document.getElementById("maxPos").value)||25,5,100);
  const investable = 100 - cashTarget;
  const elig = cands.filter(c=>c.score>=CASH_THRESHOLD && c.inMedvind).sort((a,b)=>b.score-a.score);
  const held = elig.filter(c=>owns(c.id)), fresh = elig.filter(c=>!owns(c.id));
  let chosen = held.slice(0,MAX_POSITIONS);
  for(const c of fresh){ if(chosen.length>=MAX_POSITIONS) break; chosen.push(c); }
  // volatilitetsjustert: vekt ~ (score-terskel) / vol  (invers-vol)
  const raw = {}; let sum=0;
  chosen.forEach(c=>{ const volFactor = (c.vol && c.vol>0)? (VOL_TARGET/(c.vol/100)) : 1;
    const w = Math.max(0,(c.score-CASH_THRESHOLD)) * clamp(volFactor,0.3,2.0);
    raw[c.id]=w; sum+=w; });
  const weights={};
  if(sum>0) chosen.forEach(c=>{ weights[c.id]=Math.min(investable*raw[c.id]/sum, maxPos); });
  return {weights, eligIds:new Set(chosen.map(c=>c.id))};
}

// ---------- Anbefaling ----------
function recommendation(c, ownPct, tgt, inElig){
  const rsi=c.rsi??50, macd=c.macd??0, d36=c.d36??0;
  const veryOB = rsi>=OVERBOUGHT_RSI && macd>=OVERBOUGHT_MACD && d36>=STRETCH_36;
  if(ownPct>0){
    if(veryOB) return {code:"SCALE",label:"SKALER AV",cls:"down",why:`Overkjøpt (RSI ${Math.round(rsi)}, strukket)`};
    if(c.score<35) return {code:"SCALE",label:"SKALER AV",cls:"down",why:"Score i negativ sone"};
    if(!c.inMedvind) return {code:"HOLD_WEAK",label:"HOLD (svak sjanger)",cls:"warn",why:`${c.sector} ikke i medvind — teknisk ok`};
    if(ownPct<tgt-3) return {code:"ADD",label:"LEGG TIL",cls:"up",why:"I medvind, under mål-vekt"};
    return {code:"HOLD",label:"HOLD",cls:"muted",why:"I medvind, behold"};
  }
  if(!c.inMedvind) return {code:"WAIT",label:"AVVENT",cls:"muted",why:`${c.sector} ikke i medvind`};
  if(c.score>=CASH_THRESHOLD && tgt>0) return {code:"BUY",label:"KJØP",cls:"up",why:`Medvind + score ${c.score}, lavrisiko entry`};
  if(c.score>=CASH_THRESHOLD && !inElig) return {code:"WAIT",label:"AVVENT",cls:"muted",why:`Maks ${MAX_POSITIONS} fylt`};
  return {code:"WAIT",label:"AVVENT",cls:"muted",why:`Score under ${CASH_THRESHOLD}`};
}

// ---------- Posisjonsendring (kr kostbasis + inngangspris + inngangs-FX) ----------
function setPosition(id, newCost){
  const cur=priceOf(id); const fx=fxNow(); const p=STATE.positions[id]; const old=(p&&p.cost)?p.cost:0;
  const a=DATA.assets[id]||{}; const name=`${a.name} (${a.sym})`;
  if(newCost<=0){ if(old>0){ const v=valueOf(id); STATE.cash+=v; delete STATE.positions[id];
    logHist(`SOLGT ${name} — frigjort ${kr(v)} (kostbasis ${kr(old)})`);} return; }
  if(old===0){
    // KJØPSSJEKKLISTE (disiplin før ny posisjon) + beslutningsjournal
    const mv = medvindGenres().has(a.sector);
    const rsi = a.rsi??50, ob = (rsi>=OVERBOUGHT_RSI);
    const check = `KJØPSSJEKK — ${name}\n`
      + `${mv?'✓':'✗'} Sjanger i medvind: ${a.sector}${mv?'':' (IKKE i medvind)'}\n`
      + `${(a.score>=CASH_THRESHOLD)?'✓':'✗'} Score ${a.score} (terskel ${CASH_THRESHOLD})\n`
      + `${ob?'✗ Overkjøpt (RSI '+Math.round(rsi)+')':'✓ Ikke overkjøpt (RSI '+Math.round(rsi)+')'}\n`
      + `Regime: ${DATA.regime||'ukjent'}\n\nGjennomføre kjøpet?`;
    if(!confirm(check)) return;
    const reason = prompt("Begrunnelse (valgfritt — lagres i journalen):") || "";
    STATE.positions[id]={cost:newCost, entryPrice:cur||null, entryFx:fx||null, opened:nowStr()};
    STATE.cash-=newCost;
    // Journal: hva + hvorfor + signal-snapshot (etterprøvbar beslutningskvalitet)
    logHist(`KJØPT ${name} for ${kr(newCost)} @ ${cur?cur.toFixed(2):"n/a"}`
      + (fx?` (USDNOK ${fx.toFixed(2)})`:"")
      + ` | score ${a.score}, ${a.sector}${mv?' i medvind':' IKKE i medvind'}, regime: ${DATA.regime||'?'}`
      + (reason?` | Begrunnelse: ${reason}`:""));
  }
  else { const diff=newCost-old;
    if(cur&&p.entryPrice&&diff>0){ const ov=valueOf(id);
      p.entryPrice=(ov+diff)/((ov/p.entryPrice)+(diff/cur)); }
    if(fx&&!p.entryFx) p.entryFx=fx;  // migrasjon: eldre posisjoner uten FX
    p.cost=newCost; STATE.cash-=diff;
    logHist(`JUSTERT ${name}: ${kr(old)} → ${kr(newCost)} (${diff>=0?'+':''}${kr(diff)})`); }
}

// ---------- Render ----------
function renderGenres(){
  const box=document.getElementById("genreBox");
  const gs=DATA.genres||[];
  if(!gs.length){ box.innerHTML='<p class="muted">Ingen sjanger-data.</p>'; return; }
  box.innerHTML = gs.map(g=>{
    const col = g.medvind? '#0072B2' : (g.strength>=40? '#E69F00':'#D55E00');
    const icon = g.medvind? '▲' : (g.strength>=40? '•':'▼');
    return `<div class="sc" style="border-color:${col}55">
      <div style="display:flex;justify-content:space-between"><strong>${g.rank}. ${g.genre}</strong>
      <span style="color:${col};font-weight:700;font-size:11px">${icon} ${g.state}</span></div>
      <div class="sc-score" style="color:${col}">${g.strength}<span style="font-size:12px" class="muted">% slår gull</span></div>
      <div class="muted" style="font-size:11px">${g.n} instr: ${g.members.join(", ")}</div></div>`;
  }).join("");
}

function render(){
  renderGenres();
  const cands=candidates(); const {weights, eligIds}=targetWeights(cands);
  const inv=investedValue(), total=STATE.cash+inv;
  document.getElementById("kTotal").textContent=kr(total);
  document.getElementById("kInvested").textContent=kr(inv);
  document.getElementById("kCash").textContent=kr(STATE.cash);
  document.getElementById("kCashPct").textContent= total>0? pct(STATE.cash/total*100):"–";

  // vektet trend + medvind-andel + portef.vol
  const byId={}; cands.forEach(c=>byId[c.id]=c);
  let ws=0,tw=0,mv=0,volSum=0;
  Object.keys(STATE.positions).forEach(id=>{ const v=valueOf(id), c=byId[id];
    if(v>0&&c){ ws+=c.score*v; tw+=v; if(c.inMedvind) mv+=v; if(c.vol) volSum+=c.vol*v; } });
  const ps= tw>0? Math.round(ws/tw):null;
  const te=document.getElementById("kTrend");
  if(ps==null){ te.textContent="–"; } else { const col= ps>=66?'#0072B2':ps>=45?'#E69F00':'#D55E00';
    te.innerHTML=`${ps}<span class="muted" style="font-size:12px"> / 100</span>`; te.style.color=col; }
  const me=document.getElementById("kMedvind");
  me.textContent= tw>0? pct(mv/tw*100):"–";
  document.getElementById("kVol").textContent = tw>0? (volSum/tw).toFixed(0)+"%" : "–";
  const fxe=document.getElementById("kFx");
  if(fxe) fxe.textContent = fxNow()? fxNow().toFixed(2) : "–";

  // tabell
  const ranked = cands.map(c=>{ const op=ownPctOf(c.id), tgt=weights[c.id]||0;
    return {c, op, tgt, rec:recommendation(c,op,tgt,eligIds.has(c.id))}; });
  const rank={BUY:0,ADD:1,HOLD:2,HOLD_WEAK:3,SCALE:4,WAIT:5};
  ranked.sort((a,b)=>{ const r=(rank[a.rec.code]??9)-(rank[b.rec.code]??9); return r!==0?r:b.c.score-a.c.score; });
  const body=document.getElementById("posBody"); body.innerHTML="";
  ranked.forEach(({c,op,tgt,rec})=>{
    const sc=scoreColor(c.score); const p=STATE.positions[c.id]; const cost=(p&&p.cost)?p.cost:0;
    const v=valueOf(c.id); const pnl= cost>0? (v-cost)/cost*100 : null;
    const pnlS= pnl==null? "" : ` <span class="${pnl>=0?'up':'down'}" style="font-size:10px">${pnl>=0?'+':''}${pnl.toFixed(1)}%</span>`;
    const tv=`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol(c.ticker))}`;
    const tr=document.createElement("tr");
    tr.innerHTML=`<td><strong>${c.label}</strong>${c.inMedvind?' <span class="up" style="font-size:10px">▲</span>':''}
      <a class="tv" href="${tv}" target="_blank" rel="noopener">📊</a></td>
      <td class="muted">${c.sector}</td>
      <td><span class="pill" style="background:${sc}22;color:${sc}">${c.score}</span></td>
      <td><input class="posinput" type="number" min="0" step="1000" value="${Math.round(cost)}" data-id="${c.id}" style="width:90px">
        <div class="muted" style="font-size:10px">verdi ${kr(v)}${pnlS}</div></td>
      <td>${op>0.05?op.toFixed(1)+"%":"–"}</td>
      <td>${tgt>0?tgt.toFixed(1)+"%":"–"}</td>
      <td><span class="${rec.cls}" style="font-weight:600">${rec.label}</span><br><span class="muted" style="font-size:11px">${rec.why}</span></td>`;
    body.appendChild(tr);
  });
  body.querySelectorAll(".posinput").forEach(inp=>inp.addEventListener("change",e=>{
    setPosition(e.target.dataset.id, Math.max(0,parseFloat(e.target.value)||0)); saveState(); render(); }));

  drawPie(byId); renderHist(); renderReal(); saveState();
}

function drawPie(byId){
  const inv=investedValue(), total=STATE.cash+inv;
  const slices=[];
  Object.keys(STATE.positions).forEach(id=>{ const v=valueOf(id); if(v>0){ const c=byId[id]||{};
    slices.push({label:(c.label||id), val:v, pct: total>0?v/total*100:0, col:scoreColor(c.score||50)}); }});
  slices.sort((a,b)=>b.val-a.val);
  slices.push({label:"Cash", val:STATE.cash, pct: total>0?STATE.cash/total*100:100, col:'#3a4452'});
  const size=240,r=110,cx=120,cy=120; let ang=-Math.PI/2,paths="";
  slices.forEach(s=>{ const a2=ang+(s.pct/100)*Math.PI*2;
    const x1=cx+r*Math.cos(ang),y1=cy+r*Math.sin(ang),x2=cx+r*Math.cos(a2),y2=cy+r*Math.sin(a2);
    const lg=(a2-ang)>Math.PI?1:0;
    if(s.pct>0.01) paths+=`<path d="M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${lg},1 ${x2},${y2} Z" fill="${s.col}" stroke="#0b0d10" stroke-width="2"></path>`;
    ang=a2; });
  document.getElementById("pieWrap").innerHTML=`<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${paths}</svg>`;
  document.getElementById("pieLegend").innerHTML = slices.filter(s=>s.pct>0.01).map(s=>
    `<div style="font-size:12px"><span style="display:inline-block;width:10px;height:10px;background:${s.col};border-radius:2px"></span>
     ${s.label}: <strong>${s.pct.toFixed(1)}%</strong> <span class="muted">(${kr(s.val)})</span></div>`).join("");
}

// ---------- Realavkastning (fire spor) ----------
function benchAt(series, ym){ // nærmeste verdi <= ym, ellers første
  if(!series||!series.length) return null;
  let v=null; for(const [d,val] of series){ if(d<=ym) v=val; else break; }
  return v!=null? v : series[0][1];
}
function monthKey(s){ // "12.06.2026, 14:30" eller ISO -> "YYYY-MM"
  if(!s) return null;
  const iso=s.match(/(\d{4})-(\d{2})/); if(iso) return `${iso[1]}-${iso[2]}`;
  const no=s.match(/(\d{2})\.(\d{2})\.(\d{4})/); if(no) return `${no[3]}-${no[2]}`;
  return null;
}
function renderReal(){
  const box=document.getElementById("realBox"); if(!box) return;
  const b=DATA.benchmarks;
  const ids=Object.keys(STATE.positions).filter(id=>(STATE.positions[id]?.cost||0)>0);
  if(!ids.length){ box.innerHTML='<p class="muted">Ingen posisjoner.</p>'; return; }
  if(!b||(!b.kpi_no&&!b.gold_usd)){ box.innerHTML='<p class="muted">Benchmark-data ukjent (KPI/gull mangler).</p>'; return; }
  let rows='<table><thead><tr><th>Instrument</th><th style="text-align:right">Nominell NOK</th>'
    +'<th style="text-align:right">Real NOK</th><th style="text-align:right">USD</th>'
    +'<th style="text-align:right">Gull-unser</th></tr></thead><tbody>';
  let aggCost=0, aggVal=0, aggUsdC=0, aggUsdV=0, aggOzC=0, aggOzV=0, aggRealC=0;
  ids.forEach(id=>{
    const p=STATE.positions[id]; const a=DATA.assets[id]||{}; const cur=priceOf(id);
    const cost=p.cost||0; const v=valueOf(id);
    const ym=monthKey(p.opened);
    // Nominell NOK
    const nom=(v/cost-1)*100;
    // USD: strip valutaeffekt (bruk kun prisutvikling)
    let usd=null, usdC=cost, usdV=cost;
    if(cur&&p.entryPrice){ usd=(cur/p.entryPrice-1)*100; usdC=cost; usdV=cost*(cur/p.entryPrice); }
    // Real NOK: deflater nominell med KPI-endring siden kjøp
    let real=null, realC=cost;
    const k0=benchAt(b.kpi_no,ym), k1=b.kpi_no?b.kpi_no[b.kpi_no.length-1][1]:null;
    if(k0&&k1){ const infl=k1/k0; real=((v/cost)/infl-1)*100; realC=cost*infl; }
    // Gull-unser: verdi i gull nå vs ved kjøp
    let oz=null, ozC=cost, ozV=v;
    const g0=benchAt(b.gold_usd,ym), g1=b.gold_usd?b.gold_usd[b.gold_usd.length-1][1]:null;
    if(g0&&g1){ const ozAtEntry=cost/g0, ozNow=v/g1; oz=(ozNow/ozAtEntry-1)*100; }
    aggCost+=cost; aggVal+=v;
    if(usd!=null){ aggUsdC+=usdC; aggUsdV+=usdV; }
    if(real!=null){ aggRealC+=realC; }
    if(oz!=null){ aggOzC+=(cost/g0); aggOzV+=(v/g1); }
    const cell=(x)=> x==null? '<td class="muted" style="text-align:right">ukjent</td>'
      : `<td class="${x>=0?'up':'down'}" style="text-align:right">${x>=0?'+':''}${x.toFixed(1)}%</td>`;
    rows+=`<tr><td><strong>${a.sym||id}</strong></td>${cell(nom)}${cell(real)}${cell(usd)}${cell(oz)}</tr>`;
  });
  const aNom=aggCost>0?(aggVal/aggCost-1)*100:null;
  const aReal=aggRealC>0?(aggVal/aggRealC-1)*100:null;
  const aUsd=aggUsdC>0?(aggUsdV/aggUsdC-1)*100:null;
  const aOz=aggOzC>0?(aggOzV/aggOzC-1)*100:null;
  const ac=(x)=> x==null?'<td class="muted" style="text-align:right">ukjent</td>'
    :`<td class="${x>=0?'up':'down'}" style="text-align:right;font-weight:700">${x>=0?'+':''}${x.toFixed(1)}%</td>`;
  rows+=`<tr style="border-top:2px solid var(--border)"><td><strong>Totalt</strong></td>${ac(aNom)}${ac(aReal)}${ac(aUsd)}${ac(aOz)}</tr>`;
  rows+='</tbody></table>';
  // NOWA-excess linje
  if(b.nowa!=null && aNom!=null){
    rows+=`<p class="sub" style="margin-top:8px">Mot risikofri (NOWA ${b.nowa.toFixed(2)}%): `
      +`<strong class="${aNom-b.nowa>=0?'up':'down'}">${(aNom-b.nowa)>=0?'+':''}${(aNom-b.nowa).toFixed(1)} pp</strong> `
      +`meravkastning mot å sitte i NOK-cash (forenklet, ikke tidsvektet).</p>`;
  }
  box.innerHTML=rows;
}

function renderHist(){
  const box=document.getElementById("histBox");
  if(!STATE.history.length){ box.innerHTML='<p class="muted">Ingen endringer ennå.</p>'; return; }
  box.innerHTML = STATE.history.map(h=>`<div style="padding:3px 0;border-bottom:1px solid #1a1f26">
    <span class="muted">${h.t}</span> — ${h.msg}</div>`).join("");
}

// ---------- Kapital / knapper ----------
function bind(){
  document.getElementById("applyCap").addEventListener("click",()=>{
    const start=parseFloat(document.getElementById("startCap").value)||0;
    const add=parseFloat(document.getElementById("addCap").value)||0;
    const inv=investedValue();
    if(start!==STATE.startCap && inv===0){ STATE.startCap=start; STATE.cash=start; logHist(`Startkapital satt til ${kr(start)}`); }
    if(add>0){ STATE.cash+=add; logHist(`Innskudd: ${kr(add)}`); document.getElementById("addCap").value=""; }
    STATE.cashTarget=clamp(parseFloat(document.getElementById("cashTarget").value)||15,0,100);
    STATE.maxPos=clamp(parseFloat(document.getElementById("maxPos").value)||25,5,100);
    saveState(); render();
  });
  document.getElementById("rebalance").addEventListener("click",()=>{
    // TRANCHET omfordeling (Newfound: "litt men ofte" mot timing-flaks):
    // ADD korrigerer 25% av avviket mot mål; KJØP åpner på halv målvekt;
    // SKALER AV selger alt (risikokontroll tranches ikke).
    const TRANCHE = 0.25;
    const cands=candidates(); const {weights,eligIds}=targetWeights(cands); const total=totalValue(); let ch=[];
    cands.forEach(c=>{ const op=ownPctOf(c.id), tgt=weights[c.id]||0;
      const rec=recommendation(c,op,tgt,eligIds.has(c.id)); const tgtKr=total*tgt/100;
      if(rec.code==="BUY"&&tgt>0&&!owns(c.id)){
        setPosition(c.id,Math.round(tgtKr*0.5)); ch.push(`KJØP ${c.label} (halv målvekt)`); }
      else if(rec.code==="ADD"){
        const v=valueOf(c.id); const gap=tgtKr-v;
        if(gap>500){ const cost=(STATE.positions[c.id]?.cost||0);
          setPosition(c.id,Math.round(cost+TRANCHE*gap)); ch.push(`LEGG TIL ${c.label} (1/4 av avviket)`); } }
      else if(rec.code==="SCALE"&&owns(c.id)){ setPosition(c.id,0); ch.push(`SKALER AV ${c.label}`); } });
    logHist(ch.length? "Tranchet omfordeling: "+ch.join(", ") : "Omfordeling: ingen endringer anbefalt");
    saveState(); render();
  });
  document.getElementById("clearHist").addEventListener("click",()=>{
    if(confirm("Tømme hele endringsloggen?")){ STATE.history=[]; saveState(); renderHist(); } });

  // Backup eksport/import (mot datatap)
  document.getElementById("exportBtn").addEventListener("click",()=>{
    const blob=new Blob([JSON.stringify(STATE,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob); const a=document.createElement("a");
    a.href=url; a.download=`analysor-portfolio-${new Date().toISOString().slice(0,10)}.json`;
    a.click(); URL.revokeObjectURL(url);
  });
  document.getElementById("importBtn").addEventListener("click",()=>document.getElementById("importFile").click());
  // Synk til GitHub: last ned portfolio.json for commit til docs/ (gjør porteføljen
  // synlig for daglig bygg -> Discord kan nevne DINE posisjoner). Ingen PAT i klient.
  document.getElementById("syncBtn").addEventListener("click",()=>{
    const payload={updated:new Date().toISOString(), positions:STATE.positions};
    const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob); const a=document.createElement("a");
    a.href=url; a.download="portfolio.json"; a.click(); URL.revokeObjectURL(url);
    alert("portfolio.json lastet ned.\n\nLegg den i docs/ i repoet (commit) for at det "
      +"daglige bygget skal se posisjonene dine og varsle på Discord når noe krever handling.\n\n"
      +"NB: docs/ er offentlig — posisjonene blir synlige. Hopp over dette hvis du vil holde dem private.");
  });
  document.getElementById("importFile").addEventListener("change",e=>{
    const f=e.target.files[0]; if(!f) return; const rd=new FileReader();
    rd.onload=()=>{ try{ const s=JSON.parse(rd.result);
      if(s&&s.positions){ STATE=s; logHist("Importert backup"); saveState(); render(); alert("Backup importert."); }
      else alert("Ugyldig backup-fil."); }catch(err){ alert("Kunne ikke lese filen."); } };
    rd.readAsText(f);
  });
  // Kryptering på/av
  document.getElementById("encBtn").addEventListener("click", async ()=>{
    if(CRYPTO_KEY){ if(confirm("Slå AV kryptering? State lagres i klartekst lokalt.")){
        CRYPTO_KEY=null; STATE.encrypted=false; await saveState(); updateEncStatus(); } return; }
    const p1=prompt("Velg passord for kryptering (kan ikke gjenopprettes om glemt):");
    if(!p1) return; const p2=prompt("Bekreft passord:");
    if(p1!==p2){ alert("Passordene matcher ikke."); return; }
    CRYPTO_KEY=p1; STATE.encrypted=true; await saveState(); updateEncStatus();
    alert("Kryptering på. Husk passordet — det finnes ingen gjenoppretting.");
  });
}
function updateEncStatus(){
  document.getElementById("encStatus").textContent = CRYPTO_KEY
    ? "🔒 Kryptering PÅ — state lagres AES-GCM-kryptert lokalt."
    : "🔓 Ikke kryptert. Backup anbefales uansett (mot datatap).";
}

(async function init(){ await loadState(); bind(); updateEncStatus(); render(); })();
"""
    return (tpl
            .replace("__CASH__", str(CASH_THRESHOLD))
            .replace("__MAXPOS__", str(MAX_POSITIONS))
            .replace("__OBRSI__", str(OVERBOUGHT_RSI))
            .replace("__OBMACD__", str(OVERBOUGHT_MACD))
            .replace("__STRETCH__", str(STRETCH_36))
            .replace("__VOLT__", str(VOL_TARGET_ANNUAL)))
