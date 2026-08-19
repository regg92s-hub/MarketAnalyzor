"""
v18: Dynamisk universe-utvidelse — henter indekssammensetning fra Wikipedia
i stedet for å håndskrive tusenvis av tickere (upålitelig og blir raskt
utdatert). Wikipedias indekssider har stabile, velformaterte HTML-tabeller
som oppdateres av samfunnet når selskaper byttes ut — akkurat den ferskheten
vi vil ha uten å vedlikeholde listen selv.

Hver henting er DEFENSIV: hvis Wikipedia endrer tabellformat eller siden ikke
svarer, logges det og den ene indeksen hoppes over — resten av bygget
fortsetter med det vi fikk. Ticker-symboler konverteres til yfinance/Yahoo-
formatet (suffiks per børs) siden Wikipedia bruker rå børssymboler.

Kjøres kun fra GitHub Actions (fullt nettverk) — ikke testbart fra et
nettverksbegrenset lokalt miljø. Mockes i tests/test_screener_synthetic.py.
"""
from __future__ import annotations

import re


def _clean_symbol(s: str) -> str:
    return re.sub(r"\s+", "", str(s)).upper().replace("\u200b", "")


def _fetch_wiki_table(url: str, match: str, symbol_col_candidates, name_col_candidates):
    """Generisk Wikipedia-tabellhenter. Returnerer liste av (symbol, navn)
    eller [] ved feil. `match` er en tekst-substring for å identifisere riktig
    tabell blant flere på siden (pandas.read_html gir en liste av tabeller)."""
    try:
        import pandas as pd
        import requests
        headers = {"User-Agent": "MarketAnalyzor personal-research (Mozilla/5.0 compatible)"}
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        tables = pd.read_html(r.text)
        out = []
        for t in tables:
            cols = [str(c).strip() for c in t.columns]
            sym_col = next((c for c in cols if c in symbol_col_candidates), None)
            name_col = next((c for c in cols if c in name_col_candidates), None)
            if sym_col is None:
                continue
            for _, row in t.iterrows():
                sym = _clean_symbol(row[sym_col])
                if not sym or len(sym) > 12:
                    continue
                nm = str(row[name_col]).strip() if name_col else sym
                out.append((sym, nm))
            if out:
                break  # første tabell med treff er (nesten alltid) riktig
        return out
    except Exception as e:
        print(f"  Wikipedia-henting feilet ({match}): {e}")
        return []


def fetch_sp500():
    """S&P 500 (~500 selskaper, USA — ingen suffiks)."""
    rows = _fetch_wiki_table(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "S&P 500", ["Symbol"], ["Security", "Company"])
    return [(sym.replace(".", "-"), nm, "US", "—") for sym, nm in rows]


def fetch_dax():
    """DAX 40 (Tyskland, Xetra -> .DE)."""
    rows = _fetch_wiki_table("https://en.wikipedia.org/wiki/DAX", "DAX",
                             ["Ticker", "Symbol"], ["Company", "Name"])
    return [(f"{sym}.DE", nm, "DE", "—") for sym, nm in rows]


def fetch_mdax():
    """MDAX (Tyskland, midcap -> .DE)."""
    rows = _fetch_wiki_table("https://en.wikipedia.org/wiki/MDAX", "MDAX",
                             ["Ticker", "Symbol"], ["Company", "Name"])
    return [(f"{sym}.DE", nm, "DE", "—") for sym, nm in rows]


def fetch_tsx60():
    """S&P/TSX 60 (Canada -> .TO)."""
    rows = _fetch_wiki_table("https://en.wikipedia.org/wiki/S%26P/TSX_60", "TSX",
                             ["Symbol", "Ticker"], ["Company", "Name"])
    return [(f"{sym}.TO", nm, "CA", "—") for sym, nm in rows]


def fetch_omxs30():
    """OMX Stockholm 30 (Sverige -> .ST)."""
    rows = _fetch_wiki_table("https://en.wikipedia.org/wiki/OMX_Stockholm_30", "OMX",
                             ["Ticker symbol", "Symbol"], ["Company", "Name"])
    return [(f"{sym}.ST", nm, "SE", "—") for sym, nm in rows]


def fetch_obx():
    """OBX-indeksen (Norge -> .OL)."""
    rows = _fetch_wiki_table("https://en.wikipedia.org/wiki/OBX_Index", "OBX",
                             ["Ticker", "Symbol"], ["Company", "Name"])
    return [(f"{sym}.OL", nm, "NO", "—") for sym, nm in rows]


DYNAMIC_FETCHERS = [
    ("S&P 500", fetch_sp500),
    ("DAX", fetch_dax),
    ("MDAX", fetch_mdax),
    ("S&P/TSX 60", fetch_tsx60),
    ("OMX Stockholm 30", fetch_omxs30),
    ("OBX", fetch_obx),
]


def build_expanded_universe(seed_universe):
    """Kombinerer SEED_UNIVERSE (håndplukket, verifisert) med dynamisk
    hentede indekser. Deduplikerer på ticker. Selskaper som kun finnes i
    en dynamisk indeks får sektor '—' (ukjent) — yfinance fyller inn ekte
    sektor per aksje ved fundamentalhenting, dette er kun for visning før det."""
    seen = {t[0] for t in seed_universe}
    combined = list(seed_universe)
    for label, fn in DYNAMIC_FETCHERS:
        try:
            rows = fn()
        except Exception as e:
            print(f"  Indeks-henting {label} feilet totalt: {e}")
            rows = []
        added = 0
        for sym, nm, region, sector in rows:
            if sym in seen:
                continue
            seen.add(sym)
            combined.append((sym, nm, region, sector))
            added += 1
        print(f"  {label}: {added} nye tickere (av {len(rows)} hentet)")
    return combined
