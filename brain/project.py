"""A v3 project in the hub: config + parsers for its memory files (spec §4)."""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from brain import paths

FACT_TAG = re.compile(r"\[(\d{4}-\d{2}-\d{2})\|([^\]]+)\]\s*$")
TRAP_HEAD = re.compile(r"^##\s+(M-\d+)\s+(.*)$")
STORY_STATUS = {"todo", "doing", "done", "dropped"}
STORY_TYPES = {"tiny", "normal", "high-risk"}
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
PROOF_OK = re.compile(r"^(✅|❌)\s+(\d{4}-\d{2}-\d{2})\s+([0-9a-f]{7,40}|nogit)$")


class ProjectNotFound(Exception):
    pass


@dataclass
class Fact:
    line_no: int
    section: str
    text: str
    date: date | None
    source: str | None


@dataclass
class Trap:
    id: str
    title: str
    trigger: list[str] = field(default_factory=list)
    seen: list[str] = field(default_factory=list)
    fix: str = ""
    enforce: str = "none"

    @property
    def last_seen(self) -> str:
        return max(self.seen) if self.seen else ""


@dataclass
class ProofRow:
    line_no: int
    id: str
    behavior: str
    cmd: str
    result: str


@dataclass
class Story:
    path: Path
    meta: dict


@dataclass
class Decision:
    id: str
    date: str
    summary: str
    status: str


class Project:
    def __init__(self, root: Path):
        self.root = root
        self.config = tomllib.loads((root / "brain.toml").read_text(encoding="utf-8"))

    # ---- identity ----
    @property
    def name(self) -> str:
        return self.config["name"]

    @property
    def codebase(self) -> Path:
        return paths.local(self.config["codebase"])

    def limit(self, key: str, default: int) -> int:
        return int(self.config.get("limits", {}).get(key, default))

    def file(self, rel: str) -> Path:
        return self.root / rel

    def read(self, rel: str) -> str:
        p = self.file(rel)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def read_parsed(self, rel: str) -> str:
        """File text with HTML comments blanked (line numbers kept), so template examples are not data."""
        return HTML_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), self.read(rel))

    # ---- CONTEXT ----
    def facts(self) -> list[Fact]:
        out, section = [], ""
        for i, line in enumerate(self.read_parsed("CONTEXT.md").splitlines(), 1):
            if line.startswith("## "):
                section = line[3:].strip()
            elif line.lstrip().startswith("- ") and section:
                text = line.strip()[2:]
                m = FACT_TAG.search(text)
                d = None
                if m:
                    try:
                        d = date.fromisoformat(m.group(1))
                    except ValueError:
                        d = None
                out.append(Fact(i, section, text, d, m.group(2) if m else None))
        return out

    # ---- TRAPS ----
    def traps(self) -> list[Trap]:
        traps, cur = [], None
        for line in self.read_parsed("TRAPS.md").splitlines():
            m = TRAP_HEAD.match(line)
            if m:
                cur = Trap(m.group(1), m.group(2).strip())
                traps.append(cur)
                continue
            if cur is None or ":" not in line:
                continue
            key, _, val = line.partition(":")
            key, val = key.strip().lower(), val.strip()
            if key == "trigger":
                cur.trigger = [v.strip() for v in val.split(",") if v.strip()]
            elif key == "seen":
                cur.seen = [v.strip() for v in val.split(",") if v.strip()]
            elif key == "fix":
                cur.fix = val
            elif key == "enforce":
                cur.enforce = val or "none"
        return traps

    # ---- PROOF ----
    def proofs(self) -> list[ProofRow]:
        rows = []
        for i, line in enumerate(self.read_parsed("PROOF.md").splitlines(), 1):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and re.fullmatch(r"B-\d+", cells[0]):
                rows.append(ProofRow(i, cells[0], cells[1], cells[2].strip("`").strip(), cells[3]))
        return rows

    # ---- work/ ----
    def stories(self) -> list[Story]:
        d = self.file("work")
        if not d.is_dir():
            return []
        return [Story(p, parse_frontmatter(p.read_text(encoding="utf-8")))
                for p in sorted(d.glob("*.md")) if not p.name.startswith("_")]

    # ---- decisions/ ----
    def decisions(self) -> list[Decision]:
        out = []
        for line in self.read_parsed("decisions/INDEX.md").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4:
                m = re.search(r"(ADR-\d+|D-\d+)", cells[0])
                if m:
                    out.append(Decision(m.group(1), cells[1], cells[2], cells[3].lower()))
        return out


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    meta = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            v = v.split("#", 1)[0].strip()
            if v.startswith("[") and v.endswith("]"):
                meta[k.strip()] = [x.strip() for x in v[1:-1].split(",") if x.strip()]
            else:
                meta[k.strip()] = v
    return meta


def all_projects(h: Path | None = None) -> list[Project]:
    d = paths.projects_dir(h)
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.iterdir()):
        if (p / "brain.toml").is_file():
            try:
                out.append(Project(p))
            except (tomllib.TOMLDecodeError, KeyError):
                continue
    return out


def find_project(name: str | None = None, cwd: Path | None = None, h: Path | None = None) -> Project:
    projs = all_projects(h)
    if name:
        for p in projs:
            if p.name == name:
                return p
        raise ProjectNotFound(f"Không có project '{name}' trong {paths.projects_dir(h)}")
    here = paths.fwd((cwd or Path.cwd()).resolve()).lower().rstrip("/") + "/"
    best, best_len = None, -1
    for p in projs:
        for root in (p.codebase, p.root):
            try:
                root = root.resolve()  # expands Windows 8.3 short names (MINHTO~1) the same way as cwd
            except OSError:
                pass
            r = paths.fwd(root).lower().rstrip("/") + "/"
            if here.startswith(r) and len(r) > best_len:  # deepest match wins (nested codebases)
                best, best_len = p, len(r)
    if best is None:
        raise ProjectNotFound(f"cwd {paths.fwd(cwd)} không thuộc project v3 nào. Chạy `brain init` hoặc thêm --project.")
    return best
