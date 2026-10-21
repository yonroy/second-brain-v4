"""python -m bench {list|validate|run|report}  — run from D:/SecondBrainV3/Brain."""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from bench import report
from bench.brains import BRAINS
from bench.tasks import all_tasks, select


def cmd_list(_a) -> int:
    for t in all_tasks():
        print(f"{t.id}  [{t.kind:8}] {t.title}")
    print("\nBrain:", ", ".join(BRAINS))
    return 0


def cmd_validate(a) -> int:
    """Checker sanity: the untouched repo must fail, repo + reference solution must pass."""
    bad = 0
    for t in select(a.task):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base"
            shutil.copytree(t.repo, base)
            r0 = t.check(base, [])
            sol = Path(tmp) / "sol"
            shutil.copytree(t.repo, sol)
            shutil.copytree(t.solution, sol, dirs_exist_ok=True)
            r1 = t.check(sol, [])
        ok = (not r0["pass"]) and r1["pass"] and r1.get("trap_avoided") is not False
        bad += not ok
        print(f"{'✅' if ok else '❌'} {t.id}  base.pass={r0['pass']}  solution.pass={r1['pass']} "
              f"trap={r1.get('trap_avoided')}  {'' if ok else r1.get('notes', '')}")
    return 1 if bad else 0


def cmd_run(a) -> int:
    from bench.runner import run_batch
    brains = [b.strip() for b in a.brain.split(",") if b.strip()]
    for b in brains:
        if b not in BRAINS:
            raise SystemExit(f"Không có brain '{b}'. Có: {', '.join(BRAINS)}")
    out = run_batch(select(a.task), brains, a.repeat, a.model, a.label, a.jobs, a.timeout)
    print()
    print(report.render(report.load_rows([out])))
    return 0


def cmd_report(a) -> int:
    text = report.render(report.load_rows([Path(p) for p in a.files]))
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"Đã ghi {a.out}")
    else:
        print(text)
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="python -m bench")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    v = sub.add_parser("validate")
    v.add_argument("--task", default="all")
    v.set_defaults(fn=cmd_validate)
    r = sub.add_parser("run")
    r.add_argument("--brain", default="none,v1,v2")
    r.add_argument("--task", default="all")
    r.add_argument("--repeat", type=int, default=1)
    r.add_argument("--model", default="sonnet")
    r.add_argument("--label", default="run")
    r.add_argument("--jobs", type=int, default=2)
    r.add_argument("--timeout", type=int, default=900)
    r.set_defaults(fn=cmd_run)
    rp = sub.add_parser("report")
    rp.add_argument("files", nargs="+")
    rp.add_argument("--out")
    rp.set_defaults(fn=cmd_report)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
