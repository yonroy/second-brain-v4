"""Recall ledgers (`<project>/.state/<sid>.ledger.json`) → per-run injection counters (spec v4 §9).

The ledger is the ground truth for what the Recall layer injected: stream-json output does not show
PreToolUse/UserPromptSubmit additionalContext, and bench runs keep no Claude transcript at all.
Keys (see `recall.surface`): `hist:<kind>:<ref>` prompt recall · `file:<rel>` file context ·
`rename:<rel>:<sha>` rename/delete warning · `trap:<id>` trap.
"""
from __future__ import annotations

import json
from pathlib import Path

COUNTERS = {"hist": "recall_injected", "file": "context_injected", "rename": "rename_warnings", "trap": "ledger_traps"}


def load(state_dir: Path, sid: str) -> dict[str, int] | None:
    """{key: chars}, or None when the session left no ledger (v3, no brain, nothing injected)."""
    f = state_dir / f"{sid}.ledger.json"
    try:
        spent = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {str(k): int(v) for k, v in spent.items()} if isinstance(spent, dict) else None


def summarize(spent: dict[str, int] | None) -> dict:
    if spent is None:
        return {c: None for c in (*COUNTERS.values(), "budget_used")}
    out = {c: 0 for c in COUNTERS.values()}
    for key in spent:
        col = COUNTERS.get(key.split(":", 1)[0])
        if col:
            out[col] += 1
    out["budget_used"] = sum(spent.values())
    return out


def events(source: str, run_id: str, spent: dict[str, int] | None) -> list[dict]:
    return [{"source": source, "run_id": run_id, "kind": "injected", "detail": f"{k} ({v} ký tự)"}
            for k, v in sorted((spent or {}).items())]


def from_dirs(state_dirs: list[Path]) -> dict:
    """Sum every ledger under the given `.state` dirs (one bench run = one hub = one session, usually)."""
    total = summarize(None)
    for d in state_dirs:
        for f in sorted(d.glob("*.ledger.json")):
            one = summarize(load(d, f.name[: -len(".ledger.json")]))
            if one["budget_used"] is not None:
                total = {k: (total[k] or 0) + v for k, v in one.items()}
    return total
