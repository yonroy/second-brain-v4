"""`brain` command line (spec §5). Phase 2: init · start · gate · verify · end."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from brain import VERSION, gate, paths, session, verify
from brain.init import init
from brain.project import ProjectNotFound, find_project


def _project(a):
    try:
        return find_project(a.project)
    except ProjectNotFound as e:
        if getattr(a, "quiet_missing", False):
            return None
        raise SystemExit(f"❌ {e}")


def cmd_init(a) -> int:
    r = init(a.name, Path(a.path or Path.cwd()))
    print(f"✅ brain init → {r['project']}")
    for f in r["created"]:
        print(f"  + {f}")
    print(f"  CLAUDE.md: {r['claude_md']}")
    if r["legacy"]:
        print(f"  ⚠ Codebase còn {', '.join(r['legacy'])}/ của v1/v2: chuyển phần cần giữ vào hub rồi xoá (gate sẽ báo 🔴).")
    return 0


def cmd_gate(a) -> int:
    p = _project(a)
    findings = gate.check(p)
    print(gate.summary(p, findings))
    for f in findings:
        print(f"  {f}")
    return 1 if a.strict and any(f.level == gate.RED for f in findings) else 0


def cmd_start(a) -> int:
    hook = session.read_hook_input() if a.hook else {}
    a.quiet_missing = a.hook
    p = _project(a)
    if p is None:
        return 0  # hook in a repo that has no v3 brain: say nothing, never break the session
    print(session.start_text(p, hook))
    return 0


def cmd_end(a) -> int:
    hook = session.read_hook_input() if a.hook else {}
    a.quiet_missing = a.hook
    p = _project(a)
    if p is None:
        return 0
    r = session.end(p, hook, a.check)
    if "block" in r:
        print(json.dumps({"decision": "block", "reason": r["block"]}, ensure_ascii=False))
    elif not a.hook:
        print(f"📝 journal → {r['journal']}")
    return 0


def cmd_verify(a) -> int:
    p = _project(a)
    results = verify.run(p, a.ids or None, a.timeout)
    if not results:
        print("PROOF.md chưa có dòng nào.")
    bad = 0
    for r in results:
        if r.get("skipped"):
            print(f"⚠ {r['id']}: {r['skipped']}")
            bad += 1
            continue
        print(f"{'✅' if r['ok'] else '❌'} {r['id']}  rc={r['rc']}  {r['seconds']}s  @{r['commit']}")
        if not r["ok"]:
            bad += 1
            print("   " + r["tail"].strip().replace("\n", "\n   ")[-500:])
    return 1 if bad else 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="brain", description=f"Second Brain v3 ({VERSION}) · hub {paths.fwd(paths.hub())}")
    ap.add_argument("--project", help="tên project (mặc định: suy từ cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="tạo brain cho một codebase")
    s.add_argument("--name")
    s.add_argument("--path", help="codebase (mặc định: cwd)")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("gate", help="kiểm sức khoẻ memory")
    s.add_argument("--strict", action="store_true", help="exit 1 khi có 🔴")
    s.set_defaults(fn=cmd_gate)

    s = sub.add_parser("start", help="nạp context đầu phiên (SessionStart hook)")
    s.add_argument("--hook", action="store_true", help="đọc JSON hook từ stdin; im lặng nếu cwd không có brain")
    s.set_defaults(fn=cmd_start)

    s = sub.add_parser("end", help="ghi journal; --check nhắc cập nhật memory (Stop hook)")
    s.add_argument("--check", action="store_true")
    s.add_argument("--hook", action="store_true")
    s.set_defaults(fn=cmd_end)

    s = sub.add_parser("verify", help="chạy lệnh trong PROOF.md, ghi kết quả")
    s.add_argument("ids", nargs="*")
    s.add_argument("--timeout", type=int, default=900)
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("version")
    s.set_defaults(fn=lambda _a: print(f"brain {VERSION}") or 0)

    a = ap.parse_args(argv)
    return a.fn(a)
