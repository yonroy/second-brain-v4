import os
import stat
import sys
import unittest
from unittest import mock

from brain import gate, latmd
from tests.test_brain import Base

CONTEXT_EXTRA = """## Kiến trúc
- foo nằm ở app [2026-11-01|file:app.py#foo]
- bar đã xoá [2026-11-01|file:src/bar.py:12] theo ADR-001, xem M-001, S-001 và B-001
- code `[[không đụng]] ADR-001` giữ nguyên, ADR-999 không có thì để chữ
"""


class LatBase(Base):
    def setUp(self):
        super().setUp()
        (self.code / "app.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
        ctx = self.p.read("CONTEXT.md").replace("## Kiến trúc\n", CONTEXT_EXTRA)
        self.write("CONTEXT.md", ctx)
        self.write("TRAPS.md", self.p.read("TRAPS.md")
                   + "\n## M-001 Đừng sửa app tay\ntrigger: src/app.py, *.toml, kw:pnpm\nseen: 2026-10-21\nfix: dùng generator\n")
        self.write("decisions/INDEX.md", self.p.read("decisions/INDEX.md") + "| ADR-001 | 2026-11-01 | Dùng foo | active |\n")
        self.write("decisions/ADR-001-dung-foo.md", "# ADR-001 Dùng foo\n\n## Context\nVì M-001 và ADR-001.\n")
        self.write("work/S-001-them-foo.md",
                   "---\nid: S-001\ntype: normal\nstatus: doing\nproof: [B-001]\n---\n## Ý định\nThêm foo theo ADR-001.\n")
        self.write("PROOF.md", self.p.read("PROOF.md").replace("|---|---|---|---|\n",
                                                                "|---|---|---|---|\n| B-001 | foo chạy | `python app.py` | |\n"))
        self.write("journal/2026-11-02-abcd1234.md", "# 2026-11-02 · phiên abcd1234\n\n- brain gate [demo]: ✅ sạch\n")

    def vault(self, rel):
        return (self.p.root / ".lat" / "lat.md" / rel).read_text(encoding="utf-8")


class BuildTests(LatBase):
    def test_ids_and_file_sources_become_links(self):
        v = latmd.build(self.p)
        ctx = self.vault("CONTEXT.md")
        self.assertIn("\\[2026-11-01|[[app.py#foo|file:app.py#foo]]\\]", ctx)
        self.assertIn("[[src/bar.py|file:src/bar.py:12]]", ctx)
        self.assertIn("[[decisions/ADR-001-dung-foo|ADR-001]]", ctx)
        self.assertIn("[[TRAPS#M-001 Đừng sửa app tay|M-001]]", ctx)
        self.assertIn("[[work/S-001-them-foo|S-001]]", ctx)
        self.assertIn("[[PROOF|B-001]]", ctx)
        self.assertIn("`[[không đụng]] ADR-001`", ctx)   # inline code untouched
        self.assertIn("ADR-999 không có", ctx)           # unknown ID stays text
        self.assertGreaterEqual(v.links, 7)

    def test_tables_self_links_triggers_headings(self):
        latmd.build(self.p)
        self.assertIn("| [[decisions/ADR-001-dung-foo]] | 2026-11-01 |", self.vault("decisions/INDEX.md"))  # no `|` label in a table
        adr = self.vault("decisions/ADR-001-dung-foo.md")
        self.assertIn("Vì [[TRAPS#M-001 Đừng sửa app tay|M-001]] và ADR-001.", adr)  # no self-link
        self.assertIn("# ADR-001 Dùng foo", adr)                                     # heading never linked
        self.assertIn("trigger: [[src/app.py]], *.toml, kw:pnpm", self.vault("TRAPS.md"))
        self.assertIn("proof: [B-001]", self.vault("work/S-001-them-foo.md"))         # frontmatter untouched
        self.assertIn("\\[demo\\]:", self.vault("journal/2026-11-02-abcd1234.md"))   # not a reference definition

    def test_indexes_leads_and_exclusions(self):
        v = latmd.build(self.p)
        root = self.vault("lat.md")
        for entry in ("[[decisions]]", "[[journal]]", "[[work]]", "[[CONTEXT]]", "[[TRAPS]]"):
            self.assertIn(entry, root)
        self.assertIn("[[ADR-001-dung-foo]]", self.vault("decisions/decisions.md"))
        self.assertNotIn("_template", " ".join(v.files))
        self.assertNotIn("brain.toml", " ".join(v.files))
        self.assertIn("## Mục tiêu\n\nMục «Mục tiêu» trong `CONTEXT.md`.", self.vault("CONTEXT.md"))
        self.assertNotIn("Trap M-001:", self.vault("TRAPS.md"))  # short trap body already is a valid lead
        self.write("TRAPS.md", self.p.read("TRAPS.md") + "\n## M-002 Dài\ntrigger: kw:x\nfix: " + "a" * 260 + "\n")
        latmd.build(self.p)
        self.assertIn("## M-002 Dài\n\nTrap M-002: Dài.\ntrigger:", self.vault("TRAPS.md"))
        self.assertNotIn("<!--", self.vault("TRAPS.md"))

    def test_deterministic_and_line_map(self):
        latmd.build(self.p)
        first = {f: self.vault(f) for f in latmd.build(self.p).files}
        v = latmd.build(self.p)
        self.assertEqual(first, {f: self.vault(f) for f in v.files})
        src = self.p.read("CONTEXT.md").splitlines()
        out = self.vault("CONTEXT.md").splitlines()
        i = next(n for n, l in enumerate(out) if "src/bar.py" in l)
        self.assertIn("file:src/bar.py:12", src[v.lines["CONTEXT.md"][i] - 1])

    def test_foreign_lat_dir_is_never_deleted(self):
        d = self.p.root / ".lat"
        d.mkdir()
        (d / "mine.md").write_text("x", encoding="utf-8")
        with self.assertRaises(SystemExit):
            latmd.build(self.p)
        self.assertTrue((d / "mine.md").exists())

    def test_remap_points_at_source_lines(self):
        v = latmd.build(self.p)
        i = next(n for n, l in enumerate(self.vault("CONTEXT.md").splitlines(), 1) if "src/bar.py" in l)
        raw = f"- {v.dir}/CONTEXT.md:{i}: broken link [[src/bar.py]]\n- {v.dir}/lat.md:1: x"
        out = latmd.remap(raw, self.p, v)
        src = next(n for n, l in enumerate(self.p.read("CONTEXT.md").splitlines(), 1) if "src/bar.py" in l)
        self.assertIn(f"- CONTEXT.md:{src}: broken link", out)
        self.assertIn("lat.md (tự sinh)", out)


class GateTests(LatBase):
    def fake_lat(self, code, text):
        f = self.tmp / "fake_lat.py"
        f.write_text(f"import sys\nprint({text!r})\nsys.exit({code})\n", encoding="utf-8")
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
        return mock.patch.dict(os.environ, {"BRAIN_LAT": f'"{sys.executable}" "{f}"'})

    def test_off_by_default(self):
        with self.fake_lat(1, "3 errors found"):
            self.assertFalse([f for f in gate.check(self.p) if "lat" in f.what])

    def test_on_reports_errors(self):
        self.p.config["lat"] = {"gate": True}
        with self.fake_lat(1, "- CONTEXT.md:3: broken link\n\n2 errors found"):
            found = [f for f in gate.check(self.p) if "lat" in f.what]
        self.assertEqual(len(found), 1)
        self.assertIn("2 lỗi", found[0].what)
        with self.fake_lat(0, ""):
            self.assertFalse([f for f in gate.check(self.p) if "lat" in f.what])

    def test_on_without_lat(self):
        self.p.config["lat"] = {"gate": True}
        with mock.patch.object(latmd, "lat_cmd", return_value=None):
            found = [f for f in gate.check(self.p) if "lat" in f.what]
        self.assertEqual(found[0].level, gate.YELLOW)


@unittest.skipUnless(latmd.lat_cmd(), "lat / lat-core chưa cài")
class RealLatTests(LatBase):
    def test_only_real_drift_is_reported(self):
        code, out = latmd.check(self.p)
        self.assertEqual(code, 1, out)
        self.assertIn("src/bar.py", out)       # fact points at a file that does not exist
        self.assertIn("src/app.py", out)       # trap trigger likewise (the file is app.py)
        self.assertEqual(latmd.errors_in(out), 2, out)

    def test_clean_memory_passes(self):
        ctx = self.p.read("CONTEXT.md").replace("[2026-11-01|file:src/bar.py:12]", "[2026-11-01|file:app.py]")
        self.write("CONTEXT.md", ctx)
        self.write("TRAPS.md", self.p.read("TRAPS.md").replace("src/app.py", "app.py"))
        code, out = latmd.check(self.p)
        self.assertEqual(code, 0, out)

    def test_cli_passthrough(self):
        rc, _ = self.run_cli("lat", "build")
        self.assertEqual(rc, 0)
        import subprocess
        r = subprocess.run([*latmd.lat_cmd(), "refs", "decisions/ADR-001-dung-foo#ADR-001 Dùng foo"],
                           cwd=latmd.vault_root(self.p), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("CONTEXT", r.stdout)  # the fact that cites ADR-001 is a backlink
        self.assertIn("S-001-them-foo", r.stdout)


if __name__ == "__main__":
    unittest.main()
