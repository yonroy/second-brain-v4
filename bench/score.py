"""Turn a Claude Code stream-json transcript plus before/after memory snapshots into metrics."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SHELL_TOOLS = {"Bash", "PowerShell"}
TEST_CMD_RE = re.compile(r"unittest|pytest|\btests?\b", re.I)
CLAIM_RE = re.compile(r"\b(pass(ed|es)?|OK)\b|xanh|chạy (thành công|được)|đều đạt|tất cả .{0,20}test", re.I)


def load_events(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def tool_uses(events: list[dict]) -> list[dict]:
    out = []
    for e in events:
        if e.get("type") != "assistant":
            continue
        for c in e.get("message", {}).get("content", []) or []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                out.append({"name": c.get("name"), "input": c.get("input") or {}})
    return out


def final_result(events: list[dict]) -> dict:
    for e in reversed(events):
        if e.get("type") == "result":
            return e
    return {}


def _norm(s: str) -> str:
    return s.replace("\\", "/").lower()


def touches(tu: dict, markers: list[str]) -> bool:
    blob = _norm(json.dumps(tu["input"], ensure_ascii=False).replace("\\\\", "/"))
    return any(m and m in blob for m in markers)


def snapshot(paths: list[Path]) -> dict[str, tuple[str, str]]:
    """path -> (sha1, text) for every file under the given paths."""
    snap = {}
    for root in paths:
        files = [root] if root.is_file() else (sorted(root.rglob("*")) if root.exists() else [])
        for f in files:
            if f.is_file():
                data = f.read_bytes()
                snap[str(f)] = (hashlib.sha1(data).hexdigest(), data.decode("utf-8", errors="replace"))
    return snap


def memory_delta(before: dict, after: dict) -> str:
    """Text added to memory (new files whole, changed files' new lines)."""
    added = []
    for path, (h, text) in after.items():
        old = before.get(path)
        if old is None:
            added.append(text)
        elif old[0] != h:
            old_lines = set(old[1].splitlines())
            added.extend(line for line in text.splitlines() if line not in old_lines)
    return "\n".join(added)


def score_run(events: list[dict], memory_markers: list[str], before: dict, after: dict,
              keywords: list[str], has_memory: bool) -> dict:
    tus = tool_uses(events)
    res = final_result(events)
    usage = res.get("usage") or {}
    bash_cmds = [tu["input"].get("command", "") for tu in tus if tu["name"] in SHELL_TOOLS]
    ran_tests = any(TEST_CMD_RE.search(c) for c in bash_cmds)
    text = res.get("result") or ""
    delta = memory_delta(before, after) if has_memory else ""
    return {
        "ok": res.get("subtype") == "success" and not res.get("is_error"),
        "cost_usd": res.get("total_cost_usd"),
        "duration_s": round((res.get("duration_ms") or 0) / 1000, 1),
        "turns": res.get("num_turns"),
        "tokens_in": sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
        "tokens_out": usage.get("output_tokens") or 0,
        "tool_calls": len(tus),
        "read_memory": (any(touches(tu, memory_markers) for tu in tus) if has_memory else None),
        "memory_changed": (bool(delta.strip()) if has_memory else None),
        "memory_updated": (any(k.lower() in delta.lower() for k in keywords) if has_memory else None),
        "ran_tests": ran_tests,
        "claim_unbacked": bool(CLAIM_RE.search(text)) and not ran_tests,
        "result_tail": text[-400:],
    }
