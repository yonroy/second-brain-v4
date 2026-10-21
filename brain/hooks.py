"""Install / remove the v3 hooks in a codebase's `.claude/settings.local.json` (ADR-004).

Local settings, not the shared settings.json: the hook commands point at this machine's hub.
Our entries are recognised by the launcher path, so reinstalling is idempotent and other hooks
in the file are left alone.
"""
from __future__ import annotations

import json
from pathlib import Path

from brain import paths

MARK = "/bin/brain.py"
TOOL_MATCHER = "Read|Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell"


def desired() -> dict[str, list[dict]]:
    b = paths.brain_cmd()

    def h(args: str, timeout: int = 30) -> dict:
        return {"type": "command", "command": f"{b} {args}", "timeout": timeout}

    return {
        "SessionStart": [{"matcher": "startup|resume|clear|compact", "hooks": [h("start --hook")]}],
        "UserPromptSubmit": [{"hooks": [h("trap-check --hook --prompt", 15)]}],
        "PreToolUse": [{"matcher": TOOL_MATCHER, "hooks": [h("trap-check --hook", 15)]}],
        "Stop": [{"hooks": [h("end --check --hook", 60)]}],
    }


def settings_path(codebase: Path) -> Path:
    return codebase / ".claude" / "settings.local.json"


def _ours(entry: dict) -> bool:
    return any(MARK in str(x.get("command", "")).replace("\\", "/") for x in entry.get("hooks", []))


def _load(f: Path) -> dict:
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"❌ {paths.fwd(f)} không phải JSON hợp lệ ({e}); sửa tay rồi chạy lại.") from None


def _strip(cfg: dict) -> dict:
    hooks = cfg.get("hooks") or {}
    for ev in list(hooks):
        kept = [e for e in hooks[ev] if not _ours(e)]
        if kept:
            hooks[ev] = kept
        else:
            del hooks[ev]
    if hooks:
        cfg["hooks"] = hooks
    else:
        cfg.pop("hooks", None)
    return cfg


def _git_exclude(codebase: Path, rel: str) -> None:
    ex = codebase / ".git" / "info" / "exclude"
    if not ex.parent.is_dir():
        return
    cur = ex.read_text(encoding="utf-8") if ex.exists() else ""
    if rel not in cur.splitlines():
        ex.write_text(cur.rstrip("\n") + ("\n" if cur else "") + rel + "\n", encoding="utf-8")


def install(codebase: Path) -> str:
    f = settings_path(codebase)
    cfg = _strip(_load(f))
    hooks = cfg.setdefault("hooks", {})
    for ev, entries in desired().items():
        hooks.setdefault(ev, []).extend(entries)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    _git_exclude(codebase, ".claude/settings.local.json")
    return paths.fwd(f)


def remove(codebase: Path) -> str:
    f = settings_path(codebase)
    if not f.exists():
        return "không có"
    cfg = _strip(_load(f))
    f.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return paths.fwd(f)


def status(codebase: Path) -> dict[str, bool]:
    hooks = (_load(settings_path(codebase)).get("hooks") or {})
    return {ev: any(_ours(e) for e in hooks.get(ev, [])) for ev in desired()}
