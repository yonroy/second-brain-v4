import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

from brain import cli, gate, paths, session, verify
from brain.init import init
from brain.project import ProjectNotFound, find_project

TODAY = date.today().isoformat()


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.hub = self.tmp / "hub"
        self.code = self.tmp / "code" / "demo"
        self.code.mkdir(parents=True)
        (self.code / "app.py").write_text("print('hi')\n", encoding="utf-8")
        git(self.code, "init", "-q")
        git(self.code, "add", "-A")
        git(self.code, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
        self.env = mock.patch.dict(os.environ, {"SECOND_BRAIN_V3_ROOT": str(self.hub)})
        self.env.start()
        self.result = init(None, self.code, self.hub)
        self.p = find_project("demo")

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        f = self.p.file(rel)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    def run_cli(self, *argv, stdin=None, cwd=None):
        buf = io.StringIO()
        old = os.getcwd()
        os.chdir(cwd or self.code)
        try:
            with redirect_stdout(buf), mock.patch.object(sys, "stdin", io.StringIO(stdin) if stdin is not None else sys.stdin):
                rc = cli.main(list(argv))
        finally:
            os.chdir(old)
        return rc, buf.getvalue()


class InitTests(Base):
    def test_structure(self):
        root = self.hub / "_projects" / "demo"
        for rel in ("brain.toml", "AGENTS.md", "CONTEXT.md", "TRAPS.md", "PROOF.md", "decisions/INDEX.md",
                    "work/_template.md", "journal"):
            self.assertTrue((root / rel).exists(), rel)
        for d in ("_global", "_metrics", "_archive"):
            self.assertTrue((self.hub / d).is_dir())
        self.assertLessEqual(len((root / "AGENTS.md").read_text(encoding="utf-8").splitlines()), 60)
        claude = (self.code / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("SECOND-BRAIN-V3:START", claude)
        self.assertIn(paths.fwd(root), claude)
        self.assertNotIn("{{", (root / "CONTEXT.md").read_text(encoding="utf-8"))

    def test_idempotent_and_keeps_edits(self):
        self.write("CONTEXT.md", "# edited\n")
        (self.code / "CLAUDE.md").write_text("# mine\n\nnotes\n", encoding="utf-8")
        r = init(None, self.code, self.hub)
        self.assertEqual(r["created"], [])
        self.assertEqual(r["claude_md"], "appended")
        self.assertEqual(self.p.read("CONTEXT.md"), "# edited\n")
        r = init(None, self.code, self.hub)
        self.assertEqual(r["claude_md"], "unchanged")
        self.assertIn("notes", (self.code / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_rejects_other_codebase_same_name(self):
        other = self.tmp / "elsewhere" / "demo"
        other.mkdir(parents=True)
        with self.assertRaises(SystemExit):
            init(None, other, self.hub)

    def test_fresh_project_gate_clean(self):
        self.assertEqual(gate.check(self.p), [])


class ResolveTests(Base):
    def test_cwd_inside_codebase_or_project(self):
        sub = self.code / "pkg"
        sub.mkdir()
        self.assertEqual(find_project(cwd=sub).name, "demo")
        self.assertEqual(find_project(cwd=self.p.root / "work").name, "demo")
        with self.assertRaises(ProjectNotFound):
            find_project(cwd=self.tmp)

    def test_wsl_path_mapping(self):
        self.assertEqual(paths.fwd("/mnt/d/SecondBrainV3/x"), "D:/SecondBrainV3/x")
        self.assertEqual(paths.fwd("D:\\a\\b"), "D:/a/b")
        if os.name != "nt":
            self.assertEqual(str(paths.local("D:/a/b")), "/mnt/d/a/b")


class GateTests(Base):
    def levels(self):
        return [(f.level, f.what) for f in gate.check(self.p)]

    def test_untagged_and_stale(self):
        self.write("CONTEXT.md", "# c\n## Môi trường\n- no tag here\n- old fact [2020-01-01|user]\n"
                                 "## Đang làm\n- stuck task [2020-01-01|S-001]\n- fresh [" + TODAY + "|user]\n")
        lv = self.levels()
        self.assertTrue(any(l == gate.YELLOW and "không có [ngày|nguồn]" in w for l, w in lv))
        self.assertTrue(any(l == gate.YELLOW and "fact quá" in w for l, w in lv))
        self.assertTrue(any(l == gate.RED and "Đang làm" in w for l, w in lv))

    def test_size_limits(self):
        self.write("CONTEXT.md", "# c\n" + "x\n" * 130 + "y" * 500 + "\n")
        reds = [w for l, w in self.levels() if l == gate.RED]
        self.assertTrue(any("dòng >" in w for w in reds))
        self.assertTrue(any("ký tự" in w for w in reds))

    def test_forged_proof_flagged(self):
        self.write("PROOF.md", f"| ID | Behavior | cmd | Kết quả |\n|---|---|---|---|\n"
                               f"| B-001 | runs | `python app.py` | ✅ {TODAY} abc1234 |\n")
        self.assertTrue(any(l == gate.RED and "verify log" in w for l, w in self.levels()))

    def test_story_rules_and_dup_ids(self):
        self.write("work/S-001-a.md", "---\nid: S-001\ntype: high-risk\nstatus: done\nproof: [B-009]\n---\n")
        self.write("work/S-001-b.md", "---\nid: S-001\nstatus: wip\n---\n")
        reds = [w for l, w in self.levels() if l == gate.RED]
        for frag in ("ID trùng trong work", "status 'wip'", "high-risk nhưng chưa có ADR", "done nhưng proof chưa ✅"):
            self.assertTrue(any(frag in w for w in reds), frag)

    def test_legacy_memory_in_codebase(self):
        (self.code / "MEMORY").mkdir()
        self.assertTrue(any("bản memory cũ" in w for _, w in self.levels()))

    def test_strict_exit_code(self):
        (self.code / "HARNESS").mkdir()
        rc, out = self.run_cli("gate", "--strict")
        self.assertEqual(rc, 1)
        self.assertIn("🔴1", out)


class VerifyTests(Base):
    def setUp(self):
        super().setUp()
        py = Path(sys.executable).as_posix()  # WSL has only python3; PROOF cmds run in the host shell
        self.write("PROOF.md", "| ID | Behavior | cmd | Kết quả |\n|---|---|---|---|\n"
                               f"| B-001 | app runs | `{py} app.py` |  |\n"
                               f"| B-002 | fails | `{py} -c \"raise SystemExit(3)\"` |  |\n")

    def test_stamps_and_gate_accepts(self):
        res = verify.run(self.p, ["B-001", "B-002"])
        self.assertEqual([r["ok"] for r in res], [True, False])
        rows = {r.id: r for r in self.p.proofs()}
        self.assertTrue(rows["B-001"].result.startswith(f"✅ {TODAY} "))
        self.assertTrue(rows["B-002"].result.startswith("❌"))
        self.assertEqual([f for f in gate.check(self.p) if "verify log" in f.what], [])

    def test_editing_cmd_after_verify_invalidates(self):
        verify.run(self.p, ["B-001"])
        text = self.p.read("PROOF.md").replace(" app.py`", " -c \"pass\"`")
        self.write("PROOF.md", text)
        self.assertTrue(any("verify log" in f.what for f in gate.check(self.p)))

    def test_unknown_id(self):
        with self.assertRaises(SystemExit):
            verify.run(self.p, ["B-404"])


class SessionTests(Base):
    def hook(self, **kw):
        return json.dumps({"session_id": "sess-12345678", **kw})

    def test_start_prints_context_decisions_traps(self):
        self.write("decisions/INDEX.md", "| ID | Ngày | Tóm tắt | Trạng thái |\n|---|---|---|---|\n"
                                         "| ADR-004 | 2026-09-28 | Tiền là int, half-up | active |\n"
                                         "| ADR-001 | 2026-01-01 | Cũ | superseded by ADR-004 |\n")
        self.write("TRAPS.md", "## M-007 Retry ghi trùng\ntrigger: src/store.py\nseen: 2026-10-11\nfix: upsert\n")
        rc, out = self.run_cli("start", "--hook", stdin=self.hook())
        self.assertEqual(rc, 0)
        self.assertIn("ADR-004", out)
        self.assertNotIn("ADR-001", out)
        self.assertIn("M-007 Retry ghi trùng → upsert", out)
        self.assertIn("Codebase ở", out)
        self.assertTrue(self.p.file(".state/sess-12345678.json").exists())

    def test_hook_outside_project_is_silent(self):
        rc, out = self.run_cli("start", "--hook", stdin=self.hook(), cwd=self.tmp)
        self.assertEqual((rc, out), (0, ""))

    def test_stop_blocks_once_when_code_changed_without_memory(self):
        self.run_cli("start", "--hook", stdin=self.hook())
        (self.code / "app.py").write_text("print('changed')\n", encoding="utf-8")
        rc, out = self.run_cli("end", "--check", "--hook", stdin=self.hook())
        self.assertEqual(json.loads(out)["decision"], "block")
        rc, out = self.run_cli("end", "--check", "--hook", stdin=self.hook())
        self.assertEqual(out, "", "second stop must not block again")
        self.assertTrue(any(self.p.file("journal").glob("*-sess-123.md")))

    def test_stop_allows_when_memory_updated(self):
        self.run_cli("start", "--hook", stdin=self.hook())
        (self.code / "app.py").write_text("print('changed')\n", encoding="utf-8")
        time.sleep(0.05)
        self.write("CONTEXT.md", self.p.read("CONTEXT.md") + f"- đổi app [{TODAY}|file:app.py]\n")
        rc, out = self.run_cli("end", "--check", "--hook", stdin=self.hook())
        self.assertEqual(out, "")

    def test_journal_digest_from_transcript(self):
        tr = self.tmp / "t.jsonl"
        events = [
            {"type": "user", "message": {"role": "user", "content": "Sửa bug ghi trùng khi retry"}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": str(self.code / "app.py")}},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": str(self.p.file("TRAPS.md"))}},
                {"type": "tool_use", "name": "PowerShell", "input": {"command": "python -m unittest discover"}}]}},
        ]
        tr.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
        self.run_cli("start", "--hook", stdin=self.hook())
        self.run_cli("end", "--hook", stdin=self.hook(transcript_path=str(tr)))
        j = next(self.p.file("journal").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("Mục tiêu: Sửa bug ghi trùng khi retry", j)
        self.assertIn("app.py", j)
        self.assertIn("Memory đã sửa: TRAPS.md", j)
        self.assertIn("python -m unittest discover", j)
        self.assertLessEqual(len(j.splitlines()), 15)


if __name__ == "__main__":
    unittest.main()
