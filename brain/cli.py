"""`brain` command line (spec §5). Phase 2: init · start · gate · verify · end."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from brain import VERSION, gate, hooks, paths, session, traps, verify
from brain.init import init
from brain.project import ProjectNotFound, find_project


def _project(a, hook: dict | None = None):
    cwd = Path(paths.local(hook["cwd"])) if hook and hook.get("cwd") else None
    try:
        return find_project(a.project, cwd=cwd)
    except ProjectNotFound as e:
        if getattr(a, "hook", False):
            return None  # a hook in a repo without a v3 brain stays silent and never breaks the session
        raise SystemExit(f"❌ {e}")


def cmd_init(a) -> int:
    codebase = Path(a.path or Path.cwd())
    r = init(a.name, codebase)
    print(f"✅ brain init → {r['project']}")
    for f in r["created"]:
        print(f"  + {f}")
    print(f"  CLAUDE.md: {r['claude_md']}")
    if not a.no_hooks:
        print(f"  hooks Claude Code: {hooks.install(codebase.resolve())}")
    if r["legacy"]:
        print(f"  ⚠ Codebase còn {', '.join(r['legacy'])}/ của v1/v2: chuyển phần cần giữ vào hub rồi xoá (gate sẽ báo 🔴).")
    return 0


def cmd_hooks(a) -> int:
    p = _project(a)
    if a.action == "install":
        print(f"✅ đã cài hook → {hooks.install(p.codebase)}")
    elif a.action == "remove":
        print(f"đã gỡ hook v3 khỏi {hooks.remove(p.codebase)}")
    else:
        for ev, ok in hooks.status(p.codebase).items():
            print(f"{'✅' if ok else '❌'} {ev}")
    return 0


def cmd_trap_check(a) -> int:
    hook = session.read_hook_input() if a.hook else {}
    if not a.hook:  # manual: brain trap-check <path-or-text>
        hook = {"tool_input": {"file_path": a.target, "command": a.target}, "prompt": a.target}
    p = _project(a, hook)
    if p is None:
        return 0
    out = traps.check(p, hook, prompt_mode=a.prompt)
    if out:
        print(out)
    elif not a.hook:
        print("(không có trap khớp)")
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
    p = _project(a, hook)
    if p is None:
        return 0
    print(session.start_text(p, hook))
    return 0


def cmd_end(a) -> int:
    hook = session.read_hook_input() if a.hook else {}
    p = _project(a, hook)
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
    s.add_argument("--no-hooks", action="store_true", help="không cài hook Claude Code")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("hooks", help="cài / gỡ / xem hook Claude Code của project")
    s.add_argument("action", choices=["install", "remove", "status"], nargs="?", default="status")
    s.set_defaults(fn=cmd_hooks)

    s = sub.add_parser("trap-check", help="in trap khớp với file / lệnh / prompt (PreToolUse hook)")
    s.add_argument("target", nargs="?", default="", help="đường dẫn hoặc đoạn lệnh (khi chạy tay)")
    s.add_argument("--hook", action="store_true")
    s.add_argument("--prompt", action="store_true", help="hook UserPromptSubmit: khớp từ khoá trong prompt")
    s.set_defaults(fn=cmd_trap_check)

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
