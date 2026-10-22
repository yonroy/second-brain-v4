"""Wiki retrieval eval (v4.1): does the agent find the right page when the question is worded differently?

Modes
- `raw`    : `wiki.search([question])`, no agent — what plain keyword search gives (deterministic, free).
- `nowiki` : headless agent, wiki folder only (it may read index.md, Grep, Read) — the no-v4.1 baseline.
- `skill`  : headless agent with the `wiki` skill and `brain wiki` — v4.1.
Both agent modes get the same prompt; only the tooling differs. A run passes when its final `NGUỒN:` line names
one of the expected pages.

    python -m bench.wiki_eval --modes raw,nowiki,skill --model sonnet --jobs 4
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from brain import paths
from brain.recall import wiki

PACKAGE = Path(__file__).resolve().parent.parent
QUESTIONS = Path(__file__).parent / "wiki" / "questions.toml"
RUNS_ROOT = Path(os.environ.get("BRAINBENCH_DIR", "D:/_brainbench"))
RESULTS = paths.hub() / "_metrics" / "bench"
SRC_RE = re.compile(r"NGU[ỒO]N\s*:\s*(.+)", re.I)

PROMPT = """Tra wiki kiến thức để trả lời câu hỏi sau, ngắn gọn (≤ 5 câu).
Wiki: {wiki} (markdown).

Câu hỏi: {q}

Dòng cuối cùng của câu trả lời BẮT BUỘC có dạng:
NGUỒN: <đường dẫn tương đối của trang wiki chính, vd concepts/abc.md>"""

CLAUDE_MD = """# Eval workspace
Lệnh `brain` = `python "{pkg}/bin/brain.py"` (Second Brain v4.1). Wiki đã được đăng ký: `brain wiki status`.
"""


def load_questions() -> list[dict]:
    return tomllib.loads(QUESTIONS.read_text(encoding="utf-8"))["q"]


def _rel(s: str, root: Path) -> str:
    s = s.strip().strip("`*_[]() ").replace("\\", "/")
    low, base = s.lower(), paths.fwd(root).lower().rstrip("/") + "/"
    if low.startswith(base):
        s = s[len(base):]
    s = s.split("wiki/", 1)[-1] if "/wiki/" in "/" + s.lower() else s
    return s if s.endswith(".md") else s + ".md"


def run_raw(q: dict, root: Path) -> dict:
    hits = wiki.search([q["text"]], k=3)
    got = [h.rel for h in hits]
    return {"answer_page": got[0] if got else "", "top3": got, "pass": bool(got) and got[0] in q["expect"],
            "pass_top3": any(g in q["expect"] for g in got)}


def run_agent(q: dict, mode: str, root: Path, model: str, batch: Path, timeout: int) -> dict:
    work = batch / f"{q['id']}-{mode}"
    work.mkdir(parents=True)
    if mode == "skill":
        shutil.copytree(PACKAGE / "skills" / "wiki", work / ".claude" / "skills" / "wiki")
        (work / "CLAUDE.md").write_text(CLAUDE_MD.format(pkg=paths.fwd(PACKAGE)), encoding="utf-8")
    exe = shutil.which("claude") or "claude"
    cmd = [exe, "-p", PROMPT.format(wiki=paths.fwd(root), q=q["text"]), "--output-format", "json", "--model", model,
           "--permission-mode", "bypassPermissions", "--setting-sources", "project,local", "--strict-mcp-config",
           "--no-session-persistence", "--add-dir", str(root)]
    try:
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, stdin=subprocess.DEVNULL)
        res = json.loads(r.stdout or "{}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {"pass": False, "error": f"{type(e).__name__}"}
    text = str(res.get("result", ""))
    if res.get("api_error_status") == 429 or "hit your session limit" in text:
        raise RuntimeError("quota")
    m = SRC_RE.findall(text)
    page = _rel(m[-1].split(",")[0], root) if m else ""
    return {"answer_page": page, "pass": page in q["expect"], "cost_usd": res.get("total_cost_usd"),
            "duration_s": round((res.get("duration_ms") or 0) / 1000, 1), "turns": res.get("num_turns"),
            "result_tail": text[-300:]}


def report(rows: list[dict]) -> str:
    modes = [m for m in ("raw", "nowiki", "skill") if any(r["mode"] == m for r in rows)]
    label = {"raw": "search thô (1 câu, không agent)", "nowiki": "agent, không v4.1", "skill": "agent + skill wiki (v4.1)"}

    def ms(rs, k, f):
        v = [r[k] for r in rs if isinstance(r.get(k), (int, float))]
        return f"{f.format(statistics.mean(v))} ± {f.format(statistics.stdev(v) if len(v) > 1 else 0)}" if v else "—"
    out = ["# Wiki eval (v4.1)", "", f"- {len({r['q'] for r in rows})} câu hỏi diễn đạt khác chữ với tiêu đề trang · "
           f"model: {', '.join(sorted({r.get('model', '-') for r in rows if r['mode'] != 'raw'}))}", "",
           "| Cách | Đúng trang | Giây / câu | Lượt / câu | $ / câu |", "|---|---|---|---|---|"]
    for m in modes:
        rs = [r for r in rows if r["mode"] == m]
        k = sum(bool(r.get("pass")) for r in rs)
        extra = f" (top-3: {sum(bool(r.get('pass_top3')) for r in rs)}/{len(rs)})" if m == "raw" else ""
        out.append(f"| {label[m]} | {k}/{len(rs)} ({100 * k / len(rs):.0f}%){extra} | {ms(rs, 'duration_s', '{:.0f}')} | "
                   f"{ms(rs, 'turns', '{:.1f}')} | {ms(rs, 'cost_usd', '{:.3f}')} |")
    qs = sorted({r["q"] for r in rows})
    out += ["", "| Câu | " + " | ".join(modes) + " |", "|---|" + "---|" * len(modes)]
    for qid in qs:
        cells = []
        for m in modes:
            r = next((r for r in rows if r["q"] == qid and r["mode"] == m), None)
            cells.append("—" if r is None else ("✅ " if r.get("pass") else "❌ ") + f"`{r.get('answer_page') or r.get('error', '')}`")
        out.append(f"| {qid} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m bench.wiki_eval")
    ap.add_argument("--modes", default="raw,nowiki,skill")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--only", help="W01,W05")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--report", help="chỉ in báo cáo từ file jsonl")
    a = ap.parse_args(argv)
    if a.report:
        print(report([json.loads(l) for l in Path(a.report).read_text(encoding="utf-8").splitlines() if l.strip()]))
        return 0
    ws = wiki.wikis()
    if not ws:
        raise SystemExit("Chưa đăng ký wiki: `brain wiki add <thư mục>`")
    root = ws[0][1]
    qs = [q for q in load_questions() if not a.only or q["id"] in a.only.split(",")]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch = RUNS_ROOT / f"wiki-{stamp}"
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{stamp[:8]}-wiki-eval.jsonl"
    modes = a.modes.split(",")
    rows = []
    for q in qs:
        if "raw" in modes:
            rows.append({"q": q["id"], "mode": "raw", **run_raw(q, root)})
    specs = [(q, m) for q in qs for m in modes if m != "raw"]

    def one(spec):
        q, m = spec
        row = {"q": q["id"], "mode": m, "model": a.model, **run_agent(q, m, root, a.model, batch, a.timeout)}
        print(f"{'✅' if row.get('pass') else '❌'} {q['id']} {m} → {row.get('answer_page') or row.get('error')} "
              f"{row.get('duration_s', '-')}s ${row.get('cost_usd') or 0:.3f}", flush=True)
        return row
    with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as pool:
        rows += list(pool.map(one, specs))
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    md = out.with_suffix(".md")
    md.write_text(report(rows), encoding="utf-8")
    print("\n" + report(rows) + f"\n→ {paths.fwd(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
