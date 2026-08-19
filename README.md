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
│       ├── layout.py                # delt HTML/CSS/CSP
│       ├── render.py                # Trend-oversikt + Market Daily Report
│       └── portfolio.py             # Portefølje (klientside, kryptering, backup)
└── docs/                            # genereres → deployes til gh-pages
    ├── index.html                   # 📈 Trend-oversikt
    ├── report.html                  # 📊 Market Daily Report
    ├── portfolio.html               # 💼 Portefølje
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
