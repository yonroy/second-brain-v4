"""`brain verify`: run PROOF.md commands, stamp the result cell, append to the verify log.

The log is what makes a ✅ trustworthy: `brain gate` flags any ✅ cell without a matching log entry.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import date, datetime
from pathlib import Path

from brain.project import Project, ProofRow


def verify_log(project: Project) -> Path:
    return project.root.parent.parent / "_metrics" / "verify.jsonl"  # <hub>/_projects/<p> → <hub>/_metrics


def git_head(cwd: Path) -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "nogit"
    except (OSError, subprocess.TimeoutExpired):
        return "nogit"


def cmd_hash(cmd: str) -> str:
    return hashlib.sha1(cmd.encode("utf-8")).hexdigest()[:10]


def stamp(ok: bool, day: str, commit: str) -> str:
    return f"{'✅' if ok else '❌'} {day} {commit}"


def _replace_cell(project: Project, row: ProofRow, value: str) -> None:
    p = project.file("PROOF.md")
    lines = p.read_text(encoding="utf-8").split("\n")
    line = lines[row.line_no - 1]
    lead = line[: len(line) - len(line.lstrip())]
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    cells[3] = value
    lines[row.line_no - 1] = lead + "| " + " | ".join(cells) + " |"
    p.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def run(project: Project, ids: list[str] | None = None, timeout: int = 900) -> list[dict]:
    rows = project.proofs()
    if ids:
        want = {i.upper() for i in ids}
        missing = want - {r.id for r in rows}
        if missing:
            raise SystemExit(f"❌ PROOF.md không có: {', '.join(sorted(missing))}")
        rows = [r for r in rows if r.id in want]
    log = verify_log(project)
    log.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for row in rows:
        if not row.cmd:
            results.append({"id": row.id, "ok": False, "skipped": "không có cmd"})
            continue
        commit = git_head(project.codebase)
        t0 = time.time()
        try:
            r = subprocess.run(row.cmd, shell=True, cwd=project.codebase, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
            ok, rc, tail = r.returncode == 0, r.returncode, (r.stdout + r.stderr)[-600:]
        except subprocess.TimeoutExpired:
            ok, rc, tail = False, None, f"timeout {timeout}s"
        day = date.today().isoformat()
        entry = {"ts": datetime.now().isoformat(timespec="seconds"), "project": project.name, "id": row.id,
                 "cmd_hash": cmd_hash(row.cmd), "ok": ok, "rc": rc, "date": day, "commit": commit,
                 "seconds": round(time.time() - t0, 1)}
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _replace_cell(project, row, stamp(ok, day, commit))
        results.append({**entry, "tail": tail})
    return results


def load_log(project: Project) -> list[dict]:
    log = verify_log(project)
    if not log.exists():
        return []
    out = []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("project") == project.name:
            out.append(e)
    return out
