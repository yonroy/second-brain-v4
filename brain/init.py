"""`brain init`: create _projects/<name> from templates and merge the CLAUDE.md block. Idempotent."""
from __future__ import annotations

import re
import tomllib
from datetime import date
from pathlib import Path

from brain import paths

TEMPLATES = paths.PACKAGE / "templates"
BLOCK_RE = re.compile(r"<!-- SECOND-BRAIN-V3:START.*?SECOND-BRAIN-V3:END -->", re.S)
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,63}$")


def _expand(text: str, tok: dict[str, str]) -> str:
    for k, v in tok.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def _write_new(path: Path, text: str, created: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    created.append(paths.fwd(path))


def merge_block(claude_md: Path, block: str) -> str:
    """Insert or replace the v3 block; returns what happened."""
    if not claude_md.exists():
        claude_md.write_text(f"# {claude_md.parent.name}\n\n{block}\n", encoding="utf-8", newline="\n")
        return "created"
    cur = claude_md.read_text(encoding="utf-8")
    if BLOCK_RE.search(cur):
        new = BLOCK_RE.sub(lambda _m: block.strip(), cur, count=1)
        if new != cur:
            claude_md.write_text(new, encoding="utf-8", newline="\n")
            return "updated"
        return "unchanged"
    claude_md.write_text(cur.rstrip() + "\n\n" + block, encoding="utf-8", newline="\n")
    return "appended"


def init(name: str | None, codebase: Path, hub: Path | None = None, today: date | None = None) -> dict:
    hub = hub or paths.hub()
    codebase = codebase.resolve()
    if not codebase.is_dir():
        raise SystemExit(f"❌ Codebase không tồn tại: {codebase}")
    name = name or codebase.name
    if not NAME_RE.match(name):
        raise SystemExit(f"❌ Tên project không hợp lệ: {name!r}")
    proj = paths.projects_dir(hub) / name
    cfg = proj / "brain.toml"
    if cfg.exists():
        existing = tomllib.loads(cfg.read_text(encoding="utf-8")).get("codebase", "")
        if not paths.same_path(existing, codebase):
            raise SystemExit(f"❌ Project '{name}' đã gắn với codebase khác: {existing}")
    tok = {"NAME": name, "CODEBASE": paths.fwd(codebase), "DATE": (today or date.today()).isoformat(),
           "BRAIN": paths.brain_cmd(), "PROJECT_DIR": paths.fwd(proj)}
    created: list[str] = []
    for d in ("_global", "_metrics", "_archive"):
        (hub / d).mkdir(parents=True, exist_ok=True)
    src_root = TEMPLATES / "project"
    for src in sorted(src_root.rglob("*")):
        if src.is_file():
            _write_new(proj / src.relative_to(src_root), _expand(src.read_text(encoding="utf-8"), tok), created)
    (proj / "journal").mkdir(exist_ok=True)
    block = _expand((TEMPLATES / "CLAUDE-block.md").read_text(encoding="utf-8"), tok)
    claude = merge_block(codebase / "CLAUDE.md", block)
    legacy = [d for d in ("MEMORY", "HARNESS") if (codebase / d).is_dir()]
    return {"project": paths.fwd(proj), "created": created, "claude_md": claude, "legacy": legacy}
