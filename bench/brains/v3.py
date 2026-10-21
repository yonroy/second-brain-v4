"""Second Brain v3 baseline: the real V3 package (D:/SecondBrainV3/Brain, override BENCH_V3_PACKAGE), run as a subprocess.

v3 and v4 share the memory file format, so the seed is rendered with the same functions as v4; only the CLI
that installs CLAUDE.md, hooks and skills — and therefore what the agent sees at run time — comes from V3 (ADR-009).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from bench.brains.base import Brain, Env, fwd, write
from bench.brains.v4 import _context, _decisions, _proof, _slug, _traps
from bench.brains.history import make_commits, render_history
from bench.seed import Seed

V3_PACKAGE = Path(os.environ.get("BENCH_V3_PACKAGE", "D:/SecondBrainV3/Brain"))


class V3(Brain):
    name = "v3"

    def setup(self, work: Path, hub: Path, seed: Seed) -> Env:
        make_commits(work, seed)  # history commits first: init below adds CLAUDE.md on top
        subprocess.run(["git", "init", "-q"], cwd=work, check=True)
        env = {k: v for k, v in os.environ.items() if k != "SECOND_BRAIN_V4_ROOT"}
        env["SECOND_BRAIN_V3_ROOT"] = str(hub)
        r = subprocess.run([sys.executable, str(V3_PACKAGE / "bin" / "brain.py"), "init", "--name", seed.name,
                            "--path", str(work)], env=env, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
        proj = hub / "_projects" / seed.name
        if r.returncode != 0 or not (proj / "brain.toml").exists():
            raise RuntimeError(f"v3 init failed rc={r.returncode}: {(r.stdout + r.stderr)[-600:]}")
        write(proj / "CONTEXT.md", _context(seed))
        write(proj / "TRAPS.md", _traps(seed))
        write(proj / "decisions" / "INDEX.md", _decisions(seed))
        for d in seed.decisions:
            write(proj / "decisions" / f"{d.id}-{_slug(d.title)}.md",
                  f"# {d.id} — {d.title}\n\n**Ngày:** {d.date} · **Trạng thái:** {d.status}\n\n"
                  f"## Context\n{d.why}\n\n## Decision\n{d.decision}\n")
        write(proj / "PROOF.md", _proof(seed))
        render_history(hub, seed)
        return Env(extra_env={"SECOND_BRAIN_V3_ROOT": fwd(hub)}, add_dirs=[hub])

    def memory_paths(self, work: Path, hub: Path, seed: Seed) -> list[Path]:
        return [hub / "_projects" / seed.name]
