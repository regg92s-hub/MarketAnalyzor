"""
Datahenting via yfinance, med kandidat-fallback per instrument.
Resampling til ukentlig/månedlig/kvartal.
"""
from __future__ import annotations
import time
import numpy as np
import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


def _log(msg):
    print(msg, flush=True)


def fetch_one(candidates: list, period: str = "max") -> tuple[pd.DataFrame | None, str | None]:
    """
    Prøver hver kandidat-ticker til en gir data. Returnerer (df, resolved_symbol).
    df har kolonne 'close_use' (justert close) og 'volume'.
    """
    if yf is None:
        return None, None
    for sym in candidates:
        for attempt in range(3):
            try:
                df = yf.download(sym, period=period, interval="1d",
                                 auto_adjust=True, progress=False, threads=False)
                if df is not None and not df.empty and len(df) > 30:
                    out = pd.DataFrame(index=df.index)
                    # auto_adjust=True -> 'Close' er justert
                    close_col = "Close" if "Close" in df.columns else df.columns[0]
                    if isinstance(df.columns, pd.MultiIndex):
                        close_col = [c for c in df.columns if c[0] == "Close"][0]
                        vol_col = [c for c in df.columns if c[0] == "Volume"]
                        out["close_use"] = df[close_col]
                        out["volume"] = df[vol_col[0]] if vol_col else np.nan
                    else:
                        out["close_use"] = df["Close"]
                        out["volume"] = df.get("Volume", np.nan)
                    out = out.dropna(subset=["close_use"])
                    out.index = pd.to_datetime(out.index).tz_localize(None)
                    _log(f"  yf ok: {sym}")
                    return out, sym
            except Exception as e:
                if attempt == 2:
                    _log(f"  yf feil {sym}: {e}")
                time.sleep(1.0)
    return None, None


def resample_frames(df: pd.DataFrame) -> dict:
    """Returner {daily, weekly, monthly, quarterly} med close_use + volume."""
    def rs(rule):
        out = pd.DataFrame()
        out["close_use"] = df["close_use"].resample(rule).last()
        out["volume"] = df["volume"].resample(rule).sum() if "volume" in df else np.nan
        return out.dropna(subset=["close_use"])
    return {
        "daily": df,
        "weekly": rs("W-FRI"),
        "monthly": rs("ME"),
        "quarterly": rs("QE"),
    }
