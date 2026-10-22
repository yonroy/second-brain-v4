import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from bench.brains import get_brain
from bench.tasks import select
from brain.project import Project
from brain.recall import code, history
from brain.recall.text import fts_query, norm, paths_in


def staged(task_id):
    """A v4 bench setup of a task: work repo + hub with history rendered and indexed."""
    tmp = Path(tempfile.mkdtemp())
    t = select(task_id)[0]
    work, hub = tmp / "work", tmp / "hub"
    shutil.copytree(t.repo, work)
    hub.mkdir()
    with mock.patch.dict(os.environ, {"SECOND_BRAIN_V4_ROOT": str(hub)}):
        get_brain("v4").setup(work, hub, t.seed())
    return tmp, Project(hub / "_projects" / t.seed().name)


class TextTests(unittest.TestCase):
    def test_vietnamese_normalisation(self):
        self.assertEqual(norm("Đường phố Hà Nội"), "duong pho ha noi")
        self.assertIn('"duong"', fts_query("đường"))
        self.assertEqual(paths_in("sửa `src/shipping/rules/weight.py` và config/plugins.toml."),
                         ["config/plugins.toml", "src/shipping/rules/weight.py"])


class HistoryTests(unittest.TestCase):
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_journal_lesson_found_among_noise(self):
        self.tmp, p = staged("T17")
        hits = history.search(p, "cache get_price lru_cache")
        self.assertEqual(hits[0].kind, "journal")
        self.assertIn("15 giây", hits[0].text)

    def test_commit_reason_for_file(self):
        self.tmp, p = staged("T19")
        about = history.about_file(p, "src/phone.py")
        self.assertEqual(about[0].kind, "commit")
        self.assertIn("Incident #12", about[0].text)

    def test_archived_fact_and_vietnamese_query(self):
        self.tmp, p = staged("T23")
        hits = history.search(p, "fetch_order lỗi 410 Gone đơn hàng v1")
        self.assertTrue(any(h.kind == "archive" and "X-Version: 2" in h.text for h in hits), [h.text for h in hits])

    def test_full_rebuild_is_identical_and_incremental_touches_one_file(self):
        self.tmp, p = staged("T22")
        dump = lambda: sorted(sqlite3.connect(history.db_path(p)).execute(  # noqa: E731
            "SELECT kind, ref, date, path, files, text FROM units").fetchall())
        first = dump()
        history.build(p, full=True)
        self.assertEqual(dump(), first)
        j = next(p.file("journal").glob("*.md"))
        time.sleep(0.01)
        j.write_text(j.read_text(encoding="utf-8") + "\n- thêm dòng mới về weekly\n", encoding="utf-8")
        st = history.build(p)
        self.assertEqual((st["files"], st["commits"]), (1, 0))


class CodeGraphTests(unittest.TestCase):
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_string_refs_outside_python(self):
        self.tmp, p = staged("T12")
        refs = {(r.path, r.kind) for r in code.uses(p, "handle_order_paid")}
        self.assertIn(("data/schedules.json", "string"), refs)
        self.assertIn(("config/plugins.toml", "string"), refs)
        self.assertEqual([r.path for r in code.defines(p, "handle_order_paid")], ["src/handlers.py"])

    def test_aliases_and_partial(self):
        self.tmp, p = staged("T20")
        files = {r.path for r in code.uses(p, "tax_rate")}
        for f in ("src/cart.py", "src/invoice.py", "src/reports/monthly.py", "src/api/handlers.py", "scripts/backfill.py"):
            self.assertIn(f, files)
        self.assertIn("src/cart.py", code.dependents(p, "src/tax.py"))

    def test_column_name_in_sql_and_json(self):
        self.tmp, p = staged("T21")
        files = {r.path for r in code.uses(p, "cust_name")}
        self.assertTrue({"sql/reports/top_customers.sql", "dashboards/sales.json", "src/schema.py"} <= files, files)


class JsGraphTests(unittest.TestCase):
    """JS/TS regex graph: defs, `@/` tsconfig paths, relative imports, `{ a as b }` aliases, rename warning."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        root = self.tmp / "app"
        files = {
            "tsconfig.json": '{\n  // comment\n  "compilerOptions": {"paths": {"@/*": ["./*"]},},\n}',
            "lib/ai/auto-run.ts": "export function shouldAutoRun(x: number): boolean {\n  return x > 1;\n}\n"
                                  "export const MAX_TURNS = 3;\nexport type RunMode = 'a' | 'b';\n"
                                  "const helper = async (a: string): Promise<void> => {};\n",
            "lib/ai/index.ts": "export { shouldAutoRun as decideAutoRun } from './auto-run';\n",
            "app/api/chat/route.ts": "import { shouldAutoRun } from \"@/lib/ai/auto-run\";\nshouldAutoRun(2);\n",
            "components/chat.tsx": "import { decideAutoRun as go } from '../lib/ai';\nexport default function Chat() {\n  go(1);\n}\n",
            "README.md": "Gọi `shouldAutoRun` trước khi chạy.\n",
        }
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        hub = self.tmp / "hub" / "_projects" / "app"
        hub.mkdir(parents=True)
        self.p = mock.Mock(spec=Project)
        self.p.codebase, self.p.root, self.p.config = root, hub, {}
        code.build(self.p)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_defs_imports_and_alias_chain(self):
        p = self.p
        self.assertEqual([(r.path, r.line) for r in code.defines(p, "shouldAutoRun")], [("lib/ai/auto-run.ts", 1)])
        names = {n for n, _ in code.defs_in(p, "lib/ai/auto-run.ts")}
        self.assertTrue({"shouldAutoRun", "MAX_TURNS", "RunMode", "helper"} <= names, names)
        self.assertEqual(code.dependents(p, "lib/ai/auto-run.ts"), ["app/api/chat/route.ts", "lib/ai/index.ts"],
                         "`@/` via tsconfig paths and './auto-run' relative")
        self.assertEqual(code.deps(p, "components/chat.tsx"), ["lib/ai/index.ts"], "'../lib/ai' → index.ts")
        files = {(r.path, r.kind) for r in code.uses(p, "shouldAutoRun")}
        self.assertIn(("components/chat.tsx", "code"), files, "alias chain decideAutoRun → go")
        self.assertIn(("README.md", "doc"), files)

    def test_rename_warning_for_ts(self):
        from brain.recall import surface
        warn = surface.rename_warning(self.p, "lib/ai/auto-run.ts", {
            "old_string": "export function shouldAutoRun(x: number): boolean {",
            "new_string": "export function shouldRun(x: number): boolean {"})
        self.assertIn("`shouldAutoRun` còn được dùng ở", warn)
        self.assertIn("app/api/chat/route.ts:1", warn)


if __name__ == "__main__":
    unittest.main()


class SurfaceTests(unittest.TestCase):
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def hook(self, p, tool_input, sid="s1"):
        from brain.recall import surface
        return surface.context_for_tool(p, {"session_id": sid, "tool_input": tool_input})

    def test_file_context_has_commit_reason(self):
        from brain.recall import surface
        self.tmp, p = staged("T19")
        ctx = surface.file_context(p, "src/phone.py", 800)
        self.assertIn("Incident #12", ctx)
        self.assertLessEqual(len(ctx), 800)

    def test_decision_linked_through_defined_names(self):
        from brain.recall import surface
        self.tmp, p = staged("T18")
        self.assertIn("ADR-031", surface.file_context(p, "src/notify.py", 800))

    def test_rename_warning_and_once_per_session(self):
        self.tmp, p = staged("T12")
        edit = {"file_path": str(p.codebase / "src" / "handlers.py"),
                "old_string": "def handle_order_paid(evt):", "new_string": "def on_order_paid(evt):"}
        first = self.hook(p, edit)
        self.assertIn("`handle_order_paid` còn được dùng ở", first)
        self.assertIn("data/schedules.json", first)
        again = self.hook(p, {"file_path": edit["file_path"]})
        self.assertNotIn("brain context", again, "file context goes out once per session")

    def test_budget_caps_non_essential_text(self):
        from brain.recall import surface
        self.tmp, p = staged("T20")
        led = surface.Ledger.load(p, "b")
        led.budget = 50
        self.assertFalse(led.take("file:a", "x" * 60))
        self.assertTrue(led.take("trap:M-1", "y" * 60, essential=True))

    def test_prompt_recall_finds_old_conversation(self):
        from brain.recall import surface
        self.tmp, p = staged("T22")
        text = surface.context_for_prompt(p, {"session_id": "s", "prompt": "Thêm weekly_totals tổng doanh thu theo tuần cho khách ACME"})
        self.assertIn("Chủ nhật", text)

    def test_start_lists_few_decisions_when_many(self):
        from brain.recall import surface
        self.tmp, p = staged("T18")
        picked, rest = surface.relevant_decisions(p, 8)
        self.assertLessEqual(len(picked), 8)
        self.assertEqual(len(picked) + rest, len([d for d in p.decisions() if d.status.startswith("active")]))
