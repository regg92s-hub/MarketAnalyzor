"""
v17: Kuratert aksjeunivers for Aksje-screener.

IKKE et forsøk på full markedsdekning — det ville krevd tusenvis av tickere og
er upålitelig med yfinance i bulk (dokumentert rate-limiting over ~80-100
tickere per kjøring). Dette er en håndplukket, men reell og verifiserbar
liste av likvide selskaper fra hovedindeksene i de fire markedene, ment å
utvides over tid. Kjøres UKENTLIG (ikke daglig) — fundamentaldata endrer seg
uansett bare på kvartalsbasis.

Ticker-suffiks (Yahoo Finance-konvensjon): .DE=Xetra, .OL=Oslo, .ST=Stockholm,
.CO=København, .HE=Helsinki, .TO=Toronto, ingen suffiks=USA (NYSE/NASDAQ).

ask_eligible: EØS-domisilert børs -> True (Tyskland, Norden). USA og Canada
er IKKE EØS -> ikke ASK-kvalifisert (skatteregel, uavhengig av om megleren din
tilbyr tilgang til børsen).
"""
from __future__ import annotations

REGIONS = {
    "DE": {"label": "Tyskland", "exchange": "Xetra/Frankfurt", "ask_eligible": True},
    "NO": {"label": "Norge", "exchange": "Oslo Børs", "ask_eligible": True},
    "SE": {"label": "Sverige", "exchange": "Nasdaq Stockholm", "ask_eligible": True},
    "DK": {"label": "Danmark", "exchange": "Nasdaq København", "ask_eligible": True},
    "FI": {"label": "Finland", "exchange": "Nasdaq Helsinki", "ask_eligible": True},
    "CA": {"label": "Canada", "exchange": "TSX", "ask_eligible": False},
    "US": {"label": "USA", "exchange": "NYSE/NASDAQ", "ask_eligible": False},
}

# (ticker, selskapsnavn, region, sektor)
SEED_UNIVERSE = [
    # ── Tyskland: DAX + utvalgte MDAX/SDAX ─────────────────────────
    ("SAP.DE", "SAP", "DE", "Programvare"),
    ("SIE.DE", "Siemens", "DE", "Industri"),
    ("RHM.DE", "Rheinmetall", "DE", "Forsvar"),
    ("IFX.DE", "Infineon Technologies", "DE", "Halvledere"),
    ("ALV.DE", "Allianz", "DE", "Forsikring"),
    ("DTE.DE", "Deutsche Telekom", "DE", "Telekom"),
    ("MBG.DE", "Mercedes-Benz Group", "DE", "Bilprodusent"),
    ("BMW.DE", "BMW", "DE", "Bilprodusent"),
    ("VOW3.DE", "Volkswagen", "DE", "Bilprodusent"),
    ("BAS.DE", "BASF", "DE", "Kjemi"),
    ("BAYN.DE", "Bayer", "DE", "Legemidler/agro"),
    ("MRK.DE", "Merck KGaA", "DE", "Legemidler/life science"),
    ("MUV2.DE", "Munich Re", "DE", "Reforsikring"),
    ("DBK.DE", "Deutsche Bank", "DE", "Bank"),
    ("AIR.DE", "Airbus", "DE", "Luftfart/forsvar"),
    ("HEI.DE", "Heidelberg Materials", "DE", "Byggematerialer"),
    ("HNR1.DE", "Hannover Rück", "DE", "Reforsikring"),
    ("SHL.DE", "Siemens Healthineers", "DE", "Medisinsk teknologi"),
    ("SY1.DE", "Symrise", "DE", "Spesialkjemi"),
    ("QIA.DE", "Qiagen", "DE", "Bioteknologi"),
    ("PUM.DE", "Puma", "DE", "Forbruksvarer"),
    ("RNK.DE", "Renk Group", "DE", "Forsvar"),
    ("TKA.DE", "Thyssenkrupp", "DE", "Industri"),
    ("NEM.DE", "Nemetschek", "DE", "Programvare (bygg)"),
    ("EVT.DE", "Evotec", "DE", "Bioteknologi"),

    # ── Norge: OBX og andre likvide navn ────────────────────────────
    ("EQNR.OL", "Equinor", "NO", "Energi"),
    ("DNB.OL", "DNB Bank", "NO", "Bank"),
    ("KOG.OL", "Kongsberg Gruppen", "NO", "Forsvar/maritim"),
    ("MOWI.OL", "Mowi", "NO", "Sjømat/laks"),
    ("NHY.OL", "Norsk Hydro", "NO", "Aluminium/materialer"),
    ("ORK.OL", "Orkla", "NO", "Forbruksvarer"),
    ("TEL.OL", "Telenor", "NO", "Telekom"),
    ("YAR.OL", "Yara International", "NO", "Gjødsel/kjemi"),
    ("AKRBP.OL", "Aker BP", "NO", "Energi"),
    ("NOD.OL", "Nordic Semiconductor", "NO", "Halvledere"),
    ("SALM.OL", "SalMar", "NO", "Sjømat/laks"),
    ("SUBC.OL", "Subsea 7", "NO", "Energiservice"),
    ("TOM.OL", "Tomra Systems", "NO", "Miljøteknologi"),
    ("SCATC.OL", "Scatec", "NO", "Fornybar energi"),
    ("AKSO.OL", "Aker Solutions", "NO", "Energiservice"),
    ("BAKKA.OL", "Bakkafrost", "NO", "Sjømat/laks"),
    ("GJF.OL", "Gjensidige Forsikring", "NO", "Forsikring"),
    ("VAR.OL", "Vår Energi", "NO", "Energi"),

    # ── Sverige ──────────────────────────────────────────────────────
    ("VOLV-B.ST", "Volvo Group", "SE", "Industri/kjøretøy"),
    ("ATCO-A.ST", "Atlas Copco", "SE", "Industri"),
    ("ERIC-B.ST", "Ericsson", "SE", "Telekomutstyr"),
    ("HEXA-B.ST", "Hexagon", "SE", "Industriteknologi"),
    ("SAND.ST", "Sandvik", "SE", "Industri"),
    ("INVE-B.ST", "Investor AB", "SE", "Investeringsselskap"),
    ("SEB-A.ST", "SEB", "SE", "Bank"),
    ("SWED-A.ST", "Swedbank", "SE", "Bank"),
    ("EVO.ST", "Evolution AB", "SE", "Spillteknologi/casino"),
    ("SINCH.ST", "Sinch", "SE", "Kommunikasjons-programvare"),
    ("EMBRAC-B.ST", "Embracer Group", "SE", "Spillutvikler"),
    ("SDIP-B.ST", "Sdiptech", "SE", "Infrastrukturteknologi"),
    ("ADDL-B.ST", "AddLife", "SE", "Life science distribusjon"),

    # ── Danmark ──────────────────────────────────────────────────────
    ("NOVO-B.CO", "Novo Nordisk", "DK", "Legemidler"),
    ("DSV.CO", "DSV", "DK", "Logistikk"),
    ("MAERSK-B.CO", "A.P. Møller-Mærsk", "DK", "Shipping/logistikk"),
    ("ORSTED.CO", "Ørsted", "DK", "Fornybar energi"),
    ("GN.CO", "GN Store Nord", "DK", "Høreapparater/headset"),
    ("COLO-B.CO", "Coloplast", "DK", "Medisinsk utstyr"),
    ("DEMANT.CO", "Demant", "DK", "Høreapparater"),
    ("NZYM-B.CO", "Novozymes", "DK", "Bioteknologi/enzymer"),

    # ── Finland ──────────────────────────────────────────────────────
    ("NOKIA.HE", "Nokia", "FI", "Telekomutstyr"),
    ("KNEBV.HE", "Kone", "FI", "Heiser/rulletrapper"),
    ("SAMPO.HE", "Sampo", "FI", "Forsikring"),
    ("NDA-FI.HE", "Nordea Bank", "FI", "Bank"),
    ("UPM.HE", "UPM-Kymmene", "FI", "Skog/bioindustri"),
    ("WRT1V.HE", "Wärtsilä", "FI", "Marin/energiteknologi"),
    ("NESTE.HE", "Neste", "FI", "Fornybart drivstoff"),

    # ── Canada: TSX ──────────────────────────────────────────────────
    ("SHOP.TO", "Shopify", "CA", "E-handelsplattform"),
    ("CLS.TO", "Celestica", "CA", "Elektronikkproduksjon (AI)"),
    ("RY.TO", "Royal Bank of Canada", "CA", "Bank"),
    ("TD.TO", "TD Bank", "CA", "Bank"),
    ("CNQ.TO", "Canadian Natural Resources", "CA", "Energi"),
    ("CP.TO", "Canadian Pacific Kansas City", "CA", "Jernbane"),
    ("CSU.TO", "Constellation Software", "CA", "Programvare (oppkjøp)"),
    ("WCN.TO", "Waste Connections", "CA", "Avfallshåndtering"),
    ("ATD.TO", "Alimentation Couche-Tard", "CA", "Dagligvare/bensinstasjon"),
    ("MDA.TO", "MDA Space", "CA", "Romfart/satellitt"),
    ("ATZ.TO", "Aritzia", "CA", "Klesdetaljist"),
    ("WELL.TO", "WELL Health Technologies", "CA", "Helseteknologi"),
    ("KXS.TO", "Kinaxis", "CA", "Forsyningskjede-programvare"),
    ("DOO.TO", "BRP (Ski-Doo/Sea-Doo)", "CA", "Fritidskjøretøy"),
    ("PRL.TO", "Propel Holdings", "CA", "Fintech/utlån"),

    # ── USA: utvalgte S&P 500 + kjente vekstnavn ────────────────────
    ("NVDA", "Nvidia", "US", "Halvledere (AI)"),
    ("MSFT", "Microsoft", "US", "Programvare/cloud"),
    ("AAPL", "Apple", "US", "Forbrukerelektronikk"),
    ("GOOGL", "Alphabet", "US", "Internett/AI"),
    ("AMZN", "Amazon", "US", "E-handel/cloud"),
    ("META", "Meta Platforms", "US", "Sosiale medier/AI"),
    ("AVGO", "Broadcom", "US", "Halvledere"),
    ("PLTR", "Palantir Technologies", "US", "Programvare (AI/data)"),
    ("CRM", "Salesforce", "US", "Programvare (CRM)"),
    ("NOW", "ServiceNow", "US", "Programvare (enterprise)"),
    ("APP", "AppLovin", "US", "Adtech"),
    ("CRWD", "CrowdStrike", "US", "Cybersikkerhet"),
    ("SNOW", "Snowflake", "US", "Dataplattform/cloud"),
    ("MU", "Micron Technology", "US", "Minnebrikker"),
    ("MRVL", "Marvell Technology", "US", "Halvledere"),
    ("ANET", "Arista Networks", "US", "Nettverksutstyr (datasenter)"),
    ("VRT", "Vertiv Holdings", "US", "Datasenter-infrastruktur"),
    ("DUOL", "Duolingo", "US", "Edtech-app"),
    ("CELH", "Celsius Holdings", "US", "Forbruksvarer (drikke)"),
    ("SOUN", "SoundHound AI", "US", "Taleteknologi (AI)"),
    ("HG", "Hamilton Insurance Group", "US", "Spesialforsikring"),
    ("MXL", "MaxLinear", "US", "Halvledere"),
    ("UCTT", "Ultra Clean Holdings", "US", "Halvlederutstyr"),
    ("AAOI", "Applied Optoelectronics", "US", "Optisk nettverk (AI)"),
    ("GEV", "GE Vernova", "US", "Energiutstyr"),
    ("LLY", "Eli Lilly", "US", "Legemidler"),
    ("ISRG", "Intuitive Surgical", "US", "Medisinsk robotikk"),
    ("V", "Visa", "US", "Betalingsformidling"),
    ("MA", "Mastercard", "US", "Betalingsformidling"),
    ("COST", "Costco Wholesale", "US", "Dagligvare/medlemsklubb"),
]

# CIK-oppslag (for SEC-innsidesignal) må skje dynamisk via SEC sin egen
# ticker->CIK-fil (company_tickers.json) — bygges i screener.py, ikke her.

# v19: TradingView bruker EXCHANGE:SYMBOL, ikke Yahoo sitt børs-suffiks.
# Egen oversetter for aksje-screeneren (ETF/krypto-universet har sin egen
# tv_symbol() i config.py).
_TV_EXCHANGE = {"DE": "XETR", "NO": "OSL", "SE": "OMXSTO", "DK": "OMXCOP",
               "FI": "OMXHEX", "CA": "TSX"}
_SUFFIX_TO_REGION = {"DE": "DE", "OL": "NO", "ST": "SE", "CO": "DK", "HE": "FI", "TO": "CA"}


def screener_tv_symbol(ticker: str) -> str:
    """Yahoo-ticker (f.eks. 'VOLV-B.ST', 'RHM.DE', 'AAPL') -> TradingView-symbol."""
    if "." not in ticker:
        return ticker  # USA: ingen suffiks, la TradingViews søk resolve NYSE/NASDAQ
    base, suffix = ticker.rsplit(".", 1)
    region = _SUFFIX_TO_REGION.get(suffix, "")
    exch = _TV_EXCHANGE.get(region)
    base_tv = base.replace("-", "_")  # aksjeklasser: Yahoo bruker "-", TradingView "_"
    return f"{exch}:{base_tv}" if exch else base_tv


def screener_tv_url(ticker: str) -> str:
    import urllib.parse
    return f"https://www.tradingview.com/chart/?symbol={urllib.parse.quote(screener_tv_symbol(ticker))}"


def screener_yahoo_url(ticker: str) -> str:
    """Yahoo Finance-lenke. Ingen oversettelse nødvendig — vi henter allerede
    fundamentaldata VIA yfinance, så ticker-formatet er identisk med Yahoo sitt eget."""
    import urllib.parse
    return f"https://finance.yahoo.com/quote/{urllib.parse.quote(ticker)}"
