"""`brain ingest omp`: omp subagent sessions → runs rows, using the v2-identical parser in omp_parse."""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from brain.metrics import omp_parse as op

V3_READ_PATTERNS = {"traps": ["TRAPS.md", "MEMORY/MISTAKES.md"], "context": ["CONTEXT.md"],
                    "decisions": ["decisions/INDEX.md", "decisions/ADR-", "MEMORY/DECISIONS.md"]}
V2_READ_PATTERNS = {"traps": ["MEMORY/MISTAKES.md"], "context": ["MEMORY/CONTEXT.md"],
                    "decisions": ["MEMORY/DECISIONS.md"]}
BRIEF = {
    "required": {
        "muc_tieu": ["Mục tiêu", "Goal", "Target", "Objective"],
        "khong_lam": ["Không làm", "Ranh giới", "Non-goal", "Boundaries"],
        "checklist": ["Checklist"],
        "dau_ra": ["Đầu ra", "Output", "Acceptance", "Báo cáo trả về"],
        "ngan_sach": ["Ngân sách", "Budget"],
    },
    "recommended": {
        "da_chot": ["Đã chốt", "Quyết định đã chốt", "Decided"],
        "doc_truoc": ["Đọc trước", "Read first"],
    },
}


def scan(sessions_dir: Path, cwds: list[Path], since: str | None, read_patterns: dict,
         live_hours: float = 24) -> list[op.Run]:
    op._parent_cache.clear()
    if not sessions_dir.is_dir() or not cwds:
        return []
    stale = dt.datetime.now().astimezone() - dt.timedelta(hours=live_hours)
    keyed = {k: v for k, v in read_patterns.items()}
    runs = [r for f in sorted(sessions_dir.rglob("*.jsonl"))
            if (r := op.read_session(f, [c.resolve() for c in cwds], since, keyed, stale))]
    return sorted(runs, key=lambda r: (r.started, r.sub_id))


def to_rows(runs: list[op.Run], project: str, version: str, roles: dict | None = None,
            ingested: str = "") -> tuple[list[dict], list[dict]]:
    roles = roles or {}
    reviewers = set(roles.get("reviewer") or ["data-reviewer"])
    rows, events = [], []
    cfg = {"brief": BRIEF}
    seen: set[str] = set()
    for r in runs:
        if r.running:
            continue  # same scope as agent_ops: live sessions are not booked
        if r.sub_id in seen:
            continue  # omp copies a subagent's file into later parent sessions; v2 counted each copy (+31% on AFE)
        seen.add(r.sub_id)
        f = op.findings_of(r.report, legacy=r.agent in reviewers)
        missing, _, _ = op.lint_brief(r.brief, cfg)
        t = re.search(r"(?i)\b([A-Z]{2,}-\d+)\b|dp-?(\d+)", r.name)
        ticket = (t.group(1) or f"DP-{t.group(2)}") if t else ""
        role = next((k for k, names in roles.items() if r.agent in (names or [])), "")
        unbacked = [c for c in r.claims if not c.backed]
        rows.append({
            "source": "omp", "run_id": r.sub_id, "project": project, "brain_version": version, "agent": r.agent,
            "role": role, "name": r.name, "ticket": ticket.upper(), "parent_id": "", "model": "",
            "started": r.started.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": r.started.astimezone().date().isoformat(), "minutes": round(r.minutes, 1), "turns": r.turns,
            "tool_calls": r.tool_calls, "tool_errors": r.tool_errors, "tokens": r.tokens, "tokens_in": None,
            "tokens_out": None, "cost_usd": round(r.cost, 4), "yielded": 1 if r.finished else 0,
            "verdict": op.verdict_of(r.agent, r.report, roles), "p1": f["P1"], "p2": f["P2"], "p3": f["P3"],
            "read_traps": r.reads.get("traps", r.reads.get("mistakes", 0)), "read_context": r.reads.get("context", 0),
            "read_decisions": r.reads.get("decisions", 0), "brief_missing": ",".join(missing),
            "claims": len(r.claims), "unbacked_claims": len(unbacked), "traps_injected": None, "stop_blocks": None,
            "file": r.file, "ingested": ingested,
        })
        events += [{"source": "omp", "run_id": r.sub_id, "kind": "claim_unbacked",
                    "detail": f"{c.kind} `{c.text}` — {c.where}"} for c in unbacked]
    return rows, events
