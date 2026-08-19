"""
Realavkastning-benchmarking: norsk KPI (SSB), USDNOK + NOWA (Norges Bank),
US CPI (FRED) og gull. Bygger månedlige serier som porteføljen bruker til
fire-spors dekomponering: nominell NOK, real NOK, USD og gull-unser.

Alle kilder er gratis og uten autentisering. Alt degraderer robust til None
ved feil (nettverk, formatendring, tabell-bytte) — siden viser da "ukjent"
i stedet for å feile.

Merk SSB 2026-bruddet: KPI fikk ny COICOP-klassifisering og nytt basisår
(2025=100) fra januar 2026; gamle tabeller er arkivert. Tabell-ID kan
overstyres med miljøvariabelen SSB_KPI_TABLE hvis SSB bytter igjen.
"""
from __future__ import annotations
import os
import pandas as pd

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


def _log(m):
    print(m, flush=True)


# ── SSB: norsk KPI (PxWebApi v2, GET, json-stat2) ─────────────────
SSB_KPI_TABLES = ["03013", "1086", "14370"]  # kandidater; env-override først


def fetch_ssb_kpi() -> pd.Series | None:
    """Månedlig norsk KPI totalindeks. Returnerer Series indeksert på måned."""
    if requests is None:
        return None
    tables = ([os.environ.get("SSB_KPI_TABLE")] if os.environ.get("SSB_KPI_TABLE") else []) \
        + SSB_KPI_TABLES
    for tbl in tables:
        for url in (
            f"https://data.ssb.no/api/pxwebapi/v2/tables/{tbl}/data?lang=no&format=json-stat2",
            f"https://data.ssb.no/api/v0/dataset/{tbl}.json?lang=no",
        ):
            try:
                r = requests.get(url, timeout=30)
                if r.status_code != 200:
                    continue
                js = r.json()
                ds = js.get("dataset", js)  # v0 pakker i "dataset"
                dims = ds.get("dimension", {})
                values = ds.get("value", [])
                if not dims or not values:
                    continue
                order = ds.get("id") or dims.get("id") or list(
                    k for k in dims.keys() if k not in ("id", "size", "role"))
                sizes = ds.get("size") or dims.get("size")
                # Finn tidsdimensjon
                tname = None
                for k in order:
                    cat = dims.get(k, {}).get("category", {})
                    labels = list(cat.get("index", {}) or {})
                    if labels and all(("M" in str(l) or "-" in str(l)) and any(c.isdigit() for c in str(l))
                                      for l in labels[:3]):
                        tname = k
                if tname is None:
                    tname = order[-1]
                tcat = dims[tname]["category"]["index"]
                tlabels = sorted(tcat, key=lambda k: tcat[k])
                # Velg totalindeks-posisjon i øvrige dimensjoner (kode TOTAL/00/JA_TOTAL e.l.)
                pos = {}
                for k in order:
                    if k == tname:
                        continue
                    cat = dims[k]["category"]["index"]
                    chosen = 0
                    for code, idx in cat.items():
                        cu = str(code).upper()
                        if cu in ("TOTAL", "00", "TOTALT", "ALLE", "KPITOTAL", "TOTALINDEKS"):
                            chosen = idx
                            break
                    pos[k] = chosen
                # Lineær indeksering i json-stat2
                strides = {}
                acc = 1
                for k in reversed(order):
                    strides[k] = acc
                    acc *= sizes[order.index(k)]
                out_idx, out_val = [], []
                for lab in tlabels:
                    ti = tcat[lab]
                    flat = ti * strides[tname] + sum(pos[k] * strides[k] for k in order if k != tname)
                    if flat < len(values) and values[flat] is not None:
                        # 2025M01 -> Timestamp
                        s = str(lab).replace("M", "-")
                        try:
                            out_idx.append(pd.Timestamp(s + "-01"))
                            out_val.append(float(values[flat]))
                        except Exception:
                            continue
                if len(out_val) >= 24:
                    ser = pd.Series(out_val, index=out_idx).sort_index()
                    _log(f"  ssb kpi ok: tabell {tbl} ({len(ser)} mnd, siste {ser.index[-1]:%Y-%m})")
                    return ser
            except Exception as e:
                _log(f"  ssb kpi feil ({tbl}): {e}")
    return None


# ── Norges Bank: USDNOK månedlig + NOWA/styringsrente ─────────────
NB_BASE = "https://data.norges-bank.no/api/data"


def _fetch_nb_sdmx(path: str, params: str) -> pd.Series | None:
    """Generisk SDMX-JSON-parser for Norges Banks datavarehus."""
    if requests is None:
        return None
    url = f"{NB_BASE}/{path}?format=sdmx-json&{params}"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return None
        js = r.json()
        dsets = js.get("data", {}).get("dataSets", [])
        struct = js.get("data", {}).get("structure", {})
        if not dsets:
            return None
        obs_dims = struct.get("dimensions", {}).get("observation", [])
        tvals = []
        for d in obs_dims:
            if d.get("id") in ("TIME_PERIOD", "TIME"):
                tvals = [v.get("id") for v in d.get("values", [])]
        series = dsets[0].get("series", {})
        if not series:
            return None
        first = next(iter(series.values()))
        obs = first.get("observations", {})
        idx, vals = [], []
        for k, v in obs.items():
            ti = int(k.split(":")[0]) if ":" in k else int(k)
            if ti < len(tvals) and v and v[0] is not None:
                t = str(tvals[ti])
                try:
                    ts = pd.Timestamp(t if len(t) > 7 else t + "-01")
                    idx.append(ts)
                    vals.append(float(v[0]))
                except Exception:
                    continue
        if not vals:
            return None
        return pd.Series(vals, index=idx).sort_index()
    except Exception as e:
        _log(f"  norges bank feil ({path}): {e}")
        return None


def fetch_usdnok_monthly() -> pd.Series | None:
    s = _fetch_nb_sdmx("EXR/M.USD.NOK.SP", "lastNObservations=160")
    if s is not None:
        _log(f"  norges bank usdnok ok ({len(s)} mnd)")
    return s


def fetch_nowa() -> float | None:
    """Siste NOWA (overnattenrente) — NOK risikofri. Kandidat-nøkler."""
    for path in ("SHORT_RATES/B.NOWA.ON", "IR/B.NOWA.ON.R", "IR/B.KPRA.SD.R"):
        s = _fetch_nb_sdmx(path, "lastNObservations=5")
        if s is not None and len(s):
            _log(f"  nowa/rente ok via {path}: {float(s.iloc[-1]):.2f}%")
            return float(s.iloc[-1])
    return None


# ── Sammenstilling ────────────────────────────────────────────────
def _monthly_pairs(s: pd.Series | None, n: int = 132) -> list | None:
    if s is None or s.empty:
        return None
    m = s.resample("ME").last().dropna().tail(n)
    return [(d.strftime("%Y-%m"), round(float(v), 4)) for d, v in m.items()]


def build_benchmarks(raw: dict, fred_fetch, api_key: str) -> dict:
    """
    Bygg benchmark-pakken som sendes til klienten:
      kpi_no, cpi_us, usdnok, gold_usd  — månedlige serier (par-lister)
      kpi_no_yoy, cpi_us_yoy, nowa      — siste nøkkeltall
    fred_fetch = regime.fetch_fred_series (gjenbrukes for CPIAUCSL).
    """
    out = {}
    kpi = fetch_ssb_kpi()
    out["kpi_no"] = _monthly_pairs(kpi)
    if kpi is not None and len(kpi) > 13:
        out["kpi_no_yoy"] = round((float(kpi.iloc[-1]) / float(kpi.iloc[-13]) - 1) * 100, 2)

    cpi = fred_fetch("CPIAUCSL", api_key)
    out["cpi_us"] = _monthly_pairs(cpi)
    if cpi is not None and len(cpi.dropna()) > 13:
        c = cpi.dropna()
        out["cpi_us_yoy"] = round((float(c.iloc[-1]) / float(c.iloc[-13]) - 1) * 100, 2)

    # USDNOK: Norges Bank primært, yfinance-NOK som fallback
    nb = fetch_usdnok_monthly()
    if nb is None and raw.get("NOK") is not None:
        nb = raw["NOK"]["close_use"]
    out["usdnok"] = _monthly_pairs(nb)

    if raw.get("GLD") is not None:
        out["gold_usd"] = _monthly_pairs(raw["GLD"]["close_use"])

    nowa = fetch_nowa()
    # v14-sanity: NOWA skal ligge nær styringsrenten (4-5% i 2026). Verdier utenfor
    # 0-8% er nesten sikkert feil nøkkel/enhet fra API-et — da heller ingen verdi
    # enn feil verdi (6.00% på live-siden forvrengte alle Sharpe-tall).
    if nowa is not None and not (0.0 < nowa < 8.0):
        print(f"  ADVARSEL: NOWA={nowa} utenfor sanity-området (0-8%) — forkastes")
        nowa = None
    out["nowa"] = nowa
    return out
