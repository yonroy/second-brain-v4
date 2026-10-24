"""Mini context graph (v4.2-dev, ADR-014 proposed): a deterministic, stdlib port of the Graphiti ideas.

What is kept from Graphiti (getzep/graphiti):
- **Episodes → entities → fact edges.** An episode is a raw source (journal, ADR, commit…) with a reference time.
  A fact is a directed edge `src —rel→ dst` carrying the sentence it came from and the episodes that said it.
- **Bi-temporal edges.** `valid_at`/`invalid_at` is when the fact was true in the world; `created_seq`/
  `expired_seq` is when the graph learnt / retired it (transaction time, ingest order so it stays deterministic).
- **Invalidation instead of deletion.** A new value for a functional relation (`owner`, `timeout`…) closes the
  interval of the older edge (`resolve_edge_contradictions`), both for fresh and for late-arriving facts.
- **Entity resolution:** exact normalised name, then MinHash/LSH over 3-gram shingles with an entropy gate and a
  Jaccard threshold (`dedup_helpers.py`). Graphiti asks an LLM when unsure; here unsure means "new entity".
- **Hybrid search:** BM25 over facts + BFS from the entities named in the query, fused by reciprocal rank.

What is different: no LLM extraction and no embeddings (spec v4 §2.2, ADR-010) — facts come in as triples or from
regex extraction, similarity is Jaccard over term sets, and MMR is the greedy (selected-set) form rather than
Graphiti's single-pass one. On top of retrieval there is an explicit **context allocator** (`pack`) that spends a
character budget, because what reaches the agent is the packed context, not the ranking.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from hashlib import blake2b
from pathlib import Path

from brain.recall.text import fts_query, norm, paths_in, terms

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (id INTEGER PRIMARY KEY, ref TEXT UNIQUE, kind TEXT, t_ref TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS entities (id INTEGER PRIMARY KEY, name TEXT, key TEXT UNIQUE, kind TEXT);
CREATE TABLE IF NOT EXISTS aliases (key TEXT PRIMARY KEY, entity INTEGER);
CREATE TABLE IF NOT EXISTS edges (id INTEGER PRIMARY KEY, src INTEGER, rel TEXT, dst INTEGER, fact TEXT,
    valid_at TEXT, invalid_at TEXT, created_seq INTEGER, expired_seq INTEGER, episodes TEXT);
CREATE INDEX IF NOT EXISTS edges_src ON edges (src, rel);
CREATE INDEX IF NOT EXISTS edges_dst ON edges (dst);
CREATE TABLE IF NOT EXISTS mentions (episode INTEGER, entity INTEGER, PRIMARY KEY (episode, entity));
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(norm, tokenize = 'unicode61');
"""

# dedup_helpers.py constants, unchanged
ENTROPY_MIN, NAME_MIN, TOKENS_MIN, JACCARD_MIN = 1.5, 6, 2, 0.9
PERMUTATIONS, BAND = 32, 4
RRF_K = 60  # Graphiti uses rank_const=1; 60 is the Cormack et al. default. Bench compares both.


# ---------------------------------------------------------------- entity resolution
def entity_key(name: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9_./' -]", " ", norm(name)).replace("-", " ").replace("_", " ").split())


def entropy(key: str) -> float:
    s = key.replace(" ", "")
    n = len(s)
    if not n:
        return 0.0
    counts = defaultdict(int)
    for c in s:
        counts[c] += 1
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def specific(key: str) -> bool:
    """Short or repetitive names are unreliable for fuzzy matching (Graphiti `_has_high_entropy`)."""
    if len(key) < NAME_MIN and len(key.split()) < TOKENS_MIN:
        return False
    return entropy(key) >= ENTROPY_MIN


def shingles(key: str) -> set[str]:
    s = key.replace(" ", "")
    return {s[i:i + 3] for i in range(len(s) - 2)} if len(s) > 2 else ({s} if s else set())


def minhash(sh: set[str]) -> tuple[int, ...]:
    if not sh:
        return ()
    return tuple(min(int.from_bytes(blake2b(f"{seed}:{x}".encode(), digest_size=8).digest(), "big") for x in sh)
                 for seed in range(PERMUTATIONS))


def bands(sig: tuple[int, ...]) -> list[tuple[int, ...]]:
    return [sig[i:i + BAND] for i in range(0, len(sig) - BAND + 1, BAND)]


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b) if a and b else 0.0


# ---------------------------------------------------------------- results
@dataclass
class Fact:
    id: int
    src: str
    rel: str
    dst: str | None
    fact: str
    valid_at: str
    invalid_at: str
    episodes: list[str]
    score: float = 0.0
    hop: int | None = None
    units: set = field(default_factory=set)

    def render(self) -> str:
        when = self.valid_at or "?"
        if self.invalid_at:
            when += f"→{self.invalid_at}"
        return f"- [{when}] {' '.join(self.fact.split())}"


def active(valid_at: str, invalid_at: str, as_of: str | None) -> bool:
    """Valid-time filter. `as_of=None` means "now": the interval is still open."""
    if as_of is None:
        return not invalid_at
    return (not valid_at or valid_at <= as_of) and (not invalid_at or invalid_at > as_of)


class Graph:
    def __init__(self, path: Path | str = ":memory:", functional: set[str] | None = None, temporal: bool = True):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(path))
        self.con.executescript(SCHEMA)
        self.functional = set(functional or ())
        self.temporal = temporal  # False = ablation: never invalidate
        self._lsh: dict[tuple, set[int]] = defaultdict(set)
        self._sh: dict[int, set[str]] = {}
        for eid, key in self.con.execute("SELECT entity, key FROM aliases"):
            self._remember(eid, key)
        row = self.con.execute("SELECT value FROM meta WHERE key='seq'").fetchone()
        self.seq = int(row[0]) if row else 0

    # ------------------------------------------------------------ entities
    def _remember(self, eid: int, key: str) -> None:
        if not specific(key):
            return
        sh = shingles(key)
        self._sh.setdefault(eid, set()).update(sh)
        for b in bands(minhash(sh)):
            self._lsh[b].add(eid)

    def find(self, name: str) -> int | None:
        key = entity_key(name)
        row = self.con.execute("SELECT entity FROM aliases WHERE key=?", (key,)).fetchone()
        if row:
            return row[0]
        if not specific(key):
            return None
        sh = shingles(key)
        cands = sorted({e for b in bands(minhash(sh)) for e in self._lsh.get(b, ())})
        best = max(((jaccard(sh, self._sh[e]), -e) for e in cands), default=(0.0, 0))
        return -best[1] if best[0] >= JACCARD_MIN else None

    def entity(self, name: str, kind: str = "", aliases: tuple[str, ...] = ()) -> int:
        eid = self.find(name)
        if eid is None:
            cur = self.con.execute("INSERT INTO entities (name, key, kind) VALUES (?,?,?)", (name, entity_key(name), kind))
            eid = cur.lastrowid
        for a in (name, *aliases):
            k = entity_key(a)
            if k and self.con.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (k, eid)).rowcount:
                self._remember(eid, k)
        return eid

    def name(self, eid: int | None) -> str | None:
        if eid is None:
            return None
        return self.con.execute("SELECT name FROM entities WHERE id=?", (eid,)).fetchone()[0]

    # ------------------------------------------------------------ ingest
    def episode(self, ref: str, text: str, t_ref: str = "", kind: str = "") -> int:
        row = self.con.execute("SELECT id FROM episodes WHERE ref=?", (ref,)).fetchone()
        if row:
            return row[0]
        return self.con.execute("INSERT INTO episodes (ref, kind, t_ref, text) VALUES (?,?,?,?)",
                                (ref, kind, t_ref, text)).lastrowid

    def add_fact(self, src: str, rel: str, dst: str | None, fact: str, valid_at: str = "", episode: str = "",
                 invalid_at: str = "") -> int:
        """Insert or merge a fact edge; returns its id. Functional relations invalidate overlapping values."""
        self.seq += 1
        s = self.entity(src)
        d = self.entity(dst) if dst else None
        ep = self.con.execute("SELECT id FROM episodes WHERE ref=?", (episode,)).fetchone() if episode else None
        if ep:
            for e in (s, d):
                if e is not None:
                    self.con.execute("INSERT OR IGNORE INTO mentions VALUES (?,?)", (ep[0], e))
        same = self.con.execute("SELECT id, episodes FROM edges WHERE src=? AND rel=? AND dst IS ? AND valid_at=?",
                                (s, rel, d, valid_at)).fetchone()
        if same:  # Graphiti edge dedup: same fact said again → one more episode of provenance
            eps = json.loads(same[1])
            if episode and episode not in eps:
                eps.append(episode)
                self.con.execute("UPDATE edges SET episodes=? WHERE id=?", (json.dumps(eps), same[0]))
            return same[0]
        if self.temporal and rel in self.functional:
            invalid_at = self._resolve(s, rel, d, valid_at, invalid_at)
        cur = self.con.execute(
            "INSERT INTO edges (src, rel, dst, fact, valid_at, invalid_at, created_seq, expired_seq, episodes) "
            "VALUES (?,?,?,?,?,?,?,NULL,?)",
            (s, rel, d, fact, valid_at, invalid_at, self.seq, json.dumps([episode] if episode else [])))
        names = " ".join(x for x in (src, rel.replace("_", " "), dst or "") if x)
        self.con.execute("INSERT INTO facts_fts (rowid, norm) VALUES (?,?)", (cur.lastrowid, norm(f"{fact} {names}")))
        return cur.lastrowid

    def _resolve(self, s: int, rel: str, d: int | None, valid_at: str, invalid_at: str) -> str:
        """Graphiti `resolve_edge_contradictions`, both directions. Returns the new edge's `invalid_at`."""
        for eid, odst, ov, oi in self.con.execute(
                "SELECT id, dst, valid_at, invalid_at FROM edges WHERE src=? AND rel=? AND dst IS NOT ? "
                "ORDER BY valid_at, id", (s, rel, d)).fetchall():
            if (oi and valid_at and oi <= valid_at) or (invalid_at and ov and invalid_at <= ov):
                continue  # intervals do not overlap
            if ov and valid_at and ov < valid_at:  # new value supersedes old one
                self.con.execute("UPDATE edges SET invalid_at=?, expired_seq=? WHERE id=?",
                                 (min(oi, valid_at) if oi else valid_at, self.seq, eid))
            elif ov and valid_at and valid_at < ov:  # late-arriving older value: it ended when the newer began
                invalid_at = min(invalid_at, ov) if invalid_at else ov
        return invalid_at

    def commit(self) -> None:
        self.con.execute("INSERT OR REPLACE INTO meta VALUES ('seq', ?)", (str(self.seq),))
        self.con.commit()

    # ------------------------------------------------------------ read
    def _fact(self, row) -> Fact:
        eid, s, rel, d, fact, va, ia, eps = row
        src, dst = self.name(s), self.name(d)
        f = Fact(eid, src, rel, dst, fact, va or "", ia or "", json.loads(eps))
        f.units = set(terms(fact)) | {f"@{s}"} | ({f"@{d}"} if d else set())
        return f

    def facts(self, ids: list[int]) -> dict[int, Fact]:
        if not ids:
            return {}
        q = ",".join("?" * len(ids))
        rows = self.con.execute(f"SELECT id, src, rel, dst, fact, valid_at, invalid_at, episodes FROM edges "
                                f"WHERE id IN ({q})", ids).fetchall()
        return {r[0]: self._fact(r) for r in rows}

    def stats(self) -> dict:
        one = lambda q: self.con.execute(q).fetchone()[0]
        return {"episodes": one("SELECT count(*) FROM episodes"), "entities": one("SELECT count(*) FROM entities"),
                "aliases": one("SELECT count(*) FROM aliases"), "edges": one("SELECT count(*) FROM edges"),
                "invalidated": one("SELECT count(*) FROM edges WHERE invalid_at != ''")}

    # ------------------------------------------------------------ search
    def link(self, query: str) -> list[int]:
        """Entities named in the query: exact alias spans of 1–4 tokens, then fuzzy (LSH) spans."""
        toks = entity_key(query).split()
        found: list[int] = []
        for n in (4, 3, 2, 1):
            for i in range(len(toks) - n + 1):
                span = " ".join(toks[i:i + n])
                e = self.find(span) if (n > 1 or len(span) >= 3) else None
                if e is not None and e not in found:
                    found.append(e)
        return found

    def _bm25(self, query: str, as_of: str | None, limit: int) -> list[int]:
        q = fts_query(query, 16)
        if not q:
            return []
        rows = self.con.execute(
            "SELECT e.id, e.valid_at, e.invalid_at FROM facts_fts JOIN edges e ON e.id = facts_fts.rowid "
            "WHERE facts_fts MATCH ? ORDER BY bm25(facts_fts), e.id LIMIT ?", (q, limit * 4)).fetchall()
        return [r[0] for r in rows if active(r[1] or "", r[2] or "", as_of)][:limit]

    def _bfs(self, seeds: list[int], as_of: str | None, depth: int, limit: int) -> tuple[list[int], dict[int, int]]:
        """Edges reachable from the seed entities, nearest first (Graphiti `node_distance` as a channel)."""
        hop_of: dict[int, int] = {}
        frontier, seen = list(seeds), set(seeds)
        for h in range(1, depth + 1):
            nxt = []
            for ent in frontier:
                for eid, s, d, va, ia in self.con.execute(
                        "SELECT id, src, dst, valid_at, invalid_at FROM edges WHERE src=? OR dst=? ORDER BY id",
                        (ent, ent)):
                    if not active(va or "", ia or "", as_of) or eid in hop_of:
                        continue
                    hop_of[eid] = h
                    for x in (s, d):
                        if x is not None and x not in seen:
                            seen.add(x)
                            nxt.append(x)
            frontier = nxt
        ranked = sorted(hop_of, key=lambda e: (hop_of[e], e))
        return ranked[:limit], hop_of

    def search(self, query: str, k: int = 20, as_of: str | None = None, channels: tuple[str, ...] = ("bm25", "bfs"),
               depth: int = 2, rrf_k: int = RRF_K) -> list[Fact]:
        """Hybrid retrieval with RRF fusion: score(e) = Σ_c 1 / (rrf_k + rank_c(e))."""
        lists, hop_of = [], {}
        if "bm25" in channels:
            lists.append(self._bm25(query, as_of, k * 2))
        if "bfs" in channels:
            seeds = self.link(query)
            if seeds:
                ranked, hop_of = self._bfs(seeds, as_of, depth, k * 2)
                lists.append(ranked)
        score: dict[int, float] = defaultdict(float)
        for lst in lists:
            for r, eid in enumerate(lst, 1):
                score[eid] += 1.0 / (rrf_k + r)
        top = sorted(score, key=lambda e: (-score[e], e))[:k]
        got = self.facts(top)
        out = []
        for e in top:
            f = got[e]
            f.score, f.hop = score[e], hop_of.get(e)
            out.append(f)
        return out


# ---------------------------------------------------------------- context allocation
def pack(hits: list[Fact], budget: int, policy: str = "cover", lam: float = 0.7, alpha: float = 0.5,
         r: float = 1.0) -> list[Fact]:
    """Spend `budget` characters on `hits` (ranked). Order of the result = order in the injected context.

    - `topk`  : rank order, skip what does not fit (what v4 `surface` does today).
    - `mmr`   : greedy MMR under budget, argmax λ·rel − (1−λ)·max_{j∈S} J(i, j), J = Jaccard of unit sets.
    - `cover` : budgeted monotone submodular maximisation, F(S) = α·Σ_{e∈S} rel_e + (1−α)·w(∪ U_e)/w(∪ all U),
                greedy on ΔF / cost^r plus the best-singleton check, which gives the (1 − 1/e)/2 bound
                (Khuller–Moss–Naor; Lin & Bilmes 2010). Units U_e = terms of the fact ∪ its entity ids.
    """
    if not hits:
        return []
    top = max(h.score for h in hits) or 1.0
    rel = {h.id: h.score / top for h in hits}
    cost = {h.id: len(h.render()) + 1 for h in hits}
    fits = [h for h in hits if cost[h.id] <= budget]
    if policy == "topk":
        out, used = [], 0
        for h in fits:
            if used + cost[h.id] <= budget:
                out.append(h)
                used += cost[h.id]
        return out
    df = defaultdict(int)
    for h in hits:
        for u in h.units:
            df[u] += 1
    w = {u: math.log(1 + len(hits) / c) for u, c in df.items()}  # idf over the candidate pool
    total_w = sum(w.values()) or 1.0
    out, used, covered = [], 0, set()
    pool = list(fits)
    while pool:
        best, best_val = None, -math.inf
        for h in pool:
            if used + cost[h.id] > budget:
                continue
            if policy == "mmr":
                red = max((jaccard(h.units, s.units) for s in out), default=0.0)
                val = lam * rel[h.id] - (1 - lam) * red
            else:
                gain = alpha * rel[h.id] + (1 - alpha) * sum(w[u] for u in h.units - covered) / total_w
                val = gain / cost[h.id] ** r
            if val > best_val:
                best, best_val = h, val
        if best is None:
            break
        out.append(best)
        used += cost[best.id]
        covered |= best.units
        pool.remove(best)
    if policy == "cover":
        f_val = lambda S: alpha * sum(rel[h.id] for h in S) + (1 - alpha) * sum(
            w[u] for u in set().union(*(h.units for h in S))) / total_w if S else 0.0
        single = max(fits, key=lambda h: (f_val([h]), -h.id), default=None)
        if single is not None and f_val([single]) > f_val(out):
            return [single]
    return out


def render(facts: list[Fact], header: str = "Context graph") -> str:
    return f"## {header}\n" + "\n".join(f.render() for f in facts) if facts else ""


# ---------------------------------------------------------------- project adapter
ENTITY_RES = [re.compile(r"\b(?:ADR|D)-\d{2,4}\b"), re.compile(r"\b[A-Z]{1,3}-\d{3}\b"),
              re.compile(r"`([A-Za-z_][\w.]{2,60})`")]
SENT = re.compile(r"(?<=[.!?。])\s+|\n+")


def extract(text: str) -> list[tuple[str, list[str]]]:
    """Sentences with the entities they name: file paths, ADR/trap/ticket ids, `backticked` identifiers."""
    out = []
    for s in SENT.split(text or ""):
        s = s.strip(" -*#>\t")
        if len(s) < 12:
            continue
        ents: list[str] = []
        for x in paths_in(s) + [m.group(m.lastindex or 0) for rx in ENTITY_RES for m in rx.finditer(s)]:
            if x not in ents:
                ents.append(x)
        if ents:
            out.append((s[:400], ents))
    return out


def db_path(p) -> Path:
    return p.root / ".index" / "cgraph.sqlite"


def build_project(p) -> dict:
    """Derive the graph from the history index units and the code graph (both must be built: `brain index`)."""
    from brain.recall import code, history
    f = db_path(p)
    if f.exists():
        f.unlink()
    g = Graph(f)
    hcon = history.connect(p)
    for kind, ref, date, text in hcon.execute("SELECT kind, ref, date, text FROM units ORDER BY date, kind, ref"):
        ep = f"{kind}:{ref}"
        g.episode(ep, text[:4000], date, kind)
        g.entity(ref, kind)
        for sent, ents in extract(text):
            for e in ents:
                g.add_fact(ref, "mentions", e, sent, date, ep)
    ccon = code.connect(p)
    for src, dst in ccon.execute("SELECT DISTINCT path, target FROM imports WHERE target IS NOT NULL ORDER BY 1, 2"):
        g.add_fact(src, "imports", dst, f"{src} imports {dst}")
    for name, path, line in ccon.execute("SELECT name, path, line FROM defs WHERE kind != 'method' ORDER BY 2, 3"):
        g.add_fact(path, "defines", name, f"{path}:{line} defines {name}")
    ccon.close()
    hcon.close()
    g.commit()
    return g.stats()
