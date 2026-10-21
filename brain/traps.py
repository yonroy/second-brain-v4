"""`brain trap-check`: surface a trap the moment the agent touches what it is about (spec §6).

Called by Claude Code PreToolUse / UserPromptSubmit hooks and by the omp extension. Each trap is
injected at most once per session so the reminder stays a signal, not noise.
"""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path

from brain import paths
from brain.project import Project, Trap

PATH_KEYS = ("file_path", "path", "notebook_path")
TEXT_KEYS = ("command", "new_string", "content", "old_string", "pattern", "query")
SHELL_TOOLS = {"bash", "powershell", "shell", "exec"}


def _rel(p: Project, file_path: str) -> str:
    """Path relative to the codebase when it lies inside it (8.3 short and long spellings both work)."""
    fp = paths.fwd(file_path)
    candidates = [fp]
    if Path(paths.local(fp)).is_absolute():
        try:
            candidates.append(paths.fwd(paths.local(fp).resolve()))
        except OSError:
            pass
    bases = [paths.fwd(p.codebase)]
    try:
        bases.append(paths.fwd(p.codebase.resolve()))
    except OSError:
        pass
    for c in candidates:
        for b in bases:
            b = b.rstrip("/") + "/"
            if c.lower().startswith(b.lower()):
                return c[len(b):]
    return fp


def _path_hit(pattern: str, rel: str) -> bool:
    pat = pattern.replace("\\", "/").strip()
    if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel.lower(), pat.lower()):
        return True
    return "/" not in pat and fnmatch.fnmatch(rel.rsplit("/", 1)[-1], pat)


def _texts(tool_input: dict) -> str:
    parts = [str(tool_input.get(k, "")) for k in TEXT_KEYS]
    for e in tool_input.get("edits") or []:
        if isinstance(e, dict):
            parts += [str(e.get("new_string", "")), str(e.get("old_string", ""))]
    return "\n".join(parts).lower()


def match(p: Project, tool_input: dict | None = None, prompt: str = "") -> list[tuple[Trap, str]]:
    """Traps whose triggers hit this tool call or prompt, with the reason."""
    tool_input = tool_input or {}
    file_path = next((str(tool_input[k]) for k in PATH_KEYS if tool_input.get(k)), "")
    rel = _rel(p, file_path) if file_path else ""
    text = (_texts(tool_input) + "\n" + prompt.lower()).strip()
    hits = []
    for t in p.traps():
        for trig in t.trigger:
            if trig.lower().startswith("kw:"):
                kw = trig[3:].strip().lower()
                if kw and kw in text:
                    hits.append((t, f"từ khoá '{trig[3:].strip()}'"))
                    break
            elif rel and _path_hit(trig, rel):
                hits.append((t, rel))
                break
    return hits


def _seen_path(p: Project, sid: str) -> Path:
    return p.root / ".state" / f"{sid}.traps.json"


def check(p: Project, hook: dict, prompt_mode: bool = False) -> str:
    """Hook entrypoint. Returns the JSON the hook should print, or '' when nothing to say."""
    sid = str(hook.get("session_id") or "manual")
    if prompt_mode:
        hits = match(p, prompt=str(hook.get("prompt", "")))
        event = "UserPromptSubmit"
    else:
        hits = match(p, tool_input=hook.get("tool_input") or {})
        event = "PreToolUse"
    if not hits:
        return ""
    f = _seen_path(p, sid)
    try:
        seen = set(json.loads(f.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        seen = set()
    fresh = [(t, why) for t, why in hits if t.id not in seen]
    if not fresh:
        return ""
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(sorted(seen | {t.id for t, _ in fresh})), encoding="utf-8")
    lines = [f"⚠️ brain trap {t.id} (khớp {why}): {t.title} → {t.fix}" for t, why in fresh]
    lines.append(f"(Đã gặp trước đây, xem {paths.fwd(p.file('TRAPS.md'))}. Gặp lại thì thêm ngày vào `seen:`.)")
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": "\n".join(lines)}},
                      ensure_ascii=False)
