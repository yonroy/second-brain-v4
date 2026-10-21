"""`brain skills install`: expose the execution-layer skills (ADR-006) to Claude Code.

Project scope links them into <codebase>/.claude/skills/<name> (git-excluded); --global links
into ~/.claude/skills. Links keep one copy in the package, so a package update reaches every
project. Order of attempts: symlink → Windows directory junction → copy.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from brain import paths
from brain.hooks import _git_exclude

SKILLS = paths.PACKAGE / "skills"


def names() -> list[str]:
    return sorted(d.name for d in SKILLS.iterdir() if (d / "SKILL.md").is_file())


def _link(src: Path, dst: Path) -> str:
    try:
        os.symlink(src, dst, target_is_directory=True)
        return "symlink"
    except OSError:
        pass
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)], capture_output=True, text=True)
        if r.returncode == 0:
            return "junction"
    shutil.copytree(src, dst)
    return "copy"


def _points_to(dst: Path, src: Path) -> bool:
    try:
        return dst.resolve() == src.resolve()
    except OSError:
        return False


def install(codebase: Path | None = None, global_: bool = False) -> list[tuple[str, str]]:
    target = (Path.home() / ".claude" / "skills") if global_ else codebase / ".claude" / "skills"
    target.mkdir(parents=True, exist_ok=True)
    done = []
    for name in names():
        src, dst = SKILLS / name, target / name
        if dst.exists() or dst.is_symlink():
            if _points_to(dst, src):
                done.append((name, "đã có"))
                continue
            if not (dst / ".brain-copy").exists():
                done.append((name, f"bỏ qua: {paths.fwd(dst)} đã tồn tại và không phải của brain"))
                continue
            shutil.rmtree(dst)  # our own stale copy: refresh it
        how = _link(src, dst)
        if how == "copy":
            (dst / ".brain-copy").write_text("copied by brain skills install\n", encoding="utf-8")
        done.append((name, how))
        if not global_:
            _git_exclude(codebase, f".claude/skills/{name}")
    return done
