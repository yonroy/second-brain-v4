"""`_metrics/runs.sqlite`: one schema for every agent source (ADR-008).

A run is one agent session (main or subagent). Re-ingesting replaces rows by (source, run_id),
so ingest is idempotent and the v2 "harvest wrote every row twice" bug cannot recur.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

COLUMNS = [
    ("source", "TEXT NOT NULL"), ("run_id", "TEXT NOT NULL"), ("project", "TEXT"), ("brain_version", "TEXT"),
    ("agent", "TEXT"), ("role", "TEXT"), ("name", "TEXT"), ("ticket", "TEXT"), ("parent_id", "TEXT"),
    ("model", "TEXT"), ("started", "TEXT"), ("date", "TEXT"), ("minutes", "REAL"), ("turns", "INTEGER"),
    ("tool_calls", "INTEGER"), ("tool_errors", "INTEGER"), ("tokens", "INTEGER"), ("tokens_in", "INTEGER"),
    ("tokens_out", "INTEGER"), ("cost_usd", "REAL"), ("yielded", "INTEGER"), ("verdict", "TEXT"),
    ("p1", "INTEGER"), ("p2", "INTEGER"), ("p3", "INTEGER"), ("read_traps", "INTEGER"),
    ("read_context", "INTEGER"), ("read_decisions", "INTEGER"), ("brief_missing", "TEXT"),
    ("claims", "INTEGER"), ("unbacked_claims", "INTEGER"), ("traps_injected", "INTEGER"),
    ("stop_blocks", "INTEGER"), ("file", "TEXT"), ("ingested", "TEXT"),
]
NAMES = [c for c, _ in COLUMNS]


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute(f"CREATE TABLE IF NOT EXISTS runs ({', '.join(f'{c} {t}' for c, t in COLUMNS)}, "
                "PRIMARY KEY (source, run_id))")
    con.execute("CREATE TABLE IF NOT EXISTS events (source TEXT, run_id TEXT, kind TEXT, detail TEXT)")
    con.execute("CREATE INDEX IF NOT EXISTS events_run ON events(source, run_id)")
    have = {r[1] for r in con.execute("PRAGMA table_info(runs)")}
    for c, t in COLUMNS:  # forward-compatible: new columns appear on old databases
        if c not in have:
            con.execute(f"ALTER TABLE runs ADD COLUMN {c} {t.replace(' NOT NULL', '')}")
    return con


def upsert(con: sqlite3.Connection, rows: list[dict], events: list[dict] | None = None) -> int:
    for r in rows:
        con.execute(f"INSERT OR REPLACE INTO runs ({', '.join(NAMES)}) VALUES ({', '.join('?' * len(NAMES))})",
                    [r.get(c) for c in NAMES])
        con.execute("DELETE FROM events WHERE source = ? AND run_id = ?", (r["source"], r["run_id"]))
    for e in events or []:
        con.execute("INSERT INTO events (source, run_id, kind, detail) VALUES (?, ?, ?, ?)",
                    (e["source"], e["run_id"], e["kind"], e.get("detail", "")))
    con.commit()
    return len(rows)
