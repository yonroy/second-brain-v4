"""Neutral seed format shared by every brain adapter.

A seed is the knowledge a project "already has" before the task starts. Each adapter
renders the same seed into its own version's file layout, so versions compete on how
they surface knowledge, not on how much knowledge they were given.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Fact:
    section: str
    text: str
    date: str
    source: str


@dataclass
class Trap:
    id: str
    title: str
    trigger: list[str]
    symptom: str
    fix: str
    seen: list[str]


@dataclass
class Decision:
    id: str
    date: str
    title: str
    decision: str
    why: str


@dataclass
class Proof:
    id: str
    behavior: str
    cmd: str


@dataclass
class Seed:
    name: str
    summary: str
    stack: str
    test_cmd: str
    facts: list[Fact] = field(default_factory=list)
    traps: list[Trap] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    proofs: list[Proof] = field(default_factory=list)

    def facts_in(self, *sections: str) -> list[Fact]:
        return [f for f in self.facts if f.section in sections]


def load_seed(path: Path) -> Seed:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    p = data["project"]
    return Seed(
        name=p["name"],
        summary=p["summary"],
        stack=p["stack"],
        test_cmd=p["test_cmd"],
        facts=[Fact(**f) for f in data.get("facts", [])],
        traps=[Trap(**t) for t in data.get("traps", [])],
        decisions=[Decision(**d) for d in data.get("decisions", [])],
        proofs=[Proof(**p) for p in data.get("proofs", [])],
    )
