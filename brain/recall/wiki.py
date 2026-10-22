"""Wiki layer (v4.1, ADR-013): a hub-level search index over markdown wikis, built for an agent that understands.

Meaning comes from the agent, lookup from here. The `wiki` skill makes the agent rewrite a question into several
phrasings (Vietnamese, English, synonyms, concrete terms) and pass them all to `search`; each phrasing runs as its
own FTS5 query and pages are ranked by reciprocal-rank fusion, so a page that several phrasings agree on wins even
when no single wording matches. `catalog` gives the agent a one-line-per-page map to choose from by meaning when
keywords fail. Stdlib only, deterministic, incremental — same rules as the rest of Recall (ADR-009/010).

Config `<hub>/wiki.toml`: `[[wiki]] name, path` (several allowed) · `[auto] prompt = false` (UserPromptSubmit pointers).
Index `<hub>/.index/wiki.sqlite` (derived; `brain wiki index --full` rebuilds it).
"""
from __future__ import annotations

import re
import sqlite3
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from brain import paths
from brain.recall.text import norm, terms

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (id TEXT PRIMARY KEY, wiki TEXT, rel TEXT, file TEXT, title TEXT, tags TEXT,
    aliases TEXT, summary TEXT, updated TEXT, sig TEXT);
CREATE TABLE IF NOT EXISTS links (src TEXT, dst TEXT);
CREATE INDEX IF NOT EXISTS links_dst ON links (dst);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
    page UNINDEXED, heading UNINDEXED, text UNINDEXED, head, body, tokenize = 'unicode61');
"""
RRF_K = 60          # reciprocal-rank fusion constant (standard value)
PER_QUERY = 25      # chunks fetched per phrasing before fusion
CHUNK_CHARS = 1500  # long sections are split on paragraph boundaries
HEAD_WEIGHT = 6.0   # bm25 weight of title/aliases/tags/heading vs body

FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
H2 = re.compile(r"^##\s+(.+?)\s*$", re.M)
H1 = re.compile(r"^#\s+(.+?)\s*$", re.M)
COMMENT = re.compile(r"<!--(.*?)-->", re.S)
SKIP = {"index.md", "log.md"}


# ---------------------------------------------------------------- config
def config_path(hub: Path | None = None) -> Path:
    return (hub or paths.hub()) / "wiki.toml"


def load_config(hub: Path | None = None) -> dict:
    f = config_path(hub)
    try:
        return tomllib.loads(f.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def wikis(hub: Path | None = None) -> list[tuple[str, Path]]:
    return [(str(w["name"]), paths.local(w["path"])) for w in load_config(hub).get("wiki", []) if w.get("name") and w.get("path")]


def add(path: Path, name: str, hub: Path | None = None) -> str:
    path = path.resolve()
    if not path.is_dir():
        raise SystemExit(f"Không thấy thư mục {path}")
    cfg = load_config(hub)
    ws = [w for w in cfg.get("wiki", []) if w.get("name") != name]
    ws.append({"name": name, "path": paths.fwd(path)})
    auto = cfg.get("auto", {"prompt": False})
    lines = ["# Wiki cho brain (v4.1). Sửa tay được; `brain wiki add` ghi đè mục cùng tên.", ""]
    for w in ws:
        lines += ["[[wiki]]", f'name = "{w["name"]}"', f'path = "{w["path"]}"', ""]
    lines += ["[auto]", "# true: UserPromptSubmit gợi ý tối đa 2 trang wiki khớp mạnh với prompt (chỉ con trỏ, ≤ 400 ký tự)",
              f"prompt = {'true' if auto.get('prompt') else 'false'}", ""]
    config_path(hub).write_text("\n".join(lines), encoding="utf-8")
    return paths.fwd(config_path(hub))


# ---------------------------------------------------------------- parsing
@dataclass
class Page:
    id: str
    wiki: str
    rel: str
    file: str
    title: str
    tags: list[str]
    aliases: list[str]
    summary: str
    updated: str
    links: list[str]
    sections: list[tuple[str, str]] = field(default_factory=list)


def _list(v: str) -> list[str]:
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    return [x.strip().strip("'\"") for x in v.split(",") if x.strip().strip("'\"")]


def _front(text: str) -> tuple[dict, str]:
    m = FM.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and re.fullmatch(r"[A-Za-z_]+", k.strip()):
            meta[k.strip().lower()] = v.strip()
    return meta, text[m.end():]


def _split(body: str) -> list[tuple[str, str]]:
    """[(heading, text)] per `##` section; text before the first one is the page lead."""
    marks = list(H2.finditer(body))
    out = []
    lead = body[: marks[0].start()] if marks else body
    lead = H1.sub("", lead, count=1).strip()
    if lead:
        out.append(("", lead))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out.append((m.group(1).strip(), body[m.end():end].strip()))
    return out


def _chunks(heading: str, text: str) -> list[tuple[str, str]]:
    if len(text) <= CHUNK_CHARS:
        return [(heading, text)]
    out, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        if cur and len(cur) + len(para) > CHUNK_CHARS:
            out.append((heading, cur.strip()))
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        out.append((heading, cur.strip()))
    return out


def _summary(sections: list[tuple[str, str]]) -> str:
    pick = next((t for h, t in sections if norm(h).startswith(("tom tat", "summary", "tl;dr", "tldr"))), "")
    pick = pick or next((t for _, t in sections if t.strip()), "")
    para = next((p for p in re.split(r"\n\s*\n", pick) if p.strip() and not p.lstrip().startswith(("|", "```"))), "")
    return " ".join(para.split())


def parse(wiki: str, root: Path, f: Path) -> Page:
    rel = paths.fwd(f.relative_to(root))
    meta, body = _front(f.read_text(encoding="utf-8", errors="ignore"))
    # templates/prompts have no front matter but often open with an explanatory HTML comment: use it as the summary
    lead_note = COMMENT.match(body.lstrip())
    body = COMMENT.sub("", body)
    h1 = H1.search(body)
    title = meta.get("title", "").strip("'\"")
    if not title:
        title = h1.group(1).strip() if h1 and "[" not in h1.group(1) else f.stem.replace("-", " ").replace("_", " ")
    sections = _split(body)
    summary = _summary(sections)
    if lead_note and not meta:
        note = [l.strip() for l in lead_note.group(1).splitlines() if l.strip() and not set(l.strip()) <= set("=-")]
        summary = " ".join(note[1:] if len(note) > 1 else note) or summary
    links = sorted({_link_target(m.group(1)) for m in LINK.finditer(body)} - {""})
    return Page(id=f"{wiki}:{rel}", wiki=wiki, rel=rel, file=paths.fwd(f), title=title, tags=_list(meta.get("tags", "")),
                aliases=_list(meta.get("aliases", "")), summary=summary, updated=meta.get("updated", ""),
                links=links, sections=sections)


def _link_target(s: str) -> str:
    s = s.strip().replace("\\", "/")
    return s[:-3] if s.endswith(".md") else s


# ---------------------------------------------------------------- index
def db_path(hub: Path | None = None) -> Path:
    return (hub or paths.hub()) / ".index" / "wiki.sqlite"


def connect(hub: Path | None = None) -> sqlite3.Connection:
    f = db_path(hub)
    f.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _files(root: Path) -> list[Path]:
    return sorted(f for f in root.rglob("*.md") if f.name not in SKIP and not any(p.startswith(".") for p in f.relative_to(root).parts))


def build(hub: Path | None = None, full: bool = False) -> dict:
    """Incremental by (mtime, size); pages of removed files or removed wikis are dropped."""
    con = connect(hub)
    if full:
        con.executescript("DELETE FROM pages; DELETE FROM links; DELETE FROM chunks;")
    known = {r["id"]: r["sig"] for r in con.execute("SELECT id, sig FROM pages")}
    seen, changed = set(), 0
    for name, root in wikis(hub):
        if not root.is_dir():
            continue
        for f in _files(root):
            st = f.stat()
            sig = f"{st.st_mtime_ns}:{st.st_size}"
            pid = f"{name}:{paths.fwd(f.relative_to(root))}"
            seen.add(pid)
            if known.get(pid) == sig:
                continue
            _drop(con, pid)
            _put(con, parse(name, root, f), sig)
            changed += 1
    gone = set(known) - seen
    for pid in gone:
        _drop(con, pid)
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    con.close()
    return {"pages": total, "changed": changed, "removed": len(gone)}


def _drop(con, pid: str) -> None:
    for sql in ("DELETE FROM pages WHERE id = ?", "DELETE FROM links WHERE src = ?", "DELETE FROM chunks WHERE page = ?"):
        con.execute(sql, (pid,))


def _put(con, pg: Page, sig: str) -> None:
    con.execute("INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?,?)",
                (pg.id, pg.wiki, pg.rel, pg.file, pg.title, ", ".join(pg.tags), ", ".join(pg.aliases), pg.summary,
                 pg.updated, sig))
    con.executemany("INSERT INTO links VALUES (?,?)", [(pg.id, f"{pg.wiki}:{t}") for t in pg.links])
    page_head = " ".join([pg.title, *pg.aliases, *pg.tags, pg.rel.replace("/", " ").replace("-", " ")])
    for heading, text in pg.sections or [("", "")]:
        for h, t in _chunks(heading, text):
            con.execute("INSERT INTO chunks (page, heading, text, head, body) VALUES (?,?,?,?,?)",
                        (pg.id, h, t, norm(page_head + " " + h), norm(t)))


# ---------------------------------------------------------------- search
@dataclass
class Hit:
    page: str
    rel: str
    file: str
    title: str
    tags: str
    summary: str
    heading: str
    snippet: str
    score: float
    agree: int          # how many phrasings found this page
    phrasings: int

    @property
    def key(self) -> str:
        return f"wiki:{self.page}"


def _match(q: str) -> str:
    ts = terms(q)[:12]
    return " OR ".join(f'"{t}"' for t in ts)


def _snippet(text: str, qterms: set[str], n: int = 320) -> str:
    flat = " ".join(text.split())
    low = norm(flat)
    pos = min((low.find(t) for t in qterms if low.find(t) >= 0), default=0)
    start = max(0, pos - n // 3)
    s = flat[start:start + n]
    return ("…" if start else "") + s + ("…" if start + n < len(flat) else "")


def search(phrasings: list[str], k: int = 5, wiki: str | None = None, hub: Path | None = None,
           refresh: bool = True) -> list[Hit]:
    phrasings = [p for p in (x.strip() for x in phrasings) if p and _match(p)]
    if not phrasings:
        return []
    if refresh:
        build(hub)
    con = connect(hub)
    fused: dict[str, float] = {}
    agree: dict[str, set[int]] = {}
    best: dict[str, tuple[float, sqlite3.Row]] = {}
    for qi, q in enumerate(phrasings):
        rows = con.execute(
            "SELECT rowid, page, heading, text, bm25(chunks, 0, 0, 0, ?, 1.0) AS s FROM chunks WHERE chunks MATCH ? "
            "ORDER BY s LIMIT ?", (HEAD_WEIGHT, _match(q), PER_QUERY)).fetchall()
        ranked_pages: list[str] = []
        for r in rows:
            if wiki and not r["page"].startswith(wiki + ":"):
                continue
            if r["page"] not in ranked_pages:
                ranked_pages.append(r["page"])
            # best chunk for display: highest (most negative bm25) across all phrasings
            if r["page"] not in best or r["s"] < best[r["page"]][0]:
                best[r["page"]] = (r["s"], r)
        for rank, pid in enumerate(ranked_pages):
            fused[pid] = fused.get(pid, 0.0) + 1.0 / (RRF_K + rank + 1)
            agree.setdefault(pid, set()).add(qi)
    qterms = set().union(*(terms(q) for q in phrasings))
    out = []
    for pid, score in sorted(fused.items(), key=lambda x: (-x[1], x[0]))[:k]:
        pg = con.execute("SELECT * FROM pages WHERE id = ?", (pid,)).fetchone()
        if pg is None:
            continue
        ch = best[pid][1]
        out.append(Hit(page=pid, rel=pg["rel"], file=pg["file"], title=pg["title"], tags=pg["tags"], summary=pg["summary"],
                       heading=ch["heading"], snippet=_snippet(ch["text"], qterms), score=round(score, 4),
                       agree=len(agree[pid]), phrasings=len(phrasings)))
    con.close()
    return out


def format_hit(h: Hit, i: int) -> str:
    where = f" › {h.heading}" if h.heading else ""
    lines = [f"{i}. {h.title} — `{h.rel}`{where}  (khớp {h.agree}/{h.phrasings} cách hỏi)",
             f"   file: {h.file}"]
    if h.tags:
        lines.append(f"   tags: {h.tags}")
    if h.summary:
        lines.append(f"   tóm tắt: {_cut(h.summary, 220)}")
    lines.append(f"   đoạn khớp: {h.snippet}")
    return "\n".join(lines)


def _cut(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------- catalog / related
def catalog(prefix: str | None = None, tag: str | None = None, wiki: str | None = None, hub: Path | None = None,
            width: int = 150) -> list[str]:
    build(hub)
    con = connect(hub)
    rows = con.execute("SELECT * FROM pages ORDER BY wiki, rel").fetchall()
    out = []
    for r in rows:
        if wiki and r["wiki"] != wiki:
            continue
        if prefix and not r["rel"].startswith(prefix.strip("/")):
            continue
        if tag and norm(tag) not in [norm(t) for t in r["tags"].split(", ")]:
            continue
        tags = f" [{r['tags']}]" if r["tags"] else ""
        out.append(f"- `{r['rel']}` {r['title']}{tags} — {_cut(r['summary'], width)}")
    con.close()
    return out


def related(page: str, hub: Path | None = None) -> dict:
    """Out-links, back-links and pages sharing ≥ 2 tags. `page` = rel path with or without `.md`, or `wiki:rel`."""
    build(hub)
    con = connect(hub)
    want = page.replace("\\", "/").removesuffix(".md")
    rows = con.execute("SELECT * FROM pages").fetchall()
    me = next((r for r in rows if r["id"].removesuffix(".md") == want or r["rel"].removesuffix(".md") == want), None)
    if me is None:
        con.close()
        return {}
    base = me["id"].removesuffix(".md")
    by_link = {r["id"].removesuffix(".md"): r for r in rows}
    out_ = [by_link[d["dst"]] for d in con.execute("SELECT dst FROM links WHERE src = ?", (me["id"],)) if d["dst"] in by_link]
    back = [r for r in rows if con.execute("SELECT 1 FROM links WHERE src = ? AND dst = ?", (r["id"], base)).fetchone()]
    mine = {norm(t) for t in me["tags"].split(", ") if t}
    shared = sorted(((len(mine & {norm(t) for t in r["tags"].split(", ") if t}), r) for r in rows if r["id"] != me["id"]),
                    key=lambda x: (-x[0], x[1]["rel"]))
    con.close()
    return {"page": me, "out": out_, "back": back, "tags": [r for n, r in shared if n >= 2][:6]}


def stats(hub: Path | None = None) -> dict:
    ws = wikis(hub)
    if not ws:
        return {"wikis": 0, "pages": 0}
    if not db_path(hub).exists():
        build(hub)
    con = connect(hub)
    n = con.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    con.close()
    return {"wikis": len(ws), "names": [w for w, _ in ws], "pages": n}


# ---------------------------------------------------------------- prompt pointers (optional hook)
def prompt_pointers(prompt: str, hub: Path | None = None, k: int = 2) -> list[Hit]:
    """Strong matches only: ≥ 2 prompt terms in the page's title/tags/aliases/summary (keywords, not meaning —
    so this stays off by default and only points; the agent reads the page if it is relevant)."""
    if not load_config(hub).get("auto", {}).get("prompt"):
        return []
    qterms = set(terms(prompt))
    if len(qterms) < 2:
        return []
    out = []
    for h in search([prompt], k=k * 3, hub=hub):
        con = connect(hub)
        pg = con.execute("SELECT title, tags, aliases, summary FROM pages WHERE id = ?", (h.page,)).fetchone()
        con.close()
        if len(qterms & set(terms(" ".join(pg)))) >= 2:
            out.append(h)
    return out[:k]
