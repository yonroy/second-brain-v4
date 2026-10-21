"""Second Brain v3: `brain init` (hooks + skills) into a scratch hub, then the seed in v3 format."""
from __future__ import annotations

import re
import subprocess
import unicodedata
from pathlib import Path

from bench.brains.base import Brain, Env, fwd, write
from bench.seed import Seed

SECTIONS = {"env": "Môi trường", "arch": "Kiến trúc", "status": "Đang làm", "next": "Việc tiếp theo"}


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def _context(seed: Seed) -> str:
    out = [f"# {seed.name} — CONTEXT", "",
           "> Ảnh chụp hiện tại, sửa tại chỗ. Mỗi fact là một dòng `- nội dung [YYYY-MM-DD|nguồn]`.", "",
           "## Mục tiêu", f"- {seed.summary} [2026-09-20|user]", ""]
    for key in ("env", "arch", "status", "next"):
        out.append(f"## {SECTIONS[key]}")
        if key == "env":
            out.append(f"- Stack: {seed.stack} [2026-09-20|user]")
        out += [f"- {f.text} [{f.date}|{f.source}]" for f in seed.facts_in(key)]
        out.append("")
    out += ["## Khoảng trống đã biết", ""]
    return "\n".join(out)


def _traps(seed: Seed) -> str:
    out = [f"# {seed.name} — TRAPS", ""]
    for t in seed.traps:
        out += [f"## {t.id} {t.title}", f"trigger: {', '.join(t.trigger)}", f"seen: {', '.join(t.seen)}",
                f"triệu chứng: {t.symptom}", f"fix: {t.fix}", "enforce: none", ""]
    return "\n".join(out)


def _decisions(seed: Seed) -> str:
    rows = [f"| {d.id} | {d.date} | {d.title}: {d.decision} | {d.status} |" for d in seed.decisions]
    return "\n".join([f"# {seed.name} — Decisions", "", "| ID | Ngày | Tóm tắt | Trạng thái |",
                      "|---|---|---|---|", *rows]) + "\n"


def _proof(seed: Seed) -> str:
    rows = [f"| B-001 | Bộ test hiện có pass | `{seed.test_cmd}` |  |"]
    rows += [f"| {p.id} | {p.behavior} | `{p.cmd}` |  |" for p in seed.proofs if p.id != "B-001"]
    return "\n".join([f"# {seed.name} — PROOF", "",
                      "> Cột kết quả **chỉ** do `brain verify <B-ID>` ghi.", "",
                      "| ID | Behavior | cmd | Kết quả |", "|---|---|---|---|", *rows, "",
                      "## Khoảng trống đã biết", ""])


class V3(Brain):
    name = "v3"

    def setup(self, work: Path, hub: Path, seed: Seed) -> Env:
        from brain import hooks, skills
        from brain.init import init
        subprocess.run(["git", "init", "-q"], cwd=work, check=True)  # so hooks/skills land in .git/info/exclude
        init(seed.name, work, hub)
        hooks.install(work.resolve())
        skills.install(work.resolve())
        proj = hub / "_projects" / seed.name
        write(proj / "CONTEXT.md", _context(seed))
        write(proj / "TRAPS.md", _traps(seed))
        write(proj / "decisions" / "INDEX.md", _decisions(seed))
        for d in seed.decisions:
            write(proj / "decisions" / f"{d.id}-{_slug(d.title)}.md",
                  f"# {d.id} — {d.title}\n\n**Ngày:** {d.date} · **Trạng thái:** active\n\n"
                  f"## Context\n{d.why}\n\n## Decision\n{d.decision}\n")
        write(proj / "PROOF.md", _proof(seed))
        return Env(extra_env={"SECOND_BRAIN_V3_ROOT": fwd(hub)}, add_dirs=[hub])

    def memory_paths(self, work: Path, hub: Path, seed: Seed) -> list[Path]:
        return [hub / "_projects" / seed.name]
