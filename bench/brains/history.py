"""Render a seed's [[history]] identically for every brain that keeps history (v3 and v4).

Commits are real, back-dated git commits. Each one only appends whitespace to the files it lists, so the
lesson lives in `git log`, never in the code the agent reads.
"""
from __future__ import annotations

import os
import subprocess
from collections import defaultdict
from pathlib import Path

from bench.brains.base import write
from bench.seed import Seed


def _git(work: Path, *args: str, date: str | None = None) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "dev", "GIT_AUTHOR_EMAIL": "dev@shop.local",
           "GIT_COMMITTER_NAME": "dev", "GIT_COMMITTER_EMAIL": "dev@shop.local"}
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{date}T10:00:00+07:00"
    subprocess.run(["git", *args], cwd=work, env=env, capture_output=True, check=True)


def make_commits(work: Path, seed: Seed) -> int:
    """Initial import + one commit per history commit, oldest first. Must run before anything else writes to work."""
    commits = sorted((h for h in seed.history if h.kind == "commit"), key=lambda h: h.date)
    if not commits:
        return 0
    _git(work, "init", "-q")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "chore: import project", date=commits[0].date[:8] + "01")
    for h in commits:
        for f in h.files:
            target = work / f
            if target.is_file():
                with target.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write("\n")
        _git(work, "add", "-A")
        _git(work, "commit", "-q", "--allow-empty", "-m", h.text, date=h.date)
    return len(commits)


def render_history(hub: Path, seed: Seed) -> None:
    proj = hub / "_projects" / seed.name
    archived = defaultdict(list)
    for i, h in enumerate(sorted(seed.history, key=lambda h: h.date)):
        if h.kind in ("journal", "transcript"):
            ref = h.ref or f"h{i:02d}"
            head = "phiên (tóm tắt hội thoại)" if h.kind == "transcript" else "phiên"
            write(proj / "journal" / f"{h.date}-{ref}.md", f"# {h.date} · {head} {ref}\n\n{h.text.strip()}\n")
        elif h.kind == "archived_fact":
            archived[h.date].append(h)
    for date, items in archived.items():
        stamp = date.replace("-", "")
        lines = [f"# {seed.name} — CONTEXT (bản trước khi dọn {date})", "", "## Môi trường"]
        lines += [f"- {h.text} [{h.date}|{h.ref or 'user'}]" for h in items]
        write(hub / "_archive" / f"{seed.name}-clean-{stamp}-090000" / "project" / "CONTEXT.md", "\n".join(lines) + "\n")
