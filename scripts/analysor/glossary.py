"""
Forklaringssystem ("hva betyr denne boksen?").

Ett sentralt oppslag som gir en kort, klar forklaring under HVER boks på HVER
fane — insikt først, ikke bare etikett. Rapportens #1 klarhetsgrep.

To lag:
  - one_liner(): alltid synlig under tallet ("hva betyr dette")
  - detail(): valgfri utvidelse ("hva endrer det / hva bør jeg gjøre")

Tidsramme er ALLTID med der det er relevant (rapportkrav: ingen boble uten
tidsramme).
"""
from __future__ import annotations


def regime_one_liner(score: int | None) -> str:
    if score is None:
        return "Makro-regime mangler data (krever FRED_API_KEY)."
    if score >= 66:
        return (f"Risk-on {score}/100: makrobildet favoriserer risiko — flertallet av motorene "
                "(likviditet, kredittspread, rentekurve, realrente) er positive. "
                "Historisk medvind for aksjer/krypto, motvind for kontanter/lange renter.")
    if score >= 34:
        return (f"Blandet {score}/100: motorene spriker — verken klart risk-on eller risk-off. "
                "Vær selektiv; la sjanger-medvind og enkeltoppsett avgjøre, ikke makro alene.")
    return (f"Risk-off {score}/100: flertallet av makromotorene er negative. "
            "Historisk medvind for gull/kontanter, motvind for høy-beta. Vurder å skalere ned risiko.")


# Statiske forklaringer per metrikk-nøkkel (vises under boksen)
EXPLAIN = {
    "regime_composite": {
        "what": "Andel av makromotorene som er risk-on (0-100). NB: blander ledende (rentekurve, 12-18 mnd) og samtidige (NFCI, spreader) — se hver motor for horisont.",
        "do": "Over 66 = medvind for risiko. Under 34 = vurder gull/kontanter og lavere beta.",
    },
    "yield_curve": {
        "what": "2-årig vs 10-årig statsrente. LEDENDE 12-18 mnd — invertering har historisk gått forut for resesjon.",
        "do": "Bratt/positiv = sent i syklus-OK. Invertert = sen-syklus-varsel, men ikke timing-signal alene.",
    },
    "net_liquidity": {
        "what": "Fed-balanse minus statskonto (TGA) minus revers-repo (RRP) — dollarlikviditet i systemet.",
        "do": "Stigende = medvind for risikoaktiva. Fallende = motvind. Leder ofte aksjer med uker.",
    },
    "global_liquidity": {
        "what": "Fed+ECB+BoJ samlet balanse i USD (6-mnd endring). Bred global pengemengde-proxy.",
        "do": "Ekspanderende = strukturell medvind. NB: forholdet brøt sammen 2023-25 — vekt deretter.",
    },
    "real_rate": {
        "what": "10-årig realrente (TIPS). Gull beveger seg typisk omvendt av denne.",
        "do": "Fallende realrente = medvind for gull/hard assets. Stigende = motvind, støtte for USD.",
    },
    "breakeven": {
        "what": "10-årig inflasjonsforventning (breakeven). Over ~2,5% = marked priser inn høy inflasjon.",
        "do": "Stigende breakevens støtter realaktiva (gull, råvarer, energi).",
    },
    "nfci": {
        "what": "Chicago Fed finansielle forhold. SAMTIDIG indikator — negativ = løse forhold, positiv = stramme.",
        "do": "Negativ/løs = risk-on-medvind. Positiv/stram = forsiktighet.",
    },
    "credit_spread": {
        "what": "High-yield kredittspread (OAS). SAMTIDIG/tidlig-varsel — lav = risikovilje, økende = kredittstress.",
        "do": "Utvidende spreader er et tidlig risk-off-varsel — ofte før aksjer snur.",
    },
    "panic": {
        "what": "Daniel-Moskowitz panikk-tilstand: bear-marked + høy volatilitet = momentum-krasj-fare.",
        "do": "Når aktiv: rotasjonsstrategien demper eksponering til 50%. Ellers full eksponering.",
    },
    "gpr": {
        "what": "Geopolitisk risiko-indeks (Caldara-Iacoviello). Kun kontekst, ikke et handelssignal.",
        "do": "Forhøyet GPR = forvent større svingninger; ikke en grunn til å handle alene.",
    },
    "nsbc_score": {
        "what": "Lavrisiko-entry-score 0-100 (NSBC): høyt = over trend, ikke strukket, bryter ut av base.",
        "do": "≥70 = ekte lavrisiko-entry. Lavt kan bety nedtrend (Stage 4) ELLER strukket — se etikett.",
    },
    "gold_beat": {
        "what": "Slår instrumentet gull? Måles på pris/gull-forholdet (ratio), ROC 3 mnd.",
        "do": "Positiv = leder mot baseline. NSBC: alt måles relativt til gull.",
    },
    "breadth": {
        "what": "Andel av universet over 50- og 200-dagers MA. Bredde = hvor bredt fundert trenden er.",
        "do": "Fallende bredde under stigende indeks = svekkelse under overflaten (divergens).",
    },
    "dist_ma": {
        "what": "Avstand i % fra glidende snitt. 0 = ved snittet, +10% = strukket (FOMO-sone).",
        "do": "Stor positiv = høy risiko å gå inn (vent på tilbaketrekk). Negativ = under trend.",
    },
    "stage": {
        "what": "Weinstein-fase: 1 basing, 2 opptrend, 3 distribusjon, 4 nedtrend.",
        "do": "Kjøp helst i Stage 2 ved breakout. Stage 4 = unngå. Stage 1 = følg med på breakout.",
    },
    "hit_rate": {
        "what": "Når score ≥70 historisk: hvor ofte var fremtidig avkastning positiv, vs base-rate.",
        "do": "Edge = signal minus base-rate. n<20 = lav tillit. Ikke styr sizing på lite utvalg.",
    },
    "real_return": {
        "what": "Avkastning i fire spor: nominell NOK, real NOK (etter KPI), USD, og gull-unser.",
        "do": "Real NOK viser ekte kjøpekraft. Gull-unser viser om du slår baseline.",
    },
    "mansfield_rs": {
        "what": "Mansfield relativ styrke: ratio vs benchmark normalisert mot eget 52-ukers snitt.",
        "do": "Over null = leder benchmark (gull/SPY). Under null = henger etter.",
    },
    "money_flow": {
        "what": "Hvor kapitalen strømmer: risikovillige forhold (kreditt, syklisk, EM, småselskap) vs trygge havner.",
        "do": "Risk-on = medvind for aksjer/krypto. Risk-off = kapital flykter til gull/stat/defensivt — reduser beta.",
    },
    "sector_flow": {
        "what": "Sektor-rotasjon: hvilke sjangre kapital strømmer inn i vs ut av, målt mot bredt marked.",
        "do": "Kjøp helst der pengene strømmer INN (innstrømning + akselererende). Unngå utstrømning.",
    },
    "capital_flows": {
        "what": "Kapitalstrøm mellom land: regioner rangert på relativ styrke målt i gull, pluss dollartrend og USA-konsentrasjon.",
        "do": "Kapital driver bull-markeder i destinasjonen. Flight-to-quality (gull+USD+stat samtidig opp) = krisevarsel. Kun ett datapunkt.",
    },
    "rvol": {
        "what": "Relativt volum: siste 4-ukers snittvolum vs 20-ukers snitt. Over 1,0 = volum over normalen.",
        "do": "Breakout uten volum (<1,0) feiler oftere — vent på bekreftelse før kjøp.",
    },
    "positioning": {
        "what": "COT Managed Money-netto som persentil av 3 år. Første sentiment-akse i systemet — ortogonal til pris/momentum.",
        "do": ">90. persentil = overfylt long (sårbar for unwind). <10. = utvasket. KONTEKST, ikke timing — posisjonering følger stort sett pris.",
    },
    "usd_watch": {
        "what": "Strukturelt USD-varsel: flermåneders base på/over månedlig 200-EMA har historisk gått forut for dollar-ripper (2014, 2022).",
        "do": "Aktivt base-varsel = forhøyet risiko for samtidig fall i gull, råvarer og aksjer. Teller som risk-off-tick i regimet.",
    },
    "screener": {
        "what": "Ukentlig skann av et kuratert aksjeunivers mot vekst-/value-kriteriene dine.",
        "do": "Startpunkt for egen analyse, ikke en ferdig anbefaling. Sjekk badgene per aksje — de fleste vil oppfylle noen, ikke alle, krav.",
    },
    "no_access": {
        "what": "Norsk kjøpbarhet: US-noterte ETF-er er PRIIPs-blokkert for retail (siden okt 2024); ASK krever EØS-fond med ≥80% aksjer.",
        "do": "Bruk UCITS-ekvivalenten der en er oppgitt. Eksisterende US-posisjoner kan holdes/selges, ikke økes.",
    },
    "from_52wh": {
        "what": "Avstand fra 52-ukers topp. Nærhet til toppen er et dokumentert momentum-signal (George-Hwang).",
        "do": "Innen -5% av toppen = sterkt momentum. Mer enn -20% under = svakt eller i base.",
    },
}


def one_liner(key: str) -> str:
    """Kort 'hva betyr dette' for en metrikk-boks."""
    e = EXPLAIN.get(key)
    return e["what"] if e else ""


def detail(key: str) -> str:
    """'Hva bør jeg gjøre' — vises ved utvidelse/hover."""
    e = EXPLAIN.get(key)
    return e["do"] if e else ""


def box(key: str) -> str:
    """Ferdig HTML-snutt: liten forklaring under en boks."""
    e = EXPLAIN.get(key)
    if not e:
        return ""
    return (f'<div class="explain"><span class="ex-what">{e["what"]}</span> '
            f'<span class="ex-do">→ {e["do"]}</span></div>')
