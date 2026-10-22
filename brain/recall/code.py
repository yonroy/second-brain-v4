"""Code graph (spec v4 §5): `.index/code.sqlite`.

Python via `ast`: definitions, imports (resolved to repo files), names/attributes used, `import x as y`
aliases (so `_tr(...)` counts as a use of `tax_rate`), string constants. Every other text file contributes its
identifiers as `string` (config/data/sql) or `doc` (markdown) references, which catches names referenced from
JSON/TOML/SQL that a `*.py`-only grep misses (bench T12/T21).
JS/TS (`.js .jsx .ts .tsx .mjs .cjs`): regex heuristic (spec §5) — top-level/exported function, class, arrow-const,
interface/type/enum definitions; `import … from` / `export … from` / `require()` / `import()` resolved to repo files
(relative paths and tsconfig `compilerOptions.paths`, e.g. `@/*`); `{ a as b }` aliases. Not a parser: decorators,
re-export chains and dynamic names are missed. Other languages: identifiers only.
"""
from __future__ import annotations

import ast
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

from brain import paths
from brain.project import Project

TEXT_EXT = {".py", ".toml", ".json", ".yaml", ".yml", ".sql", ".md", ".ini", ".cfg", ".html", ".js", ".ts", ".tsx",
            ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".txt", ".csv", ".sh"}
JS_EXT = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
JS_RESOLVE = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", "/index.ts", "/index.tsx", "/index.js", "/index.jsx")
_ID = r"([A-Za-z_$][\w$]*)"
JS_DEFS = [
    (re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*" + _ID), "function"),
    (re.compile(r"^\s*export\s+(?:default\s+)?(?:async\s+)?function\s*\*?\s*" + _ID), "function"),
    (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+" + _ID), "class"),
    (re.compile(r"^(?:export\s+)?(?:const|let|var)\s+" + _ID + r"\s*(?::[^=]{0,200})?=\s*(?:async\s+)?"
                r"(?:\([^)]*\)\s*(?::[^=]{0,120})?=>|[A-Za-z_$][\w$]*\s*=>|function\b)"), "function"),
    (re.compile(r"^\s*export\s+(?:const|let|var)\s+" + _ID), "const"),
    (re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(?:interface|type|enum)\s+" + _ID), "type"),
]
JS_IMPORT = re.compile(r"(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)[\"']([^\"'\n]+)[\"']")
JS_NAMED = re.compile(r"\b(?:import|export)\s+(?:type\s+)?(?:[\w$]+\s*,\s*)?\{([^}]*)\}\s*from", re.S)
JS_AS = re.compile(r"\s*(?:type\s+)?" + _ID + r"\s+as\s+" + _ID)
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".claude", ".index", "dist", "build"}
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
MAX_BYTES = 512 * 1024
SCHEMA = """
CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, sig TEXT);
CREATE TABLE IF NOT EXISTS defs (name TEXT, qual TEXT, kind TEXT, path TEXT, line INTEGER);
CREATE TABLE IF NOT EXISTS refs (name TEXT, path TEXT, line INTEGER, kind TEXT);
CREATE TABLE IF NOT EXISTS imports (path TEXT, target TEXT, line INTEGER);
CREATE TABLE IF NOT EXISTS aliases (path TEXT, alias TEXT, target TEXT);
CREATE INDEX IF NOT EXISTS refs_name ON refs(name);
CREATE INDEX IF NOT EXISTS defs_name ON defs(name);
CREATE INDEX IF NOT EXISTS imports_target ON imports(target);
"""


@dataclass
class Ref:
    path: str
    line: int
    kind: str  # def | code | string | doc


def db_path(p: Project) -> Path:
    return p.root / ".index" / "code.sqlite"


def connect(p: Project) -> sqlite3.Connection:
    f = db_path(p)
    f.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f)
    con.executescript(SCHEMA)
    return con


def repo_files(root: Path) -> list[str]:
    try:
        r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        listed = [l.strip() for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired):
        listed = []
    if not listed:
        listed = [paths.fwd(f.relative_to(root)) for f in root.rglob("*") if f.is_file()]
    out = []
    for rel in listed:
        parts = rel.split("/")
        if any(x in SKIP_DIRS for x in parts[:-1]) or Path(rel).suffix.lower() not in TEXT_EXT:
            continue
        f = root / rel
        if f.is_file() and f.stat().st_size <= MAX_BYTES:
            out.append(rel)
    return sorted(out)


def _module_file(mod: str, files: set[str]) -> str | None:
    base = mod.replace(".", "/")
    for cand in (f"{base}.py", f"{base}/__init__.py"):
        if cand in files:
            return cand
    return None


class _PyVisitor(ast.NodeVisitor):
    def __init__(self, rel: str, files: set[str]):
        self.rel, self.files = rel, files
        self.defs, self.refs, self.imports, self.aliases = [], [], [], []
        self._cls: list[str] = []

    def _def(self, node, kind):
        qual = ".".join(self._cls + [node.name])
        self.defs.append((node.name, qual, kind, self.rel, node.lineno))

    def visit_FunctionDef(self, node):
        self._def(node, "method" if self._cls else "function")
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self._def(node, "class")
        self._cls.append(node.name)
        self.generic_visit(node)
        self._cls.pop()

    def visit_Import(self, node):
        for a in node.names:
            t = _module_file(a.name, self.files)
            if t:
                self.imports.append((self.rel, t, node.lineno))
            if a.asname:
                self.aliases.append((self.rel, a.asname, a.name.split(".")[-1]))

    def visit_ImportFrom(self, node):
        mod = node.module or ""
        t = _module_file(mod, self.files)
        if t:
            self.imports.append((self.rel, t, node.lineno))
        for a in node.names:
            sub = _module_file(f"{mod}.{a.name}" if mod else a.name, self.files)
            if sub:
                self.imports.append((self.rel, sub, node.lineno))
            self.refs.append((a.name, self.rel, node.lineno, "code"))
            if a.asname:
                self.aliases.append((self.rel, a.asname, a.name))

    def visit_Name(self, node):
        self.refs.append((node.id, self.rel, node.lineno, "code"))

    def visit_Attribute(self, node):
        self.refs.append((node.attr, self.rel, node.lineno, "code"))
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and len(node.value) < 400:
            for tok in IDENT.findall(node.value):
                self.refs.append((tok, self.rel, node.lineno, "string"))


def _index_python(rel: str, text: str, files: set[str]) -> _PyVisitor | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    v = _PyVisitor(rel, files)
    v.visit(tree)
    return v


def ts_paths(root: Path) -> list[tuple[str, str]]:
    """tsconfig/jsconfig `compilerOptions.paths` as (prefix, replacement), e.g. `"@/*": ["./*"]` → ("@/", "")."""
    for name in ("tsconfig.json", "jsconfig.json"):
        f = root / name
        if not f.is_file():
            continue
        raw = f.read_text(encoding="utf-8", errors="ignore")
        raw = re.sub(r"^\s*//.*$", "", raw, flags=re.M)
        raw = re.sub(r",(\s*[}\]])", r"\1", raw)
        try:
            opts = json.loads(raw).get("compilerOptions", {})
        except ValueError:
            return []
        base = (opts.get("baseUrl") or ".").replace("\\", "/").lstrip("./").rstrip("/")
        out = []
        for pat, targets in (opts.get("paths") or {}).items():
            if pat.endswith("*") and targets and str(targets[0]).endswith("*"):
                tgt = str(targets[0])[:-1].replace("\\", "/")
                while tgt.startswith("./"):
                    tgt = tgt[2:]
                out.append((pat[:-1], (base + "/" if base else "") + tgt))
        return out
    return []


def _resolve_js(spec: str, rel: str, files: set[str], aliases: list[tuple[str, str]]) -> str | None:
    if spec.startswith("."):
        parts = rel.split("/")[:-1]
        for seg in spec.split("/"):
            if seg == "..":
                parts = parts[:-1]
            elif seg not in (".", ""):
                parts.append(seg)
        base = "/".join(parts)
    else:
        base = next((repl + spec[len(pre):] for pre, repl in aliases if spec.startswith(pre)), None)
        if base is None:
            return None  # a package, not a repo file
    for ext in JS_RESOLVE:
        if base + ext in files:
            return base + ext
    return None


def _index_js(rel: str, text: str, files: set[str], path_aliases: list[tuple[str, str]]) -> dict:
    out = {"defs": [], "refs": [], "imports": [], "aliases": []}
    seen = set()
    for i, line in enumerate(text.splitlines(), 1):
        for rx, kind in JS_DEFS:
            m = rx.match(line)
            if m:
                out["defs"].append((m.group(1), m.group(1), kind, rel, i))
                break
        for tok in IDENT.findall(line):
            if (tok, i) not in seen:
                seen.add((tok, i))
                out["refs"].append((tok, rel, i, "code"))
    for m in JS_IMPORT.finditer(text):
        t = _resolve_js(m.group(1), rel, files, path_aliases)
        if t and t != rel:
            out["imports"].append((rel, t, text.count("\n", 0, m.start()) + 1))
    for m in JS_NAMED.finditer(text):
        for part in m.group(1).split(","):
            a = JS_AS.match(part)
            if a and a.group(1) != "default":
                out["aliases"].append((rel, a.group(2), a.group(1)))
    return out


def _index_text(rel: str, text: str) -> list[tuple]:
    kind = "doc" if rel.endswith((".md", ".txt")) else "string"
    out, seen = [], set()
    for i, line in enumerate(text.splitlines(), 1):
        for tok in IDENT.findall(line):
            if (tok, i) not in seen:
                seen.add((tok, i))
                out.append((tok, rel, i, kind))
    return out


def build(p: Project, full: bool = False) -> dict:
    root = p.codebase
    con = connect(p)
    if full:
        con.executescript("DELETE FROM files; DELETE FROM defs; DELETE FROM refs; DELETE FROM imports; DELETE FROM aliases;")
    listed = repo_files(root)
    files = set(listed)
    js_aliases = ts_paths(root)
    stats = {"files": 0, "changed": 0}
    old = dict(con.execute("SELECT path, sig FROM files").fetchall())
    for rel in set(old) - files:
        for t in ("files", "defs", "refs", "imports", "aliases"):
            con.execute(f"DELETE FROM {t} WHERE path = ?", (rel,))
    for rel in listed:
        st = (root / rel).stat()
        sig = f"{st.st_mtime_ns}:{st.st_size}"
        stats["files"] += 1
        if old.get(rel) == sig:
            continue
        stats["changed"] += 1
        for t in ("defs", "refs", "imports", "aliases"):
            con.execute(f"DELETE FROM {t} WHERE path = ?", (rel,))
        text = (root / rel).read_text(encoding="utf-8", errors="ignore")
        v = _index_python(rel, text, files) if rel.endswith(".py") else None
        if rel.endswith(JS_EXT):
            j = _index_js(rel, text, files, js_aliases)
            con.executemany("INSERT INTO defs VALUES (?, ?, ?, ?, ?)", j["defs"])
            con.executemany("INSERT INTO refs VALUES (?, ?, ?, ?)", j["refs"])
            con.executemany("INSERT INTO imports VALUES (?, ?, ?)", j["imports"])
            con.executemany("INSERT INTO aliases VALUES (?, ?, ?)", j["aliases"])
        elif v:
            con.executemany("INSERT INTO defs VALUES (?, ?, ?, ?, ?)", v.defs)
            con.executemany("INSERT INTO refs VALUES (?, ?, ?, ?)", v.refs)
            con.executemany("INSERT INTO imports VALUES (?, ?, ?)", v.imports)
            con.executemany("INSERT INTO aliases VALUES (?, ?, ?)", v.aliases)
        else:
            con.executemany("INSERT INTO refs VALUES (?, ?, ?, ?)", _index_text(rel, text))
        con.execute("INSERT OR REPLACE INTO files(path, sig) VALUES (?, ?)", (rel, sig))
    con.commit()
    stats["defs"] = con.execute("SELECT COUNT(*) FROM defs").fetchone()[0]
    con.close()
    return stats


# ---------------------------------------------------------------- queries
def _names_for(con, sym: str) -> set[str]:
    """sym plus every alias that (transitively) points at it: `import tax_rate as _tr` → {_tr}."""
    names, frontier = {sym}, {sym}
    while frontier:
        q = ",".join("?" * len(frontier))
        nxt = {a for (a,) in con.execute(f"SELECT alias FROM aliases WHERE target IN ({q})", list(frontier))} - names
        names |= nxt
        frontier = nxt
    return names


def defines(p: Project, sym: str) -> list[Ref]:
    con = connect(p)
    rows = con.execute("SELECT path, line FROM defs WHERE name = ? OR qual = ? ORDER BY path, line", (sym, sym)).fetchall()
    con.close()
    return [Ref(a, b, "def") for a, b in rows]


def uses(p: Project, sym: str) -> list[Ref]:
    con = connect(p)
    names = _names_for(con, sym)
    q = ",".join("?" * len(names))
    rows = con.execute(f"SELECT DISTINCT path, line, kind FROM refs WHERE name IN ({q}) ORDER BY path, line", list(names)).fetchall()
    defs = {(a, b) for a, b in con.execute(f"SELECT path, line FROM defs WHERE name IN ({q})", list(names))}
    con.close()
    return [Ref(a, b, c) for a, b, c in rows if (a, b) not in defs]


def dependents(p: Project, rel: str) -> list[str]:
    con = connect(p)
    rows = [a for (a,) in con.execute("SELECT DISTINCT path FROM imports WHERE target = ? ORDER BY path", (rel,))]
    con.close()
    return rows


def deps(p: Project, rel: str) -> list[str]:
    con = connect(p)
    rows = [a for (a,) in con.execute("SELECT DISTINCT target FROM imports WHERE path = ? ORDER BY target", (rel,))]
    con.close()
    return rows


def defs_in(p: Project, rel: str) -> list[tuple[str, int]]:
    con = connect(p)
    rows = con.execute("SELECT name, line FROM defs WHERE path = ? AND kind != 'method' ORDER BY line", (rel,)).fetchall()
    con.close()
    return rows
