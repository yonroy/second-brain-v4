"""omp session parser for `brain ingest omp` (ADR-008).

Ported verbatim from Second Brain v2 `Harness/skills/agent-ops/scripts/agent_ops.py` (0.4.0, lines 112-553):
read_session (active minutes per yield segment, parent-task agent lookup), claim ↔ tool-call matching,
verdict/finding parsing and brief lint. The only change: reviewer/tester roles come from brain.toml
[roles] instead of the hardcoded `data-reviewer` / `local-tester`. Keep it in step with v2 so `brain stats`
and `agent_ops.py runs` agree on the same logs (phase 5 acceptance: within ±5%).
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

def _inside(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents



def _instant(s: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.astimezone()


def _flatten(value, key: str = "") -> list[str]:
    """Chuỗi trong `yield.data` (giống clean_memory._flatten)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out = []
        for v in value:
            out += [f"- {s}" if re.search(r"memory|harness", key, re.I) and isinstance(v, str) else s for s in _flatten(v, key)]
        return out
    if isinstance(value, dict):
        out = []
        for k, v in value.items():
            if re.search(r"memory|harness", k, re.I):
                out.append("Memory/Harness đã dùng")
            out += _flatten(v, k)
        return out
    return []


_parent_cache: dict[str, str] = {}


def _agent_of(parent: str | None, name: str) -> str:
    """Loại agent = `tasks[].agent` trong lời gọi `task` của phiên cha (mặc định "task"), như clean_memory."""
    if not parent:
        return "?"
    if parent not in _parent_cache:
        try:
            _parent_cache[parent] = Path(parent).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            _parent_cache[parent] = ""
    text = _parent_cache[parent]
    n = re.escape(json.dumps(name)[1:-1])
    m = (re.search(r'"agent"\s*:\s*"([^"]+)"\s*,\s*"name"\s*:\s*"' + n + '"', text)
         or re.search(r'"name"\s*:\s*"' + n + r'"[^{}]{0,4000}?"agent"\s*:\s*"([^"]+)"', text))
    return m.group(1) if m else "task"


@dataclass
class Claim:
    kind: str        # cmd | num
    text: str
    backed: bool
    where: str       # câu chứa claim (cắt 200 ký tự)


@dataclass
class Run:
    sub_id: str
    file: str
    name: str
    agent: str
    started: dt.datetime
    last: dt.datetime
    finished: dt.datetime | None = None
    dead: bool = False                 # chưa yield mà phiên đã thoát / im quá live_hours
    turns: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    tokens: int = 0
    cost: float = 0.0
    report: str = ""
    brief: str = ""
    reads: dict = field(default_factory=dict)
    claims: list = field(default_factory=list)
    skipped_claims: int = 0
    active: float = 0.0                # giây của các đoạn làm việc đã đóng (bắt đầu/đánh thức → "Result submitted")
    seg: dt.datetime | None = None     # đầu đoạn đang mở; None = đang nghỉ sau yield
    awake: bool = False                # đã yield, bị đánh thức lại (irc) và đang làm tiếp — phiên chưa thoát, chưa im quá live_hours

    @property
    def minutes(self) -> float:
        """Thời gian làm thật: bắt đầu → "Result submitted", cộng các lần bị đánh thức lại (irc) → yield kế tiếp.
        Không tính lúc nằm chờ giữa hai lần yield, cũng không tính 7 phút chờ thoát sau yield cuối."""
        tail = (self.last - self.seg).total_seconds() if self.seg else 0.0
        return (self.active + tail) / 60

    @property
    def running(self) -> bool:
        """Đang chạy: chưa yield lần nào và chưa chết, HOẶC đã yield nhưng bị đánh thức lại và chưa yield/thoát."""
        return not self.dead and (self.finished is None or self.awake)


def _texts(content) -> str:
    if isinstance(content, str):
        return content
    return " ".join(c.get("text", "") for c in content or [] if isinstance(c, dict) and isinstance(c.get("text"), str))


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def _context_of(system_prompt: str) -> str:
    m = re.search(r"\n§ Context\n(.*?)(?=\n§ [A-Z]|\Z)", system_prompt or "", re.S)
    return m.group(1) if m else ""


def read_session(path: Path, cwds: list[Path], since: str | None, read_patterns: dict, stale_before: dt.datetime | None) -> Run | None:
    """Một file JSONL → Run (subagent trong phạm vi) hoặc None. Không giữ nội dung tool result sau khi tính claim."""
    run: Run | None = None
    parent = None
    yield_args = None
    last_text = ""
    final = None
    exited = False
    corpus: list[str] = []     # lệnh bash (đã thay biến) + code eval
    results: list[str] = []    # text tool result (trừ yield) + kết quả job nền
    reads = {k: 0 for k in read_patterns}
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            t = o.get("type")
            if t == "session":
                parent = o.get("parentSession")
                if not parent:
                    return None
                started = _instant(o.get("timestamp", ""))
                if since and started < _instant(since):
                    return None
                if not any(_inside(Path(o.get("cwd", "/")).resolve(), c) for c in cwds):
                    return None
                run = Run(o.get("id", ""), str(path), path.stem, "", started, started, seg=started)
                continue
            if run is None:
                continue
            ts = o.get("timestamp")
            if isinstance(ts, str) and t in ("message", "custom_message"):
                at = _instant(ts)
                run.last = max(run.last, at)
                if run.seg is None:
                    run.seg = at
            if t == "session_init":
                run.brief = (_context_of(o.get("systemPrompt", "")) + "\n" + (o.get("task") or "")).strip()
                continue
            if t == "custom" and o.get("customType") == "session_exit":
                exited = True
                continue
            if t == "custom_message":
                if o.get("customType") == "async-result":
                    results.append(_texts(o.get("content")))
                continue
            msg = o.get("message") if t == "message" else None
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if msg.get("role") == "assistant":
                usage = msg.get("usage") or {}
                if usage:
                    run.turns += 1
                    run.tokens += int(usage.get("totalTokens") or 0)
                    run.cost += float((usage.get("cost") or {}).get("total") or 0)
                if not isinstance(content, list):
                    continue
                texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text" and c.get("text", "").strip()]
                if texts:
                    last_text = "\n".join(texts)
                for c in content:
                    if not (isinstance(c, dict) and c.get("type") == "toolCall"):
                        continue
                    run.tool_calls += 1
                    args = c.get("arguments") or {}
                    if c.get("name") == "yield":
                        yield_args = args
                        continue
                    blob = "\n".join(_strings(args))
                    for k, pats in read_patterns.items():
                        if not reads[k] and any(p in blob for p in pats):
                            reads[k] = 1
                    if c.get("name") == "bash":
                        corpus.append(_expand_vars(str(args.get("command", ""))))
                    elif c.get("name") == "eval":
                        corpus.append(str(args.get("code", "")))
            elif msg.get("role") == "toolResult":
                if msg.get("isError"):
                    run.tool_errors += 1
                txt = _texts(content)
                if msg.get("toolName") == "yield":
                    if txt.startswith("Result submitted") and yield_args is not None:
                        final = (yield_args, last_text)
                        run.finished = _instant(ts) if isinstance(ts, str) else run.last
                        run.active += (run.finished - run.seg).total_seconds() if run.seg else 0.0
                        run.seg = None
                elif msg.get("toolName") in EXEC_TOOLS:
                    results.append(txt)
    if run is None:
        return None
    run.agent = _agent_of(parent, run.name)
    run.reads = reads
    stale = stale_before is not None and run.last < stale_before
    if run.finished is None:
        run.dead = exited or stale
        return run
    run.awake = run.seg is not None and not exited and not stale
    args, fallback = final
    data = args.get("data")
    run.report = "\n".join(_flatten(data)) if data not in (None, "", {}) else ("" if "error" in args else fallback)
    run.claims, run.skipped_claims = find_claims(run.report, _expand_py(corpus), results)
    return run


def scan(p: Project, recent_hours: float | None = None) -> list[Run]:
    sdir = Path(p.cfg["sessions_dir"]).expanduser()
    cwds = p.cwds()
    _parent_cache.clear()  # phiên cha còn chạy thì lời gọi `task` mới chỉ có ở lần đọc này
    if not sdir.is_dir() or not cwds:
        return []
    t = now()
    stale = t - dt.timedelta(hours=p.cfg["live_hours"])
    since = str(p.cfg["since"]) if p.cfg["since"] else None
    files = sorted(sdir.rglob("*.jsonl"))
    if recent_hours is not None:
        cut = (t - dt.timedelta(hours=recent_hours)).timestamp()
        files = [f for f in files if f.stat().st_mtime >= cut]
    runs = [r for f in files if (r := read_session(f, cwds, since, p.cfg["read_patterns"], stale))]
    return sorted(runs, key=lambda r: (r.started, r.sub_id))


# ----------------------------------------------------------------------------- claim ↔ tool call

RUNNERS = {"make": r"make", "pytest": r"pytest", "python": r"python3?", "python3": r"python3?", "dbt": r"dbt",
           "bash": r"bash", "git": r"git", "uv": r"uv"}
PATH_RUNNERS = ("scripts/", "./", ".dbt-venv/")
# số kết quả chỉ được chứng minh bởi output của tool CHẠY lệnh (+ job nền `async-result`), không bởi `read`/`grep`
# một file tài liệu có sẵn con số đó (reviewer đọc báo cáo của engineer rồi chép lại số)
EXEC_TOOLS = {"bash", "eval", "wait"}
# git ghi/đổi nhánh trong báo cáo hầu như luôn là lệnh ĐỀ XUẤT cho user, không phải lệnh đã chạy
GIT_PROPOSALS = {"add", "commit", "push", "checkout", "switch", "rebase", "reset", "merge", "stash", "cherry-pick",
                 "tag", "branch", "worktree", "pull", "fetch", "restore", "rm", "mv"}
BACKTICK = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"^\s*```.*?^\s*```", re.S | re.M)
LOG_TEXT = re.compile(r"\d\d:\d\d:\d\d|succeeded|Done\.|error:", re.I)
PLACEHOLDER = re.compile(r"<[^>]+>|…|\.\.\.")
NUM = re.compile(r"(?<![\w=.,+])(?:(\d+) (passed|failed)\b|(PASS|ERROR|FAIL)=(\d+))")
# câu chứa claim: phải có dấu hiệu "đã chạy" và không có dấu hiệu đề xuất / phủ định / chép lại / kỳ vọng
DID_RUN = re.compile(r"(?i)(\bchạy|\bran\b|re-?ran|rerun|exit|→|->|passed|PASS=|\bxanh\b|green|\bOK\b|✅|thành công|succe)")
NOT_RUN = re.compile(
    r"(?i)(đề xuất|đề nghị|lệnh (commit|cho user|gửi)|user (chạy|tự)|để user|sẽ\b|nên\b|cần chạy|chưa\b|không\b|sau khi|"
    r"trước khi|khi cần|nếu\b|kỳ vọng|expected?|expectation|suggest|should|would|will\b|not\b|n't\b|to run|cho user|copy|"
    r"dán|paste|ví dụ|e\.g\.|\bvd\b|\?|báo\b|claimed?|reported|theo báo cáo|suy luận|INFERENCE|runbook|hướng dẫn|can run|"
    r"có thể|sửa .{0,40}thành|thay cho|trước đây|cũ\b|cần kho|previous|lần trước|vòng \d|"
    r"của (?:local-tester|data-engineer|data-reviewer|engineer|tester|reviewer)|"
    # câu tả nội dung tài liệu (§, `:12-30`, file.md:12, 07:38-41) — số trong đó là số đã ghi, không phải output vừa chạy
    r"§|`:\d+|\w\.(?:md|sql|ya?ml|py|json):\d+|(?<![\d:])\d\d:\d+-\d+)")


def _expand_vars(cmd: str) -> str:
    """`L=/x/local_dbt.sh; $L build` → `/x/local_dbt.sh build` (để lệnh qua biến vẫn khớp claim)."""
    vals = {m.group(1): m.group(2).strip("\"'") for m in re.finditer(r"(?:^|[\s;&(])([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|[^\s;&|]+)", cmd)}
    if not vals:
        return cmd
    return re.sub(r"\$\{?([A-Za-z_]\w*)\}?", lambda m: vals.get(m.group(1), m.group(0)), cmd)


def _expand_py(corpus: list[str]) -> list[str]:
    """Kernel eval giữ biến giữa các ô: `L='/x/local_dbt.sh'` ở ô 1, `Popen([L,'run',…])` ở ô 5 → thay tên bằng đường dẫn."""
    vals = {m.group(1): m.group(2) for c in corpus
            for m in re.finditer(r"^\s*([A-Za-z_]\w*)\s*=\s*['\"]([^'\"\n]*/[^'\"\n]*)['\"]\s*$", c, re.M)}
    if not vals:
        return corpus
    pat = re.compile(r"(?<![\w.'\"/$])(" + "|".join(map(re.escape, sorted(vals, key=len, reverse=True))) + r")(?![\w'\"])")
    return [pat.sub(lambda m: vals[m.group(1)], c) for c in corpus]


def _cmd_head(s: str) -> tuple[str, str | None] | None:
    """Lệnh → (runner, đối số/target đầu) hoặc None nếu không bắt đầu bằng runner."""
    s = re.sub(r"^(?:[A-Z_][A-Z0-9_]*=\S+\s+)+", "", s.strip())
    s = re.sub(r"^cd\s+\S+\s*(?:&&|;)\s*", "", s)
    parts = s.split()
    if not parts:
        return None
    head = parts[0]
    if head.startswith(PATH_RUNNERS):
        base = head.rsplit("/", 1)[-1]
        if base not in RUNNERS:
            return (head[2:] if head.startswith("./") else head, None)
    elif head in RUNNERS:
        base = head
    else:
        return None
    rest = parts[1:]
    if base in ("python", "python3") and "-m" in rest:
        i = rest.index("-m")
        return (base, rest[i + 1] if i + 1 < len(rest) else None)
    return (base, next((a for a in rest if not a.startswith("-")), None))


def _backed_cmd(head: tuple[str, str | None], corpus: list[str]) -> bool:
    runner, arg = head
    # runner theo sau `/`, `-`, `_` là đường dẫn / target khác (`dbt/models`, `make dbt-parse`), không phải lệnh đó
    pat = r"(?<![A-Za-z0-9])" + (RUNNERS.get(runner) or re.escape(runner)) + r"(?![\w/-])"
    arg_re = re.compile(r"(?<![\w-])" + re.escape(arg.strip("'\"")) + r"(?![\w-])") if arg else None
    for c in corpus:
        for m in re.finditer(pat, c):
            if arg_re is None or arg_re.search(re.split(r"\n|;|&&|\|\|?", c[m.end():m.end() + 200])[0]):
                return True
    return False


def _sentence(text: str, pos: int) -> str:
    """Câu chứa vị trí `pos`: cắt ở xuống dòng hoặc `. ` nằm NGOÀI backtick (`Done. PASS=1` không cắt câu)."""
    masked = BACKTICK.sub(lambda m: "`" + "x" * (len(m.group(0)) - 2) + "`", text)
    a = max(masked.rfind("\n", 0, pos), masked.rfind(". ", 0, pos)) + 1
    ends = [x for x in (masked.find("\n", pos), masked.find(". ", pos)) if x != -1]
    return text[a:min(ends) if ends else len(text)].strip()


def find_claims(report: str, corpus: list[str], results: list[str]) -> tuple[list[Claim], int]:
    """→ (claim đã lọc kèm có/không bằng chứng, số ứng viên bị bỏ vì câu là đề xuất/phủ định/chép lại)."""
    text = FENCE.sub("", report or "")
    out: dict[tuple[str, str], Claim] = {}
    skipped = 0
    for m in BACKTICK.finditer(text):
        s = m.group(1).strip()
        head = _cmd_head(s)
        if not head or LOG_TEXT.search(s) or PLACEHOLDER.search(s):
            continue
        if head[0] == "git" and head[1] in GIT_PROPOSALS:
            continue
        sent = _sentence(text, m.start())
        if NOT_RUN.search(sent) or not DID_RUN.search(sent):
            skipped += 1
            continue
        out.setdefault(("cmd", s), Claim("cmd", s, _backed_cmd(head, corpus), sent[:200]))
    for m in NUM.finditer(text):
        if m.group(2) == "failed" and m.group(1) == "0":
            continue  # pytest không in "0 failed" khi xanh → luôn là báo động giả
        sent = _sentence(text, m.start())
        if NOT_RUN.search(sent):
            skipped += 1
            continue
        key = rf"(?<![\d.,]){m.group(1)} {m.group(2)}\b" if m.group(1) else rf"\b{m.group(3)}={m.group(4)}(?!\d)"
        out.setdefault(("num", m.group(0)), Claim("num", m.group(0), any(re.search(key, r) for r in results), sent[:200]))
    return list(out.values()), skipped


# ----------------------------------------------------------------------------- verdict, finding, brief

REVIEW_VERDICT = re.compile(r"VERDICT\W{0,6}(APPROVE WITH NOTES|REQUEST CHANGES|APPROVE|BLOCK)\b")
REVIEW_LEAD = re.compile(r"^\W*(APPROVE WITH NOTES|REQUEST CHANGES|APPROVE|BLOCK)\b", re.M)
LOCAL_VERDICT = re.compile(r"LOCAL\s*:\s*\**\s*(PASS|FAIL|BLOCKED)\b")
FINDINGS_SUMMARY = re.compile(r"^\W*FINDINGS\s*:\s*(.*)$", re.M)    # FINDINGS: P0=0 P1=1 P2=2 P3=0
FINDING_NEW = re.compile(r"^\s*[-*]\s*\[(P[0-3])\]")                 # - [P2] file:dòng — vấn đề · bằng chứng · sửa
FINDING_TABLE = re.compile(r"^\s*\|[^|\n]*\|\s*\**(P[0-3])\b")      # | 3 | P2 | file:dòng | … (bảng finding cũ)
FINDING_FIELD = re.compile(r"^\s*(P[0-3])\s*$")                      # findings[].level = "P2" trong yield.data (cũ)


def verdict_of(agent: str, report: str, roles: dict | None = None) -> str:
    """Vai trò lấy từ brain.toml [roles] (v3); thiếu thì giữ tên agent mặc định của v2."""
    roles = roles or {}
    reviewers = set(roles.get("reviewer") or ["data-reviewer"])
    testers = set(roles.get("tester") or ["local-tester"])
    if agent in reviewers:
        m = REVIEW_VERDICT.search(report) or REVIEW_LEAD.search(report)
        return m.group(1) if m else ""
    if agent in testers:
        m = LOCAL_VERDICT.search(report)
        return m.group(1) if m else ""
    return ""


def findings_of(report: str, legacy: bool = False) -> dict[str, int]:
    """Ưu tiên dòng `FINDINGS: P0=… P1=…` (dòng cuối nếu có nhiều) → đếm `- [Pn]` → khuôn cũ (bảng, trường level).
    Khuôn cũ chỉ bật cho data-reviewer: ở agent khác `| Labels | P1 |` / `P1` là nhãn Jira hay mã quyết định."""
    out = {"P1": 0, "P2": 0, "P3": 0}
    summaries = [m.group(1) for m in FINDINGS_SUMMARY.finditer(report) if re.search(r"P[0-3]\s*=\s*\d", m.group(1))]
    if summaries:
        for k, v in re.findall(r"(P[0-3])\s*=\s*(\d+)", summaries[-1]):
            if k in out:
                out[k] = int(v)
        return out
    lines = report.splitlines()
    found = [m.group(1) for line in lines if (m := FINDING_NEW.match(line))]
    if not found and legacy:
        found = [m.group(1) for line in lines if (m := FINDING_TABLE.match(line) or FINDING_FIELD.match(line))]
    for k in found:
        if k in out:
            out[k] += 1
    return out


HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
BOLD_LINE = re.compile(r"^\s*\*\*(.+?)\*\*")
LABEL_LINE = re.compile(r"^\s*(?:[-*]\s+)?([^\W\d_][^:\n`]{0,40}?):\s+\S")   # nhãn đầu dòng "Non-goal: …" (house style 29/09–15/10)


def lint_brief(text: str, cfg: dict) -> tuple[list[str], list[str], dict[str, str]]:
    """→ (khoá bắt buộc thiếu, khoá khuyến nghị thiếu, {khoá: heading tìm thấy})."""
    heads = []
    for line in text.splitlines():
        m = HEADING.match(line) or BOLD_LINE.match(line) or LABEL_LINE.match(line)
        if m:
            heads.append(re.sub(r"^[\W\d_]*?(?=\w)", "", m.group(1).replace("*", "")).strip())
    found: dict[str, str] = {}
    groups = {**cfg["brief"]["required"], **cfg["brief"]["recommended"]}
    for key, syns in groups.items():
        for h in heads:
            if any(h.casefold().startswith(s.casefold()) for s in syns):
                found[key] = h
                break
    missing = [k for k in cfg["brief"]["required"] if k not in found]
    rec = [k for k in cfg["brief"]["recommended"] if k not in found]
    return missing, rec, found
