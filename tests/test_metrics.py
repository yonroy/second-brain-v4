import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from brain import clean, hooks
from brain.init import init
from brain.metrics import claude as mc, omp as mo, store
from brain.metrics import omp_parse as op
from brain.project import find_project


def jl(path: Path, events: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8")
    return path


def omp_session(cwd: str, sid: str, parent: Path, minutes: int = 10, read: str = "TRAPS.md") -> list[dict]:
    t0, t1 = "2026-10-20T10:00:00Z", f"2026-10-20T10:{minutes:02d}:00Z"
    return [
        {"type": "session", "id": sid, "parentSession": str(parent), "timestamp": t0, "cwd": cwd},
        {"type": "session_init", "systemPrompt": "\n§ Context\n# Mục tiêu\nx\n# Không làm\ny\n", "task": "do it"},
        {"type": "message", "timestamp": t0, "message": {"role": "assistant", "usage": {"totalTokens": 1000, "cost": {"total": 0.5}},
         "content": [{"type": "toolCall", "name": "read", "arguments": {"path": f"/hub/_projects/p/{read}"}},
                     {"type": "toolCall", "name": "bash", "arguments": {"command": "python -m unittest"}}]}},
        {"type": "message", "timestamp": t0, "message": {"role": "toolResult", "toolName": "bash", "isError": True,
                                                         "content": [{"type": "text", "text": "Ran 3 tests OK"}]}},
        {"type": "message", "timestamp": t1, "message": {"role": "assistant", "usage": {"totalTokens": 500, "cost": {"total": 0.25}},
         "content": [{"type": "text", "text": "Đã chạy `python -m unittest` → OK"},
                     {"type": "toolCall", "name": "yield", "arguments": {"data": "Đã chạy `python -m unittest` → OK"}}]}},
        {"type": "message", "timestamp": t1, "message": {"role": "toolResult", "toolName": "yield",
                                                         "content": [{"type": "text", "text": "Result submitted"}]}},
    ]


class OmpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.code = self.tmp / "code"
        self.code.mkdir()
        self.sessions = self.tmp / "sessions"
        parent = jl(self.sessions / "p1" / "main.jsonl",
                    [{"type": "message", "message": {"content": [{"type": "toolCall", "name": "task", "arguments":
                     {"tasks": [{"agent": "data-engineer", "name": "Worker"}]}}]}}])
        events = omp_session(str(self.code), "sub-1", parent)
        jl(self.sessions / "p1" / "Worker.jsonl", events)
        jl(self.sessions / "p2-resumed" / "Worker.jsonl", events)  # omp copies the subagent file into a later session

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parse_dedupe_and_fields(self):
        runs = mo.scan(self.sessions, [self.code], None, mo.V3_READ_PATTERNS)
        self.assertEqual(len(runs), 2, "both file copies are parsed, like v2")
        rows, events = mo.to_rows(runs, "p", "3", {"engineer": ["data-engineer"]})
        self.assertEqual(len(rows), 1, "copies collapse to one run")
        r = rows[0]
        self.assertEqual((r["agent"], r["role"], r["turns"], r["tokens"], r["cost_usd"]), ("data-engineer", "engineer", 2, 1500, 0.75))
        self.assertEqual((r["minutes"], r["yielded"], r["tool_errors"], r["read_traps"]), (10.0, 1, 1, 1))
        self.assertEqual(r["brief_missing"], "checklist,dau_ra,ngan_sach")
        self.assertEqual(r["claims"], 1)
        self.assertEqual(r["unbacked_claims"], 0)

    def test_store_upsert_is_idempotent(self):
        con = store.connect(self.tmp / "runs.sqlite")
        rows, events = mo.to_rows(mo.scan(self.sessions, [self.code], None, mo.V3_READ_PATTERNS), "p", "3")
        store.upsert(con, rows, events)
        store.upsert(con, rows, events)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)

    def test_roles_drive_verdict(self):
        self.assertEqual(op.verdict_of("qa", "LOCAL: PASS", {"tester": ["qa"]}), "PASS")
        self.assertEqual(op.verdict_of("qa", "LOCAL: PASS", {}), "")


class ClaudeTests(unittest.TestCase):
    def test_parse_transcript(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            mem = tmp / "hub" / "_projects" / "demo"
            f = jl(tmp / "s.jsonl", [
                {"type": "user", "timestamp": "2026-10-21T10:00:00Z", "sessionId": "abc", "message": {"content": "fix it"}},
                {"type": "assistant", "timestamp": "2026-10-21T10:01:00Z", "message": {"id": "m1", "model": "claude-sonnet-5",
                 "usage": {"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 5},
                 "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": str(mem / "TRAPS.md")}}]}},
                {"type": "assistant", "timestamp": "2026-10-21T10:01:01Z", "message": {"id": "m1", "model": "claude-sonnet-5",
                 "usage": {"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 5},
                 "content": [{"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "python -m unittest"}}]}},
                {"type": "attachment", "timestamp": "2026-10-21T10:01:02Z", "attachment": {"type": "hook_success",
                 "stdout": "⚠️ brain trap M-007 (khớp src/x.py): …"}},
                {"type": "user", "timestamp": "2026-10-21T10:30:00Z", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "t2", "is_error": True, "content": "Ran 2 tests OK"}]}},
                {"type": "assistant", "timestamp": "2026-10-21T10:31:00Z", "message": {"id": "m2", "model": "claude-sonnet-5",
                 "usage": {"input_tokens": 1, "output_tokens": 1}, "content": [{"type": "text", "text": "Đã chạy `pytest -q` → passed"}]}},
            ])
            r = mc.parse(f, mem, {"claude-sonnet": [3, 15, 3.75, 0.3]})
            self.assertEqual((r["turns"], r["tool_calls"], r["tool_errors"]), (2, 2, 1), "usage counted once per message id")
            self.assertEqual((r["tokens_in"], r["tokens_out"]), (101, 6))
            self.assertEqual(r["minutes"], round((60 + 1 + 1 + 300 + 60) / 60, 1), "idle gap capped at 5 minutes")
            self.assertEqual(r["reads"]["traps"], 1)
            self.assertEqual(r["traps_injected"], 1)
            self.assertEqual(r["cost_usd"], round((11 * 3 + 6 * 15 + 90 * 0.3) / 1e6, 6))
            self.assertEqual(sum(not c.backed for c in r["claims"]), 1, "`pytest` claimed but only unittest ran")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_slug_matches_claude_folder_names(self):
        self.assertEqual(mc.slug("d:\\SecondBrain\\AI Agentic"), "d--SecondBrain-AI-Agentic")
        self.assertEqual(mc.slug("D:/SecondBrain/AI Agentic"), "D--SecondBrain-AI-Agentic")


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.hub = self.tmp / "hub"
        self.code = self.tmp / "demo"
        self.code.mkdir()
        self.env = mock.patch.dict(os.environ, {"SECOND_BRAIN_V3_ROOT": str(self.hub)})
        self.env.start()
        init(None, self.code, self.hub)
        self.p = find_project("demo")

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_backup_verify_retire(self):
        with self.assertRaises(SystemExit):
            clean.retire(self.p, ["work/_template.md"], "test")  # no backup today yet
        d = clean.backup(self.p, "trước khi dọn")
        self.assertEqual(clean.verify_backup(self.p, d)["corrupt"], [])
        clean.retire(self.p, ["work/_template.md"], "test")
        r = clean.verify_backup(self.p, d)
        self.assertIn("work/_template.md", r["retired"])
        self.assertEqual(r["missing"], [])
        self.assertIn("_template.md", (clean.retired_dir(self.p) / "INDEX.md").read_text(encoding="utf-8"))

    def test_diff_facts_finds_lost_facts(self):
        old, new = self.tmp / "old.md", self.tmp / "new.md"
        old.write_text("- dùng `upsert` theo ADR-004, cổng 6543 và commit a1b2c3d\n", encoding="utf-8")
        new.write_text("- dùng `upsert` theo ADR-004\n", encoding="utf-8")
        r = clean.diff_facts(old, new, [self.p.root])
        self.assertEqual(set(r["gone"]), {"6543", "a1b2c3d"})

    def test_promote(self):
        self.p.file("TRAPS.md").write_text("## M-001 pnpm trong WSL xoá node_modules\ntrigger: kw:pnpm\n"
                                           "seen: 2026-10-01, 2026-10-09\nfix: x\nenforce: none\n\n"
                                           "## M-002 Một lần\ntrigger: a\nseen: 2026-10-01\nfix: y\n", encoding="utf-8")
        other = self.tmp / "svc"
        other.mkdir()
        init(None, other, self.hub)
        find_project("svc").file("TRAPS.md").write_text("## M-004 PNPM trong WSL xoá node_modules!\ntrigger: kw:pnpm\n",
                                                        encoding="utf-8")
        r = clean.promote(self.p)
        self.assertEqual([t.id for t in r["ready"]], ["M-001"])
        self.assertEqual([(t.id, o) for t, o in r["shared"]], [("M-001", ["svc:M-004"])])

    def test_agent_hook_registered(self):
        self.assertIn("Agent|Task", [e["matcher"] for e in hooks.desired()["PreToolUse"]])


if __name__ == "__main__":
    unittest.main()
