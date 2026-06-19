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
        "what": "Andel av makromotorene som er risk-on akkurat nå (0-100).",
        "do": "Over 66 = medvind for risiko. Under 34 = vurder gull/kontanter og lavere beta.",
    },
    "yield_curve": {
        "what": "2-årig vs 10-årig statsrente. Invertert (negativ) har historisk gått forut for resesjon.",
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
        "what": "Chicago Fed finansielle forhold. Negativ = løse forhold (lett kreditt), positiv = stramme.",
        "do": "Negativ/løs = risk-on-medvind. Positiv/stram = forsiktighet.",
    },
    "credit_spread": {
        "what": "High-yield kredittspread (OAS). Lav = risikovilje, høy/økende = stress i kreditt.",
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
