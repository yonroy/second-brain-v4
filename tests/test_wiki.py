import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from brain.recall import wiki

PAGES = {
    "concepts/memory-system.md": """---
title: Memory System
tags: [memory, persistence]
aliases: [trí nhớ dài hạn]
updated: 2026-10-01
---

## Tóm tắt
Hệ thống lưu thông tin của agent qua nhiều tầng.

## Các tầng
- Short-term: context window
- Long-term: vector database, persistent memory giữa các phiên
""",
    "concepts/claude-hooks.md": """---
title: Claude Code Hooks
tags: [hooks, claude-code]
---

## Tóm tắt
Hook chạy theo vòng đời phiên: SessionStart, PreToolUse, Stop.

## Stop
Stop hook có thể chặn agent kết thúc khi chưa có bằng chứng. Xem [[concepts/memory-system]].
""",
    "sources/notes.md": "# Ghi chú rời\n\nĐường dẫn đặt tên kebab-case. Nhắc tới [[concepts/claude-hooks]].\n",
    "index.md": "# Index\n[[concepts/memory-system]] memory memory memory\n",
}


class WikiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.hub, self.w = self.tmp / "hub", self.tmp / "wiki"
        self.hub.mkdir()
        for rel, text in PAGES.items():
            f = self.w / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        self.env = mock.patch.dict(os.environ, {"SECOND_BRAIN_V4_ROOT": str(self.hub)})
        self.env.start()
        wiki.add(self.w, "kb")

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parse_front_matter_and_fallback_title(self):
        pg = wiki.parse("kb", self.w, self.w / "concepts/memory-system.md")
        self.assertEqual((pg.title, pg.tags, pg.aliases), ("Memory System", ["memory", "persistence"], ["trí nhớ dài hạn"]))
        self.assertEqual(pg.summary, "Hệ thống lưu thông tin của agent qua nhiều tầng.")
        self.assertEqual(wiki.parse("kb", self.w, self.w / "sources/notes.md").title, "Ghi chú rời")

    def test_index_skips_index_md_and_is_incremental(self):
        self.assertEqual(wiki.build()["pages"], 3, "index.md / log.md are navigation, not content")
        self.assertEqual(wiki.build()["changed"], 0)
        time.sleep(0.01)
        (self.w / "sources/notes.md").write_text("# Ghi chú\n\nmới\n", encoding="utf-8")
        (self.w / "concepts/claude-hooks.md").unlink()
        r = wiki.build()
        self.assertEqual((r["pages"], r["changed"], r["removed"]), (2, 1, 1))

    def test_fusion_rewards_agreement_across_phrasings(self):
        one = wiki.search(["chặn kết thúc"])
        self.assertEqual(one[0].rel, "concepts/claude-hooks.md")
        many = wiki.search(["nhớ lâu giữa các phiên", "long-term memory", "persistent memory", "trí nhớ dài hạn"])
        self.assertEqual(many[0].rel, "concepts/memory-system.md")
        self.assertEqual((many[0].agree, many[0].phrasings), (4, 4))
        self.assertIn("persistent memory", many[0].snippet)

    def test_vietnamese_without_diacritics_and_alias(self):
        self.assertEqual(wiki.search(["tri nho dai han"])[0].rel, "concepts/memory-system.md")
        self.assertEqual(wiki.search(["duong dan kebab"])[0].rel, "sources/notes.md")

    def test_catalog_and_related(self):
        lines = wiki.catalog()
        self.assertEqual(len(lines), 3)
        self.assertTrue(any("`concepts/memory-system.md` Memory System [memory, persistence]" in l for l in lines))
        self.assertEqual(len(wiki.catalog(prefix="concepts")), 2)
        self.assertEqual(len(wiki.catalog(tag="hooks")), 1)
        r = wiki.related("concepts/claude-hooks")
        self.assertEqual([x["rel"] for x in r["out"]], ["concepts/memory-system.md"])
        self.assertEqual([x["rel"] for x in r["back"]], ["sources/notes.md"])

    def test_prompt_pointers_off_by_default(self):
        self.assertEqual(wiki.prompt_pointers("memory system persistence giữa phiên"), [])
        cfg = wiki.config_path().read_text(encoding="utf-8").replace("prompt = false", "prompt = true")
        wiki.config_path().write_text(cfg, encoding="utf-8")
        hits = wiki.prompt_pointers("memory system persistence giữa phiên")
        self.assertEqual([h.rel for h in hits], ["concepts/memory-system.md"])
        self.assertEqual(wiki.prompt_pointers("sửa bug thanh toán"), [], "weak keyword overlap must not point")

    def test_add_keeps_auto_flag_and_replaces_same_name(self):
        wiki.add(self.w, "kb")
        self.assertEqual(len(wiki.wikis()), 1)
        self.assertIn("prompt = false", wiki.config_path().read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
