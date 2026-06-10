"""
Konfigurasjon for market-analysor.

All analyse er relativ til gull (XAU) som baseline – gull reflekterer
likviditet, realrenter og monetær politikk (Northstar/NFTRH-metodikk).

Endringer fra market-daily-report (v8 -> analysor):
  - ROC/momentum-baserte relativstyrke-signaler (ikke MA-kryssing på ratio)
  - Bredde-, risiko- og korrelasjonsmetrikker
  - Volatilitetsjustert posisjonsstørrelse
  - Colorblind-trygg palett (Okabe-Ito)
  - Lightweight Charts i stedet for matplotlib-PNG-er
"""

VERSION = "2026-06-09-analysor-v2"

# ──────────────────────────────────────────────────────────────────
# INSTRUMENT-UNIVERS
# Tickere valgt for lang historikk der mulig (50-perioders signaler
# krever historikk). SOXX (2001) > SOXQ (2021); DBC (2006) > PDBC;
# URA (2010) dekker uran. BTC/ETH bruker spot.
# ──────────────────────────────────────────────────────────────────
INSTRUMENT_GROUPS = [
    {
        "key": "renter_valuta", "title": "0. Renter & Valuta", "sector": "Renter & Valuta",
        "instruments": [
            {"id": "TLT", "label": "20yr Treasuries", "symbol_label": "TLT", "candidates": ["TLT"]},
            {"id": "HYG", "label": "High Yield",      "symbol_label": "HYG", "candidates": ["HYG"]},
            {"id": "UUP", "label": "US Dollar",       "symbol_label": "UUP", "candidates": ["UUP", "USDU"]},
            {"id": "FXE", "label": "Euro",            "symbol_label": "FXE", "candidates": ["FXE"]},
            {"id": "CEW", "label": "EM Valuta",       "symbol_label": "CEW", "candidates": ["CEW"]},
        ],
    },
    {
        "key": "aksjer", "title": "1. Aksjer", "sector": "Aksjer",
        "instruments": [
            {"id": "SPY",  "label": "S&P 500",        "symbol_label": "SPY",  "candidates": ["SPY"]},
            {"id": "QQQ",  "label": "Nasdaq 100",     "symbol_label": "QQQ",  "candidates": ["QQQ"]},
            {"id": "IWM",  "label": "Small Cap",      "symbol_label": "IWM",  "candidates": ["IWM"]},
            {"id": "ACWI", "label": "Global aksjer",  "symbol_label": "ACWI", "candidates": ["ACWI"]},
            {"id": "EXSA", "label": "Europa STOXX",   "symbol_label": "EXSA", "candidates": ["EXSA.DE", "EXSA"]},
            {"id": "EEM",  "label": "Emerging Mkts",  "symbol_label": "EEM",  "candidates": ["EEM"]},
            {"id": "VNQ",  "label": "Eiendom (REIT)", "symbol_label": "VNQ",  "candidates": ["VNQ"]},
        ],
    },
    {
        "key": "tech", "title": "2. Tech & Halvledere", "sector": "Tech",
        "instruments": [
            {"id": "SOXX", "label": "Semiconductors", "symbol_label": "SOXX", "candidates": ["SOXX", "SOXQ"]},
            {"id": "HACK", "label": "Cybersecurity",  "symbol_label": "HACK", "candidates": ["HACK"]},
            {"id": "BOTZ", "label": "Robotikk/AI",    "symbol_label": "BOTZ", "candidates": ["BOTZ"]},
        ],
    },
    {
        "key": "raavarer", "title": "3. Råvarer", "sector": "Rawarer",
        "instruments": [
            {"id": "DBC",  "label": "Commodity bred", "symbol_label": "DBC",  "candidates": ["DBC", "PDBC"]},
            {"id": "USO",  "label": "Olje (WTI)",     "symbol_label": "USO",  "candidates": ["USO"]},
            {"id": "UNG",  "label": "Naturgass",      "symbol_label": "UNG",  "candidates": ["UNG"]},
            {"id": "COPX", "label": "Kobbergruver",   "symbol_label": "COPX", "candidates": ["COPX"]},
            {"id": "XME",  "label": "Metaller/gruver","symbol_label": "XME",  "candidates": ["XME"]},
            {"id": "XLE",  "label": "Energi-aksjer",  "symbol_label": "XLE",  "candidates": ["XLE"]},
            {"id": "DBA",  "label": "Landbruk",       "symbol_label": "DBA",  "candidates": ["DBA"]},
        ],
    },
    {
        "key": "edelmetaller", "title": "4. Edelmetaller", "sector": "Edelmetaller",
        "instruments": [
            {"id": "GLD",  "label": "Gull",           "symbol_label": "GLD",  "candidates": ["GLD", "IAU"]},
            {"id": "SLV",  "label": "Sølv",           "symbol_label": "SLV",  "candidates": ["SLV"]},
            {"id": "GDX",  "label": "Gullgruver",     "symbol_label": "GDX",  "candidates": ["GDX"]},
            {"id": "GDXJ", "label": "Junior gull",    "symbol_label": "GDXJ", "candidates": ["GDXJ"]},
            {"id": "SIL",  "label": "Sølvgruver",     "symbol_label": "SIL",  "candidates": ["SIL"]},
            {"id": "SILJ", "label": "Junior sølv",    "symbol_label": "SILJ", "candidates": ["SILJ"]},
            {"id": "PPLT", "label": "Platina",        "symbol_label": "PPLT", "candidates": ["PPLT"]},
            {"id": "PALL", "label": "Palladium",      "symbol_label": "PALL", "candidates": ["PALL"]},
        ],
    },
    {
        "key": "uran", "title": "5. Uranium", "sector": "Rawarer",
        "instruments": [
            {"id": "URA", "label": "Uranium ETF", "symbol_label": "URA", "candidates": ["URA"]},
        ],
    },
    {
        "key": "crypto", "title": "6. Crypto", "sector": "Crypto",
        "instruments": [
            {"id": "BTC",  "label": "Bitcoin",  "symbol_label": "BTC",  "candidates": ["BTC-USD"]},
            {"id": "ETHA", "label": "Ethereum", "symbol_label": "ETH",  "candidates": ["ETH-USD"]},
        ],
    },
]

# DPM-stil aktivaklasse (underklasse-henvisning per instrument)
ASSET_SUBCLASS = {
    "SPY": "Stocks", "QQQ": "Stocks", "IWM": "Stocks", "ACWI": "Stocks",
    "EXSA": "Stocks", "EEM": "Stocks", "VNQ": "Stocks",
    "SOXX": "Tech", "HACK": "Tech", "BOTZ": "Tech",
    "TLT": "Bonds", "HYG": "Bonds", "UUP": "Cash", "FXE": "Cash", "CEW": "Cash",
    "GLD": "Edelmetaller", "SLV": "Edelmetaller", "GDX": "Edelmetaller", "GDXJ": "Edelmetaller",
    "SIL": "Edelmetaller", "SILJ": "Edelmetaller", "PPLT": "Edelmetaller", "PALL": "Edelmetaller",
    "DBC": "Commodity", "USO": "Commodity", "UNG": "Commodity", "COPX": "Commodity",
    "XME": "Commodity", "XLE": "Commodity", "DBA": "Commodity", "URA": "Commodity",
    "BTC": "Crypto", "ETHA": "Crypto",
}

# Sykliske instrumenter for leadership ranking (alt unntatt rene edelmetaller/cash)
CYCLICAL_IDS = [
    "SPY", "QQQ", "IWM", "ACWI", "EXSA", "EEM", "VNQ",
    "SOXX", "HACK", "BOTZ",
    "DBC", "USO", "UNG", "COPX", "XME", "XLE", "DBA", "URA",
    "PALL", "BTC", "ETHA",
    "TLT", "FXE", "UUP",
]

# Hovedinstrumenter for kapitalrotasjon (store trender på tvers av klasser)
ROTATION_MAIN = ["SPY", "EEM", "USO", "URA", "XLE", "SLV", "BTC", "NOK", "DBA", "ACWI", "VNQ"]

# Sykliske par (intern rotasjon)
CYCLICAL_PAIRS = [
    ("XLE", "URA",  "Energi vs Uran"),
    ("USO", "XLE",  "Olje vs Energi-aksjer"),
    ("EEM", "SPY",  "EM vs US"),
    ("IWM", "SPY",  "Small-cap vs Large-cap"),
    ("SOXX", "QQQ", "Halvledere vs Nasdaq"),
    ("COPX", "XME", "Kobber vs Metaller"),
    ("BTC", "QQQ",  "Krypto vs Tech"),
    ("DBA", "DBC",  "Agri vs Bred råvare"),
    ("URA", "SPY",  "Uran vs US-aksjer"),
]

# TradingView-symbolmapping (krypto -> spot, ikke ETF)
TV_SYMBOL_MAP = {"BTC": "BTCUSD", "ETH": "ETHUSD", "ETHA": "ETHUSD", "NOK": "USDNOK"}

# Kuratert sett for korrelasjonsmatrise (hovedaktivaklasser – en 33x33 er uleselig)
CORR_SET = ["SPY", "QQQ", "IWM", "EEM", "TLT", "HYG", "GLD", "SLV",
            "DBC", "USO", "XLE", "URA", "BTC", "UUP"]

# Instrumenter på RRG-scatter (leadership vs gull). Holdes lesbart.
RRG_SET = ["SPY", "QQQ", "IWM", "EEM", "ACWI", "SOXX", "XLE", "USO", "DBC",
           "COPX", "SLV", "GDX", "URA", "BTC", "TLT", "VNQ"]

# ──────────────────────────────────────────────────────────────────
# SIGNAL-PARAMETRE
# ──────────────────────────────────────────────────────────────────
# Relativ styrke: multi-horisont ROC (momentum) på ratio mot baseline.
# Krever IKKE lang historikk slik 50MA-på-ratio gjør.
ROC_HORIZONS = {"1M": 21, "3M": 63, "6M": 126, "12M": 252}  # handelsdager
ROC_WEIGHTS = {"1M": 0.20, "3M": 0.35, "6M": 0.25, "12M": 0.20}

# "Slår gull" = positiv vektet ROC mot gull på kort+mellomlang horisont.
BEATS_ROC_HORIZONS = ["1M", "3M"]  # enten/begge positiv => slår

# Sjanger i medvind hvis >= 70 % av medlemmene slår både gull og dollar
GENRE_TAILWIND_PCT = 70.0
GENRE_DOWNTREND_PCT = 70.0  # >=70 % taper => nedadgående

# Northstar-score (0-100, høyere = lavere risiko / bedre entry)
SCORE_TIMEFRAMES = ["weekly", "monthly", "quarterly"]

# Portefølje
CASH_THRESHOLD = 55      # min score for tildeling
MAX_POSITIONS = 7
OVERBOUGHT_RSI = 65
OVERBOUGHT_MACD = 2
STRETCH_36 = 0.20
VOL_TARGET_ANNUAL = 0.12  # 12 % årlig vol-mål for posisjonsstørrelse

# Risikometrikker
RISK_LOOKBACK_DAYS = 252  # 1 år for vol/Sharpe/drawdown
RISK_FREE_ANNUAL = 0.04   # antatt risikofri rente for Sharpe

# Bredde
BREADTH_MA = [50, 200]    # % over disse MA-ene

# ──────────────────────────────────────────────────────────────────
# COLORBLIND-TRYGG PALETT (Okabe-Ito) – aldri rød/grønn alene
# ──────────────────────────────────────────────────────────────────
PALETTE = {
    "up":      "#0072B2",  # blå = positivt/leder
    "down":    "#D55E00",  # vermillion = negativt/taper
    "neutral": "#999999",
    "warn":    "#E69F00",  # oransje = avventende
    "good":    "#009E73",  # bluish-green (sekundær)
    "accent":  "#56B4E9",
    "bg":      "#0b0d10",
    "panel":   "#14181d",
    "panel2":  "#1a1f26",
    "border":  "#262d36",
    "text":    "#e6edf3",
    "muted":   "#9aa7b5",
}


def tv_symbol(sym: str) -> str:
    """TradingView-symbol for en ticker (krypto -> spot)."""
    return TV_SYMBOL_MAP.get(sym, sym)


def all_instruments():
    """Flat liste av alle instrument-dicts med sektor og subclass påført."""
    out = []
    for g in INSTRUMENT_GROUPS:
        for inst in g["instruments"]:
            d = dict(inst)
            d["sector"] = g["sector"]
            d["category_key"] = g["key"]
            d["category_title"] = g["title"]
            d["subclass"] = ASSET_SUBCLASS.get(inst["id"], "")
            out.append(d)
    return out
