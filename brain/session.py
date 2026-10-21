"""`brain start` / `brain end`: what the SessionStart and Stop hooks call (spec §6).

start  prints the smallest useful context and records the session's starting state.
end    writes journal/<date>-<sid8>.md from the transcript; with --check it asks the agent once
       to update memory when code changed during the session but memory did not.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from brain import gate, paths
from brain.project import Project
from brain.verify import load_log

MEMORY_GLOBS = ("CONTEXT.md", "TRAPS.md", "PROOF.md", "decisions/*.md", "work/*.md")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
CHECK_WORDS = ("test", "unittest", "pytest", "verify", "lint", "check")


# ---------------------------------------------------------------- helpers
def read_hook_input() -> dict:
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        data = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    try:
        return json.loads(data) if data.strip() else {}
    except json.JSONDecodeError:
        return {}


def _state_path(p: Project, sid: str) -> Path:
    return p.root / ".state" / f"{sid}.json"


def _git(p: Project, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=p.codebase, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def memory_mtime(p: Project) -> float:
    m = 0.0
    for g in MEMORY_GLOBS:
        for f in p.root.glob(g):
            if f.is_file() and not f.name.startswith("_"):
                m = max(m, f.stat().st_mtime)
    return m


def _snapshot(p: Project) -> dict:
    return {"started": time.time(), "head": _git(p, "rev-parse", "HEAD"),
            "porcelain": _git(p, "status", "--porcelain"), "memory_mtime": memory_mtime(p), "blocked": False}


def _load_state(p: Project, sid: str) -> dict | None:
    f = _state_path(p, sid)
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _save_state(p: Project, sid: str, st: dict) -> None:
    f = _state_path(p, sid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(st), encoding="utf-8")


# ---------------------------------------------------------------- start
def start_text(p: Project, hook: dict | None = None, max_traps: int = 5) -> str:
    hook = hook or {}
    sid = str(hook.get("session_id") or "manual")
    _save_state(p, sid, _snapshot(p))
    findings = gate.check(p)
    out = [f"=== brain start · {p.name} · {date.today().isoformat()} ===", gate.summary(p, findings)]
    out += [f"  {f}" for f in findings if f.level == gate.RED]
    ctx = [l for l in p.read("CONTEXT.md").splitlines() if not l.startswith(">")]
    out += ["", f"--- CONTEXT ({paths.fwd(p.file('CONTEXT.md'))}) ---", *[l for l in ctx if l.strip()]]
    active = [d for d in p.decisions() if d.status.startswith("active")]
    if active:
        out += ["", "--- Quyết định đang hiệu lực (decisions/INDEX.md) — làm theo, không làm ngược ---"]
        out += [f"- {d.id} ({d.date}) {d.summary}" for d in active[:15]]
    traps = sorted(p.traps(), key=lambda t: t.last_seen, reverse=True)
    if traps:
        out += ["", f"--- Trap gần nhất ({len(traps[:max_traps])}/{len(traps)}, đủ ở TRAPS.md) ---"]
        out += [f"- {t.id} {t.title} → {t.fix}" + (f"  [trigger: {', '.join(t.trigger)}]" if t.trigger else "")
                for t in traps[:max_traps]]
    doing = [s for s in p.stories() if s.meta.get("status") == "doing"]
    if doing:
        out += ["", "--- Story đang làm ---"] + [f"- {s.meta.get('id', s.path.stem)} {s.path.name}" for s in doing]
    out += ["", f"Luật ghi + thứ bậc sự thật: {paths.fwd(p.file('AGENTS.md'))}"]
    return "\n".join(out)


# ---------------------------------------------------------------- transcript digest
def _content_items(msg: dict) -> list:
    c = (msg or {}).get("content")
    return c if isinstance(c, list) else ([{"type": "text", "text": c}] if isinstance(c, str) else [])


def digest(transcript: Path | None, p: Project) -> dict:
    d = {"goal": "", "code_files": [], "memory_files": [], "checks": []}
    if not transcript or not transcript.exists():
        return d
    root = paths.fwd(p.root).lower().rstrip("/") + "/"
    seen_files: set[str] = set()
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        typ, msg = e.get("type"), e.get("message") or {}
        if typ == "user" and not d["goal"]:
            for c in _content_items(msg):
                if c.get("type") == "text" and c.get("text", "").strip() and not c["text"].startswith("<"):
                    d["goal"] = " ".join(c["text"].split())[:200]
                    break
        if typ != "assistant":
            continue
        for c in _content_items(msg):
            if c.get("type") != "tool_use":
                continue
            name, inp = c.get("name"), c.get("input") or {}
            if name in EDIT_TOOLS:
                fp = paths.fwd(inp.get("file_path") or inp.get("notebook_path") or "")
                if fp and fp not in seen_files:
                    seen_files.add(fp)
                    (d["memory_files"] if fp.lower().startswith(root) else d["code_files"]).append(fp)
            elif name in SHELL_TOOLS:
                cmd = " ".join(str(inp.get("command", "")).split())
                if any(w in cmd.lower() for w in CHECK_WORDS):
                    d["checks"].append(cmd[:140])
    return d


# ---------------------------------------------------------------- end
def _code_changed(p: Project, st: dict) -> bool:
    if _git(p, "rev-parse", "HEAD") != st.get("head", ""):
        return True
    return _git(p, "status", "--porcelain") != st.get("porcelain", "")


def write_journal(p: Project, sid: str, st: dict | None, hook: dict) -> Path:
    tp = hook.get("transcript_path")
    dg = digest(paths.local(tp) if tp else None, p)
    started = (st or {}).get("started", 0)
    verified = [f"{e['id']} {'✅' if e['ok'] else '❌'}" for e in load_log(p)
                if started and _ts(e.get("ts")) >= started]
    rel = lambda f: f.split("/")[-1]  # noqa: E731
    lines = [f"# {date.today().isoformat()} · phiên {short_sid(sid)}", ""]
    if dg["goal"]:
        lines.append(f"- Mục tiêu: {dg['goal']}")
    if dg["code_files"]:
        lines.append(f"- Code đã sửa ({len(dg['code_files'])}): " + ", ".join(dg["code_files"][:8]))
    if dg["memory_files"]:
        lines.append("- Memory đã sửa: " + ", ".join(sorted({rel(f) for f in dg["memory_files"]})))
    if dg["checks"]:
        lines.append(f"- Lệnh kiểm ({len(dg['checks'])}): `{dg['checks'][-1]}`")
    if verified:
        lines.append("- verify: " + ", ".join(verified[-8:]))
    head = _git(p, "rev-parse", "--short", "HEAD")
    dirty = len([l for l in _git(p, "status", "--porcelain").splitlines() if l.strip()])
    lines.append(f"- Commit: {((st or {}).get('head') or '?')[:7]} → {head or '?'}; chưa commit: {dirty} file")
    lines.append(f"- {gate.summary(p, gate.check(p))}")
    out = p.file("journal") / f"{date.today().isoformat()}-{short_sid(sid)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines[:15]) + "\n", encoding="utf-8", newline="\n")
    return out


def short_sid(sid: str) -> str:
    """8 chars that differ between sessions: uuid prefix for Claude, the time tail for omp-<pid>-<ms>."""
    clean = re.sub(r"[^A-Za-z0-9]", "", sid)
    return clean[:8] if re.match(r"^[0-9a-f]{8}-", sid) else clean[-8:]


def _ts(s) -> float:
    from datetime import datetime
    try:
        return datetime.fromisoformat(s).timestamp()
    except (TypeError, ValueError):
        return 0.0


def end(p: Project, hook: dict, check: bool) -> dict:
    """Returns {'block': reason} when the Stop hook should keep the agent going, else {'journal': path}."""
    sid = str(hook.get("session_id") or "manual")
    st = _load_state(p, sid)
    if check and st and not hook.get("stop_hook_active") and not st.get("blocked"):
        if _code_changed(p, st) and memory_mtime(p) <= st.get("memory_mtime", 0):
            st["blocked"] = True
            _save_state(p, sid, st)
            return {"block": (f"Code trong {paths.fwd(p.codebase)} đã đổi nhưng memory của {p.name} chưa cập nhật. "
                              f"Trước khi dừng: sửa {paths.fwd(p.file('CONTEXT.md'))} (Đang làm / Việc tiếp theo, "
                              "fact có [ngày|nguồn]; việc đã xong thì xoá khỏi Đang làm, không ghi thêm vào đó; "
                              "điều đã học về hệ thống thì ghi vào Môi trường / Kiến trúc); lỗi/bẫy mới → TRAPS.md; quyết định → decisions/INDEX.md; "
                              "behavior đổi → `brain verify <B-ID>`. Không có gì đáng ghi thì nói rõ lý do rồi dừng.")}
    return {"journal": paths.fwd(write_journal(p, sid, st, hook))}
