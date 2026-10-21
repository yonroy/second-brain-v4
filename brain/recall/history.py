"""History index (spec v4 §4): `.index/history.sqlite`, SQLite FTS5 over normalised text.

Units: journal pages, decisions (index rows + ADR files, superseded included), traps, work stories, archived
CONTEXT facts and retired files, git commits. Incremental: file sources by (mtime, size); git from the last
indexed HEAD. The index is derived data — `--full` rebuilds it to the same content.
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

from brain import paths
from brain.project import FACT_TAG, TRAP_HEAD, Project
from brain.recall.text import fts_query, norm, paths_in

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (path TEXT PRIMARY KEY, sig TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS units USING fts5(
    kind UNINDEXED, ref UNINDEXED, date UNINDEXED, path UNINDEXED, files UNINDEXED, text UNINDEXED, norm,
    tokenize = 'unicode61');
"""


@dataclass
class Hit:
    kind: str
    ref: str
    date: str
    path: str
    files: list[str]
    text: str
    score: float

    @property
    def key(self) -> str:
        return f"hist:{self.kind}:{self.ref}"


def db_path(p: Project) -> Path:
    return p.root / ".index" / "history.sqlite"


def connect(p: Project) -> sqlite3.Connection:
    f = db_path(p)
    f.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f)
    con.executescript(SCHEMA)
    return con


# ---------------------------------------------------------------- extractors: path -> [(kind, ref, date, text, files)]
def _date_of(name: str) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else ""


def _journal(f: Path) -> list[tuple]:
    t = f.read_text(encoding="utf-8", errors="ignore")
    return [("journal", f.stem, _date_of(f.name), t, paths_in(t))]


def _decision_file(f: Path) -> list[tuple]:
    t = f.read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"(ADR-\d+|D-\d+)", f.name)
    d = re.search(r"\*\*Ngày:\*\*\s*(\d{4}-\d{2}-\d{2})", t)
    return [("decision", m.group(1) if m else f.stem, d.group(1) if d else "", t, paths_in(t))]


def _decision_index(p: Project) -> list[tuple]:
    return [("decision", d.id, d.date, f"{d.id} {d.summary} [{d.status}]", paths_in(d.summary)) for d in p.decisions()]


def _traps(p: Project) -> list[tuple]:
    out = []
    for t in p.traps():
        text = f"{t.id} {t.title}\ntrigger: {', '.join(t.trigger)}\nfix: {t.fix}"
        files = [x for x in t.trigger if not x.startswith("kw:")]
        out.append(("trap", t.id, t.last_seen, text, files + paths_in(t.fix)))
    return out


def _work(f: Path) -> list[tuple]:
    t = f.read_text(encoding="utf-8", errors="ignore")
    return [("work", f.stem, "", t, paths_in(t))]


def _archived_context(f: Path, current: set[str]) -> list[tuple]:
    """Fact lines of an old CONTEXT that are no longer in the current one."""
    folder_date = re.search(r"-clean-(\d{4})(\d{2})(\d{2})", str(f))
    fallback = "-".join(folder_date.groups()) if folder_date else ""
    out = []
    for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        s = line.strip()
        if not s.startswith("- ") or s in current:
            continue
        m = FACT_TAG.search(s)
        out.append(("archive", f"{f.parent.parent.name}:{i}", m.group(1) if m else fallback, s[2:], paths_in(s)))
    return out


def _retired(f: Path) -> list[tuple]:
    t = f.read_text(encoding="utf-8", errors="ignore")
    return [("archive", f"retired:{f.name}", "", t[:4000], paths_in(t))]


def _file_sources(p: Project) -> list[tuple[Path, callable]]:
    current = {l.strip() for l in p.read("CONTEXT.md").splitlines()}
    archive = p.root.parent.parent / "_archive"
    src: list[tuple[Path, callable]] = []
    src += [(f, _journal) for f in sorted(p.file("journal").glob("*.md"))]
    src += [(f, _decision_file) for f in sorted(p.file("decisions").glob("*.md")) if f.name != "INDEX.md"]
    src += [(f, _work) for f in sorted(p.file("work").glob("*.md")) if not f.name.startswith("_")]
    src += [(f, lambda f, c=current: _archived_context(f, c))
            for f in sorted(archive.glob(f"{p.name}-clean-*/project/CONTEXT.md"))]
    src += [(f, _retired) for f in sorted((archive / f"{p.name}-retired").rglob("*.md")) if f.name != "INDEX.md"]
    src += [(p.file("TRAPS.md"), lambda f: _traps(p)), (p.file("decisions/INDEX.md"), lambda f: _decision_index(p))]
    return src


# ---------------------------------------------------------------- git
def _git(p: Project, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=p.codebase, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _commits(p: Project, since: str | None) -> list[tuple]:
    rng = [f"{since}..HEAD"] if since else []
    raw = _git(p, "log", *rng, "--date=short", "--name-only", "--format=\x1e%h\x1f%ad\x1f%s\x1f%b\x1f")
    out = []
    for block in raw.split("\x1e")[1:]:
        parts = block.split("\x1f")
        if len(parts) < 5:
            continue
        h, d, subj, body, rest = parts[0], parts[1], parts[2], parts[3], parts[4]
        files = [x.strip() for x in rest.splitlines() if x.strip()]
        out.append(("commit", h, d, f"{subj}\n{body}".strip(), files))
    return out


# ---------------------------------------------------------------- build
def _insert(con, path: str, rows: list[tuple]) -> int:
    for kind, ref, date, text, files in rows:
        con.execute("INSERT INTO units(kind, ref, date, path, files, text, norm) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (kind, ref, date, path, json.dumps(sorted(set(files))), text, norm(text + " " + " ".join(files))))
    return len(rows)


def build(p: Project, full: bool = False) -> dict:
    con = connect(p)
    if full:
        con.executescript("DELETE FROM units; DELETE FROM sources; DELETE FROM meta;")
    stats = {"files": 0, "units": 0, "commits": 0}
    seen: set[str] = set()
    for f, extract in _file_sources(p):
        key = paths.fwd(f)
        seen.add(key)
        if not f.is_file():
            continue
        st = f.stat()
        sig = f"{st.st_mtime_ns}:{st.st_size}"
        old = con.execute("SELECT sig FROM sources WHERE path = ?", (key,)).fetchone()
        if old and old[0] == sig:
            continue
        con.execute("DELETE FROM units WHERE path = ?", (key,))
        stats["units"] += _insert(con, key, extract(f))
        con.execute("INSERT OR REPLACE INTO sources(path, sig) VALUES (?, ?)", (key, sig))
        stats["files"] += 1
    for (gone,) in con.execute("SELECT path FROM sources").fetchall():
        if gone not in seen and not gone.startswith("git:"):
            con.execute("DELETE FROM units WHERE path = ?", (gone,))
            con.execute("DELETE FROM sources WHERE path = ?", (gone,))
    head = _git(p, "rev-parse", "HEAD").strip()
    last = (con.execute("SELECT value FROM meta WHERE key = 'git_head'").fetchone() or [None])[0]
    if head and head != last:
        ancestor = bool(last) and subprocess.run(["git", "merge-base", "--is-ancestor", last, head], cwd=p.codebase,
                                                 capture_output=True).returncode == 0
        if not ancestor:
            con.execute("DELETE FROM units WHERE path = 'git:log'")
        rows = _commits(p, last if ancestor else None)
        stats["commits"] = _insert(con, "git:log", rows)
        stats["units"] += stats["commits"]
        con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('git_head', ?)", (head,))
        con.execute("INSERT OR REPLACE INTO sources(path, sig) VALUES ('git:log', ?)", (head,))
    con.commit()
    stats["total"] = con.execute("SELECT COUNT(*) FROM units").fetchone()[0]
    con.close()
    return stats


# ---------------------------------------------------------------- query
def _hit(row, score) -> Hit:
    kind, ref, date, path, files, text = row
    return Hit(kind, ref, date, path, json.loads(files or "[]"), text, score)


def search(p: Project, query: str, kind: str | None = None, file: str | None = None, limit: int = 5) -> list[Hit]:
    if not db_path(p).exists():
        return []
    q = fts_query(query)
    if not q:
        return []
    con = connect(p)
    sql = "SELECT kind, ref, date, path, files, text, bm25(units) FROM units WHERE units MATCH ?"
    args: list = [q]
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    rows = con.execute(sql + " ORDER BY bm25(units) LIMIT ?", args + [limit * 4]).fetchall()
    con.close()
    hits = []
    for r in rows:
        score = -r[6]  # bm25: lower is better
        if file and file in json.loads(r[4] or "[]"):
            score += 5.0
        hits.append(_hit(r[:6], score))
    hits.sort(key=lambda h: (-h.score, h.date, h.ref))
    return hits[:limit]


def about_file(p: Project, rel: str, limit: int = 4) -> list[Hit]:
    """Units that name this file: newest commit with a real reason, then journal/decision/archive/trap mentions."""
    if not db_path(p).exists():
        return []
    con = connect(p)
    rows = con.execute("SELECT kind, ref, date, path, files, text FROM units WHERE files LIKE ?",
                       (f'%"{rel}"%',)).fetchall()
    con.close()
    hits = [_hit(r, 0.0) for r in rows if rel in json.loads(r[4] or "[]")]
    commits = [h for h in hits if h.kind == "commit" and not re.match(r"(chore|style|docs)(\(|:)", h.text)]
    others = [h for h in hits if h.kind != "commit"]
    commits.sort(key=lambda h: (h.date, h.ref), reverse=True)
    others.sort(key=lambda h: (h.date, h.ref), reverse=True)
    return (commits[:1] + others)[:limit]


def mentions(p: Project, names: list[str], kinds=("decision", "archive", "journal", "work"), limit: int = 3) -> list[Hit]:
    """Units that name one of these identifiers (functions/classes defined in a file) verbatim."""
    names = [n for n in names if len(n) >= 4]
    if not names or not db_path(p).exists():
        return []
    con = connect(p)
    q = " OR ".join(f'"{norm(n)}"' for n in names[:20])
    marks = ",".join("?" * len(kinds))
    rows = con.execute(f"SELECT kind, ref, date, path, files, text, bm25(units) FROM units WHERE units MATCH ? "
                       f"AND kind IN ({marks}) ORDER BY bm25(units) LIMIT ?", [q, *kinds, limit * 4]).fetchall()
    con.close()
    out = []
    for r in rows:
        if any(re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", r[5]) for n in names):
            out.append(_hit(r[:6], -r[6]))
    out.sort(key=lambda h: (h.kind != "decision", -h.score, h.ref))
    return out[:limit]
