"""market-analysor: gull-relativt, regime-basert markeds-dashboard."""
try:
    from .config import VERSION
except Exception:  # robust: en delvis config skal ikke velte hele pakken
    VERSION = "unknown"

__all__ = ["VERSION"]
