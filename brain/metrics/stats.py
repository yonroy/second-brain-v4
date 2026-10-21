"""`brain stats`: field numbers from runs.sqlite, grouped by brain version / agent / ticket (spec §8)."""
from __future__ import annotations

import math
import sqlite3
import statistics


def _median(xs):
    return statistics.median(xs) if xs else None


def _p90(xs):
    """Nearest-rank p90 (never below the median for small n, unlike v2's int(0.9·(n−1)) index)."""
    xs = sorted(xs)
    return xs[max(0, math.ceil(0.9 * len(xs)) - 1)] if xs else None


def _rate(rows, key):
    vals = [r[key] for r in rows if r[key] is not None]
    return f"{sum(1 for v in vals if v)}/{len(vals)}" if vals else "—"


def _fmt(x, nd=1):
    return "—" if x is None else f"{x:.{nd}f}"


def report(con: sqlite3.Connection, by: str = "agent", project: str | None = None, since: str | None = None,
           source: str | None = None) -> str:
    where, args = [], []
    for col, val in (("project", project), ("source", source)):
        if val:
            where.append(f"{col} = ?")
            args.append(val)
    if since:
        where.append("date >= ?")
        args.append(since)
    q = "SELECT * FROM runs" + (" WHERE " + " AND ".join(where) if where else "")
    rows = [dict(r) for r in con.execute(q, args)]
    if not rows:
        return "Chưa có run nào khớp. Chạy `brain ingest` trước."
    key = {"agent": lambda r: f"{r['source']}:{r['agent']}", "version": lambda r: f"v{r['brain_version']}",
           "ticket": lambda r: r["ticket"] or "(không ticket)", "project": lambda r: r["project"]}[by]
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(key(r), []).append(r)
    dates = sorted(r["date"] for r in rows)
    out = [f"# brain stats — theo {by}", "",
           f"{len(rows)} run · {dates[0]} → {dates[-1]} · nguồn: {', '.join(sorted({r['source'] for r in rows}))}", "",
           "| Nhóm | Run | Trung vị phút | p90 phút | Lỗi tool % | Trung vị token | $ | Đọc trap | Trap được tiêm | "
           "Stop chặn | Brief đủ | Claim không bằng chứng |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for g, rs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        mins = [r["minutes"] for r in rs if r["minutes"] is not None]
        calls = sum(r["tool_calls"] or 0 for r in rs)
        errs = sum(r["tool_errors"] or 0 for r in rs)
        costs = [r["cost_usd"] for r in rs if r["cost_usd"] is not None]
        briefs = [r for r in rs if r["source"] == "omp"]
        out.append(
            f"| {g} | {len(rs)} | {_fmt(_median(mins))} | {_fmt(_p90(mins))} | {_fmt(100 * errs / calls if calls else 0)} | "
            f"{_fmt(_median([r['tokens'] for r in rs if r['tokens']]), 0)} | "
            f"{_fmt(sum(costs), 2) if costs else '—'}{'' if len(costs) == len(rs) else f' ({len(costs)}/{len(rs)} có giá)'} | "
            f"{_rate(rs, 'read_traps')} | {sum(r['traps_injected'] or 0 for r in rs) if any(r['traps_injected'] is not None for r in rs) else '—'} | "
            f"{sum(r['stop_blocks'] or 0 for r in rs) if any(r['stop_blocks'] is not None for r in rs) else '—'} | "
            f"{(str(sum(1 for r in briefs if not r['brief_missing'])) + '/' + str(len(briefs))) if briefs else '—'} | "
            f"{sum(r['unbacked_claims'] or 0 for r in rs)} |")
    out += ["", "- Phút = thời gian làm thật (omp: theo đoạn yield như v2; Claude: khoảng giữa các sự kiện, mỗi khoảng tối đa 5′).",
            "- $ omp = usage.cost (giá list). $ Claude chỉ có khi `[metrics.prices]` trong brain.toml có giá cho model.",
            "- `brain stats --unbacked` liệt kê từng claim không có lệnh chứng minh."]
    return "\n".join(out)


def unbacked(con: sqlite3.Connection, project: str | None = None, limit: int = 30) -> str:
    q = ("SELECT r.source, r.agent, r.name, r.date, e.detail FROM events e JOIN runs r USING (source, run_id) "
         "WHERE e.kind = 'claim_unbacked'" + (" AND r.project = ?" if project else "") + " ORDER BY r.started DESC LIMIT ?")
    rows = con.execute(q, ([project] if project else []) + [limit]).fetchall()
    if not rows:
        return "Không có claim nào thiếu bằng chứng."
    return "\n".join(f"- {r['date']} {r['source']}:{r['agent']} `{r['name']}` — {r['detail'][:220]}" for r in rows)
