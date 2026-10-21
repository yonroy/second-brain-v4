"""Second Brain v2 (0.4.0): the real `harness.ps1 init --level L1` into a scratch hub, then seed.

The package is copied from D:/SecondBrainV2/Harness (override with BENCH_V2_PACKAGE) so the
CLAUDE.md block points at a hub that really contains Harness/, as it does in normal use.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from bench.brains.base import Brain, Env, fwd, write
from bench.seed import Seed

V2_PACKAGE = Path(os.environ.get("BENCH_V2_PACKAGE", "D:/SecondBrainV2/Harness"))
BASH = os.environ.get("BENCH_BASH") or (r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt" else "bash")


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def _src(f) -> str:
    return f" (nguồn: {f.source}, {f.date})"


def _context(seed: Seed, root: Path) -> str:
    env = [f"- {f.text}{_src(f)}" for f in seed.facts_in("env")]
    arch = [f"- {f.text}{_src(f)}" for f in seed.facts_in("arch")]
    nxt = [f"{i}. 🟡 [NEXT] {f.text}" for i, f in enumerate(seed.facts_in("next"), 1)] or ["1. 🟢 [LATER] (trống)"]
    traps = [f"- {t.title} — {t.fix} (xem MISTAKES)" for t in seed.traps] or ["- (không có)"]
    return "\n".join([
        f"# Project: {seed.name}",
        "**Updated:** 2026-10-15 (khởi tạo harness) | **Status:** Active | **Started:** 2026-09-20", "",
        "> **Ảnh chụp trạng thái** dự án, không phải nhật ký. Luật ghi: `../AGENTS.md` mục \"Cách ghi `MEMORY/CONTEXT.md`\".",
        "> **[HỎI USER]** = AI không suy ra được, đừng bịa. **[CẦN ĐO]** = có thể đã lỗi thời, đo trước khi dùng.", "",
        "---", "", "## 1. Phạm vi", f"Toàn bộ repo `{seed.name}`.", "",
        "## 2. Môi trường", *env, "",
        "## 3. Tổng quan + stack", seed.summary, f"- **Stack:** {seed.stack}", *arch, "",
        "## 4. Trạng thái", "", "| Module / việc | Trạng thái | Ghi chú |", "|---|---|---|",
        "| Core | ✅ Đang chạy | |", "",
        "## 5. Bẫy đang có hiệu lực", *traps, "",
        "## 6. Việc tiếp theo", *nxt, "",
        "## 7. Key patterns", "- Chỉ dùng thư viện chuẩn", "",
        "## 8. Lệnh / cấu hình", f"- **Test:** `{seed.test_cmd}`", "",
        "## 9. Liên kết",
        "- Entrypoint `../AGENTS.md` · quyết định `DECISIONS.md` · bài học `MISTAKES.md` · nhật ký `sessions/` · "
        "ADR `../HARNESS/decisions/` · bằng chứng `../HARNESS/TEST_MATRIX.md`", "",
    ])


def _mistakes(seed: Seed) -> str:
    out = [f"# Mistakes — {seed.name}", "", "> Bug đã gặp + cách fix. Append-only.", "", "---"]
    for t in seed.traps:
        out += ["", f"### [{t.seen[-1] if t.seen else '2026-10-01'}] {t.title}", f"- Triệu chứng: {t.symptom}",
                f"- Nguyên nhân gốc: {t.title}", f"- Cách fix: {t.fix}", f"- Cách tránh tái diễn: {t.fix}"]
    return "\n".join(out) + "\n"


def _decisions_log(seed: Seed) -> str:
    out = [f"# Decisions — {seed.name} (tactical log)", "",
           "> Tactical decisions, session-scope. Append-only. **Durable** → `HARNESS/decisions/ADR-XXX.md`.", "", "---",
           "", "### [2026-09-20] Khởi tạo", f"- Stack được chọn: {seed.stack}"]
    return "\n".join(out) + "\n"


def _adr(d) -> str:
    status = "Accepted" if d.active else d.status.replace("superseded by", "Superseded by")
    return (f"# {d.id} — {d.title}\n\n**Ngày:** {d.date} · **Trạng thái:** {status}\n\n"
            f"## Context\n{d.why}\n\n## Decision\n{d.decision}\n\n## Consequences\n- Áp dụng cho mọi thay đổi liên quan.\n")


def _test_matrix(seed: Seed) -> str:
    rows = [f"| {p.id} | {p.behavior} | unit | `{p.cmd}` | ✅ |" for p in seed.proofs]
    rows = rows or [f"| B-001 | Bộ test hiện có pass | unit | `{seed.test_cmd}` | ✅ |"]
    return "\n".join([f"# Test Matrix — {seed.name}", "", "> Mapping behavior → proof. Mỗi behavior phải có ít nhất 1 proof.",
                      "", "---", "", "| ID | Behavior | Proof type | Proof location | Status |",
                      "|----|----------|------------|----------------|--------|", *rows]) + "\n"


class V2(Brain):
    name = "v2"

    def setup(self, work: Path, hub: Path, seed: Seed) -> Env:
        # harness.sh shares init logic with harness.ps1. The .ps1 path stalled PowerShell before parsing when
        # launched from the bench runner (2026-10-21, cause not found), so the bench uses the bash twin.
        pkg = hub / "Harness"
        shutil.copytree(V2_PACKAGE, pkg, copy_function=shutil.copyfile,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", "docs"))
        (hub / "_projects").mkdir(parents=True, exist_ok=True)
        write(hub / "_global" / "my-stack.md", "# My stack\n- Python: stdlib trước, type hint, unittest.\n")
        env = {**os.environ, "SECOND_BRAIN_ROOT": fwd(hub)}
        r = subprocess.run([BASH, fwd(pkg / "bin" / "harness.sh"), "init", "--name", seed.name, "--path", fwd(work),
                            "--level", "L1"], env=env, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", stdin=subprocess.DEVNULL, timeout=120)
        proj = hub / "_projects" / seed.name
        if r.returncode != 0 or not (proj / "AGENTS.md").exists():
            raise RuntimeError(f"v2 init failed rc={r.returncode}: {(r.stdout + r.stderr)[-800:]}")
        write(proj / "MEMORY" / "CONTEXT.md", _context(seed, hub))
        write(proj / "MEMORY" / "MISTAKES.md", _mistakes(seed))
        write(proj / "MEMORY" / "DECISIONS.md", _decisions_log(seed))
        write(proj / "MEMORY" / "sessions" / "2026-10-15-khoi-tao.md",
              f"# Session 2026-10-15 — khởi tạo harness {seed.name}\n- `harness init --level L1`\n")
        for d in seed.decisions:
            write(proj / "HARNESS" / "decisions" / f"{d.id}-{_slug(d.title)}.md", _adr(d))
        write(proj / "HARNESS" / "TEST_MATRIX.md", _test_matrix(seed))
        return Env(extra_env={"SECOND_BRAIN_ROOT": fwd(hub)}, add_dirs=[hub])

    def memory_paths(self, work: Path, hub: Path, seed: Seed) -> list[Path]:
        return [hub / "_projects" / seed.name]
