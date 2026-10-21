"""Aggregate bench JSONL rows into a Markdown comparison across brains."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ORDER = ["none", "v1", "v2", "v3", "v4"]


def load_rows(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _rate(rows: list[dict], key: str) -> str:
    vals = [r.get(key) for r in rows if r.get(key) is not None]
    if not vals:
        return "—"
    k = sum(1 for v in vals if v)
    return f"{k}/{len(vals)} ({100 * k / len(vals):.0f}%)"


def _mean_sd(rows: list[dict], key: str, fmt: str) -> str:
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    if not vals:
        return "—"
    m = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return f"{fmt.format(m)} ± {fmt.format(sd)}"


def _brains(rows):
    seen = {r["brain"] for r in rows}
    return [b for b in ORDER if b in seen] + sorted(seen - set(ORDER))


def render(rows: list[dict]) -> str:
    by_brain = defaultdict(list)
    for r in rows:
        by_brain[r["brain"]].append(r)
    brains = _brains(rows)
    models = sorted({r.get("model", "?") for r in rows})
    out = [f"# Bench report", "", f"- Lượt chạy: {len(rows)} · model: {', '.join(models)} · "
           f"task: {len({r['task'] for r in rows})}", "",
           "## Tổng hợp theo brain", "",
           "| Brain | n | Pass | Tránh trap | Đọc memory | Cập nhật memory | Chạy test | Claim không bằng chứng | Lỗi chạy | $ / lượt | Giây / lượt | Token vào / lượt |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for b in brains:
        rs = by_brain[b]
        errors = sum(1 for r in rs if r.get("error"))
        out.append(f"| {b} | {len(rs)} | {_rate(rs, 'pass')} | {_rate(rs, 'trap_avoided')} | {_rate(rs, 'read_memory')} | "
                   f"{_rate(rs, 'memory_updated')} | {_rate(rs, 'ran_tests')} | {_rate(rs, 'claim_unbacked')} | {errors} | "
                   f"{_mean_sd(rs, 'cost_usd', '{:.3f}')} | {_mean_sd(rs, 'duration_s', '{:.0f}')} | "
                   f"{_mean_sd(rs, 'tokens_in', '{:.0f}')} |")
    tasks = sorted({r["task"] for r in rows})
    out += ["", "## Pass theo task", "", "| Task | Loại | " + " | ".join(brains) + " |",
            "|---|---|" + "---|" * len(brains)]
    for t in tasks:
        kind = next(r.get("kind", "") for r in rows if r["task"] == t)
        cells = []
        for b in brains:
            rs = [r for r in by_brain[b] if r["task"] == t]
            k = sum(1 for r in rs if r.get("pass"))
            cells.append(f"{k}/{len(rs)}" if rs else "—")
        out.append(f"| {t} | {kind} | " + " | ".join(cells) + " |")
    out += ["", "## Ghi chú đọc số", "",
            "- `±` là độ lệch chuẩn giữa các lượt. Chênh lệch giữa hai brain nhỏ hơn độ lệch thì **chưa kết luận được**.",
            "- `Đọc memory` / `Cập nhật memory` không áp cho `none`.",
            "- `Claim không bằng chứng`: câu trả lời cuối nói test pass/xanh nhưng transcript không có lệnh chạy test.",
            ""]
    errs = [r for r in rows if r.get("error")]
    if errs:
        out += ["## Lượt lỗi", ""] + [f"- {r['task']} {r['brain']} r{r['repeat']}: {r['error'][:200]}" for r in errs] + [""]
    return "\n".join(out)
