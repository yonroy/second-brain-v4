import json
import shutil
import tempfile
import unittest
from pathlib import Path

from bench import report, score
from bench.brains import get_brain
from bench.tasks import all_tasks, select


def _assistant(*tool_uses):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": n, "input": i} for n, i in tool_uses]}}


def _result(text, cost=0.5):
    return {"type": "result", "subtype": "success", "is_error": False, "result": text, "total_cost_usd": cost,
            "duration_ms": 12000, "num_turns": 4,
            "usage": {"input_tokens": 10, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 50,
                      "output_tokens": 20}}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.task = select("T07")[0]
        self.seed = self.task.seed()
        self.work, self.hub = self.tmp / "work", self.tmp / "hub"
        shutil.copytree(self.task.repo, self.work)
        self.hub.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_none_has_no_memory(self):
        b = get_brain("none")
        b.setup(self.work, self.hub, self.seed)
        self.assertEqual(b.memory_paths(self.work, self.hub, self.seed), [])
        self.assertFalse((self.work / "CLAUDE.md").exists())

    def test_v1_renders_trap_and_pointer(self):
        b = get_brain("v1")
        env = b.setup(self.work, self.hub, self.seed)
        mem = self.hub / "_projects" / "orders-etl" / "MEMORY"
        self.assertIn("upsert", (mem / "MISTAKES.md").read_text(encoding="utf-8"))
        self.assertIn("MEMORY/CONTEXT.md", (self.work / "CLAUDE.md").read_text(encoding="utf-8"))
        self.assertEqual(env.add_dirs, [self.hub])

    def test_v2_runs_real_init_and_seeds(self):
        b = get_brain("v2")
        env = b.setup(self.work, self.hub, self.seed)
        proj = self.hub / "_projects" / "orders-etl"
        self.assertTrue((proj / "AGENTS.md").exists())
        self.assertTrue((proj / "HARNESS" / "TOOL_REGISTRY.md").exists(), "L1 artifact")
        self.assertIn("SECOND-BRAIN-V2:START", (self.work / "CLAUDE.md").read_text(encoding="utf-8"))
        self.assertIn("upsert", (proj / "MEMORY" / "CONTEXT.md").read_text(encoding="utf-8"))
        self.assertTrue(any((proj / "HARNESS" / "decisions").glob("ADR-001-*.md")))
        self.assertEqual(env.extra_env["SECOND_BRAIN_ROOT"], str(self.hub).replace("\\", "/"))


class ScoreTests(unittest.TestCase):
    def test_metrics_from_events(self):
        events = [_assistant(("Read", {"file_path": "D:\\x\\hub\\_projects\\p\\MEMORY\\MISTAKES.md"}),
                             ("Bash", {"command": "python -m unittest discover -s tests -t ."})),
                  _result("Tất cả test pass.")]
        before = {"m": ("a", "old line")}
        after = {"m": ("b", "old line\n- dùng upsert theo order_id")}
        row = score.score_run(events, ["d:/x/hub"], before, after, ["upsert"], has_memory=True)
        self.assertTrue(row["read_memory"])
        self.assertTrue(row["memory_updated"])
        self.assertTrue(row["ran_tests"])
        self.assertFalse(row["claim_unbacked"])
        self.assertEqual(row["tokens_in"], 160)

    def test_powershell_test_run_counts_as_evidence(self):
        row = score.score_run([_assistant(("PowerShell", {"command": "python -m unittest discover -s tests -t ."})),
                               _result("4/4 pass.")], [], {}, {}, [], has_memory=False)
        self.assertTrue(row["ran_tests"])
        self.assertFalse(row["claim_unbacked"])

    def test_unbacked_claim(self):
        row = score.score_run([_assistant(("Edit", {"file_path": "src/a.py"})), _result("Xong, test xanh.")],
                              [], {}, {}, [], has_memory=False)
        self.assertTrue(row["claim_unbacked"])
        self.assertIsNone(row["read_memory"])


class TaskTests(unittest.TestCase):
    def test_eight_tasks_with_seeds(self):
        tasks = all_tasks()
        self.assertEqual([t.id for t in tasks], [f"T0{i}" for i in range(1, 9)])
        for t in tasks:
            self.assertTrue(t.seed().test_cmd)


class ReportTests(unittest.TestCase):
    def test_render_table(self):
        rows = [{"task": "T01", "kind": "trap", "brain": b, "repeat": 1, "model": "sonnet", "pass": p,
                 "cost_usd": 0.4, "duration_s": 30, "tokens_in": 1000, "trap_avoided": p}
                for b, p in (("none", False), ("v2", True))]
        text = report.render(rows)
        self.assertIn("| none | 1 | 0/1 (0%)", text)
        self.assertIn("| T01 | trap | 0/1 | 1/1 |", text)


if __name__ == "__main__":
    unittest.main()
