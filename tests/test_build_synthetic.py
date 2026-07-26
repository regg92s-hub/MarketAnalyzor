"""
v14/D2: Syntetisk full-bygg-test — kjøres i CI på hver push (ingen nettverk).
Monkeypatcher alle datakilder og kjører HELE bygget. Fanger:
  - avkuttede/ufullstendige filer (import-feil, manglende funksjoner)
  - runtime-feil ast.parse aldri ser (KeyError, AttributeError, ...)
  - tomt leaderboard (rendering/join-feil — bet live-siden i juli 2026)
  - avkuttet HTML (størrelsesgulv per side)
Kjør lokalt: python tests/test_build_synthetic.py
"""
import sys, os, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
import pandas as pd

from analysor import data as datamod, regime as regimemod, benchmarks as benchmarksmod, config

np.random.seed(20)
idx = pd.date_range("2009-01-01", pd.Timestamp.today().normalize(), freq="B")


def synth(t):
    n = len(idx)
    base = 50 + np.cumsum(np.random.randn(n) * 0.3) + np.linspace(0, t, n)
    base = np.maximum(base, 1.0)
    return pd.DataFrame({
        "close_use": base,
        "high": base * (1 + np.abs(np.random.randn(n) * 0.01)),
        "low": base * (1 - np.abs(np.random.randn(n) * 0.01)),
        "open": base,
        "volume": np.random.randint(100000, 1000000, n).astype(float),
    }, index=idx)


datamod.fetch_one = lambda c, period="max": (synth((hash(c[0]) % 90) - 25), c[0])
midx = pd.date_range("2010-01-01", pd.Timestamp.today().normalize(), freq="MS")


def fake_fred(series_id, api_key):
    base = {"DGS2": 2.0, "DGS10": 3.0, "DGS3MO": 2.5, "WALCL": 8e6, "BAMLH0A0HYM2": 4.0,
            "WTREGEN": 500000, "RRPONTSYD": 300000, "NFCI": -0.2, "DFII10": 1.5, "T10YIE": 2.3,
            "ECBASSETSW": 7e6, "JPNASSETS": 7e6, "DEXUSEU": 1.08, "DEXJPUS": 150.0,
            "CPIAUCSL": 300.0}.get(series_id, 1.0)
    return pd.Series(base * (1 + np.cumsum(np.random.randn(len(midx)) * 0.01)), index=midx)


regimemod.fetch_fred_series = fake_fred
regimemod.fetch_gpr = lambda: None
benchmarksmod.fetch_ssb_kpi = lambda: pd.Series(
    100 * (1 + np.cumsum(np.random.randn(len(midx)) * 0.003)), index=midx)
benchmarksmod.fetch_usdnok_monthly = lambda: pd.Series(
    10 + np.cumsum(np.random.randn(len(midx)) * 0.05), index=midx)
benchmarksmod.fetch_nowa = lambda: 4.5

import build  # noqa: E402

OUT = Path(os.environ.get("TEST_DOCS", "/tmp/analysor_ci"))
build.DOCS = OUT
OUT.mkdir(parents=True, exist_ok=True)
build.ensure_lwc = lambda: None
os.environ["FRED_API_KEY"] = "x"
os.environ["DISCORD_WEBHOOK_URL"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ.pop("GITHUB_REPOSITORY", None)  # ingen nettverkshenting av forrige tilstand

build.main()

# ── Assertions ────────────────────────────────────────────────────
PAGES_MIN_KB = {"index.html": 30, "trend.html": 60, "report.html": 400,
                "roadmap.html": 200, "portfolio.html": 30, "backtest.html": 15}
for page, min_kb in PAGES_MIN_KB.items():
    p = OUT / page
    assert p.exists(), f"MANGLER {page}"
    kb = p.stat().st_size / 1024
    assert kb >= min_kb, f"{page} er {kb:.0f}KB (< {min_kb}KB gulv) — avkuttet?"
    assert config.VERSION in p.read_text(encoding="utf-8"), f"{page} mangler versjonsstempel {config.VERSION}"

model = json.loads((OUT / "index.json").read_text(encoding="utf-8"))
lb = (model.get("today") or {}).get("leaderboard") or []
assert len(lb) >= 60, f"Leaderboard har bare {len(lb)} rader (< 60) — rendering/join-feil"
assert model.get("version") == config.VERSION

print(f"CI-TEST OK: {config.VERSION}, {len(lb)} leaderboard-rader, alle 6 sider over størrelsesgulv")
