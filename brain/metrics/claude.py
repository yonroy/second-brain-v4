"""`brain ingest claude`: Claude Code transcripts (~/.claude/projects/<slug>/) → runs rows.

Main sessions are `<slug>/<sid>.jsonl`; subagents are `<slug>/<sid>/subagents/agent-*.jsonl` with
`agent-*.meta.json` (agentType). Assistant content blocks are split over several lines that share
one message id, so usage is counted once per message id.

Active minutes = sum of gaps between consecutive timestamps, each gap capped at IDLE_CAP (time the
human spends reading is not agent work). Cost is computed only when brain.toml [metrics.prices]
gives a price for the model; otherwise it stays NULL instead of guessing.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from brain import paths
from brain.metrics import ledger, omp_parse as op
from brain.recall.text import paths_in

IDLE_CAP = 300.0
SHELL_TOOLS = {"Bash", "PowerShell"}
FOLLOW_WINDOW = 5  # tool calls after an injection in which a suggested file counts as followed
TRAP_RE = re.compile(r"brain trap (M-\d+)")
SUBJECT_RE = re.compile(r"brain context `([^`]+)`")


def slug(path) -> str:
    """Claude Code's per-cwd folder name: every non-alphanumeric character becomes '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def project_dirs(codebase: Path, root: Path | None = None) -> list[Path]:
    root = root or Path.home() / ".claude" / "projects"
    if not root.is_dir():
        return []
    win = paths.fwd(codebase)                      # D:/x/y  (Claude on Windows)
    m = re.match(r"^([A-Za-z]):/(.*)$", win)
    wsl = f"/mnt/{m.group(1).lower()}/{m.group(2)}" if m else win   # /mnt/d/x/y (Claude inside WSL)
    want = {slug(win).lower(), slug(wsl).lower()}
    return [d for d in root.iterdir() if d.is_dir() and d.name.lower() in want]


def _ts(s) -> dt.datetime | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        return op._instant(s)
    except ValueError:
        return None


def _items(msg) -> list:
    c = (msg or {}).get("content")
    return c if isinstance(c, list) else []


def parse(path: Path, memory_root: Path, prices: dict | None = None) -> dict | None:
    stamps: list[dt.datetime] = []
    usage_by_id: dict[str, dict] = {}
    models: dict[str, int] = {}
    tools: dict[str, dict] = {}
    errors = 0
    last_text = ""
    corpus, results = [], []
    trap_ids: set[str] = set()
    stop_blocks = suggested = followed = 0
    pending: list[list] = []  # [paths still unvisited, tool calls left]
    sid = ""
    mem = paths.fwd(memory_root).lower().rstrip("/") + "/"
    reads = {"traps": 0, "context": 0, "decisions": 0}
    shell_ids: set[str] = set()
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            sid = sid or e.get("sessionId", "")
            t = _ts(e.get("timestamp"))
            if t:
                stamps.append(t)
            typ, msg = e.get("type"), e.get("message") or {}
            if typ == "attachment":
                a = e.get("attachment") or {}
                out = str(a.get("stdout", "")) + str(a.get("content", ""))
                if a.get("type", "").startswith("hook"):
                    # newer Claude Code logs one injection twice (hook_success stdout + hook_additional_context),
                    # and brain sends each trap once per session, so distinct ids are the count
                    trap_ids.update(TRAP_RE.findall(out))
                if a.get("type") == "hook_additional_context" and ("brain context" in out or "còn được dùng ở" in out):
                    subject = set(SUBJECT_RE.findall(out))
                    want = {q.lower() for q in paths_in(out) if q not in subject}
                    if want:
                        suggested += len(want)
                        pending.append([want, FOLLOW_WINDOW])
                if a.get("type", "").startswith("hook") and '"decision": "block"' in out.replace('":"', '": "'):
                    stop_blocks += 1
                continue
            if typ == "assistant":
                mid = msg.get("id") or e.get("uuid")
                if msg.get("usage"):
                    usage_by_id[mid] = msg["usage"]
                    models[msg.get("model", "")] = models.get(msg.get("model", ""), 0) + 1
                texts = [c.get("text", "") for c in _items(msg) if c.get("type") == "text" and c.get("text", "").strip()]
                if texts:
                    last_text = "\n".join(texts)
                for c in _items(msg):
                    if c.get("type") != "tool_use":
                        continue
                    tools[c.get("id", str(len(tools)))] = c
                    inp = c.get("input") or {}
                    blob = paths.fwd(json.dumps(inp, ensure_ascii=False).replace("\\\\", "/")).lower()
                    for item in pending:
                        hit = {q for q in item[0] if q in blob}
                        followed += len(hit)
                        item[0] -= hit
                        item[1] -= 1
                    pending = [i for i in pending if i[0] and i[1] > 0]
                    if mem in blob or "/_projects/" in blob:
                        reads["traps"] |= int("traps.md" in blob or "mistakes.md" in blob)
                        reads["context"] |= int("context.md" in blob)
                        reads["decisions"] |= int("decisions" in blob)
                    if c.get("name") in SHELL_TOOLS:
                        corpus.append(op._expand_vars(str(inp.get("command", ""))))
                        shell_ids.add(c.get("id", ""))
            elif typ == "user":
                for c in _items(msg):
                    if c.get("type") == "tool_result":
                        if c.get("is_error"):
                            errors += 1
                        if c.get("tool_use_id") in shell_ids:
                            content = c.get("content")
                            results.append(op._texts(content) if not isinstance(content, str) else content)
    if not stamps:
        return None
    stamps.sort()
    active = sum(min((b - a).total_seconds(), IDLE_CAP) for a, b in zip(stamps, stamps[1:]))
    tin = sum((u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
              + (u.get("cache_read_input_tokens") or 0) for u in usage_by_id.values())
    tout = sum(u.get("output_tokens") or 0 for u in usage_by_id.values())
    model = max(models, key=models.get) if models else ""
    claims, _ = op.find_claims(last_text, corpus, results)
    return {"session_id": sid, "started": stamps[0], "minutes": round(active / 60, 1), "turns": len(usage_by_id),
            "tool_calls": len(tools), "tool_errors": errors, "tokens_in": tin, "tokens_out": tout,
            "model": model, "cost_usd": _cost(usage_by_id.values(), prices or {}, model), "reads": reads,
            "claims": claims, "traps_injected": len(trap_ids), "stop_blocks": stop_blocks,
            "suggested": suggested, "followed": followed}


def _cost(usages, prices: dict, model: str) -> float | None:
    """prices = {model-prefix: [input, output, cache_write, cache_read]} in USD per million tokens."""
    key = next((k for k in sorted(prices, key=len, reverse=True) if model.startswith(k)), None)
    if not key:
        return None
    pin, pout, pw, pr = (list(prices[key]) + [None] * 4)[:4]
    pw = pin if pw is None else pw
    pr = pin if pr is None else pr
    total = 0.0
    for u in usages:
        total += ((u.get("input_tokens") or 0) * pin + (u.get("output_tokens") or 0) * pout
                  + (u.get("cache_creation_input_tokens") or 0) * pw + (u.get("cache_read_input_tokens") or 0) * pr) / 1e6
    return round(total, 6)


def scan(codebase: Path, memory_root: Path, project: str, version: str, since: str | None = None,
         prices: dict | None = None, roles: dict | None = None, root: Path | None = None,
         ingested: str = "") -> tuple[list[dict], list[dict]]:
    rows, events = [], []
    since_t = op._instant(since) if since else None
    for d in project_dirs(codebase, root):
        for main in sorted(d.glob("*.jsonl")):
            jobs = [(main, "main", "", "")]
            sub = main.with_suffix("") / "subagents"
            for f in sorted(sub.glob("agent-*.jsonl")) if sub.is_dir() else []:
                try:
                    meta = json.loads(f.with_suffix(".meta.json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    meta = {}
                jobs.append((f, meta.get("agentType") or "subagent", main.stem, meta.get("description", "")))
            for f, agent, parent, desc in jobs:
                r = parse(f, memory_root, prices)
                if not r or (since_t and r["started"] < since_t):
                    continue
                run_id = f.stem if parent else main.stem
                role = next((k for k, names in (roles or {}).items() if agent in (names or [])), "")
                unbacked = [c for c in r["claims"] if not c.backed]
                # hooks get the main session id, so the ledger belongs to the main run only
                spent = None if parent else ledger.load(memory_root / ".state", main.stem)
                inj = ledger.summarize(spent)
                rows.append({
                    "source": "claude", "run_id": run_id, "project": project, "brain_version": version, "agent": agent,
                    "role": role, "name": desc or main.stem[:8], "ticket": "", "parent_id": parent, "model": r["model"],
                    "started": r["started"].astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "date": r["started"].astimezone().date().isoformat(), "minutes": r["minutes"], "turns": r["turns"],
                    "tool_calls": r["tool_calls"], "tool_errors": r["tool_errors"],
                    "tokens": r["tokens_in"] + r["tokens_out"], "tokens_in": r["tokens_in"], "tokens_out": r["tokens_out"],
                    "cost_usd": r["cost_usd"], "yielded": None, "verdict": "", "p1": None, "p2": None, "p3": None,
                    "read_traps": r["reads"]["traps"], "read_context": r["reads"]["context"],
                    "read_decisions": r["reads"]["decisions"], "brief_missing": "", "claims": len(r["claims"]),
                    "unbacked_claims": len(unbacked), "traps_injected": max(r["traps_injected"], inj["ledger_traps"] or 0),
                    "stop_blocks": r["stop_blocks"], "file": paths.fwd(f), "ingested": ingested,
                    "recall_injected": inj["recall_injected"], "context_injected": inj["context_injected"],
                    "rename_warnings": inj["rename_warnings"], "budget_used": inj["budget_used"],
                    "suggested_files": r["suggested"], "followed_files": r["followed"],
                })
                events += [{"source": "claude", "run_id": run_id, "kind": "claim_unbacked",
                            "detail": f"{c.kind} `{c.text}` — {c.where}"} for c in unbacked]
                events += ledger.events("claude", run_id, spent)
    return rows, events
