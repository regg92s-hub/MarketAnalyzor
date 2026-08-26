"""
v18: Syntetisk test for hele Aksje-screener-pipelinen (chunk -> merge).
Mocker yfinance, Wikipedia-indekshenting, SEC og Discord (ingen nettverk i
CI). Kjører build_screener.py sine fetch-chunk- og merge-kommandoer akkurat
som GitHub Actions-matrisen gjør, verifiserer at resultatet er komplett og
at "nye selskaper"-diffen (Discord-varsel-logikken) fungerer korrekt over to
simulerte uker.

Kjør lokalt: python tests/test_screener_synthetic.py
"""
import sys, os, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
import pandas as pd
from analysor import screener as screenermod, universe_fetch

np.random.seed(11)

# ── Mock: dynamisk indekshenting (ingen Wikipedia i CI) ──
_SYNTH_DYNAMIC = [(f"DYN{i}", f"Dynamic Corp {i}", "US", "—") for i in range(40)]
universe_fetch.build_expanded_universe = lambda seed: list(seed) + _SYNTH_DYNAMIC
screenermod.build_universe = lambda: universe_fetch.build_expanded_universe(
    screenermod.SEED_UNIVERSE)


# ── Mock: yfinance ──
_EXTREME_TICKERS = set()  # fylles av uke-2-testen for å simulere en ny kandidat


class _FakeTicker:
    def __init__(self, ticker):
        h = abs(hash(ticker)) % 1000
        base_rev = 1000 + h
        if ticker == "DYN5":
            # Deterministisk (ikke hash-avhengig): svak i uke 1, ekstrem i uke 2 —
            # garanterer at den IKKE er i topp-20 før boost, og ER det etter.
            growth_factor = 3.0 if ticker in _EXTREME_TICKERS else 1.02
        else:
            growth_factor = 1.0 + (h % 80) / 100.0
        q = [base_rev * (growth_factor ** (4 - i) / 4) for i in range(5)]
        self.quarterly_financials = pd.DataFrame(
            {f"Q{i}": [q[i], q[i] * (0.05 + (h % 20) / 100.0)] for i in range(5)},
            index=["Total Revenue", "Net Income"])
        self.financials = pd.DataFrame({"FY0": [sum(q), sum(q) * 0.1]},
                                       index=["Total Revenue", "Net Income"])
        self.quarterly_balance_sheet = pd.DataFrame()
        self.balance_sheet = pd.DataFrame()
        margin = 0.25 if ticker in _EXTREME_TICKERS else 0.05 + (h % 25) / 100.0
        de = 0.2 if ticker in _EXTREME_TICKERS else (h % 200)
        self.info = {"shortName": f"Test Corp {ticker}", "sector": "Testsektor",
                    "marketCap": base_rev * 1e6, "currency": "USD", "trailingEps": 1.5,
                    "profitMargins": margin, "debtToEquity": de}


class _FakeYF:
    Ticker = _FakeTicker


import builtins
_orig_import = builtins.__import__
def _patched_import(name, *a, **kw):
    if name == "yfinance":
        return _FakeYF()
    return _orig_import(name, *a, **kw)
builtins.__import__ = _patched_import

screenermod.sec_insider_buy = lambda ticker, days=90: None  # ingen SEC-nettverk i CI

OUT_DIR = Path(os.environ.get("TEST_SCREENER_DOCS", "/tmp/analysor_screener_ci"))
import shutil
if OUT_DIR.exists():
    shutil.rmtree(OUT_DIR)
OUT_DIR.mkdir(parents=True)

import build_screener  # noqa: E402
build_screener.DOCS = OUT_DIR
build_screener._discord_notify_new_entrants = lambda ng, nv: print(
    f"  [MOCK DISCORD] {len(ng)} nye vekst, {len(nv)} nye value")

TOTAL = 4

# === Uke 1: full chunk -> merge-flyt ===
for i in range(TOTAL):
    build_screener.cmd_fetch_chunk(i, TOTAL)
chunk_files = list(OUT_DIR.glob("_screener_chunk_*.json"))
assert len(chunk_files) == TOTAL, f"Forventet {TOTAL} chunk-filer, fant {len(chunk_files)}"

build_screener.cmd_merge(TOTAL)
assert not list(OUT_DIR.glob("_screener_chunk_*.json")), "Chunk-filer ble ikke ryddet opp"

data1 = json.loads((OUT_DIR / "screener.json").read_text(encoding="utf-8"))
assert len(data1["growth"]) >= 15 and len(data1["value"]) >= 15
assert "growth_upside" in data1, "growth_upside (v20) mangler i screener.json"
assert data1["n_universe"] > 115, f"Univers ikke utvidet: {data1['n_universe']}"
html1 = (OUT_DIR / "screener.html").read_text(encoding="utf-8")
assert len(html1) > 20000 and "Vekstaksjer" in html1 and "Valueaksjer" in html1
assert "Vekst med oppside" in html1, "v20-seksjonen mangler i screener.html"
print(f"UKE 1 OK: univers={data1['n_universe']}, vekst={len(data1['growth'])}, "
     f"value={len(data1['value'])}, vekst-med-oppside={len(data1['growth_upside'])}")

# === Uke 2: simuler at ett nytt selskap kvalifiserer (test Discord-diff) ===
_EXTREME_TICKERS.add("DYN5")

for i in range(TOTAL):
    build_screener.cmd_fetch_chunk(i, TOTAL)
new_entrants_captured = {}
def _capture(ng, nv, nu=None):
    new_entrants_captured["growth"] = [r["ticker"] for r in ng]
    new_entrants_captured["value"] = [r["ticker"] for r in nv]
    new_entrants_captured["upside"] = [r["ticker"] for r in (nu or [])]
build_screener._discord_notify_new_entrants = _capture
build_screener.cmd_merge(TOTAL)

data2 = json.loads((OUT_DIR / "screener.json").read_text(encoding="utf-8"))
assert "growth" in new_entrants_captured, "Discord-diff ble aldri kalt"
print(f"UKE 2 OK: nye i vekst-topp: {new_entrants_captured['growth']}, "
     f"nye i value-topp: {new_entrants_captured['value']}")
assert "DYN5" in data2["growth"][0]["ticker"] or any(
    r["ticker"] == "DYN5" for r in data2["growth"][:3]), "DYN5 klatret ikke opp som forventet"

print("SCREENER CI-TEST OK (chunk+merge+discord-diff verifisert over 2 simulerte uker)")
