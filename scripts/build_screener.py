#!/usr/bin/env python3
"""
v18: Ukentlig bygg for Aksje-screener — TO MODUSER for å håndtere et stort
univers innenfor trygge yfinance-rate-limit-grenser per jobb:

  python build_screener.py fetch-chunk --index N --total M
      Henter fundamentaler for KUN 1/M-del av universet, skriver
      docs/_screener_chunk_N.json. Kjøres av parallelle GitHub Actions-jobber
      (matrix-strategi) — se screener.yml.

  python build_screener.py merge --total M
      Leser alle M chunk-filene, slår sammen, rangerer topp-20 per skjerm,
      sjekker innsidekjøp (kun for de endelige topp-40), sammenligner mot
      FORRIGE ukes screener.json for å finne NYE selskaper på listene
      (-> Discord-varsel), skriver screener.json + screener.html, rydder
      chunk-filene.

Sentinel-beskyttet: hvis forrige ukes screener.json ikke kan hentes (nettverk
feil), sendes ingen "nytt selskap"-varsler den uken i stedet for falske
positiver — men selve screeneren publiseres uansett.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysor import screener as screenermod  # noqa: E402
from analysor import render  # noqa: E402
from analysor.config import VERSION  # noqa: E402

DOCS = Path(__file__).resolve().parent.parent / "docs"


def log(msg):
    print(msg, flush=True)


def _chunk_path(index: int) -> Path:
    return DOCS / f"_screener_chunk_{index}.json"


def cmd_fetch_chunk(index: int, total: int):
    DOCS.mkdir(parents=True, exist_ok=True)
    log(f"Aksje-screener {VERSION} — fetch-chunk {index}/{total}")
    universe = screenermod.build_universe()
    log(f"Fullt univers (seed + dynamiske indekser): {len(universe)} tickere")
    result = screenermod.fetch_universe_chunk(universe, index, total)
    with open(_chunk_path(index), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    log(f"Chunk {index}: {result['n_ok']}/{result['n_slice']} tickere ga data "
       f"-> {_chunk_path(index).name}")


def _load_prev_screener():
    """Forrige ukes screener.json — lokal docs/ hvis den finnes (samme
    build-katalog gjenbrukt), ellers gh-pages rå-URL. None = genuint
    førstegangskjøring. '_FETCH_FAILED' = ukjent, ikke overskriv/varsle feil."""
    local = DOCS / "screener.json"
    if local.exists():
        try:
            return json.loads(local.read_text(encoding="utf-8"))
        except Exception:
            pass
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        return None
    try:
        import requests
        r = requests.get(f"https://raw.githubusercontent.com/{repo}/gh-pages/screener.json",
                         timeout=20)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
    except Exception as e:
        log(f"  klarte ikke hente forrige screener.json: {e}")
        return "_FETCH_FAILED"
    return "_FETCH_FAILED"


def _discord_notify_new_entrants(new_growth, new_value):
    url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not url or (not new_growth and not new_value):
        return
    try:
        import requests
        lines = ["📋 **Aksje-screener: nye selskaper denne uken**"]
        if new_growth:
            lines.append("**📈 Nye i Vekst-topp-20:**")
            for r in new_growth:
                yoy = r.get("rev_yoy")
                extra = f" — omsetning YoY {yoy:+.0f}%" if yoy is not None else ""
                lines.append(f"• {r['display_name']} ({r['ticker']}, {r['region_label']}){extra}")
        if new_value:
            lines.append("**💎 Nye i Value-topp-20:**")
            for r in new_value:
                eps = r.get("eps_yoy")
                extra = f" — EPS YoY {eps:+.0f}%" if eps is not None else ""
                lines.append(f"• {r['display_name']} ({r['ticker']}, {r['region_label']}){extra}")
        lines.append("Se full liste: screener.html")
        payload = {"content": "\n".join(lines)[:1900]}
        requests.post(url, json=payload, timeout=15)
        log(f"Discord-varsel sendt: {len(new_growth)} nye vekst, {len(new_value)} nye value")
    except Exception as e:
        log(f"  Discord-varsel feilet: {e}")


def _find_chunk_files(total: int):
    """Finner chunk-filene uansett om nedlasting av artifacts flatet ut
    mappestrukturen eller beholdt den (GitHub Actions-oppførsel varierer
    litt mellom enkeltfil- og wildcard-opplasting) — søker rekursivt under
    docs/ i stedet for å anta én bestemt plassering."""
    found = {}
    for p in DOCS.rglob("_screener_chunk_*.json"):
        try:
            idx = int(p.stem.rsplit("_", 1)[-1])
        except ValueError:
            continue
        if 0 <= idx < total and idx not in found:
            found[idx] = p
    return found


def cmd_merge(total: int):
    DOCS.mkdir(parents=True, exist_ok=True)
    log(f"Aksje-screener {VERSION} — slår sammen {total} chunks")

    chunk_files = _find_chunk_files(total)
    all_rows = []
    n_slice_total = 0
    missing_chunks = [i for i in range(total) if i not in chunk_files]
    for i, p in chunk_files.items():
        data = json.loads(p.read_text(encoding="utf-8"))
        all_rows.extend(data.get("rows", []))
        n_slice_total += data.get("n_slice", 0)

    if missing_chunks:
        log(f"ADVARSEL: manglende chunk-filer: {missing_chunks} (fetch-jobb kan ha feilet)")

    log(f"Totalt {len(all_rows)}/{n_slice_total} tickere ga data på tvers av alle chunks")

    if n_slice_total == 0 or len(all_rows) < n_slice_total * 0.3:
        log("ADVARSEL: for lite data samlet inn (<30%) — avbryter uten å "
           "overskrive forrige fungerende screener.html/json.")
        sys.exit(1)

    result = screenermod.rank_and_select(all_rows, top_n=20)
    result["version"] = VERSION
    result["n_universe"] = n_slice_total

    prev = _load_prev_screener()
    if prev not in (None, "_FETCH_FAILED"):
        prev_growth_ids = {r["ticker"] for r in prev.get("growth", [])}
        prev_value_ids = {r["ticker"] for r in prev.get("value", [])}
        new_growth = [r for r in result["growth"] if r["ticker"] not in prev_growth_ids]
        new_value = [r for r in result["value"] if r["ticker"] not in prev_value_ids]
        _discord_notify_new_entrants(new_growth, new_value)
    elif prev == "_FETCH_FAILED":
        log("  Forrige screener.json kunne ikke hentes — hopper over "
           "nye-selskap-varsel denne uken (unngår falske positiver).")
    else:
        log("  Første kjøring — ingen forrige liste å sammenligne mot.")

    with open(DOCS / "screener.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    log(f"screener.json skrevet ({len(result['growth'])} vekst, {len(result['value'])} value)")

    html = render.render_screener(result)
    (DOCS / "screener.html").write_text(html, encoding="utf-8")
    log("screener.html skrevet")

    for p in chunk_files.values():
        p.unlink(missing_ok=True)
    log(f"FERDIG — Aksje-screener {VERSION}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    fc = sub.add_parser("fetch-chunk")
    fc.add_argument("--index", type=int, required=True)
    fc.add_argument("--total", type=int, required=True)
    mg = sub.add_parser("merge")
    mg.add_argument("--total", type=int, required=True)
    args = ap.parse_args()

    if args.cmd == "fetch-chunk":
        cmd_fetch_chunk(args.index, args.total)
    elif args.cmd == "merge":
        cmd_merge(args.total)


if __name__ == "__main__":
    main()
