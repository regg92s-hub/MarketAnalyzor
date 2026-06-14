"""
Delt HTML-layout: <head> med streng CSP, colorblind-trygg CSS, navigasjon,
og Lightweight Charts (selvhostet, med SRI om CDN brukes).

Sikkerhet (rapportens funn):
  - Streng Content-Security-Policy via <meta> (GitHub Pages kan ikke sette headere)
  - Lightweight Charts SELVHOSTES (lastet ned i bygg) - ingen tredjeparts-script
  - Ingen tredjeparts-analytics/trackere
"""
from .config import PALETTE, VERSION

# Lightweight Charts selvhostes i docs/ under bygg (build.py laster ned filen).
# Da unngaar vi CDN-avhengighet og SRI-hash som kan brekke; rapportens raad om
# aa selvhoste scripts -> ingen tredjeparts-XSS-flate og enklere CSP.
LWC_LOCAL = "lightweight-charts.standalone.production.js"
LWC_CDN = "https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"

# Streng CSP: alt fra egen origin, ingen tredjeparts-script.
CSP = (
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'"
)

NAV = """
<nav class="nav">
  <a href="index.html" class="{a0}">📈 Trend-oversikt</a>
  <a href="report.html" class="{a1}">📊 Market Daily Report</a>
  <a href="portfolio.html" class="{a2}">💼 Portefølje</a>
  <a href="backtest.html" class="{a3}">🧪 Backtest</a>
</nav>
"""


def css() -> str:
    p = PALETTE
    return f"""
:root {{
  --up:{p['up']}; --down:{p['down']}; --neutral:{p['neutral']}; --warn:{p['warn']};
  --good:{p['good']}; --accent:{p['accent']}; --bg:{p['bg']}; --panel:{p['panel']};
  --panel2:{p['panel2']}; --border:{p['border']}; --text:{p['text']}; --muted:{p['muted']};
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:16px; }}
.nav {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; position:sticky; top:0;
  background:var(--bg); padding:10px 0; z-index:10; border-bottom:1px solid var(--border); }}
.nav a {{ color:var(--muted); text-decoration:none; padding:7px 12px; border-radius:9px;
  font-weight:600; font-size:14px; border:1px solid transparent; }}
.nav a:hover {{ background:var(--panel2); }}
.nav a.active {{ background:var(--panel2); color:var(--text); border-color:var(--border); }}
h1 {{ font-size:22px; margin:6px 0 2px; }}
h2 {{ font-size:17px; margin:22px 0 6px; }}
h3 {{ font-size:14px; margin:0; }}
.sub {{ color:var(--muted); font-size:12px; margin:0 0 10px; }}
.section {{ background:var(--panel); border:1px solid var(--border); border-radius:14px;
  padding:16px; margin:14px 0; }}
.grid {{ display:grid; gap:12px; }}
.grid2 {{ grid-template-columns:1fr 1fr; }}
@media(max-width:760px) {{ .grid2 {{ grid-template-columns:1fr; }} }}
.sector-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }}
.sc {{ background:var(--panel2); border:1px solid var(--border); border-radius:11px;
  padding:11px 13px; text-decoration:none; color:var(--text); display:block; }}
.sc-name {{ font-weight:600; font-size:13px; }}
.sc-score {{ font-size:26px; font-weight:700; }}
.sc-label {{ font-size:11px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ text-align:left; padding:6px 8px; color:var(--muted); font-weight:600; font-size:11px;
  background:var(--panel2); border-bottom:1px solid var(--border); }}
td {{ padding:5px 8px; border-bottom:1px solid var(--border); }}
tr:last-child td {{ border-bottom:none; }}
.pill {{ display:inline-block; padding:2px 8px; border-radius:7px; font-size:12px; font-weight:600; }}
.muted {{ color:var(--muted); }}
.up {{ color:var(--up); }} .down {{ color:var(--down); }} .warn {{ color:var(--warn); }}
.tag {{ display:inline-block; padding:1px 6px; border-radius:6px; font-size:10px; font-weight:600;
  background:var(--panel2); border:1px solid var(--border); }}
.chip {{ display:inline-flex; align-items:center; gap:5px; padding:4px 10px; margin:2px;
  border-radius:8px; font-size:13px; font-weight:700; text-decoration:none;
  background:var(--panel2); border:1px solid var(--accent); color:var(--accent); }}
.chip:hover {{ background:var(--accent); color:#06121f; }}
.chip-tf {{ font-size:10px; font-weight:600; opacity:0.8; padding:1px 5px; border-radius:5px;
  background:rgba(86,180,233,0.18); }}
.lwc {{ width:100%; height:240px; }}
.tv {{ color:var(--accent); font-size:11px; text-decoration:none; }}
details {{ background:var(--panel2); border:1px solid var(--border); border-radius:9px;
  padding:8px 12px; margin:8px 0; }}
summary {{ cursor:pointer; font-weight:600; font-size:13px; color:var(--muted); }}
.btn {{ background:var(--accent); color:#06121f; border:none; border-radius:9px; padding:8px 14px;
  font-weight:700; cursor:pointer; font-size:13px; }}
.btn.secondary {{ background:var(--panel2); color:var(--text); border:1px solid var(--border); }}
input,select {{ background:var(--panel2); border:1px solid var(--border); color:var(--text);
  border-radius:8px; padding:6px 8px; font-size:13px; }}
footer {{ color:var(--muted); font-size:12px; margin:20px 0; }}
.kpi {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; }}
.k {{ background:var(--panel2); border:1px solid var(--border); border-radius:11px; padding:11px; }}
.k .lbl {{ font-size:11px; color:var(--muted); }}
.k .val {{ font-size:20px; font-weight:700; }}
.legend-icon {{ font-size:11px; }}
"""


def head(title: str, active: int) -> str:
    cls = ["", "", "", ""]
    cls[active] = "active"
    nav = NAV.format(a0=cls[0], a1=cls[1], a2=cls[2], a3=cls[3])
    return f"""<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="theme-color" content="#0b0d10">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-192.png">
<title>{title} — market-analysor</title>
<style>{css()}</style>
</head>
<body><div class="wrap">
{nav}
<script>
if ('serviceWorker' in navigator) {{
  window.addEventListener('load', function() {{
    try {{ navigator.serviceWorker.register('sw.js'); }} catch (e) {{}}
  }});
}}
</script>
"""


def lwc_script() -> str:
    """Selvhostet Lightweight Charts fra egen origin (lastet ned i bygg)."""
    return f'<script src="{LWC_LOCAL}"></script>'


def foot() -> str:
    return f"""
<footer>
  Generert {VERSION} · Data: yfinance/FRED · Metodikk: Northstar &amp; Badcharts / NFTRH ·
  <strong>Ikke finansrådgivning</strong> — ditt eget regelbaserte rammeverk.
</footer>
</div></body></html>"""
