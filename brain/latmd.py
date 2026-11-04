"""`brain lat`: project memory → a derived lat.md vault (ADR-014).

`_projects/<p>/` stays the one source of truth in brain's own format. `build` writes a lat vault next to it
(`<project>/.lat/lat.md/`), and `lat check` validates it against the codebase, so memory and code
share one link graph:

- the IDs brain already uses become `[[wiki links]]`:
  - `ADR-NNN` / `D-NNN` → `decisions/ADR-…`;
  - `M-NNN` → its section in TRAPS;
  - `S-NNN` → `work/S-…`;
  - `B-NNN` → PROOF;
- fact sources `file:src/x.py` and trap triggers with a path become links into the codebase. `lat check`
  then reports a fact or trap whose file or symbol (`file:src/x.py#func`) no longer exists;
- what lat requires and brain's format lacks is generated:
  - one index per directory;
  - a short leading paragraph on every section;
  - `\\[` escapes for `[date|source]` tags, which lat would otherwise read as broken reference links.

Same rules as Recall (ADR-010):
- stdlib, deterministic (same memory → same vault), derived (delete `.lat/` and `build` recreates it).
- `lat` itself is an optional external tool, found via `BRAIN_LAT`, then `lat`, then `lat-core` on PATH.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from brain import paths
from brain.project import HTML_COMMENT, Project

ROOT = ".lat"
VAULT = "lat.md"            # lat finds a vault by this directory name
MARKER = ".brain-generated"  # `build` only ever deletes a .lat/ that carries it
MAX_LEAD = 250              # lat's limit on a section's leading paragraph (wiki links excluded)

ID_RE = re.compile(r"(?<![\w/-])((?:ADR|D|M|S|B)-\d+)(?![\w-])")
FILE_SRC = re.compile(r"(?<![\w/])file:([A-Za-z0-9_./\-]+[A-Za-z0-9_/\-])((?:#[A-Za-z_][\w.]*)?)((?::\d+(?:-\d+)?|#L\d+(?:-L?\d+)?)?)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1")
WIKI = re.compile(r"\[\[[^\]\n]*\]\]")
# a bracket group that is not part of a wiki link, markdown link/reference, image, footnote or escape
BARE_BRACKET = re.compile(r"(?<![\[\\!\]])\[(?![\[^])([^\[\]\n]*)\](?![\(\[\]])")
REF_DEF = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*\S+\s*$")  # a real `[x]: url` reference definition
TASK_BOX = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+$")
BLOCK_START = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|\||>|#|```|~~~|<)")
UNSAFE_SECTION = re.compile(r"[#|\[\]]")
GLOB = re.compile(r"[*?\[\]{}]")
EXCLUDE_NAMES = {"lat.md"}


@dataclass
class Vault:
    root: Path                       # <project>/.lat (lat's project root for section/refs/locate/search)
    dir: Path                        # <project>/.lat/lat.md
    files: list[str] = field(default_factory=list)
    lines: dict[str, list[int]] = field(default_factory=dict)  # vault rel → source line per output line (0 = generated)
    links: int = 0


# ---------------------------------------------------------------- sources and targets
def sources(p: Project) -> list[str]:
    """Memory files that go into the vault: every .md except dot dirs, `_` files (templates) and a stray lat.md."""
    out = []
    for f in sorted(p.root.rglob("*.md")):
        rel = f.relative_to(p.root)
        if any(part.startswith((".", "_")) for part in rel.parts) or rel.name in EXCLUDE_NAMES:
            continue
        out.append(rel.as_posix())
    return out


def targets(p: Project, files: list[str]) -> dict[str, tuple[str, str]]:
    """ID → (link target, file it lives in). Only IDs that exist get a link; the rest stay text."""
    stems = {f[:-3] for f in files}
    out: dict[str, tuple[str, str]] = {}
    for d in p.decisions():
        out[d.id] = ("decisions/INDEX", "decisions/INDEX.md")
    for f in files:
        m = re.match(r"decisions/((?:ADR|D)-\d+)\b", f)
        if m:
            out[m.group(1)] = (f[:-3], f)
    if "TRAPS" in stems:
        for line in p.read_parsed("TRAPS.md").splitlines():
            m = re.match(r"^##\s+(M-\d+)\b(.*)$", line)
            if m:
                head = line[2:].strip()
                out.setdefault(m.group(1), ("TRAPS" if UNSAFE_SECTION.search(head) else f"TRAPS#{head}", "TRAPS.md"))
    for s in p.stories():
        rel = s.path.relative_to(p.root).as_posix()
        sid = str(s.meta.get("id", "")).strip()
        m = re.match(r"(S-\d+)\b", s.path.name)
        for i in {sid, m.group(1) if m else ""} - {""}:
            if re.fullmatch(r"S-\d+", i):
                out.setdefault(i, (rel[:-3], rel))
    if "PROOF" in stems:
        for r in p.proofs():
            out.setdefault(r.id, ("PROOF", "PROOF.md"))
    return out


# ---------------------------------------------------------------- line transforms
def _segments(line: str):
    """(text, is_code) pieces of one line, so links and escapes never touch inline code."""
    pos = 0
    for m in INLINE_CODE.finditer(line):
        if m.start() > pos:
            yield line[pos:m.start()], False
        yield m.group(0), True
        pos = m.end()
    if pos < len(line):
        yield line[pos:], False


def _escape(text: str, before: str) -> str:
    if not before and REF_DEF.match(text):
        return text

    def rep(m: re.Match) -> str:
        if m.group(1) in (" ", "x", "X") and TASK_BOX.match(before + text[:m.start()]):
            return m.group(0)
        return "\\[" + m.group(1) + "\\]"
    return BARE_BRACKET.sub(rep, text)


def _outside_wiki(text: str, fn) -> str:
    """Apply fn only to the parts of text that are not already [[wiki links]]."""
    out, pos = [], 0
    for m in WIKI.finditer(text):
        out.append(fn(text[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(fn(text[pos:]))
    return "".join(out)


class _Linker:
    def __init__(self, ids: dict[str, tuple[str, str]], here: str):
        self.ids, self.here, self.count = ids, here, 0

    def _link(self, target: str, label: str, table: bool) -> str:
        self.count += 1
        # `\|` inside a table cell breaks lat's link parser, so a table gets the bare target
        return f"[[{target}]]" if table or label == target else f"[[{target}|{label}]]"

    def line(self, text: str, table: bool, trigger: bool) -> str:
        def ids(seg: str) -> str:
            def rep(m: re.Match) -> str:
                t = self.ids.get(m.group(1))
                if not t or t[1] == self.here:  # unknown ID, or a self-link inside its own file: leave as text
                    return m.group(0)
                return self._link(t[0], m.group(1), table)
            return ID_RE.sub(rep, seg)

        def files(seg: str) -> str:
            def rep(m: re.Match) -> str:
                path, sym = m.group(1).rstrip("/."), m.group(2)
                return self._link(path + sym, m.group(0), table)
            return FILE_SRC.sub(rep, seg)

        text = _outside_wiki(text, files)
        text = _outside_wiki(text, ids)
        if trigger:
            text = _trigger_links(text, self)
        return text


def _trigger_links(text: str, linker: _Linker) -> str:
    """`trigger: src/a.py, kw:x` → paths with a `/` and no glob become code links (bare names match anywhere)."""
    key, _, val = text.partition(":")
    parts = []
    for item in val.split(","):
        raw = item.strip()
        if raw and "/" in raw and not GLOB.search(raw) and not raw.startswith("kw:") and "[[" not in raw:
            item = item.replace(raw, linker._link(raw.rstrip("/"), raw, False), 1)
        parts.append(item)
    return key + ":" + ",".join(parts)


def _is_table(line: str) -> bool:
    return line.lstrip().startswith("|")


def convert_lines(text: str, ids: dict[str, tuple[str, str]], here: str) -> tuple[list[str], int]:
    """Comments dropped (line numbers kept), brackets escaped, IDs and file sources linked. Code is untouched."""
    text = HTML_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    linker = _Linker(ids, here)
    out, fence, front = [], None, False
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            front = True
            out.append(line)
            continue
        if front:
            front = line.strip() != "---"
            out.append(line)
            continue
        m = FENCE.match(line)
        if fence:
            fence = None if m and m.group(1) == fence else fence
            out.append(line)
            continue
        if m:
            fence = m.group(1)
            out.append(line)
            continue
        if HEADING.match(line):
            out.append(_escape(line, ""))  # never link inside a heading: it would rename the section
            continue
        table, trigger = _is_table(line), here == "TRAPS.md" and line.lower().startswith("trigger:")
        done, before = [], ""
        for seg, code in _segments(line):
            done.append(seg if code else linker.line(_escape(seg, before), table, trigger))
            before += seg
        out.append("".join(done))
    return out, linker.count


# ---------------------------------------------------------------- leading paragraphs
def _lead_ok(lines: list[str], j: int) -> bool:
    """A section is fine for lat when its first block is a plain paragraph of ≤ MAX_LEAD chars."""
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines) or BLOCK_START.match(lines[j]):
        return False
    para = []
    while j < len(lines) and lines[j].strip() and not BLOCK_START.match(lines[j]):
        para.append(lines[j].strip())
        j += 1
    return len(WIKI.sub("", " ".join(para))) <= MAX_LEAD


def _lead_text(level: int, title: str, rel: str) -> str:
    title = title.replace("\\[", "[").replace("\\]", "]").strip()
    m = re.match(r"(M-\d+)\s+(.*)", title)
    if rel == "TRAPS.md" and m:
        s = f"Trap {m.group(1)}: {m.group(2)}."
    elif level == 1:
        s = f"Tệp `{rel}` trong memory dự án."
    else:
        s = f"Mục «{title}» trong `{rel}`."
    s = re.sub(r"[\[\]]", "", s)
    return s if len(s) <= MAX_LEAD else s[:MAX_LEAD - 1] + "…"


def add_leads(lines: list[str], src_lines: list[int], rel: str) -> tuple[list[str], list[int]]:
    out, nums, fence = [], [], None
    for i, line in enumerate(lines):
        out.append(line)
        nums.append(src_lines[i])
        m = FENCE.match(line)
        if fence:
            fence = None if m and m.group(1) == fence else fence
            continue
        if m:
            fence = m.group(1)
            continue
        h = HEADING.match(line)
        if h and not _lead_ok(lines, i + 1):
            out += ["", _lead_text(len(h.group(1)), h.group(2), rel)]
            nums += [src_lines[i], src_lines[i]]
    return out, nums


# ---------------------------------------------------------------- directory indexes
def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        h = HEADING.match(line)
        if h and len(h.group(1)) == 1:
            t = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", h.group(2)).replace("\\[", "[").replace("\\]", "]")
            return re.sub(r"[\[\]]", "", t).strip() or fallback
    return fallback


def indexes(p: Project, files: list[str], titles: dict[str, str]) -> dict[str, str]:
    """lat wants `<dir>/<dir>.md` listing each page and subdirectory; the vault root's index is `lat.md`."""
    dirs: dict[str, set[str]] = {"": set()}
    for f in files:
        parts = f.split("/")
        for k in range(len(parts) - 1):
            dirs.setdefault("/".join(parts[:k + 1]), set())
    parent = lambda x: x.rsplit("/", 1)[0] if "/" in x else ""  # noqa: E731
    out = {}
    for d in sorted(dirs):
        entries = [f"- [[{sub.rsplit('/', 1)[-1]}]] — thư mục `{sub}/`" for sub in sorted(dirs) if sub and parent(sub) == d]
        for f in files:
            if parent(f) == d:
                stem = f.rsplit("/", 1)[-1][:-3]
                entries.append(f"- [[{stem}]] — {titles.get(f, stem)}")
        name = d.rsplit("/", 1)[-1] if d else VAULT
        path = f"{d}/{name}.md" if d else VAULT
        head = f"# {p.name} — memory" if not d else f"# {d}/"
        lead = (f"Vault dẫn xuất từ `_projects/{p.name}/` bởi `brain lat build`. Không sửa tay: sửa file gốc rồi build lại."
                if not d else f"Thư mục `{d}/` trong memory dự án {p.name}.")
        out[path] = "\n".join([head, "", lead, "", *entries]) + "\n"
    return out


# ---------------------------------------------------------------- build
def vault_root(p: Project) -> Path:
    return p.root / ROOT


def build(p: Project) -> Vault:
    root = vault_root(p)
    if root.exists():
        if not (root / MARKER).is_file():
            raise SystemExit(f"❌ {paths.fwd(root)} có sẵn mà không do brain tạo; không xoá. Đổi tên nó rồi build lại.")
        shutil.rmtree(root)
    v = Vault(root, root / VAULT)
    v.dir.mkdir(parents=True)
    (root / MARKER).write_text("Dẫn xuất từ memory dự án bởi `brain lat build` (ADR-014). Xoá được; build lại y hệt.\n",
                               encoding="utf-8", newline="\n")
    files = sources(p)
    ids = targets(p, files)
    titles = {}
    for rel in files:
        text = (p.root / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
        lines, n = convert_lines(text, ids, rel)
        lines, nums = add_leads(lines, list(range(1, len(lines) + 1)), rel)
        v.links += n
        titles[rel] = _title(text, rel[:-3])
        _write(v.dir / rel, "\n".join(lines).rstrip("\n") + "\n")
        v.files.append(rel)
        v.lines[rel] = nums
    for rel, text in indexes(p, files, titles).items():
        if rel in v.lines:
            continue  # a memory file already named like the index wins; lat will say what is missing
        _write(v.dir / rel, text)
        v.files.append(rel)
        v.lines[rel] = [0] * (text.count("\n") + 1)
    return v


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- running lat
def lat_cmd() -> list[str] | None:
    env = os.environ.get("BRAIN_LAT", "").strip()
    if env:
        return shlex.split(env, posix=os.name != "nt")
    for name in ("lat", "lat-core"):
        exe = shutil.which(name)
        if exe:
            return [exe]
    return None


MISSING = "không tìm thấy lat: `npm install -g @lat.md/core` (hoặc `lat.md` cho search/ui), hoặc đặt env BRAIN_LAT"


def remap(out: str, p: Project, v: Vault) -> str:
    """lat's vault paths and line numbers → the memory file and line the user actually edits."""
    prefixes = {paths.fwd(v.dir) + "/", str(v.dir) + os.sep}
    try:
        rel = os.path.relpath(v.dir, p.codebase)
        prefixes |= {rel.replace("\\", "/") + "/", rel + os.sep}
    except ValueError:  # different drive on Windows
        pass
    for pre in sorted(prefixes, key=len, reverse=True):
        out = out.replace(pre, "")

    def rep(m: re.Match) -> str:
        nums = v.lines.get(m.group(1))
        if nums is None:
            return m.group(0)
        n = int(m.group(2))
        src = nums[n - 1] if 0 < n <= len(nums) else 0
        return f"{m.group(1)}:{src}" if src else f"{m.group(1)} (tự sinh)"
    return re.sub(r"((?:[\w.\-]+/)*[\w.\-]+\.md):(\d+)", rep, out)


def check(p: Project, timeout: int = 120) -> tuple[int, str]:
    """(exit code, output). Exit 2 when lat is not installed. cwd = codebase so code links resolve against it."""
    v = build(p)
    cmd = lat_cmd()
    if not cmd:
        return 2, MISSING
    env = {**os.environ, "NO_COLOR": "1"}
    try:
        r = subprocess.run([*cmd, "check", "--", str(v.dir)], cwd=p.codebase, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 2, f"lat không chạy được: {e}"
    return r.returncode, remap((r.stdout + r.stderr).strip(), p, v)


def errors_in(out: str) -> int:
    m = re.search(r"(\d+)\s+errors?\s+found", out)
    return int(m.group(1)) if m else sum(1 for l in out.splitlines() if l.startswith("- "))


def run(p: Project, args: list[str], timeout: int = 300) -> int:
    """Any other lat command (section, refs, locate, search, expand, ui, mcp …) on a fresh vault."""
    v = build(p)
    cmd = lat_cmd()
    if not cmd:
        print(f"❌ {MISSING}")
        return 2
    try:
        return subprocess.run([*cmd, *args], cwd=v.root, timeout=None if args[:1] in (["ui"], ["mcp"]) else timeout).returncode
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"❌ lat không chạy được: {e}")
        return 2


def enabled(p: Project) -> bool:
    return bool(p.config.get("lat", {}).get("gate", False))
