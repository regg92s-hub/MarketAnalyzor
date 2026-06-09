#!/usr/bin/env python3
"""
Backfill av score-historikk (idempotent).

Rekonstruerer ~8 uker med ukentlige Northstar-score-snapshots fra prishistorikk,
slik at sektor-sparklines og trend har data fra dag én. Skriver til
docs/history/score_history.json. Ekte (senere) snapshots overskrives ikke.

Kjøres én gang i pipelinen før hovedbygg (valgfritt).
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa
from analysor import data as datamod, scoring, config  # noqa

DOCS = Path(__file__).resolve().parent.parent / "docs"
HIST = DOCS / "history"
WEEKS = 8


def log(m):
    print(m, flush=True)


def main():
    HIST.mkdir(parents=True, exist_ok=True)
    out_path = HIST / "score_history.json"
    existing = {}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    meta = config.all_instruments()
    raw = {}
    for m in meta:
        df, _ = datamod.fetch_one(m["candidates"])
        if df is not None:
            raw[m["id"]] = df
            log(f"  hentet {m['id']}")

    today = datetime.utcnow().date()
    # Ukentlige fredager bakover
    fridays = []
    d = today
    while len(fridays) < WEEKS:
        if d.weekday() == 4:
            fridays.append(d)
        d -= timedelta(days=1)
    fridays = sorted(fridays)

    written = 0
    for fri in fridays:
        key = fri.isoformat()
        snap = existing.get(key, {})
        if snap.get("_real"):  # ikke rør ekte snapshots
            continue
        cutoff = pd.Timestamp(fri)
        row = {"_backfilled": True}
        for iid, df in raw.items():
            sub = df[df.index <= cutoff]
            if len(sub) < 60:
                continue
            frames = datamod.resample_frames(sub)
            score, _ = scoring.northstar_score(frames)
            row[iid] = score
        existing[key] = row
        written += 1
        log(f"  skrev {key} ({len(row)-1} instrumenter)")

    out_path.write_text(json.dumps(existing, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
    log(f"Ferdig — {written} snapshots skrevet, {len(existing)} datoer totalt")


if __name__ == "__main__":
    main()
