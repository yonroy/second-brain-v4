"""`brain gate`: memory health. Every 🔴 carries the action that clears it (spec §2 rule 7)."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

from brain import LEGACY_BLOCKS
from brain.project import PROOF_OK, STORY_STATUS, STORY_TYPES, Project
from brain.verify import cmd_hash, load_log

LIVE_SECTIONS = {"Đang làm", "Việc tiếp theo"}
RED, YELLOW = "🔴", "🟡"


@dataclass
class Finding:
    level: str
    what: str
    action: str

    def __str__(self) -> str:
        return f"{self.level} {self.what} → {self.action}"


def check(project: Project, today: date | None = None) -> list[Finding]:
    today = today or date.today()
    out: list[Finding] = []
    out += _context(project, today)
    out += _ids(project)
    out += _traps(project)
    out += _proofs(project)
    out += _stories(project)
    out += _legacy(project)
    return out


def _context(p: Project, today: date) -> list[Finding]:
    text = p.read("CONTEXT.md")
    if not text:
        return [Finding(RED, "Thiếu CONTEXT.md", "chạy `brain init` lại để tạo file thiếu")]
    out = []
    lines = text.splitlines()
    max_lines, max_chars, stale_days = p.limit("context_lines", 120), p.limit("line_chars", 400), p.limit("fact_stale_days", 30)
    if len(lines) > max_lines:
        out.append(Finding(RED, f"CONTEXT {len(lines)} dòng > {max_lines}",
                           "dời chi tiết sang decisions/ hoặc TRAPS, giữ ảnh chụp ngắn (`brain clean diff-facts` trước khi viết lại lớn)"))
    long_lines = [i for i, l in enumerate(lines, 1) if len(l) > max_chars]
    if long_lines:
        out.append(Finding(RED, f"CONTEXT có dòng > {max_chars} ký tự (dòng {', '.join(map(str, long_lines[:5]))})",
                           "tách thành nhiều fact ngắn, mỗi fact một tag"))
    untagged, stale_live, stale = [], [], []
    for f in p.facts():
        if f.date is None:
            untagged.append(f.line_no)
        elif (today - f.date).days > stale_days:
            (stale_live if f.section in LIVE_SECTIONS else stale).append(f)
    if stale_live:
        out.append(Finding(RED, f"{len(stale_live)} việc trong Đang làm/Việc tiếp theo quá {stale_days} ngày "
                           f"(dòng {', '.join(str(f.line_no) for f in stale_live[:5])})",
                           "kiểm còn đúng không: xong thì xoá, còn làm thì cập nhật ngày"))
    if stale:
        out.append(Finding(YELLOW, f"{len(stale)} fact quá {stale_days} ngày (dòng {', '.join(str(f.line_no) for f in stale[:5])})",
                           "kiểm lại trên repo trước khi dùng; đúng thì đổi ngày, sai thì sửa"))
    if untagged:
        out.append(Finding(YELLOW, f"{len(untagged)} fact không có [ngày|nguồn] (dòng {', '.join(map(str, untagged[:5]))})",
                           "thêm tag hoặc coi là chưa kiểm"))
    return out


def _ids(p: Project) -> list[Finding]:
    out = []
    groups = {
        "TRAPS": [t.id for t in p.traps()],
        "PROOF": [r.id for r in p.proofs()],
        "decisions": [d.id for d in p.decisions()],
        "work": [str(s.meta.get("id", "")) for s in p.stories() if s.meta.get("id")],
    }
    for where, ids in groups.items():
        dup = [i for i, n in Counter(ids).items() if n > 1]
        if dup:
            out.append(Finding(RED, f"ID trùng trong {where}: {', '.join(dup)}", "đổi số cho bản sau, sửa chỗ tham chiếu"))
    return out


def _traps(p: Project) -> list[Finding]:
    no_trigger = [t.id for t in p.traps() if not t.trigger]
    if no_trigger:
        return [Finding(YELLOW, f"Trap thiếu trigger: {', '.join(no_trigger)}",
                        "thêm `trigger:` (path hoặc kw:) để hook nạp đúng lúc")]
    return []


def _proofs(p: Project) -> list[Finding]:
    out = []
    log = load_log(p)
    rows = p.proofs()
    no_cmd = [r.id for r in rows if not r.cmd]
    if no_cmd:
        out.append(Finding(RED, f"PROOF thiếu cmd: {', '.join(no_cmd)}", "ghi lệnh chứng minh, rồi `brain verify <ID>`"))
    forged = []
    for r in rows:
        cell = r.result.strip()
        if not cell:
            continue
        m = PROOF_OK.match(cell)
        if not m:
            forged.append(r.id)
            continue
        ok, day, commit = m.group(1) == "✅", m.group(2), m.group(3)
        if not any(e["id"] == r.id and e["ok"] == ok and e["date"] == day and e["commit"] == commit
                   and e.get("cmd_hash") == cmd_hash(r.cmd) for e in log):
            forged.append(r.id)
    if forged:
        out.append(Finding(RED, f"Kết quả PROOF không có trong verify log: {', '.join(forged)}",
                           "xoá ô kết quả và chạy `brain verify <ID>` (chỉ tool được ghi ✅)"))
    return out


def _stories(p: Project) -> list[Finding]:
    out = []
    ok_ids = {r.id for r in p.proofs() if r.result.startswith("✅")}
    for s in p.stories():
        status, typ = str(s.meta.get("status", "")), str(s.meta.get("type", ""))
        name = s.path.name
        if status not in STORY_STATUS:
            out.append(Finding(RED, f"{name}: status '{status or 'thiếu'}' không hợp lệ",
                               f"đặt `status:` là {' | '.join(sorted(STORY_STATUS))}"))
        if typ and typ not in STORY_TYPES:
            out.append(Finding(YELLOW, f"{name}: type '{typ}' lạ", f"dùng {' | '.join(sorted(STORY_TYPES))}"))
        if typ == "high-risk" and not s.meta.get("adr"):
            out.append(Finding(RED, f"{name}: high-risk nhưng chưa có ADR", "ghi ADR vào decisions/, điền `adr:`"))
        proofs = s.meta.get("proof") or []
        if isinstance(proofs, str):
            proofs = [x for x in re.split(r"[,\s]+", proofs) if x]
        if status == "done":
            missing = [b for b in proofs if b not in ok_ids]
            if missing:
                out.append(Finding(RED, f"{name}: done nhưng proof chưa ✅ ({', '.join(missing)})",
                                   "chạy `brain verify` hoặc mở lại story"))
    return out


def _legacy(p: Project) -> list[Finding]:
    out = []
    dup = [d for d in ("MEMORY", "HARNESS") if (p.codebase / d).is_dir()]
    if dup:
        out.append(Finding(RED, f"Codebase còn bản memory cũ: {', '.join(dup)}/",
                           "chuyển nội dung cần giữ vào hub rồi xoá/đổi tên thư mục trong codebase (một sự thật, một chỗ)"))
    claude = p.codebase / "CLAUDE.md"
    text = claude.read_text(encoding="utf-8", errors="ignore") if claude.is_file() else ""
    old = [b for b in LEGACY_BLOCKS if f"<!-- {b}:START" in text]
    if old:
        out.append(Finding(RED, f"CLAUDE.md còn block {', '.join(old)} (hai thế hệ brain cùng chạy)",
                           "chạy `brain hooks migrate` (gỡ block + hook của thế hệ cũ, link lại skill). Đừng dùng `hooks remove` của v3: nó gỡ cả hook v4"))
    return out


def summary(project: Project, findings: list[Finding]) -> str:
    reds = sum(f.level == RED for f in findings)
    yellows = sum(f.level == YELLOW for f in findings)
    if not findings:
        return f"brain gate [{project.name}]: ✅ sạch"
    return f"brain gate [{project.name}]: {RED}{reds} {YELLOW}{yellows}"
