"""Baseline: the repo alone, no memory of any kind."""
from __future__ import annotations

from pathlib import Path

from bench.brains.base import Brain, Env
from bench.seed import Seed


class NoBrain(Brain):
    name = "none"

    def setup(self, work: Path, hub: Path, seed: Seed) -> Env:
        return Env()
