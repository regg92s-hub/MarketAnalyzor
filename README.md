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
