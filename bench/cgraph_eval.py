"""Offline, deterministic benchmark of context allocation (v4.2-dev, plan: docs/bench/20261024-cgraph-plan.md).

No agent, no network, no LLM: a seeded synthetic "project history" with ground truth, so every number is exact and
re-runnable. It measures what reaches the agent — the packed context under a character budget — not only rankings.

World: services with surface-form aliases (CamelCase, kebab, snake, spaced, typo), people, databases. Functional
relations change over time (owner, timeout, storage) so the history contains stale values; `calls` is a static
dependency graph for multi-hop questions; on-call / review / standup notes are distractors. Some episodes arrive
late (out of order), as journals written after the fact do.

Systems
- `recency`   : newest episodes first until the budget is spent (≈ "dump the recent journal").
- `flat`      : FTS5 bm25 over whole episodes (≈ v4 `history.search` today).
- `facts`     : graph facts, bm25 only, no invalidation.
- `graph-nt`  : bm25 + BFS + RRF, no invalidation (ablation of the temporal model).
- `graph`     : bm25 + BFS + RRF + bi-temporal invalidation (+ `as_of` when the question names a date).
Allocation policies on `graph`: `topk`, `mmr`, `cover` (see `cgraph.pack`).

    python -m bench.cgraph_eval                       # default seed, markdown to stdout
    python -m bench.cgraph_eval --seeds 1,2,3 --out docs/bench/20261024-cgraph-offline.md
"""
from __future__ import annotations

import argparse
import math
import random
import sqlite3
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from brain.recall import cgraph
from brain.recall.text import fts_query, norm, terms

BUDGETS = (300, 600, 1200, 2400)
MAIN_BUDGET = 1200
K = 10
FIRST = ("Payment", "Ledger", "Search", "Invoice", "Catalog", "Shipping", "Pricing", "Identity", "Billing", "Report",
         "Inventory", "Notify", "Session", "Refund", "Checkout", "Profile", "Audit", "Media", "Export", "Routing")
SECOND = ("Service", "Gateway", "Worker", "Engine")
PEOPLE = ("Alice", "Bao", "Chau", "Dung", "Emma", "Farid", "Giang", "Hana", "Ivan", "Khoa", "Linh", "Minh", "Nam",
          "Oanh", "Phuc", "Quang", "Rosa", "Son", "Thao", "Uyen", "Vinh", "Xuan", "Yen", "Zoe")
DBS = ("pg-main", "pg-analytics", "mysql-legacy", "redis-cache", "mongo-docs", "clickhouse-events")


# ---------------------------------------------------------------- world
@dataclass
class GoldFact:
    sent: str
    subj: str  # canonical entity
    rel: str
    obj: str
    surface: str  # how the subject is written in this sentence
    valid_at: str
    invalid_at: str = ""


@dataclass
class Episode:
    ref: str
    day: str
    facts: list[GoldFact]
    noise: list[tuple[str, str, str, str]]  # (sent, surface subj, rel, obj)

    @property
    def text(self) -> str:
        return " ".join([f.sent for f in self.facts] + [n[0] for n in self.noise])


@dataclass
class Query:
    qid: str
    kind: str
    text: str
    gold: list[str]  # sentences that must be in context
    stale: list[str] = field(default_factory=list)  # competing values for the same key
    as_of: str | None = None


def surfaces(first: str, second: str, rng: random.Random) -> list[str]:
    camel = first + second
    typo_at = rng.randrange(3, len(camel) - 1)
    return [camel, f"{first.lower()}-{second.lower()}", f"{first.lower()}_{second.lower()}",
            f"{first.lower()} {second.lower()}", camel[:typo_at] + camel[typo_at + 1:]]


def build_world(seed: int, days: int = 180, late_p: float = 0.15):
    rng = random.Random(seed)
    names = [(a, b) for a in FIRST for b in SECOND]
    rng.shuffle(names)
    svcs = names[:24]
    canon = {f + s: surfaces(f, s, rng) for f, s in svcs}
    svc_ids = list(canon)
    start = date(2026, 1, 1)
    day = lambda i: (start + timedelta(days=i)).isoformat()
    say = lambda s: rng.choice(canon[s][:4]) if rng.random() < 0.85 else canon[s][4]

    timeline: dict[tuple[str, str], list[GoldFact]] = defaultdict(list)
    facts_by_day: dict[int, list[GoldFact]] = defaultdict(list)

    def emit(i, subj, rel, obj, template):
        sf = say(subj)
        gf = GoldFact(template.format(d=day(i), s=sf, o=obj), subj, rel, obj, sf, day(i))
        facts_by_day[i].append(gf)
        if rel != "calls":
            timeline[(subj, rel)].append(gf)
        return gf

    templates = {"owner": "{d}: {o} became the owner of {s}.",
                 "timeout": "{d}: request timeout of {s} set to {o}.",
                 "storage": "{d}: {s} moved its persistent storage to {o}."}
    for s in svc_ids:
        for rel, values in (("owner", PEOPLE), ("timeout", [f"{n}s" for n in (5, 10, 15, 20, 30, 45, 60, 90)]),
                            ("storage", DBS)):
            n_changes = rng.choice((0, 1, 1, 2, 3))
            points = sorted(rng.sample(range(1, days - 5), n_changes)) if n_changes else []
            prev = None
            for i in [0] + points:
                v = rng.choice([x for x in values if x != prev])
                emit(i if i else rng.randrange(0, 10), s, rel, v, templates[rel])
                prev = v
    calls = []
    for idx, s in enumerate(svc_ids):
        for t in rng.sample(svc_ids[idx + 1:], min(len(svc_ids) - idx - 1, rng.choice((0, 1, 2)))):
            calls.append(emit(rng.randrange(0, 20), s, "calls", t, "{s} calls {o} on every request."))
    # close intervals (ground truth)
    for key, lst in timeline.items():
        lst.sort(key=lambda f: f.valid_at)
        for a, b in zip(lst, lst[1:]):
            a.invalid_at = b.valid_at

    noise_t = [("{p} reviewed a pull request touching {s}.", "reviewed"),
               ("{p} was on call for {s} this week and saw no alerts.", "oncall"),
               ("Standup: {s} dashboards look normal, owner meeting moved to Friday.", "note"),
               ("{p} asked whether the timeout dashboards for {s} are still useful.", "asked")]
    episodes = []
    for i in range(days):
        noise = []
        for _ in range(rng.choice((1, 2, 3))):
            t, rel = rng.choice(noise_t)
            s, p = rng.choice(svc_ids), rng.choice(PEOPLE)
            sf = say(s)
            noise.append((f"{day(i)}: " + t.format(p=p, s=sf), sf, rel, p if "{p}" in t else ""))
        if facts_by_day[i] or noise:
            episodes.append(Episode(f"journal:{day(i)}", day(i), facts_by_day[i], noise))
    # late arrivals: ingest order ≠ valid-time order
    order = list(episodes)
    for j in range(len(order)):
        if rng.random() < late_p:
            k = min(len(order) - 1, j + rng.randrange(5, 30))
            order.insert(k, order.pop(j))

    queries = make_queries(rng, canon, timeline, calls, day(days - 1))
    return {"canon": canon, "episodes": order, "queries": queries}


def make_queries(rng, canon, timeline, calls, today) -> list[Query]:
    qs: list[Query] = []
    ask = {"owner": ["Who is the owner of {s} now?", "Who is responsible for {s} currently?"],
           "timeout": ["What request timeout does {s} use?", "How long before {s} times out?"],
           "storage": ["Which database does {s} store data in?", "Where is the persistent storage of {s}?"]}
    ask_at = {"owner": "Who owned {s} on {d}?", "timeout": "What was the timeout of {s} on {d}?",
              "storage": "Which storage did {s} use on {d}?"}
    keys = sorted(timeline)
    for n, (s, rel) in enumerate(keys):
        lst = timeline[(s, rel)]
        alias = rng.choice(canon[s])
        cur = lst[-1]
        qs.append(Query(f"cur{n}", "current" + ("-alias" if alias == canon[s][4] else ""),
                        rng.choice(ask[rel]).format(s=alias), [cur.sent], [f.sent for f in lst[:-1]]))
        if len(lst) > 1:
            a = rng.choice(lst[:-1])
            d = (date.fromisoformat(a.valid_at) + timedelta(days=1)).isoformat()
            if a.invalid_at and d < a.invalid_at:
                qs.append(Query(f"at{n}", "as_of", ask_at[rel].format(s=rng.choice(canon[s][:4]), d=d), [a.sent],
                                [f.sent for f in lst if f is not a], as_of=d))
    for n, c in enumerate(calls):
        t = timeline[(c.obj, "timeout")]
        qs.append(Query(f"hop{n}", "multihop",
                        f"What is the timeout of the service that {rng.choice(canon[c.subj][:4])} calls?",
                        [c.sent, t[-1].sent], [f.sent for f in t[:-1]]))
    by_target = defaultdict(list)
    for c in calls:
        by_target[c.obj].append(c)
    for n, (t, cs) in enumerate(sorted(by_target.items())):
        if len(cs) >= 2:
            qs.append(Query(f"in{n}", "inbound", f"Which services call {rng.choice(canon[t][:4])}?", [c.sent for c in cs]))
    return qs


# ---------------------------------------------------------------- systems → packed context lines
def build_flat(world):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE ep USING fts5(ref UNINDEXED, day UNINDEXED, text UNINDEXED, norm)")
    for e in world["episodes"]:
        con.execute("INSERT INTO ep VALUES (?,?,?,?)", (e.ref, e.day, e.text, norm(e.text)))
    return con


def flat_ranked(con, q: Query) -> list[str]:
    fq = fts_query(q.text, 16)
    rows = con.execute("SELECT day, text FROM ep WHERE ep MATCH ? ORDER BY bm25(ep), day LIMIT 40", (fq,)).fetchall()
    return [f"- [{d}] {t}" for d, t in rows]


def recency_ranked(world) -> list[str]:
    return [f"- [{e.day}] {e.text}" for e in sorted(world["episodes"], key=lambda e: e.day, reverse=True)]


def pack_lines(lines: list[str], budget: int) -> list[str]:
    out, used = [], 0
    for l in lines:
        if used + len(l) + 1 <= budget:
            out.append(l)
            used += len(l) + 1
    return out


def build_graph(world, temporal: bool) -> cgraph.Graph:
    g = cgraph.Graph(functional={"owner", "timeout", "storage"}, temporal=temporal)
    for e in world["episodes"]:  # ingest order includes late arrivals
        g.episode(e.ref, e.text, e.day, "journal")
        for f in e.facts:
            g.add_fact(f.surface, f.rel, f.obj, f.sent, f.valid_at, e.ref)
        for sent, sf, rel, obj in e.noise:
            g.add_fact(sf, rel, obj or None, sent, e.day, e.ref)
    g.commit()
    return g


# ---------------------------------------------------------------- metrics
def contains(lines: list[str], sent: str) -> bool:
    return any(sent in l for l in lines)


def ranking_metrics(ranked: list[str], q: Query, k: int = K) -> dict:
    gains = [sum(s in l for s in q.gold) for l in ranked[:k]]
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(q.gold))))
    first = next((i for i, g in enumerate(gains) if g), None)
    found = {s for s in q.gold if contains(ranked[:k], s)}
    return {"recall@k": len(found) / len(q.gold), "mrr": 1 / (first + 1) if first is not None else 0.0,
            "ndcg@k": dcg / ideal if ideal else 0.0}


def context_metrics(ctx: list[str], q: Query, budget: int) -> dict:
    text_len = sum(len(l) + 1 for l in ctx)
    gold_in = [s for s in q.gold if contains(ctx, s)]
    stale_in = [s for s in q.stale if contains(ctx, s)]
    gold_chars = sum(len(s) for s in gold_in)
    pos = [i / max(1, len(ctx) - 1) for i, l in enumerate(ctx) if any(s in l for s in q.gold)]
    cov = len(gold_in) / len(q.gold)
    full = cov == 1.0
    # naive reader: when k competing values are visible it picks one uniformly → E[acc] = 1/(1+k)
    naive = (1.0 / (1 + len(stale_in))) if full else 0.0
    lines_terms = [set(terms(l)) for l in ctx]
    pairs = [(a, b) for i, a in enumerate(lines_terms) for b in lines_terms[i + 1:]]
    return {"coverage": cov, "answerable": float(full), "clean": float(full and not stale_in),
            "stale_any": float(bool(stale_in)), "naive_acc": naive,
            "density": gold_chars / text_len if text_len else 0.0, "util": text_len / budget,
            "redundancy": statistics.fmean(cgraph.jaccard(a, b) for a, b in pairs) if pairs else 0.0,
            "mid_risk": statistics.fmean(1 - abs(2 * p - 1) for p in pos) if pos else None}


def b_cubed(g: cgraph.Graph, canon: dict) -> dict:
    """Entity resolution quality over every surface form: B-cubed precision / recall / F1."""
    pred, gold = {}, {}
    for c, forms in canon.items():
        for f in forms:
            e = g.find(f)
            if e is not None:
                pred[f], gold[f] = e, c
    items = list(pred)
    P = statistics.fmean(sum(gold[j] == gold[i] for j in items if pred[j] == pred[i]) /
                         sum(pred[j] == pred[i] for j in items) for i in items)
    R = statistics.fmean(sum(pred[j] == pred[i] for j in items if gold[j] == gold[i]) /
                         sum(gold[j] == gold[i] for j in items) for i in items)
    return {"P": P, "R": R, "F1": 2 * P * R / (P + R), "forms": len(items),
            "unresolved": sum(len(v) for v in canon.values()) - len(items)}


def bootstrap(xs: list[float], n: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    rng = random.Random(seed)
    m = statistics.fmean(xs)
    means = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(n))
    return m, means[int(0.025 * n)], means[int(0.975 * n) - 1]


def sign_test(a: list[float], b: list[float]) -> tuple[int, int, float]:
    """Exact two-sided sign test on paired per-query scores (ties dropped)."""
    w = sum(x > y for x, y in zip(a, b))
    l = sum(x < y for x, y in zip(a, b))
    n = w + l
    if not n:
        return w, l, 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(w, l) + 1)) / 2 ** n
    return w, l, min(1.0, 2 * tail)


# ---------------------------------------------------------------- run
def run(seed: int) -> dict:
    world = build_world(seed)
    qs = world["queries"]
    flat = build_flat(world)
    rec = recency_ranked(world)
    g_t, g_nt = build_graph(world, True), build_graph(world, False)

    def graph_lines(g, q, budget, policy="topk", channels=("bm25", "bfs"), temporal_q=True):
        hits = g.search(q.text, k=40, as_of=q.as_of if temporal_q else None, channels=channels)
        return [h.render() for h in hits], [h.render() for h in cgraph.pack(hits, budget, policy)]

    systems = {
        "recency": lambda q, B: (rec, pack_lines(rec, B)),
        "flat": lambda q, B: (lambda r: (r, pack_lines(r, B)))(flat_ranked(flat, q)),
        "facts": lambda q, B: graph_lines(g_nt, q, B, channels=("bm25",), temporal_q=False),
        "graph-nt": lambda q, B: graph_lines(g_nt, q, B, temporal_q=False),
        "graph": lambda q, B: graph_lines(g_t, q, B),
        "graph+mmr": lambda q, B: graph_lines(g_t, q, B, "mmr"),
        "graph+cover": lambda q, B: graph_lines(g_t, q, B, "cover"),
    }
    rows = defaultdict(lambda: defaultdict(list))  # rows[(system, budget)][metric] = per-query list
    kinds = {q.qid: q.kind for q in qs}
    for name, fn in systems.items():
        for B in BUDGETS:
            for q in qs:
                ranked, ctx = fn(q, B)
                m = context_metrics(ctx, q, B)
                if B == MAIN_BUDGET:
                    m.update(ranking_metrics(ranked, q))
                m["qid"] = q.qid
                for k_, v in m.items():
                    rows[(name, B)][k_].append(v)
    return {"rows": rows, "kinds": kinds, "n_q": len(qs), "systems": list(systems),
            "er": b_cubed(g_t, world["canon"]), "graph": g_t.stats(),
            "episodes": len(world["episodes"]), "chars": sum(len(e.text) for e in world["episodes"])}


def aubc(rows, name, metric="coverage") -> float:
    """Area under the budget curve, x = log2(budget) rescaled to [0, 1] (trapezoid)."""
    xs = [math.log2(b) for b in BUDGETS]
    ys = [statistics.fmean(rows[(name, b)][metric]) for b in BUDGETS]
    area = sum((xs[i + 1] - xs[i]) * (ys[i] + ys[i + 1]) / 2 for i in range(len(xs) - 1))
    return area / (xs[-1] - xs[0])


def report(results: list[dict], seeds: list[int]) -> str:
    r0 = results[0]
    merged = defaultdict(lambda: defaultdict(list))
    for r in results:
        for key, ms in r["rows"].items():
            for m, v in ms.items():
                merged[key][m].extend(v)
    kinds_all = []
    for r in results:
        kinds_all.extend(r["kinds"][qid] for qid in r["rows"][(r0["systems"][0], MAIN_BUDGET)]["qid"])
    mean = lambda xs: statistics.fmean(x for x in xs if x is not None) if any(x is not None for x in xs) else float("nan")
    L = [f"# Context graph — offline bench (seeds {', '.join(map(str, seeds))})", "",
         f"Mỗi seed: {r0['episodes']} episode ({r0['chars']:,} ký tự lịch sử), {r0['n_q']} câu hỏi; "
         f"graph {r0['graph']['entities']} entity, {r0['graph']['edges']} cạnh, {r0['graph']['invalidated']} cạnh đã đóng. "
         f"Tổng {len(kinds_all)} câu hỏi. Ngân sách chính B = {MAIN_BUDGET} ký tự, xếp hạng tính ở k = {K}.", "",
         f"## Bảng chính (B = {MAIN_BUDGET})", "",
         "| Hệ | Coverage | Answerable | **Clean** [95% CI] | Stale | E[acc] naive | Density | Recall@10 | MRR | nDCG@10 | AUBC |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name in r0["systems"]:
        m = merged[(name, MAIN_BUDGET)]
        c, lo, hi = bootstrap(m["clean"])
        L.append(f"| {name} | {mean(m['coverage']):.3f} | {mean(m['answerable']):.3f} | **{c:.3f}** [{lo:.3f}, {hi:.3f}] | "
                 f"{mean(m['stale_any']):.3f} | {mean(m['naive_acc']):.3f} | {mean(m['density']):.3f} | "
                 f"{mean(m['recall@k']):.3f} | {mean(m['mrr']):.3f} | {mean(m['ndcg@k']):.3f} | {aubc(merged, name):.3f} |")
    L += ["", "## Clean theo loại câu hỏi (B = %d)" % MAIN_BUDGET, ""]
    kinds = sorted(set(kinds_all))
    L += ["| Hệ | " + " | ".join(f"{k} (n={kinds_all.count(k)})" for k in kinds) + " |", "|---|" + "---|" * len(kinds)]
    for name in r0["systems"]:
        cl = merged[(name, MAIN_BUDGET)]["clean"]
        L.append(f"| {name} | " + " | ".join(
            f"{statistics.fmean(v for v, kk in zip(cl, kinds_all) if kk == k):.2f}" for k in kinds) + " |")
    L += ["", "## Đường cong ngân sách: Clean theo B", "", "| Hệ | " + " | ".join(f"B={b}" for b in BUDGETS) + " |",
          "|---|" + "---|" * len(BUDGETS)]
    for name in r0["systems"]:
        L.append(f"| {name} | " + " | ".join(f"{mean(merged[(name, b)]['clean']):.3f}" for b in BUDGETS) + " |")
    L += ["", f"## Hình dạng context (B = {MAIN_BUDGET})", "", "| Hệ | Dùng ngân sách | Trùng lặp (Jaccard TB) | Rủi ro giữa (0 = ở mép, 1 = giữa) |",
          "|---|---|---|---|"]
    for name in r0["systems"]:
        m = merged[(name, MAIN_BUDGET)]
        L.append(f"| {name} | {mean(m['util']):.2f} | {mean(m['redundancy']):.3f} | {mean(m['mid_risk']):.3f} |")
    L += ["", "## Kiểm định cặp (sign test chính xác, Clean, B = %d)" % MAIN_BUDGET, "",
          "| So sánh | thắng | thua | p |", "|---|---|---|---|"]
    for a, b in (("graph", "flat"), ("graph", "graph-nt"), ("graph-nt", "facts"), ("graph+cover", "graph"),
                 ("graph+mmr", "graph"), ("flat", "recency")):
        w, l, p = sign_test(merged[(a, MAIN_BUDGET)]["clean"], merged[(b, MAIN_BUDGET)]["clean"])
        L.append(f"| {a} vs {b} | {w} | {l} | {p:.2g} |")
    L += ["", "## Entity resolution (B-cubed trên mọi dạng viết)", "", "| Seed | P | R | F1 | dạng viết nhận được | không nhận |",
          "|---|---|---|---|---|---|"]
    for s, r in zip(seeds, results):
        e = r["er"]
        L.append(f"| {s} | {e['P']:.3f} | {e['R']:.3f} | {e['F1']:.3f} | {e['forms']} | {e['unresolved']} |")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m bench.cgraph_eval")
    ap.add_argument("--seeds", default="1")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    seeds = [int(x) for x in a.seeds.split(",")]
    text = report([run(s) for s in seeds], seeds)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
