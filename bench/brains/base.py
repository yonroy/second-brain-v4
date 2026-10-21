"""Brain adapter contract.

An adapter turns a neutral Seed into one Second Brain version's on-disk layout.
Adding a version (v4, ...) means adding one module that subclasses Brain.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from bench.seed import Seed


@dataclass
class Env:
    """What the runner needs to launch the agent against this brain."""
    extra_env: dict[str, str] = field(default_factory=dict)
    add_dirs: list[Path] = field(default_factory=list)


class Brain:
    name = "base"

    def setup(self, work: Path, hub: Path, seed: Seed) -> Env:
        """Render the seed. `work` is the codebase (cwd of the agent), `hub` a private scratch hub."""
        raise NotImplementedError

    def memory_paths(self, work: Path, hub: Path, seed: Seed) -> list[Path]:
        """Directories or files whose changes count as memory updates."""
        return []

    def teardown(self, work: Path, hub: Path) -> None:
        pass


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def fwd(p: Path) -> str:
    return str(p).replace("\\", "/")
