"""Second Brain v1 (2026-05): hub MEMORY/ + project CLAUDE.md, rituals by instruction only.

Layout follows `AI Agentic/wiki/templates/{CLAUDE-md-template,project-context-template}.md`
and `wiki/auto/init-project-prompt.md`. v1 has no per-fact dates, no TEST_MATRIX, no ADR files.
"""
from __future__ import annotations

from pathlib import Path

from bench.brains.base import Brain, Env, fwd, write
from bench.seed import Seed

SECTION_TITLES = {"env": "Environment / Config", "arch": "Key Patterns của project này",
                  "status": "Trạng thái hiện tại", "next": "TODO tiếp theo"}


def _context(seed: Seed) -> str:
    out = [f"# Project: {seed.name}", "**Updated:** 2026-10-15 | **Status:** Active | **Started:** 2026-09-20", "",
           "---", "", "## Tổng quan", seed.summary, "", "## Tech Stack", f"- **Backend:** {seed.stack}", ""]
    for key in ("arch", "status", "next"):
        facts = seed.facts_in(key)
        if facts:
            out += ["---", "", f"## {SECTION_TITLES[key]}"] + [f"- {f.text}" for f in facts] + [""]
    if seed.decisions:
        out += ["---", "", "## Quyết định kiến trúc quan trọng"]
        out += [f"- {d.title} — {d.why}" for d in seed.decisions] + [""]
    out += ["---", "", "## Environment / Config", f"- **Test:** `{seed.test_cmd}`"]
    out += [f"- {f.text}" for f in seed.facts_in("env")]
    out += ["", "<!-- AI INSTRUCTIONS: Đọc file này trước khi bắt đầu. Nếu thông tin không đủ, hỏi lại. "
            "Không tự bịa context. -->", ""]
    return "\n".join(out)


def _decisions(seed: Seed) -> str:
    out = [f"# Decisions — {seed.name}", "Lịch sử quyết định kiến trúc. Chỉ append, không xóa.", "---"]
    for d in seed.decisions:
        out += ["", f"### [{d.date}] {d.title}", f"- Quyết định: {d.decision}", f"- Lý do: {d.why}"]
    return "\n".join(out) + "\n"


def _mistakes(seed: Seed) -> str:
    out = [f"# Mistakes — {seed.name}", "Lỗi đã gặp + cách fix. Chỉ append, không xóa.", "---"]
    for t in seed.traps:
        out += ["", f"### [{t.seen[-1] if t.seen else '2026-10-01'}] {t.title}",
                f"**Lỗi:** {t.symptom}", f"**Fix:** {t.fix}", f"**Lesson:** {t.fix}"]
    return "\n".join(out) + "\n"


def _claude_md(seed: Seed, mem: str, glob: str) -> str:
    return f"""# {seed.name}

## Second Brain
Đọc các file sau trước khi làm bất cứ gì:
- `{mem}/CONTEXT.md` — trạng thái dự án
- `{glob}/my-stack.md` — preferences cá nhân

---

## Tổng quan dự án
{seed.summary}

## Tech Stack
- **Backend:** {seed.stack}

---

## Quy tắc bắt buộc

### Không được làm
- ❌ Không tự ý xóa hoặc rename file mà không báo trước
- ❌ Không để hardcode secret, API key trong code
- ❌ Không tự `git commit` hoặc `git push` khi chưa được xác nhận rõ ràng

### Luôn phải làm
- ✅ Validate input tại mọi API boundary
- ✅ Trả về error message có đủ context để debug

---

## Files quan trọng — đọc trước khi sửa
- `{mem}/DECISIONS.md` — lịch sử quyết định kiến trúc
- `{mem}/MISTAKES.md` — lỗi đã gặp

---

## Build & Run
```bash
# Test
{seed.test_cmd}
```

---

## Session Management — Bắt buộc

### Cuối mỗi session
Khi người dùng nói "kết thúc", "done", "xong", hoặc trước khi `/clear`:

1. Cập nhật `{mem}/CONTEXT.md`
2. Tạo session log tại `{mem}/sessions/YYYY-MM-DD-[tên-ngắn].md`
3. Nếu có quyết định kiến trúc → append vào `DECISIONS.md`
4. Nếu có bug đã fix → append vào `MISTAKES.md`

### Khi mắc lỗi
Ngay khi phát hiện sai, append vào `{mem}/MISTAKES.md`:
```
### [YYYY-MM-DD] <tên lỗi ngắn>
**Lỗi:** <làm gì sai>
**Fix:** <đã sửa thế nào>
**Lesson:** <rule cần nhớ>
```
"""


class V1(Brain):
    name = "v1"

    def _mem(self, hub: Path, seed: Seed) -> Path:
        return hub / "_projects" / seed.name / "MEMORY"

    def setup(self, work: Path, hub: Path, seed: Seed) -> Env:
        mem = self._mem(hub, seed)
        write(mem / "CONTEXT.md", _context(seed))
        write(mem / "DECISIONS.md", _decisions(seed))
        write(mem / "MISTAKES.md", _mistakes(seed))
        write(mem / "sessions" / "2026-10-15-khoi-tao.md",
              f"# Session Log — 2026-10-15 {seed.name}\n## Mục tiêu\nKhởi tạo Second Brain.\n## Đã làm\n- Tạo MEMORY/\n")
        write(hub / "_global" / "my-stack.md", "# My stack\n- Python: stdlib trước, type hint, unittest.\n")
        write(work / "CLAUDE.md", _claude_md(seed, fwd(mem), fwd(hub / "_global")))
        return Env(add_dirs=[hub])

    def memory_paths(self, work: Path, hub: Path, seed: Seed) -> list[Path]:
        return [self._mem(hub, seed)]
