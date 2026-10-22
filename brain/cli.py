"""`brain` command line (spec §5). Phase 2: init · start · gate · verify · end."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from brain import GEN, VERSION, gate, hooks, paths, session, skills, traps, verify
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
    if not a.no_skills:
        res = skills.install(codebase.resolve())
        print("  skills: " + ", ".join(f"{n} ({how})" for n, how in res))
    if r["legacy"]:
        print(f"  ⚠ Codebase còn {', '.join(r['legacy'])}/ của v1/v2: chuyển phần cần giữ vào hub rồi xoá (gate sẽ báo 🔴).")
    return 0


def cmd_hooks(a) -> int:
    p = _project(a)
    if a.action == "install":
        print(f"✅ đã cài hook → {hooks.install(p.codebase)}")
    elif a.action == "migrate":
        from brain.init import remove_legacy_blocks
        blocks = remove_legacy_blocks(p.codebase / "CLAUDE.md")
        n = hooks.remove_foreign(p.codebase)
        hooks.install(p.codebase)
        linked = skills.install(p.codebase)
        print(f"✅ migrate: gỡ block {', '.join(blocks) or 'không có'} · gỡ {n} hook của thế hệ khác · "
              f"cài lại hook v{GEN} · skill: " + ", ".join(f"{k} ({v})" for k, v in linked))
    elif a.action == "remove":
        print(f"đã gỡ hook v{GEN} khỏi {hooks.remove(p.codebase)}")
    else:
        for ev, ok in hooks.status(p.codebase).items():
            print(f"{'✅' if ok else '❌'} {ev}")
    return 0


def _db():
    from brain.metrics import store
    return store.connect(paths.hub() / "_metrics" / "runs.sqlite")


def cmd_ingest(a) -> int:
    from datetime import datetime
    from brain.metrics import claude as mc, omp as mo, store
    now = datetime.now().isoformat(timespec="seconds")
    if a.cwd:  # a project outside v3 (v1/v2 baseline): name + version given explicitly
        codebase, name, version, roles, root, mcfg = Path(a.cwd), a.name or Path(a.cwd).name, a.version or "?", {}, None, {}
    else:
        p = _project(a, session.read_hook_input() if a.hook else None)
        if p is None:
            return 0
        codebase, name, version = p.codebase, p.name, str(a.version or p.config.get("version", GEN))
        roles, root, mcfg = p.config.get("roles", {}), p.root, p.config.get("metrics", {})
    patterns = mo.V2_READ_PATTERNS if (a.patterns or ("v2" if a.cwd else "v3")) == "v2" else mo.V3_READ_PATTERNS
    con = _db()
    total = 0
    if a.source in ("claude", "all"):
        rows, events = mc.scan(codebase, root or codebase, name, version, a.since, mcfg.get("prices"), roles, ingested=now)
        total += store.upsert(con, rows, events)
        print(f"claude: {len(rows)} run ({sum(r['agent'] == 'main' for r in rows)} phiên chính)")
    if a.source in ("omp", "all"):
        sdir = Path(mcfg.get("omp_sessions", "~/.omp/agent/sessions")).expanduser()
        if not sdir.is_dir():
            print(f"omp: không thấy {sdir} (omp chạy trong WSL → chạy lệnh này bằng python3 trong WSL)")
        else:
            cwds = [paths.local(c) for c in mcfg.get("cwds", [])] or [codebase]
            runs = mo.scan(sdir, cwds, a.since or mcfg.get("since"), patterns, float(mcfg.get("live_hours", 24)))
            rows, events = mo.to_rows(runs, name, version, roles, ingested=now)
            total += store.upsert(con, rows, events)
            live = sum(1 for r in runs if r.running)
            copies = len(runs) - live - len(rows)
            print(f"omp: {len(rows)} run subagent · {copies} bản sao file bỏ qua · {live} đang chạy, không tính")
    print(f"→ {total} dòng vào {paths.fwd(paths.hub() / '_metrics' / 'runs.sqlite')}")
    return 0


def cmd_stats(a) -> int:
    from brain.metrics import stats
    con = _db()
    project = a.name or (None if a.all else _project(a).name)
    print(stats.unbacked(con, project) if a.unbacked else stats.injected(con, project) if a.injected
          else stats.report(con, a.by, project, a.since, a.source))
    return 0


def cmd_brief_lint(a) -> int:
    from brain.metrics import omp as mo, omp_parse as op
    if a.hook:
        hook = session.read_hook_input()
        text = str((hook.get("tool_input") or {}).get("prompt", ""))
    else:
        text = sys.stdin.read() if a.file == "-" else Path(a.file).read_text(encoding="utf-8")
    missing, rec, found = op.lint_brief(text, {"brief": mo.BRIEF})
    if a.hook:
        if missing:
            msg = (f"⚠️ brain brief-lint: brief subagent thiếu mục {', '.join(missing)} "
                   "(Mục tiêu · Không làm · Checklist · Đầu ra · Ngân sách). Subagent không kế thừa context của bạn; "
                   "thêm các mục này nếu việc không tầm thường.")
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": msg}},
                             ensure_ascii=False))
        return 0
    for label, keys, bad in (("bắt buộc", mo.BRIEF["required"], "❌"), ("khuyến nghị", mo.BRIEF["recommended"], "⚠")):
        for k, syns in keys.items():
            print(f"{'✅' if k in found else bad} {k} ({label}): " + (f"`{found[k]}`" if k in found else "thiếu — một trong: " + " | ".join(syns)))
    return 1 if missing else 0


def cmd_clean(a) -> int:
    from brain import clean
    p = _project(a)
    if a.action == "backup":
        d = clean.backup(p, a.reason or "")
        print(f"✅ backup → {paths.fwd(d)}")
    elif a.action == "verify-backup":
        r = clean.verify_backup(p, Path(a.args[0]))
        print(f"backup nguyên vẹn: {'✅' if not r['corrupt'] else '❌ ' + ', '.join(r['corrupt'])}")
        for k in ("same", "changed", "retired", "missing"):
            print(f"- {k}: {len(r[k])}" + ("".join(f"\n    {x}" for x in r[k]) if k != "same" else ""))
        return 2 if r["corrupt"] else (1 if r["missing"] else 0)
    elif a.action == "diff-facts":
        old, new = Path(a.args[0]), Path(a.args[1])
        r = clean.diff_facts(old, new, [p.root, clean.archive_dir(p)])
        print(f"fact bản cũ {r['facts_old']} · rút đi {r['lost']} (có ở nơi khác {len(r['kept_elsewhere'])} · "
              f"**mất hẳn {len(r['gone'])}**)")
        for tok, kind in list(r["gone"].items())[:60]:
            print(f"  - [{kind}] `{tok}`")
        if r["gone"]:
            print("→ đưa phần mất hẳn vào chỗ khác (TRAPS / decisions / journal) hoặc xin user duyệt bỏ, rồi mới thay bản cũ.")
        return 1 if r["gone"] else 0
    elif a.action == "retire":
        for line in clean.retire(p, a.args, a.reason or "không ghi lý do", a.dry_run):
            print(line)
    return 0


def cmd_promote(a) -> int:
    from brain import clean
    p = _project(a)
    r = clean.promote(p, a.min_days)
    print(f"# promote — {p.name}\n")
    print(f"## Trap gặp ≥ {a.min_days} ngày, chưa có enforcer → lên bậc 3 (skill `root-fix`)")
    print("\n".join(f"- {t.id} {t.title} · seen {', '.join(t.seen)}" for t in r["ready"]) or "- (không có)")
    print("\n## Trap trùng ở project khác → cân nhắc chuyển lên `_global/traps.md`")
    print("\n".join(f"- {t.id} {t.title} · cũng có ở {', '.join(o)}" for t, o in r["shared"]) or "- (không có)")
    return 0


def cmd_index(a) -> int:
    from brain.recall import code, history
    p = _project(a, session.read_hook_input() if getattr(a, "hook", False) else None)
    if p is None:
        return 0
    h = history.build(p, a.full)
    c = code.build(p, a.full)
    if not getattr(a, "hook", False):
        print(f"history: {h['total']} đơn vị ({h['files']} file đổi, {h['commits']} commit mới) · "
              f"code: {c['files']} file ({c['changed']} đổi), {c['defs']} định nghĩa")
    return 0


def cmd_context(a) -> int:
    from brain.recall import surface
    if a.hook:
        hook = session.read_hook_input()
        p = _project(a, hook)
        if p is None:
            return 0
        text = surface.context_for_tool(p, hook)
        if text:
            print(surface.hook_json("PreToolUse", text))
        return 0
    p = _project(a)
    from brain.traps import _rel
    rel = _rel(p, a.path)
    print(surface.file_context(p, rel, surface.limits(p)["file"]) or f"(không có context cho {rel})")
    return 0


def cmd_recall(a) -> int:
    from brain.recall import history, surface
    if a.hook:
        hook = session.read_hook_input()
        p = _project(a, hook)
        if p is None:
            return 0
        text = surface.context_for_prompt(p, hook)
        if text:
            print(surface.hook_json("UserPromptSubmit", text))
        return 0
    p = _project(a)
    hits = history.search(p, a.query, a.kind, a.file, a.limit)
    if not hits:
        print("(không có kết quả — `brain index` đã chạy chưa?)")
    for h in hits:
        body = " ".join(h.text.split())
        print(f"- [{h.kind} {h.ref} {h.date}] {body[:260]}" + (f"  · file: {', '.join(h.files[:4])}" if h.files else ""))
    return 0


def cmd_graph(a) -> int:
    from brain.recall import code
    p = _project(a)
    if a.what == "uses":
        refs = code.uses(p, a.target)
        print(f"{a.target}: {len(refs)} chỗ dùng" + (" (gồm alias)" if refs else ""))
        for r in refs:
            print(f"  {r.path}:{r.line}  [{r.kind}]")
    elif a.what == "defines":
        for r in code.defines(p, a.target):
            print(f"  {r.path}:{r.line}")
    elif a.what == "dependents":
        print("\n".join(f"  {x}" for x in code.dependents(p, a.target)) or "  (không có)")
    else:
        print("\n".join(f"  {x}" for x in code.deps(p, a.target)) or "  (không có)")
    return 0


def cmd_wiki(a) -> int:
    from brain.recall import wiki
    if a.what == "add":
        if not a.args:
            raise SystemExit("brain wiki add <thư mục wiki> [--name tên]")
        path = Path(a.args[0])
        print(f"Đã ghi {wiki.add(path, a.name or path.resolve().name)}")
        print(f"Index: {wiki.build()['pages']} trang")
    elif a.what == "index":
        r = wiki.build(full=a.full)
        print(f"wiki: {r['pages']} trang · {r['changed']} cập nhật · {r['removed']} xoá → {paths.fwd(wiki.db_path())}")
    elif a.what == "search":
        if not wiki.wikis():
            print("Chưa có wiki nào: `brain wiki add <thư mục>`.")
            return 1
        hits = wiki.search(a.args, k=a.limit, wiki=a.name)
        if not hits:
            print("(không trang nào khớp — thử cách diễn đạt khác, tiếng Anh/Việt, hoặc `brain wiki map`)")
        print("\n".join(wiki.format_hit(h, i) for i, h in enumerate(hits, 1)))
    elif a.what == "map":
        if not wiki.wikis():
            print("Chưa có wiki nào: `brain wiki add <thư mục>`.")
            return 1
        lines = wiki.catalog(prefix=a.args[0] if a.args else None, tag=a.tag, wiki=a.name)
        print("\n".join(lines) or "(trống)")
    elif a.what == "related":
        if not a.args:
            raise SystemExit("brain wiki related <trang, vd concepts/memory-system>")
        r = wiki.related(a.args[0])
        if not r:
            print("(không thấy trang)")
            return 1
        print(f"{r['page']['title']} — {r['page']['file']}")
        for label, rows in (("Trỏ tới", r["out"]), ("Được trỏ từ", r["back"]), ("Cùng ≥2 tag", r["tags"])):
            print(f"{label}: " + (", ".join(f"`{x['rel']}`" for x in rows) or "—"))
    else:
        s = wiki.stats()
        print(f"wiki: {s['wikis']} nguồn {s.get('names', [])} · {s['pages']} trang · config {paths.fwd(wiki.config_path())}")
    return 0


def cmd_skills(a) -> int:
    codebase = None if a.global_ else _project(a).codebase
    for name, how in skills.install(codebase, global_=a.global_, only=a.only):
        print(f"  {name}: {how}")
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
    ap = argparse.ArgumentParser(prog="brain", description=f"Second Brain v{GEN} ({VERSION}) · hub {paths.fwd(paths.hub())}")
    ap.add_argument("--project", help="tên project (mặc định: suy từ cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="tạo brain cho một codebase")
    s.add_argument("--name")
    s.add_argument("--path", help="codebase (mặc định: cwd)")
    s.add_argument("--no-hooks", action="store_true", help="không cài hook Claude Code")
    s.add_argument("--no-skills", action="store_true", help="không link skill lớp thực thi vào .claude/skills")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("skills", help="link skill lớp thực thi (work, explain, recall, tdd, cross-review, root-fix, decision-log)")
    s.add_argument("action", choices=["install"], nargs="?", default="install")
    s.add_argument("--global", dest="global_", action="store_true", help="vào ~/.claude/skills thay vì codebase")
    s.add_argument("--only", nargs="+", help="chỉ các skill này (vd: --global --only wiki)")
    s.set_defaults(fn=cmd_skills)

    s = sub.add_parser("hooks", help="cài / gỡ / xem hook Claude Code của project")
    s.add_argument("action", choices=["install", "remove", "status", "migrate"], nargs="?", default="status")
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

    s = sub.add_parser("ingest", help="đọc transcript Claude Code / omp vào _metrics/runs.sqlite")
    s.add_argument("source", choices=["claude", "omp", "all"], nargs="?", default="all")
    s.add_argument("--since", help="YYYY-MM-DD")
    s.add_argument("--cwd", help="codebase ngoài v3 (đo v1/v2 để so); cần --name, --version")
    s.add_argument("--name")
    s.add_argument("--version", help="nhãn brain_version, vd 2")
    s.add_argument("--patterns", choices=["v2", "v3"], help="mẫu đường dẫn memory để tính read_*")
    s.add_argument("--hook", action="store_true", help="SessionEnd hook: project từ JSON stdin, im lặng nếu không có")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("stats", help="số đo thực tế từ runs.sqlite")
    s.add_argument("--by", choices=["agent", "version", "ticket", "project"], default="agent")
    s.add_argument("--since")
    s.add_argument("--source", choices=["claude", "omp"])
    s.add_argument("--name", help="project (mặc định: project của cwd)")
    s.add_argument("--all", action="store_true", help="mọi project")
    s.add_argument("--unbacked", action="store_true", help="liệt kê claim không có lệnh chứng minh")
    s.add_argument("--injected", action="store_true", help="liệt kê từng mục Recall đã tiêm (từ sổ ghi)")
    s.set_defaults(fn=cmd_stats)

    s = sub.add_parser("brief-lint", help="kiểm brief subagent đủ mục (PreToolUse Agent hook)")
    s.add_argument("file", nargs="?", default="-")
    s.add_argument("--hook", action="store_true")
    s.set_defaults(fn=cmd_brief_lint)

    s = sub.add_parser("clean", help="backup · verify-backup DIR · diff-facts OLD NEW · retire FILE… (port clean-memory v2)")
    s.add_argument("action", choices=["backup", "verify-backup", "diff-facts", "retire"])
    s.add_argument("args", nargs="*")
    s.add_argument("--reason")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_clean)

    s = sub.add_parser("promote", help="trap đủ điều kiện lên bậc 3 / lên _global")
    s.add_argument("--min-days", type=int, default=2)
    s.set_defaults(fn=cmd_promote)

    s = sub.add_parser("index", help="dựng / cập nhật index lịch sử + code graph (.index/)")
    s.add_argument("--full", action="store_true", help="dựng lại từ đầu")
    s.add_argument("--hook", action="store_true")
    s.set_defaults(fn=cmd_index)

    s = sub.add_parser("context", help="xem trước file context mà hook sẽ tiêm khi Read/Edit file này")
    s.add_argument("path", nargs="?", default="")
    s.add_argument("--hook", action="store_true", help="PreToolUse: trap + file context + cảnh báo đổi tên")
    s.set_defaults(fn=cmd_context)

    s = sub.add_parser("recall", help="tìm trong lịch sử: journal, quyết định, archive, commit")
    s.add_argument("query", nargs="?", default="")
    s.add_argument("--hook", action="store_true", help="UserPromptSubmit: trap kw + lịch sử liên quan tới prompt")
    s.add_argument("--prompt", action="store_true", help="(giữ cho tương thích; --hook đã đọc prompt)")
    s.add_argument("--kind", choices=["journal", "decision", "trap", "work", "archive", "commit"])
    s.add_argument("--file", help="ưu tiên mục nhắc tới file này")
    s.add_argument("--limit", type=int, default=5)
    s.set_defaults(fn=cmd_recall)

    s = sub.add_parser("graph", help="code graph: uses / defines / dependents / deps")
    s.add_argument("what", choices=["uses", "defines", "dependents", "deps"])
    s.add_argument("target")
    s.set_defaults(fn=cmd_graph)

    s = sub.add_parser("wiki", help="tra wiki (v4.1): search nhiều cách hỏi · map · related · index · add · status")
    s.add_argument("what", choices=["search", "map", "related", "index", "add", "status"])
    s.add_argument("args", nargs="*", help="search: các cách diễn đạt; map: thư mục con; related: trang; add: thư mục")
    s.add_argument("--name", help="chỉ wiki này (add: tên wiki)")
    s.add_argument("--tag", help="map: lọc theo tag")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--full", action="store_true", help="index: dựng lại từ đầu")
    s.set_defaults(fn=cmd_wiki)

    s = sub.add_parser("version")
    s.set_defaults(fn=lambda _a: print(f"brain {VERSION}") or 0)

    a = ap.parse_args(argv)
    return a.fn(a)
