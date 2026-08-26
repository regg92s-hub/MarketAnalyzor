# market-analysor

Gull-relativt, regime-basert markeds-dashboard for personlig bruk. Etterfølgeren
til `market-daily-report`, bygget på nytt med forbedringene fra forbedringsrapporten:
ROC/momentum-signaler, risiko- og breddemetrikker, volatilitetsjustert
posisjonsstørrelse, interaktive Lightweight Charts, colorblind-trygg palett, og
hardere datatrygghet (CSP, selvhostede scripts, JSON-backup, valgfri kryptering).

> **Ikke finansrådgivning.** Dette er ditt eget regelbaserte rammeverk for å lese
> markedet. All analyse er relativ til gull (XAU) som baseline, etter
> Northstar & Badcharts (Kevin Wadsworth) og NFTRH (Gary Tanashian).

---

## Hva er nytt vs market-daily-report

| Område | Før (v8) | Nå (analysor) |
|---|---|---|
| Relativ styrke | 50MA-kryssing på ratio (krever 4–12 års historikk) | **Multi-horisont ROC/momentum** (1/3/6/12M) — fungerer for unge instrumenter |
| Risiko | ingen | **Vol, max drawdown, Sharpe, Sortino** per instrument |
| Bredde | ingen | **% over 50/200-dagers MA** for hele universet |
| Posisjonsstørrelse | score-vektet | **Volatilitetsjustert** (invers-vol mot 12% mål) |
| Regime | 2s10s, Fed | + **10y-3m spread, kredittspreader (HY OAS), samlet regime-score** |
| Grafer | matplotlib-PNG (300+ filer) | **Lightweight Charts** (interaktive, ~35 KB, lazy-lastet) |
| Farger | rød/grønn | **Okabe-Ito colorblind-trygg** (blå/oransje) + alltid ikon+tekst |
| Datatrygghet | localStorage rå | **CSP, selvhostede scripts, JSON eksport/import, valgfri AES-GCM-kryptering** |
| Portefølje | kr-kostbasis + daglig rebalansering | beholdt + risiko-KPI-er og vol-justert mål-vekt |
| Leadership-visning | to tabeller | + **RRG-scatter** (RS-Ratio/RS-Momentum, rotasjonsgraf) |
| Diversifisering | ingen | **Korrelasjonsmatrise** (252 dager, heatmap) |
| Troverdighet | påstått | **Walk-forward backtest** (dual momentum + vol-skalering) vs SPY/gull |
| Realavkastning | ingen | **Fire spor**: nominell NOK, real NOK (SSB KPI), USD, gull-unser + NOWA-excess |
| Makro-dybde | 6 faktorer | + **realrente (TIPS), breakeven, G3-likviditet, panikk-regime** (D&M) |
| Beslutning | spredt | **🎯 Beslutningsbilde** øverst: regime + tidslinje + endringer + dine posisjoner |
| Alpha | momentum | + **value-tilt** (Asness) og **panikk-demper** (Daniel & Moskowitz) |
| Automatisering | manuell | **paper-ledger** (regelen vs deg), **portfolio-synk**, **AI-morgenbrief** |
| App | nettside | **PWA**: installerbar hjemskjerm + offline (service worker) |

---

## Repo-struktur

```
market-analysor/
├── .github/workflows/analysor.yml   # daglig kjøring + deploy til gh-pages
├── requirements.txt
├── scripts/
│   ├── build.py                     # hovedbygg (kjør denne)
│   ├── backfill_history.py          # rekonstruerer score-historikk (valgfri)
│   └── analysor/                    # Python-pakke
│       ├── config.py                # instrument-univers, parametre, palett
│       ├── data.py                  # yfinance-henting + resampling
│       ├── indicators.py            # RSI/MACD/ROC + risikometrikker
│       ├── scoring.py               # Northstar-score (0–100)
│       ├── analytics.py             # leadership, sjanger, bredde, par, money flow, rotasjon
│       ├── regime.py                # makro-regime (FRED)
│       ├── backtest.py              # walk-forward backtest av rotasjonsregelen
│       ├── layout.py                # delt HTML/CSS/CSP
│       ├── render.py                # Trend-oversikt + Report + RRG + korrelasjon + Backtest
│       └── portfolio.py             # Portefølje (klientside, kryptering, backup)
└── docs/                            # genereres → deployes til gh-pages
    ├── index.html                   # 📈 Trend-oversikt (+ RRG + korrelasjon)
    ├── report.html                  # 📊 Market Daily Report
    ├── portfolio.html               # 💼 Portefølje
    ├── backtest.html                # 🧪 Backtest
    ├── index.json                   # all data (minifisert)
    └── lightweight-charts...js      # selvhostet (lastes ned i bygg)
```

---

## Oppsett (samme mønster som market-daily-report)

1. **Lag nytt repo** på GitHub, f.eks. `market-analysor`.
2. **Last opp alle filene** i denne mappen (behold strukturen).
3. **Settings → Pages**: sett Source = *Deploy from a branch*, branch = `gh-pages`, mappe = `/ (root)`.
   (Branchen `gh-pages` opprettes automatisk første gang workflowen kjører.)
4. **Settings → Secrets and variables → Actions**: legg til `FRED_API_KEY`
   (gratis nøkkel fra https://fredaccount.stlouisfed.org/apikeys). Uten den
   hoppes makro-regime-kortene over — alt annet virker.
   Valgfritt: `DISCORD_WEBHOOK_URL` for push-varsel ved signalendringer
   (Discord: Server Settings → Integrations → Webhooks → New Webhook → Copy URL).
   Varselet sendes kun når noe faktisk flipper (sjanger, slår-gull, regime, bredde).
   Valgfritt: `ANTHROPIC_API_KEY` for AI-generert norsk morgenbrief (Claude API).
   Modell kan settes med `ANTHROPIC_MODEL` (default claude-haiku-4-5 — koster
   brøkdeler av en øre per bygg). Briefen er strengt grunnet i beregnede signaler.
5. **Actions-fanen**: kjør *Market Analysor* manuelt én gang (`Run workflow`,
   force=true). Den bygger og deployer.
6. Siden ligger på `https://<bruker>.github.io/market-analysor/`.

Workflowen kjører deretter daglig 19:50 Oslo-tid.

---

## Kjøre lokalt

```bash
pip install -r requirements.txt
python scripts/build.py          # skriver til docs/
# åpne docs/index.html i nettleser (kjør en lokal server for at fetch skal virke):
cd docs && python -m http.server 8000   # -> http://localhost:8000
```

> Merk: porteføljesiden bruker `localStorage` per nettleser/maskin. Bruk
> **⬇ Eksporter backup** jevnlig — det er den viktigste beskyttelsen mot datatap.

---

## Metodikk kort

**Slår gull / dollar.** Et instrument "slår" baseline hvis ratioen mot gull (eller
dollar) har **positiv ROC på 1M eller 3M**. Momentum-basert, så det krever ikke
lang historikk slik en 50MA-på-ratio gjorde.

**Northstar-score (0–100).** Høyere = lavere risiko / bedre entry. Snitt av RSI,
MACD-retning og MA-avstand over ukentlig/månedlig/kvartal.

**Sjanger-rangering.** Sektor-score = % av medlemmene som slår både gull og dollar.
≥70% = i medvind, ≤30% (dvs. 70%+ taper) = nedadgående, ellers avventende.

**Portefølje (to trinn).** (1) Finn sektorer i medvind. (2) Innenfor dem, anbefal
lavrisiko-entry-instrumenter etter score, med volatilitetsjustert mål-vekt. Posisjoner
føres i kr kostbasis; verdien drifter daglig med kursen (kostbasis × dagens pris /
inngangspris), så kake og andeler oppdateres automatisk.

---

## Viktige forbehold

- **Backtest ≠ fremtid.** Scoren og rotasjonsregelen er ikke out-of-sample-validert
  ennå (se rapportens Stage 3). Behandle alt som beslutnings*støtte*, ikke signaler
  å handle mekanisk på. Momentum kan krasje hardt i skarpe vendinger etter bear-marked.
- **Kryptering beskytter ikke mot XSS** i en kjørende side — den beskytter data i ro
  (delt maskin). CSP + selvhostede scripts er forsvaret mot XSS. Ta backup uansett.
- **50-perioders signaler** er erstattet med ROC nettopp fordi de krevde for lang
  historikk; men ROC har egne svakheter (whipsaw i sidelengs marked). Les begge
  tidsrammer (1M og 3M) sammen.

## v5: Realavkastning, dyp makro, semi-automatisering

**Realavkastning (fire spor).** Porteføljesiden viser nå avkastning i fire mål samtidig:
nominell NOK, real NOK (deflatert med norsk KPI fra SSB), USD (uten valutaeffekt) og
gull-unser. Pluss en NOWA-excess-linje (meravkastning mot NOK-cash). Krever ingen
oppsett — henter SSB KPI (PxWebApi v2) og Norges Bank USDNOK/NOWA automatisk og gratis.
SSB byttet KPI-tabell i 2026 (ny COICOP, basisår 2025=100); tabell-ID kan overstyres med
miljøvariabelen `SSB_KPI_TABLE` hvis SSB endrer igjen.

**Dyp makro.** Regimet har fått realrente (10y TIPS), inflasjonsforventning (10y breakeven),
G3-sentralbanklikviditet (Fed+ECB+BoJ i USD) og et panikk-regime (Daniel & Moskowitz:
bear + høy vol = momentum-krasj-fare). G3-likviditet hadde ~1 kvartals ledelse historisk,
men brøt sammen 2023–25 — vektes deretter.

**Beslutningsbilde.** Øverst på Trend-oversikt: samlet regime, momentum-regime, endringsteller,
benchmark-snapshot (norsk KPI, US CPI, USDNOK, NOWA), en regime-tidslinje (fargestripe over
tid), dine posisjoner som krever handling, og "regelen vs deg".

**Paper-ledger ("regelen vs deg").** En hypotetisk portefølje som mekanisk følger
rotasjonsregelen (momentum + value, månedlig rebalansering), verdsatt daglig i NOK. Speil
for din egen disiplin. State i `docs/paper_ledger.json`.

**Portefølje-synk.** "⬆ Synk til GitHub" laster ned `portfolio.json` du kan committe til
`docs/`. Da ser det daglige bygget posisjonene dine og Discord-varselet kan si "SPY: SKALER AV".
NB: `docs/` er offentlig — posisjonene blir synlige. Hopp over hvis du vil holde dem private.

**AI-morgenbrief.** Med `ANTHROPIC_API_KEY` skriver Claude en ~200-ords norsk kommentar i
hvert bygg, strengt grunnet i de beregnede tallene (ingen egne tall, sier "ukjent" ved
manglende data). Degraderer til ingenting uten nøkkel.

**PWA.** Siden er nå installerbar på hjemskjerm (manifest + ikoner) og fungerer offline
(service worker: network-first for data, cache-first for resten). Push krever server, så
Discord forblir varselkanalen.

> Verdiavhengige forbehold: backtest ≠ fremtid; dual momentum gir nedsidebeskyttelse, ikke
> bull-meravkastning; makro-relasjoner (særlig global likviditet) er ustabile; value-tilt og
> panikk-demper er evidensbaserte men ingen garanti. **Ikke finansrådgivning.**

## v6: NSBC-korrigert score, roadmaps og hit-rate-validering

Denne versjonen retter opp den viktigste feilen og bygger to nye analyse-motorer,
basert på et grundig studium av Northstar & Badcharts' egne dokumenter.

**Korrigert NSBC-score (viktigst).** Den gamle scoren brukte RSI + MACD og belønnet
*oversold* (lav RSI = "god entry") — stikk i strid med NSBCs metode. NSBC bruker
**ikke MACD**. Deres faktiske system er en evidens-klynge: **12 & 36 SMA Trend
Navigator** (over begge = bull), **Ichimoku-sky 9/26/52** (over sky = bull),
**distance-fra-36MA** (0 = nøytral, +10 % = stretched/FOMO-sone), **Stochastic RSI**,
og **breakout fra konsolidering**. NSBCs definisjon av lavrisiko-entry er: *«ikke
stretched fra langtids-MA OG nettopp brutt ut av en base/konsolidering»*. Scoren
teller nå tente bevis, straffer stretched pris hardt (FOMO = høy risiko, ikke lav),
og skiller **langtidsregime (M/Q)** fra **korttidstiming (W)** — du kan være LT bull
og KT bear samtidig. Daily Report viser nå LT/KT-tilstand, evidens-badges, breakout-
og stretched-merker per instrument.

**🗺️ Roadmaps-fane (ny).** Auto-genererte roadmaps i NSBC-stil for hele universet:
support/resistance fra klustrede swing-pivoter, trend-kanal med R² (trend-kvalitet),
mål via measured move (AB=CD) og Fibonacci-extension, og scenarioer (bull/base/bear)
hver med et **invaliderings-nivå** («line in the sand»). Kan vises både nominelt og
**priced-in-gold**. Bygget fra ukentlig OHLC.

**📊 Hit-rate-validering (ny).** Fra akkumulert score-historikk: «når NSBC-score ≥ 70,
hva ble fremtidig 1/3/6-måneders avkastning — og hvor ofte var den positiv?» Vises
alltid mot **base-rate** (alle perioder); edge = differansen. Streng metodikk: ingen
look-ahead, n vises alltid, n<20 flagges «lav tillit». Inkluderer en kvart-Kelly-
guide som først aktiveres ved stort nok utvalg. Score-historikk lagres daglig i
`docs/history/score_history.json` og bygger seg opp over tid.

**🎯 Triage-visning (ny, øverst på Trend).** Én fusjonert handlingsliste: nye
lavrisiko-entries (breakout + ikke stretched), FOMO-exit-kandidater (stretched fra
36-MA), og dine posisjoner som krever handling — hver med roadmap-mål. «Hva bør jeg
vurdere i dag» på én skjerm.

Nye moduler: `roadmap.py`, `validation.py`. Omskrevet: `scoring.py` (NSBC-metode),
`data.py` (OHLC for Ichimoku/S/R), `indicators.py` (Ichimoku, StochRSI, Trend
Navigator, support/resistance, breakout). Ny fane i navigasjonen: 🗺️ Roadmaps.

> Forbehold: NSBCs eksakte numeriske terskler (StochRSI-bånd, distance-bånd) er
> medlemsinnhold — strukturen er gjengitt tro mot dokumentene, men båndverdiene er
> parametre å kalibrere mot din egen validering. Hit-rate-databasen er ung; de fleste
> tall er foreløpige i starten. **Ikke finansrådgivning.**

## v7: Stage-analyse (fikser crypto-feilen), forklaringer i hver boks, SMA-avstand

Denne versjonen retter feilen du fant og bygger forklaringssystemet.

**Stage-analyse (Weinstein) — fikser "stretched"-feilen.** Den viktigste rettelsen:
en lav score kunne før få etiketten "Høy risiko / stretched" selv om instrumentet var
i NEDTREND (ikke strukket i det hele tatt). Nå klassifiseres hvert instrument i en
Weinstein-fase: **Stage 1 basing, Stage 2 opptrend, Stage 3 distribusjon, Stage 4
nedtrend**. Strukket/FOMO er nå korrekt en under-tilstand av Stage 2 (opptrend, men
for langt over 36-MA) — aldri det samme som Stage 4 (nedtrend, under fallende MA).
Crypto i nedtrend viser nå "Nedtrend (Stage 4)" med forklaring "ingen bullish bevis",
ikke "stretched". Gjelder både enkeltinstrumenter og sektorscore.

**Forklaring i hver boks.** Et nytt sentralt forklaringssystem (`glossary.py`) gir en
kort klartekst under hver boks: hva betyr "Risk-on 80/100"? → "Makrobildet favoriserer
risiko: flertallet av motorene er positive. Historisk medvind for aksjer/krypto." Hver
makro-boks, score og nøkkeltall har nå en "hva betyr dette → hva bør jeg gjøre"-linje.

**SMA-avstand med tidsramme.** Under hvert instrument i Daily Report vises nå avstand
fra **både 12 og 36 MA, på både ukentlig og månedlig** — fargekodet (grønn over snitt,
oransje strukket >+10%, rød under). Dette er NSBCs distance-gauge.

**Alltid merket tidsramme.** Alle "over/under MA"-bobler oppgir nå tidsrammen eksplisitt
("71% over 30-ukers MA (ukentlig)") — rapportkrav om at ingen boble skal stå uten
tidsramme.

**"Slår gull" verifisert + Mansfield RS.** Bekreftet at beats-gull bruker korrekt
ratio-metode (ROC av pris/gull-forholdet, ikke differanse av to ROC-er). Lagt til
**Mansfield relativ styrke** (ratio normalisert mot eget 52-ukers snitt) — NSBC-native
nullinje-test. Vises ved siden av slår-gull.

> Gjenstår fra rapporten (planlagt): indikatorer tegnet PÅ chartene (Ichimoku-sky, MA-er,
> sub-paneler), roadmaps som annoterte charts, anbefalings-backtest ("hvis alle signaler
> var fulgt"), flere instrumenter (sektorer, land, renter, faktorer, trend-sleeve), og
> global bredde-måler. **Ikke finansrådgivning.**

## v8: 62 instrumenter, indikatorer på charts, roadmap-charts, anbefalings-backtest

Denne versjonen bygger ut de fire store ønskene.

**Flere instrumenter (33 → 62).** Lagt til hele Select Sector SPDR-settet (XLK, XLF,
XLV, XLI, XLY, XLP, XLU, XLB, XLRE, XLC), land/regioner (EWJ Japan, EWG Tyskland, EWU,
EWC, EWA, EWZ Brasil, INDA India, FXI Kina), renter/kreditt (IEF, SHY, LQD, EMB, TIP,
BIL), faktorer (MTUM, VLUE, QUAL, USMV) og en managed futures-trend-sleeve (DBMF). Alle
store, likvide, lang historikk. Ny **global bredde-måler**: % av land+sektorer over
200-dagers MA — et kjent regime-filter.

**Northstar-indikatorer på chartene.** Daily Report-chartene tegner nå candlesticks +
12 & 36 SMA (Trend Navigator) + Ichimoku-sky (9/26/52) — beregnet i pandas og sendt som
serier (unngår risikabel v5-migrering av chart-biblioteket).

**Roadmaps som tegnede charts.** Hver roadmap viser nå et annotert candlestick-chart med
12/36 MA, støtte/motstand som prislinjer, og bull/base/bear-mål + invaliderings-nivå
tegnet som horisontale linjer. Tall-detaljer er flyttet til en utvidbar seksjon
(progressiv avsløring).

**Anbefalings-backtest.** Ny seksjon på Backtest-fanen: «hvis alle NSBC-anbefalinger var
fulgt». Rekonstruerer NSBC-scoren punkt-for-punkt historisk (ingen look-ahead), eier alle
instrumenter i konstruktiv tilstand som slår gull 3M, og sammenligner mot kjøp-og-hold
SPY/gull med tre ekvitykurver. Inkluderer ærlig verdikt (slår den SPY risikojustert eller
ikke?) og et røkt-flagg hvis ytelsen er mistenkelig høy (mulig look-ahead).

Ytelse: anbefalings-backtesten precomputer månedlige score-serier vektorisert (~3s i
stedet for å re-score hver måned). index.json holdes liten ved å stripe chart-data
(kun HTML-sidene embedder dem). Sidene gzipper godt (report ~300KB over nett).

> Forbehold: anbefalings-backtesten er en SIMULERING av mekanisk fulgte signaler, ikke en
> logg over faktiske handler — reell diskresjonær timing vil avvike. Den månedlige
> score-proxyen i backtesten er litt forenklet vs. den fulle daglige NSBC-scoren (samme
> ånd: 12&36 SMA + Ichimoku + ikke stretched). **Ikke finansrådgivning.**

## v9: Ny "🎯 I dag"-landingsside med kommando-bånd og sorterbar leaderboard

Denne versjonen strukturerer dataen i tre lag så det viktigste flagges øverst, mens
alle detaljer fortsatt er tilgjengelige ved å bla eller bytte fane.

**Ny default-fane "🎯 I dag".** Erstatter Trend-oversikt som landingsside (den gamle
trend-siden ligger nå på trend.html, fortsatt med full dybde). Tre lag:

*Lag 1 — Kommando-bånd (én skjerm):* én makro-verdikt-linje på toppen, så tre kolonner —
**Kjøp-kandidater** (instrumenter i ekte lavrisiko-entry med sjanger- og makro-medvind),
**Skaler av / unngå** (stretched FOMO eller Stage 4 nedtrend), og **Dine posisjoner**
som krever handling. Svaret på "hva gjør jeg i dag" uten å bla.

*Lag 2 — Sorterbar leaderboard:* hele universet (62 instrumenter) i ett rutenett. Klikk
en hvilken som helst kolonne for å sortere — kompositt, score, stage, slår-gull,
Mansfield, 3M-momentum, avstand-fra-36MA. Farget grønn→rød, med sparklines. Klikk
symbol for å hoppe til detaljer i Daily Report.

*Lag 3 — Detaljer:* per-instrument-charts, roadmaps, korrelasjon osv. ligger fortsatt på
sine respektive faner, nå demotert under landingssiden.

**Vekt-av-bevis-rangering (Northstar-filosofi).** Kompositt-scoren = NSBC-score ×
sjanger-medvind × makro-regime. Et instrument flyter til toppen bare når DETS oppsett,
DETS sjanger OG makrobildet alle peker samme vei. En sterk graf i en svak sjanger eller
i risk-off-makro rabatteres deretter — akkurat slik Northstar vekter bevis på tvers av
tidsrammer, sjanger og makro.

Ny modul: `today.py` (rangerings-motoren). Sorteringen skjer klientside i ren JS (ingen
rammeverk). Landingssiden er ~15KB gzipped. **Ikke finansrådgivning.**

## v10: Money flow som førsteklasses signal

Pengestrøm — hvor kapitalen faktisk strømmer — er nå et sentralt signal, ikke begravd.

**Utvidet money flow (3 → 7 par).** La til syklisk vs defensiv (XLY/XLP), småselskaper
vs store (IWM/SPY), kreditt vs stat (LQD/IEF) og halvleder-ledelse (SOXX/SPY) i tillegg
til de eksisterende (kreditt-appetitt, kobber/gull, EM-ledelse). Samlet pengestrøm-verdikt
(risk-on / blandet / risk-off) basert på hvor mange par som peker mot risiko vs trygghet.

**Ny sektor-rotasjon.** Egen tabell som rangerer alle 11 sjangre på relativ momentum mot
bredt marked (ACWI) — innstrømning øverst, utstrømning nederst, med ⚡ for akselererende
strøm (1M leder 3M). Viser rotasjonsbildet på ett blikk.

**Pengestrøm på I dag-siden.** Kommando-båndet har nå en egen pengestrøm-stripe: samlet
retning + hvilke sektorer kapital strømmer INN i vs UT av. Verdikt-linjen nevner også
pengestrøm-tilstanden. Slik ser du umiddelbart om trenden støttes av kapitalflyt.

**Ikke finansrådgivning.**

## v11: Historikk-bevaring + live anbefalings-portefølje

To viktige ting: aldri miste historikk igjen, og spore anbefalingene framover.

**Historikk nullstilles ikke lenger (kritisk feilretting).** Deploy-steget brukte en ren
gh-pages-erstatning uten `keep_files` — hver kjøring som ikke klarte å hente forrige
tilstand (nettverksglipp før deploy) skrev tomme historikk-filer som så ble permanente.
Nå: (1) `keep_files: true` på deploy gjør gh-pages additiv, og (2) alle tilstandsfiler
(score_history, paper_ledger, regime_history, recommendation_log) bruker et sentinel-
vern: hvis forrige tilstand IKKE kunne hentes, hopper bygget over skrivingen i stedet for
å overskrive med tomt. Dine synkede posisjoner og all historikk overlever nå.

**Live anbefalings-portefølje (ny, på Backtest-fanen).** Skiller seg fra anbefalings-
backtesten (som rekonstruerer fortiden): denne lagrer de FAKTISKE kjøp-anbefalingene fra
«I dag»-siden hver dag og fører en likevektet portefølje som følger dem framover. Hver
dag kjøpes nye anbefalinger, og de som faller ut selges; daglig verdsetting gir en
ekvitykurve indeksert til 100 ved oppstart. Kurven bygger seg opp i sanntid etter hvert
som anbefalingene kommer inn — så du ser hvordan det faktisk hadde gått å følge rådene.

> Forenklet modell: likevektet, ingen transaksjonskostnad, daglig verdsetting. Kurven er
> tom de første dagene og fylles ut etter hvert. **Ikke finansrådgivning.**

## v12: Runde 5 — kompositt-fiks, kapitalstrøm, volum-gating, 52u-topp, UX

Basert på femte dybderesearch (Fable + research). Fem endringer:

**Kompositt-formelen rettet (viktigst).** Den multiplikative vekt-av-bevis-kompositten
(score × sjanger × makro) dobbeltstraffet og kollapset skalaen — et instrument med
score 80 i svak sjanger og risk-off endte på ~46 uten at tallet var tolkbart. Nå:
**normalisert vektet sum** — kompositt = 0,65×score + 0,20×sjangerstyrke + 0,15×makro-
score, alle på 0-100-skala. Eget oppsett veier tyngst; sjanger og makro er kontekst.
Skalaen er nå tolkbar og sorterbar uten skjulte interaksjoner.

**🌍 Kapitalstrøm (Armstrong-inspirert, som datapunkt).** Regioner rangert på relativ
styrke målt i GULL (felles nøytral valuta) — proxy for hvor internasjonal kapital søker
seg. Pluss dollartrend (kapital inn/ut av USD), USA-konsentrasjon (SPY/ACWI), og
flight-to-quality-varsel (gull+USD+stat opp samtidig = krisestrøm). Vises som stripe på
I dag og full tabell på Trend. Bevisst kun de evidensbaserte delene av rammeverket
(kapitalflukt, valutadrevet avkastning) — ingen sykluspåstander.

**Volum-gating på kjøp-kandidater.** Breakout uten volum-bekreftelse (RVOL < 1,0,
4-ukers vs 20-ukers snittvolum) kvalifiserer ikke lenger — volumløse brudd feiler
oftere. Breakout med RVOL ≥ 1,2 merkes «m/volum».

**52-ukers-topp-nærhet.** Ny leaderboard-kolonne (George-Hwang: nærhet til 52u-topp er
et dokumentert momentum-signal). Innen -5 % av toppen styrker kjøps-begrunnelsen.

**UX: filter, diff og guidet flyt.** Leaderboarden har tekstfilter (symbol/sjanger).
I dag viser «Endret siden forrige bygg» (nye kjøp-kandidater, stage-overganger til
nedtrend, regime-skift). Ny «🧭 Start her»-guide viser arbeidsflyten steg for steg.
Discord-varsler prioriterer nå nye kjøp-kandidater og nye Stage 4-nedtrender.

**Ikke finansrådgivning.**

## v13: Runde 6 — kutt-først-revisjon, ukedisiplin, posisjonsvarsler, CI-vern

Sjette runde var en kritisk revisjon med ferske øyne. Hovedfunn: etter fem runder med
bygging målte verktøyet samme relative momentum på seks nesten-kollineære måter.
Denne versjonen KUTTER mer enn den legger til.

**Kuttet/konsolidert.** Triage-visningen på Trend er fjernet (duplisert av I dag-
kommandobåndet). RRG og sykliske par er fjernet (samme rotasjonsinformasjon som
leaderboard + sektor-rotasjon, målt på fjerde og femte måte). Korrelasjonsmatrisen er
demotert til en expander merket «for rebalansering — ikke et daglig signal».
«Regelen vs deg»-paper-raden er fjernet fra UI (duplisert av live anbefalings-
porteføljen; tilstandsfilen består). Backtest-siden er snudd: live sporing og
anbefalings-backtest øverst, den mekaniske rotasjonsregelen demotert til referanse
nederst (den slår ikke kjøp-og-hold risikojustert og skal ikke stå først).

**Ukentlig-close-disiplin (Weinstein).** NSBC-signalene er ukentlige; daglig evaluering
ga intra-uke-flimmer. Nå: kjøp-kandidater midtuke merkes «⏳ Foreløpig — bekreftes på
fredagens close», og den live anbefalings-porteføljen endrer beholdning KUN på
fredag/helg-bygg (midtuke revalueres bare). Mindre churn, tro mot metodikken.

**Posisjonsspesifikke varsler (viktigste tilføyelse).** Diff/Discord varsler nå
🚨-prioritert på DINE beholdninger: invalideringsnivå brutt (pris under roadmapens
linje-i-sanden), posisjon nylig strukket (FOMO-sone), og posisjon inn i Stage 4-
nedtrend. Kun på overganger — ingen daglig gjentakelse.

**Metodikk-fikser.** Sjangerstyrke krympes bayesiansk mot nøytral for små sjangre
(n/(n+4): 2-medlems crypto kan ikke lenger gi 0/100-ekstremer). Live-porteføljen har
SPY- og gull-benchmark tegnet ved siden av (en kurve uten benchmark er ikke tolkbar).
Makro-glossaret merker nå ledende (rentekurve, 12-18 mnd) vs samtidige (NFCI, spreader)
motorer — komposittet blander horisonter, se hver motor.

**CI-smoke-test (infrastruktur).** Nytt workflow-steg FØR bygget: compileall + import
av alle moduler + sjekk at render-funksjonene og instrument-universet finnes. Dette
fanger de avkuttede filene (som har veltet to bygg) før de når deploy. yfinance har
allerede 3-forsøks retry.

Utsatt med vilje (fra revisjonens gjerrig-liste): Stooq-fallback for yfinance, mobil
kortvisning, posisjonsstørrelse på kandidat-kort, print-CSS, ukemodus-oppsummering.
**Ikke finansrådgivning.**

## v14: Runde 7 — pålitelighet, norsk kjøpbarhet, mobil, ukedigest

Runde 7-revisjonen fant at live-siden var 5 uker gammel med tomt leaderboard —
deployene nådde aldri ut (Actions-schedule dør etter 60 dager uten commits, og
håndlim gir ingen commits). v14 angriper det strukturelt pluss norsk kjøpbarhet.

**Pålitelighet (D1/D2/D4 + B1).** `deploy.ps1`: git-basert deploy — robocopy inn i
klonen, commit, push; git nekter delvise filer OG holder Actions-timeren i live.
`tests/test_build_synthetic.py` + `ci.yml`: syntetisk FULL-bygg-test på hver push
(størrelsesgulv per side, versjonsstempel, leaderboard ≥ 60 rader — den siste hadde
fanget juli-feilen). Cron er nå én oppføring med `timezone: 'Europe/Oslo'` (GitHub
støtter IANA-tidssoner fra mars 2026) i stedet for sommer/vinter-paret. Ferskhets-
vakt i footeren: er dataene > 3 dager gamle vises et oransje banner med diagnose.
NOWA-sanity: verdier utenfor 0-8% forkastes (live-siden viste 6,00% mot 4,25%
styringsrente — det forvrengte alle Sharpe-tall).

**Norsk kjøpbarhet (C1).** Statisk kart i config: US-noterte ETF-er er PRIIPs-
blokkert for norsk retail (siden okt 2024) og ikke ASK-kvalifiserte (EØS-krav).
Kjøp-kandidatene viser nå chip: «🇳🇴 ASK ✓» (EXSA), «kjøpbar · ikke ASK» (BTC/ETH)
eller «PRIIPs-blokkert → CSPX (IE00B5BMR087)» med verifisert UCITS-ekvivalent der
en finnes (SPY, QQQ, SOXX, GDX, GDXJ, EEM, GLD). Uten kjent ekvivalent sies det.

**Mobil + ukedigest (B3/B4).** Under 720px kollapser leaderboarden til kort-grid
(symbol, kompositt, stage, score, 52u-avstand — trykk for Daily Report). 📅
Ukesoppsummering på I dag: diff mot forrige fredags referanse-snapshot, oppdateres
kun på fre/helg-bygg — ukens fasit, midtukens diff er støy.

**Risiko-datapunkter (C3/C4).** Posisjoner med handlingsbehov viser avstand fra
52u-topp; porteføljens drawdown-fra-topp vises fra faktisk NAV-kurve. Realisert
treffprosent fra lukkede handler er koblet, men vises først ved n ≥ 20.

**Stooq-fallback (D3).** Når yfinance feiler alle forsøk på en enkel US-ticker,
hentes rå close fra Stooq (gratis CSV) så bygget ikke velter — flagges i loggen
som ujustert gap-filler, yfinance forblir primærkilde.

Verifisert i denne runden: B2 (nav) og B7 (lazy charts) var allerede riktig i
v13-koden — live-avvikene var kun den gamle deployen. C5/C6 forblir gatet (Kelly
ved n≥30-50, regime-splitt ved n≥40), C7/C8 avvist. **Ikke finansrådgivning.**

### Deploy-sjekkliste (én gang)
1. `git clone https://github.com/regg92s-hub/MarketAnalyzor.git C:\repos\MarketAnalyzor`
2. Pakk ut zip → `.\deploy.ps1 -Source <utpakket mappe>`
3. GitHub → Actions-fanen: **reaktiver workflowen** hvis den står som disabled
4. Kjør workflowen manuelt én gang (Run workflow) og sjekk at alle sider stemples v14

## v15: Posisjonering (COT), Gull→Miners-sekvens, USD basing-watch

Basert på integrasjonsanalysen av AF Newsletter (Mergott) og Armstrongs
«Understanding The World Economy». Ærlig destillat: to 45/86-siders dokumenter
ga ÉN genuint ny akse pluss to små tillegg. Resten var bekreftelse av metodikk
som allerede kjører, eller synspunkter/syklus-numerologi som holdes ute.

**🎭 Posisjonering — COT Managed Money (rec 1, viktigst).** Systemets første
sentiment-/posisjoneringsakse — ortogonal til alt annet (som er pris/momentum/
makro-avledet). CFTC disaggregert futures-only via Socrata (gratis, ingen nøkkel):
gull (088691) og sølv (084691), Managed Money-netto som % av åpen balanse,
persentil mot rullerende 3 år. Vises som full tabell på Trend og som chip på
I dag KUN ved ekstremer (>90. persentil = overfylt long/sårbar, <10. = utvasket).
Ærlighet innebygd: fagfellevurdert litteratur (Sanders 2004/2009, Bosch &
Pradkhan 2015) finner at posisjonering stort sett FØLGER pris — dette er
kontekst/risiko, aldri timing, og endrer aldri beholdninger alene. Terskel fra
analysen: hvis ekstrem-flaggene ikke viser sammenheng med forward hit-rate ved
n ≥ 20, demoteres den til ren visning.

**⛏️ Gull → Miners-sekvens (rec 2).** Mergotts disiplin formalisert som
femtrinns tilstandskort på Trend: Ro → Korreksjon (kjøp GULL) → Kapitulasjon
(vent) → Stabilisering → Bekreftelse (miners OK, via eksisterende NSBC
lavrisiko-entry på GDX — IKKE nye indikatorer, 13/30 EMA avvist som kollineær
med 12/36). Evidensen bak: GDX 26% totalavkastning 2006–2025 mot GLDs 373% —
miners skuffer kronisk uten bekreftet vending. Rent visningskort, ikke
kompositt-input.

**💵 USD basing-watch (rec 3).** Strukturelt varsel FØR en dollar-rip: FRED
DTWEXBGS, avstand fra månedlig 200-EMA + konsolideringsvarighet + avstand fra
12-måneders bunn. Flermåneders base på/over 200-EMA gikk forut for 2014- og
2022-rippene som knuste gull, råvarer og aksjer samtidig — noe 3M ROC ikke ser.
Aktivt base-varsel teller som ett risk-off-tick i makro-komposittet og vises
som eget regime-kort.

Avvist (fra analysens punkt 5): 13/30 EMA, kalender-tidssymmetri på Roadmaps,
offentlig/privat-kurv (duplisert av makro-komposittet), TIC-gjenoppliving,
CNN/krypto-sentiment, og begge forfatternes retningssyn og syklusdatoer.
Backlog: AAII-ekstremflagg (kun SPX-kontekst), GLD/TLT-tick.
**Ikke finansrådgivning.**

## v16: Trend-oversikt — bedre struktur og navigasjon

Direkte respons på tilbakemelding om at Trend-fanen ble uoversiktlig etter fem
runder med tillegg (ti makrokort, sju pengestrøm-par, to 51-rads tabeller,
posisjonering, sekvenskort, korrelasjon, hit-rate — alt stablet rett etter
hverandre uten navigasjon).

**Hurtignav.** Sticky navigasjonsstripe rett under toppmenyen med hopp-lenker
til hver seksjon (Regime, Bredde, Money flow, Sektorer, Kapitalstrøm,
Posisjonering, Gull→Miners, Rotasjon, Leadership, Hit-rate). Kun seksjoner med
faktisk data denne dagen vises som lenke.

**Leadership-tabellene kuttet til topp 10.** De to 51-rads tabellene (vs Gull,
vs Dollar) dominerte hele siden visuelt. Viser nå topp 10 med «Vis alle 51»
bak en enkel utvid-knapp (ren HTML/CSS `<details>`, ingen JS).

**Posisjonering og Gull→Miners-sekvens demotert til kollapsede paneler**, som
korrelasjonsmatrisen fra v13 — dette er lavfrekvente kontekst-signaler (COT
oppdateres ukentlig, sekvenstilstanden endrer seg sjelden), ikke daglige
handlingspunkter. Tilstanden vises likevel i selve overskriften («Gull (COMEX):
Nøytral · Sølv: Utvasket») så du ser hovedpoenget uten å klikke.

Ryddet vekk en ubrukt kodesnutt (dødt for-loop fra v15-endringen).
**Ikke finansrådgivning.**

## v17: Aksje-screener — ny fane, ukentlig bygg

Ny syvende fane basert på brukerens vekst-/value-kriterier. Kjøres UKENTLIG
(egen workflow `screener.yml`, søndag kveld, tidssone Europe/Oslo) — ikke i
det daglige bygget, siden fundamentaldata endrer seg på kvartalsbasis uansett.

**Kriterier (endelig etter avklaring):**
- Vekst: omsetningsvekst YoY > 50% OG QoQ > 40%
- Value: EPS-vekst YoY > 50% OG QoQ > 40% OG profit margin > 10% OG D/E < 1,2

**Ærlig designvalg: myk rangering, ikke hardt filter.** QoQ > 40% er en
ekstremt sjelden kombinasjon for etablerte, lønnsomme selskaper — et hardt
alt-eller-ingenting-filter ville ofte gitt tomme lister. Screeneren rangerer
derfor alle kandidater etter hvor mange av kravene som er oppfylt (0-2 for
vekst, 0-4 for value), og viser eksplisitte grønn/rød-badges per krav på hver
rad, slik at du selv ser nøyaktig hva som stemmer og hva som ikke gjør det.
En "✅ Kvalifisert"-merking vises kun når ALLE krav er oppfylt.

**Kuratert univers, ikke full markedsdekning (v17.stock_universe.py).** ~115
kjente, likvide selskaper fra hovedindeksene i Tyskland (DAX/MDAX/SDAX),
Norge (OBX), Sverige/Danmark/Finland, Canada (TSX) og USA. Bevisst valg etter
research: yfinance i bulk er dokumentert upålitelig over ~80-100 tickere per
kjøring, og et forsøk på full markedsskanning ville gitt hyppige, stille feil
snarere enn en reell fordel — særlig for ikke-amerikanske børser der
gratis-datadekningen er tynn. Universet er ment å utvides gradvis.

**Innsidekjøp (kun USA) via SEC Form 4 — gratis, myndighetsdrevet, ingen
nøkkel.** `company_tickers.json` for ticker→CIK, deretter
`data.sec.gov/submissions/CIK{cik}.json` for filingliste, og til slutt selve
Form 4-XML-en for transaksjonskode "P" (åpent-marked-kjøp) siste 90 dager.
Tyskland, Norden og Canada har **ingen tilsvarende strukturerte gratis
kilder** for innsidehandel (kun PDF-varsler/portaler) — disse markedene vises
ærlig som "n/a" i stedet for å late som dekningen finnes.

**ASK-kvalifisering per marked.** Tyskland og Norden er EØS-domisilert og
ASK-kvalifisert; USA og Canada er det ikke (skatteregel, uavhengig av om
megleren din tilbyr tilgang til børsen). Merk korrigert fra forrige runde:
PRIIPs/KID-regelen gjelder kun fond/ETF-er, ikke enkeltaksjer — irrelevant
for denne screeneren.

**Vern mot delvis feilet kjøring.** Hvis under 40% av universet gir data i en
kjøring (f.eks. yfinance nede), avbrytes bygget UTEN å overskrive forrige
fungerende screener.html/json — samme sentinel-prinsipp som resten av siden.

**Ny CI-test** (`tests/test_screener_synthetic.py`) mocker yfinance og SEC
fullstendig og validerer at begge tabellene fylles og at HTML ikke er
avkuttet — kjøres ikke automatisk i `ci.yml` ennå (egen kjøring anbefales
lokalt eller legges til som eget steg ved behov).

**Ikke finansrådgivning — startpunkt for egen analyse, ikke en anbefaling.**

## v18: Screener skalert opp — dynamisk univers, parallell henting, Discord-varsel

**Universet er ikke lenger en fast håndskrevet liste.** `universe_fetch.py`
henter indekssammensetning direkte fra Wikipedia (S&P 500, DAX, MDAX,
S&P/TSX 60, OMX Stockholm 30, OBX) ved hver ukentlige kjøring — stabile,
velformaterte tabeller som samfunnet holder oppdatert, i stedet for at jeg
skriver inn hundrevis av tickere for hånd (upålitelig, blir fort utdatert).
Kombineres med den håndplukkede seed-listen fra v17 (dedupliseres på
ticker). Universet vokser dermed fra ~115 til typisk 600-900+ selskaper,
avhengig av hvor mange av Wikipedia-tabellene som svarer den uken.

**Parallell innhenting, fortsatt kun ukentlig.** Ett stort univers ville
truffet yfinance sin dokumenterte rate-limit-grense (~80-100 tickere per
kjøring). Løsningen er IKKE å kjøre oftere — det er å dele opp ÉN ukentlig
kjøring i 8 parallelle GitHub Actions-jobber (matrise-strategi), der hver
jobb henter sin egen 1/8-del av universet. En egen sammenslåingsjobb samler
alle delene, rangerer topp-20 på nytt over HELE det samlede datasettet (ikke
per del), sjekker innsidekjøp kun for de endelige topp-40 (holder SEC-
kallbudsjettet konstant uansett universstørrelse), og publiserer. `CHUNK_TOTAL`
i `screener.yml` kan økes videre (f.eks. til 12-16) hvis universet vokser enda
mer over tid.

**Discord-varsel ved nye selskaper.** Sammenslåingsjobben henter forrige ukes
`screener.json` (samme sentinel-mønster som resten av tilstanden: hvis
forrige liste ikke kan hentes, sendes IKKE et falskt "alt er nytt"-varsel),
sammenligner tickere mot denne ukens topp-20 på begge lister, og poster kun
de faktisk nye selskapene til webhooken din — ikke hele listen hver gang.

**Testet grundig med mock-data** (`tests/test_screener_synthetic.py`
simulerer to påfølgende uker, inkludert et selskap som går fra svakt til
ekstremt og bekrefter at det korrekt fanges opp som "nytt" i Discord-diffen).
Som med COT-posisjoneringen i v15: selve nettverkskallene (Wikipedia,
yfinance, SEC, Discord) kan ikke testes fra et nettverksbegrenset miljø —
første ekte kjøring i GitHub Actions er den endelige verifiseringen.

**Ikke finansrådgivning — startpunkt for egen analyse, ikke en anbefaling.**

## v19: PWA-cache-bug fikset, TradingView/Yahoo-lenker på screener

**Kritisk fiks: service worker cachet siden permanent.** `CACHE`-navnet i
`sw.js` var en hardkodet streng (`'analysor-v5'`) som ALDRI endret seg
mellom daglige bygg. Nettlesere oppdaterer kun en installert service worker
når filen er byte-forskjellig fra sist — siden sw.js var identisk hver dag,
oppdaget nettleseren aldri en endring, og siden forble låst til det som ble
hentet ved aller første besøk. Inkognito har ingen lagret service worker og
hentet derfor alltid ferskt — derfor virket det kun der. Fikset på to måter:
(1) cache-navnet inkluderer nå `VERSION`, så sw.js blir bytes-forskjellig
hver dag og tvinger frem en reell oppdatering; (2) HTML-sider er byttet fra
cache-first til **network-first** (faller kun tilbake til cache når du er
offline) — mer robust enn å stole på at oppdateringssyklusen alltid treffer
i tide. `screener.html` er også lagt til i kjerne-cachen.

**Hvis siden fortsatt viser gammelt innhold i vanlig nettleser etter denne
deployen:** dette er den SISTE gangen — gammel service worker må ryddes
manuelt én gang (F12 → Application → Service Workers → Unregister → last
siden på nytt). Etter det skal v19s versjonerte cache holde seg selv
oppdatert automatisk for alle fremtidige bygg.

**TradingView- og Yahoo Finance-lenker på Aksje-screener.** Hver rad har nå
📊 (TradingView-chart) og 💹 (Yahoo Finance-detaljer). TradingView krever
BØRS:SYMBOL-format, ikke Yahoo sitt suffiks-format — egen oversetter i
`stock_universe.py` (`.DE`→XETR, `.OL`→OSL, `.ST`→OMXSTO, `.CO`→OMXCOP,
`.HE`→OMXHEX, `.TO`→TSX, aksjeklasser `VOLV-B`→`VOLV_B`; USA uten suffiks
sendes rått til TradingViews eget søk). Yahoo-lenken trenger ingen
oversettelse — vi henter allerede fundamentaldata via yfinance, som bruker
nøyaktig samme ticker-format som Yahoo Finance selv.

**Ikke finansrådgivning.**

## v20: Flere børser, "Vekst med oppside", søkbare tabeller

**Flere børser i Aksje-screeneren.** Bekreftet direkte fra Nordnet at
Zero-kontoen dekker de nordiske børsene, Tyskland, USA, Canada,
Storbritannia og Euronext. Lagt til Storbritannia (FTSE 100), Nederland
(AEX) og Frankrike (CAC 40) — samme mønster som v18: en håndplukket
seed-liste (`stock_universe.py`) kombinert med en dynamisk Wikipedia-hentet
indeks (`universe_fetch.py`). Universet vokser videre fra det som allerede
var der. **Kontokolonnen** viser nå «🇳🇴 ASK» eller «Zero» i stedet for et
rått «ikke ASK» — tydeliggjør at amerikanske/kanadiske/britiske aksjer
fortsatt er fullt handlbare via Zero-kontoen, bare uten ASK-ens skattefordel
(utsatt/skattefri gevinstbeskatning), siden disse børsene ikke er
EØS-domisilert.

**Den viktigste endringen: «🚀 Vekst med oppside».** Vekst- og
Value-listene svarer begge kun på ett spørsmål — *har selskapet vokst?* En
aksje kan ha steget 300 % og troner øverst på vekstlisten uten at det er
noe igjen å hente; «vokser rett og bra» og «har fortsatt mye kursoppside
igjen» er to forskjellige spørsmål. Den nye listen krysser ekte vekst
(minst ett av vekstkravene oppfylt) med tre fremoverskuende mål:
**PEG-ratio** < 2 (er prisen fornuftig relativt til inntjeningsveksten),
**avstand fra 200-dagers snitt** < 25 % (er den allerede strukket), og
**analytikernes kursmål** > 10 % over dagens kurs (ser markedet fortsatt
oppside). Rangert på dekningsgrad, samme mønster som Vekst/Value. Alle tre
feltene hentes fra samme yfinance `.info`-kall som resten av
fundamentaldataene — ingen ekstra nettverkskostnad.

**Søkefilter og omskrevet forklaringsboks.** Hver av de tre tabellene har
nå sitt eget tekstfilter (klientside, filtrerer på selskap/ticker/sektor/
land). Forklaringsboksen øverst er skrevet om for faktisk å forklare
forskjellen mellom «har vokst» og «har mer å gå på», ikke bare liste opp
kravene.

**Ærlig begrensning:** PEG og analytiker-kursmål er mer konsistent
tilgjengelig for amerikanske og store europeiske aksjer enn for mindre
nordiske selskaper i yfinances gratis-data — der vil disse to badgene
oftere vise «ukjent». Det er ikke en bug, det er dekningsgrensen i
gratisdata, og den vises ærlig som «ukjent» i stedet for å gjette.

**Ikke finansrådgivning.**

## v21: Northstar-teknisk lag, pris i listen, ⭐-merking

**Hvorfor:** fundamentaldata (vekst/value/oppside) svarer på HVA som er en
bra aksje å eie — de sier ingenting om NÅR det er et fornuftig tidspunkt å
gå inn. v21 legger til akkurat samme Northstar/NSBC-metodikk
(`scoring.nsbc_score`) som resten av siden allerede bruker på ETF-ene i det
daglige bygget — Trend Navigator (12/36-SMA), Ichimoku-sky, Weinstein
stage-analyse, distance-fra-36-SMA (stretched/FOMO-sjekk) og
breakout-fra-konsolidering — kjørt på hver enkelt screener-aksjes egen
ukentlige/månedlige/kvartalsvise prishistorikk (`data.resample_frames`).

**Ny «Teknisk (Northstar)»-kolonne** på alle tre tabellene viser
stage-etikett + score 0-100 (gjenbruker `scoring.score_label` for identisk
fargekoding/tekst som resten av siden). Hentes via samme yf.Ticker-objekt
som fundamentaldataene (`.history()`) — kun én ekstra forespørsel per aksje,
ingen ny Ticker-instansiering. Degraderer grasiøst til «ukjent (for kort
historikk)» for aksjer uten nok prishistorikk til at ukentlig/månedlig gir
mening (typisk nylige børsnoteringer) — samme filosofi som PEG/analytiker-mål.

**⭐-merking**: aksjer som er fundamentalt kvalifisert OG i Northstar
lavrisiko-entry (score ≥70) SAMTIDIG merkes med en stjerne — de nærmeste
"klar til å handle nå"-kandidatene på hele siden, og hver seksjon viser nå
også et telletall for hvor mange av de kvalifiserte som er stjernemerket.

**Bevisst IKKE latt teknisk score omrokkere hovedrangeringen.** Første
forsøk brukte `ta_score` som sekundært sorteringskriterium (før selve
vekst-/value-magnituden) — det viste seg fort å produsere kontraintuitive
resultater i test (en aksje med ekstrem, reell vekst kunne falle helt ut av
topp-20 fordi timingen tilfeldigvis var svak). Rettet til: dekningsgrad og
faktisk vekst-/value-magnitude bestemmer FORTSATT rekkefølgen (en ekte
300%-vekstaksje skal trone øverst uansett timing); teknisk score brukes kun
som aller siste tiebreaker ved reelle uavgjort. Teknisk-kolonnen og
⭐-merket viser deg heller HVILKE av de allerede beste kandidatene som også
har god timing — riktigere løsning på "sorter beste øverst" enn å la
teknikk overstyre fundamentale ytterpunkter.

**Prisen vises nå** i hver rad (valuta inkludert) — nyttig når du faktisk
skal legge inn en ordre, ikke bare vurdere kvalifisering.

**Testet**: `test_screener_synthetic.py` fikk en syntetisk 5-års
prishistorikk per mock-ticker (korrelert med samme vekstfaktor som
fundamentaldataene) slik at hele NSBC-integrasjonsveien faktisk øves i CI,
ikke bare "ukjent"-fallbacken — verifiserer at Teknisk-kolonnen finnes i
HTML-en og at minst noen rader får en reell score.

**Ikke finansrådgivning.**
