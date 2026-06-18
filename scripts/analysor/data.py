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
                    if isinstance(df.columns, pd.MultiIndex):
                        def col(name):
                            m = [c for c in df.columns if c[0] == name]
                            return df[m[0]] if m else None
                        out["close_use"] = col("Close")
                        out["high"] = col("High")
                        out["low"] = col("Low")
                        out["open"] = col("Open")
                        vol = col("Volume")
                        out["volume"] = vol if vol is not None else np.nan
                    else:
                        out["close_use"] = df["Close"]
                        out["high"] = df.get("High")
                        out["low"] = df.get("Low")
                        out["open"] = df.get("Open")
                        out["volume"] = df.get("Volume", np.nan)
                    # Fallback: hvis high/low mangler, bruk close
                    for c in ("high", "low", "open"):
                        if c not in out or out[c].isna().all():
                            out[c] = out["close_use"]
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
    """Returner {daily, weekly, monthly, quarterly} med OHLC + volume."""
    def rs(rule):
        out = pd.DataFrame()
        out["close_use"] = df["close_use"].resample(rule).last()
        out["high"] = df["high"].resample(rule).max() if "high" in df else out["close_use"]
        out["low"] = df["low"].resample(rule).min() if "low" in df else out["close_use"]
        out["open"] = df["open"].resample(rule).first() if "open" in df else out["close_use"]
        out["volume"] = df["volume"].resample(rule).sum() if "volume" in df else np.nan
        return out.dropna(subset=["close_use"])
    return {
        "daily": df,
        "weekly": rs("W-FRI"),
        "monthly": rs("ME"),
        "quarterly": rs("QE"),
    }
