"""What the Recall layer injects, and when (spec v4 §6, ADR-011/012).

Deterministic: same index + same event → same text. Budgeted: a per-session ledger caps total characters and
lets every key (trap, file, history unit) through once. Generalises v3 `traps.check`.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from brain import paths
from brain.project import Project
from brain.recall import code, history
from brain.recall.text import norm, paths_in, terms
from brain.traps import _rel, match as trap_match

DEF_RE = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)", re.M)


def limits(p: Project) -> dict:
    r = p.config.get("recall", {})
    return {"budget": int(r.get("budget_chars", 4000)), "file": int(r.get("file_chars", 800)),
            "prompt_hits": int(r.get("prompt_hits", 3)), "decisions": int(r.get("start_decisions", 8))}


@dataclass
class Ledger:
    path: Path
    budget: int
    spent: dict = field(default_factory=dict)

    @classmethod
    def load(cls, p: Project, sid: str) -> "Ledger":
        f = p.root / ".state" / f"{sid}.ledger.json"
        try:
            spent = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            spent = {}
        return cls(f, limits(p)["budget"], spent)

    @property
    def used(self) -> int:
        return sum(self.spent.values())

    def take(self, key: str, text: str, essential: bool = False) -> bool:
        """Record and allow `text` unless already sent this session or over budget (traps/warnings are essential)."""
        if key in self.spent:
            return False
        if not essential and self.used + len(text) > self.budget:
            return False
        self.spent[key] = len(text)
        return True

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.spent, ensure_ascii=False), encoding="utf-8")


def _one_line(s: str, n: int) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------- file context (PreToolUse)
def file_context(p: Project, rel: str, max_chars: int) -> str:
    if not rel or rel.startswith("/") or ":" in rel[:3]:
        return ""
    lines = []
    deps = code.dependents(p, rel)
    if deps:
        lines.append(f"- File phụ thuộc vào file này ({len(deps)}): " + ", ".join(deps[:5]) + (" …" if len(deps) > 5 else ""))
    outside = []
    for name, _line in code.defs_in(p, rel)[:12]:
        for r in code.uses(p, name):
            if not r.path.endswith(".py") and r.path != rel:
                outside.append(f"{name} → {r.path}:{r.line}")
    if outside:
        lines.append("- Tên trong file này được tham chiếu ngoài code Python: " + "; ".join(sorted(set(outside))[:5]))
    defined = [n for n, _ in code.defs_in(p, rel)]
    about = history.about_file(p, rel, limit=3)
    seen = {h.key for h in about}
    about += [h for h in history.mentions(p, defined) if h.key not in seen]
    for h in about[:4]:
        label = {"commit": f"commit {h.ref} ({h.date})", "journal": f"journal {h.date}", "decision": f"quyết định {h.ref}",
                 "archive": f"archive {h.date}", "trap": f"trap {h.ref}", "work": f"story {h.ref}"}.get(h.kind, h.kind)
        lines.append(f"- {label}: {_one_line(h.text, 220)}")
    if not lines:
        return ""
    text = f"📎 brain context `{rel}`:\n" + "\n".join(lines)
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


# ---------------------------------------------------------------- rename / delete warning (PreToolUse Edit)
def _removed_defs(tool_input: dict) -> list[str]:
    pairs = [(tool_input.get("old_string", ""), tool_input.get("new_string", ""))]
    pairs += [(e.get("old_string", ""), e.get("new_string", "")) for e in tool_input.get("edits") or [] if isinstance(e, dict)]
    gone = []
    for old, new in pairs:
        kept = set(DEF_RE.findall(new or ""))
        gone += [n for n in DEF_RE.findall(old or "") if n not in kept]
    return sorted(set(gone))


def rename_warning(p: Project, rel: str, tool_input: dict) -> str:
    out = []
    for name in _removed_defs(tool_input):
        refs = [r for r in code.uses(p, name) if not (r.path == rel)]
        if refs:
            where = ", ".join(f"{r.path}:{r.line}" + ("" if r.kind == "code" else f" [{r.kind}]") for r in refs[:8])
            out.append(f"⚠️ brain: `{name}` còn được dùng ở {where}" + (" …" if len(refs) > 8 else "")
                       + ". Đổi hết chỗ gọi (kể cả config/data) hoặc giữ lại.")
    return "\n".join(out)


# ---------------------------------------------------------------- prompt recall (UserPromptSubmit)
def prompt_recall(p: Project, prompt: str, k: int) -> list[history.Hit]:
    qterms = set(terms(prompt))
    need = 2 if len(qterms) >= 3 else 1
    hits = []
    for h in history.search(p, prompt, limit=k * 3):
        if h.kind == "trap":
            continue  # traps have their own trigger path
        overlap = len(qterms & set(terms(h.text + " " + " ".join(h.files))))
        if overlap >= need:
            hits.append(h)
    return hits[:k]


def format_hit(h: history.Hit) -> str:
    return f"- [{h.kind} {h.ref} {h.date}] {_one_line(h.text, 260)}"


# ---------------------------------------------------------------- relevant decisions (SessionStart)
def _recent_files(p: Project, days: int = 7) -> set[str]:
    def git(*a):
        try:
            r = subprocess.run(["git", *a], cwd=p.codebase, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=30)
            return r.stdout if r.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            return ""
    out = {l.strip() for l in git("diff", "--name-only", "HEAD").splitlines() if l.strip()}
    out |= {l.strip() for l in git("log", f"--since={days}.days", "--name-only", "--format=").splitlines() if l.strip()}
    return out


def relevant_decisions(p: Project, limit: int) -> tuple[list, int]:
    active = [d for d in p.decisions() if d.status.startswith("active")]
    if len(active) <= limit:  # few decisions: printing all is cheap and loses nothing (v3 behaviour)
        return active, 0
    recent = _recent_files(p)
    doing = " ".join(s.path.read_text(encoding="utf-8", errors="ignore") for s in p.stories()
                     if s.meta.get("status") == "doing")
    doing_terms = set(terms(doing))
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    scored = []
    for d in active:
        text = d.summary
        adr = next(iter(sorted(p.file("decisions").glob(f"{d.id}-*.md"))), None)
        if adr:
            text += " " + adr.read_text(encoding="utf-8", errors="ignore")
        files = set(paths_in(text))
        score = 3 * len(files & recent) + (2 if d.date >= cutoff else 0) + min(3, len(doing_terms & set(terms(text))))
        if score > 0:
            scored.append((score, d.date, d))
    scored.sort(key=lambda x: (x[0], x[1], x[2].id), reverse=True)  # score, then newest
    picked = [d for _, _, d in scored[:limit]]
    return picked, len(active) - len(picked)


# ---------------------------------------------------------------- PreToolUse entrypoint
def context_for_tool(p: Project, hook: dict) -> str:
    sid = str(hook.get("session_id") or "manual")
    led = Ledger.load(p, sid)
    lim = limits(p)
    tool_input = hook.get("tool_input") or {}
    fp = next((str(tool_input[k]) for k in ("file_path", "path", "notebook_path") if tool_input.get(k)), "")
    rel = _rel(p, fp) if fp else ""
    parts = []
    for t, why in trap_match(p, tool_input=tool_input):
        line = f"⚠️ brain trap {t.id} (khớp {why}): {t.title} → {t.fix}"
        if led.take(f"trap:{t.id}", line, essential=True):
            parts.append(line)
    if rel:
        warn = rename_warning(p, rel, tool_input)
        if warn and led.take(f"rename:{rel}:{hashlib.sha1(warn.encode('utf-8')).hexdigest()[:10]}", warn, essential=True):
            parts.append(warn)
        ctx = file_context(p, rel, lim["file"])
        if ctx and led.take(f"file:{rel}", ctx):
            parts.append(ctx)
    if not parts:
        return ""
    led.save()
    return "\n".join(parts)


def context_for_prompt(p: Project, hook: dict) -> str:
    sid = str(hook.get("session_id") or "manual")
    led = Ledger.load(p, sid)
    prompt = str(hook.get("prompt", ""))
    parts = []
    for t, why in trap_match(p, prompt=prompt):
        line = f"⚠️ brain trap {t.id} (khớp {why}): {t.title} → {t.fix}"
        if led.take(f"trap:{t.id}", line, essential=True):
            parts.append(line)
    hist = [format_hit(h) for h in prompt_recall(p, prompt, limits(p)["prompt_hits"])
            if led.take(h.key, format_hit(h))]
    if hist:
        parts.append("📚 brain recall (lịch sử liên quan tới yêu cầu này):\n" + "\n".join(hist))
    try:
        from brain.recall import wiki
        ptr = []
        for h in wiki.prompt_pointers(prompt):
            line = f"- `{h.rel}` {h.title}: {_one_line(h.summary, 150)} ({h.file})"
            if led.take(h.key, line):
                ptr.append(line)
        if ptr:
            parts.append("📘 wiki có trang có thể liên quan (đọc nếu cần):\n" + "\n".join(ptr))
    except Exception:  # noqa: BLE001 — wiki is optional
        pass
    if not parts:
        return ""
    led.save()
    return "\n".join(parts)


def hook_json(event: str, text: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}, ensure_ascii=False)
