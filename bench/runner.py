"""Run tasks × brains × repeats with a headless agent and append scored rows to a JSONL file."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bench import score
from bench.brains import get_brain
from bench.brains.base import fwd
from bench.tasks import Task

PACKAGE = Path(__file__).resolve().parent.parent
HUB = Path(os.environ.get("SECOND_BRAIN_V4_ROOT", PACKAGE.parent))
RUNS_ROOT = Path(os.environ.get("BRAINBENCH_DIR", "D:/_brainbench"))
RESULTS_DIR = HUB / "_metrics" / "bench"
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"


@dataclass
class RunSpec:
    task: Task
    brain: str
    repeat: int
    model: str
    agent: str = "claude"


def _git_baseline(work: Path) -> None:
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.email=bench@local", "-c", "user.name=bench", "commit", "-qm", "baseline"]):
        subprocess.run(["git", *args], cwd=work, capture_output=True, check=True)


def _claude_cmd(prompt: str, model: str, add_dirs: list[Path]) -> list[str]:
    exe = shutil.which("claude") or "claude"
    cmd = [exe, "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", model,
           "--permission-mode", "bypassPermissions", "--setting-sources", "project,local",
           "--strict-mcp-config", "--no-session-persistence"]
    for d in add_dirs:
        cmd += ["--add-dir", str(d)]
    return cmd


def _run_agent(cmd: list[str], cwd: Path, env: dict, run_dir: Path, timeout: int) -> tuple[int, bool]:
    """Stream the transcript to disk so a timed-out run still leaves evidence; kill the whole tree."""
    with (run_dir / "events.jsonl").open("w", encoding="utf-8") as out, \
            (run_dir / "stderr.txt").open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                                text=True, encoding="utf-8", errors="replace")
        try:
            return proc.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
            else:
                proc.kill()
            proc.wait()
            return proc.returncode, True


def _forget_claude_project(work: Path) -> None:
    """Drop the per-cwd auto-memory/transcript folder Claude Code may create for a bench workdir."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(work))
    d = CLAUDE_PROJECTS / slug
    if "brainbench" in slug and d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


def run_one(spec: RunSpec, batch_dir: Path, timeout: int) -> dict:
    task, brain = spec.task, get_brain(spec.brain)
    run_dir = batch_dir / f"{task.id}-{spec.brain}-r{spec.repeat}"
    work, hub = run_dir / "work", run_dir / "hub"
    shutil.copytree(task.repo, work)
    hub.mkdir(parents=True)
    seed = task.seed()
    row = {"ts": datetime.now().isoformat(timespec="seconds"), "task": task.id, "kind": task.kind,
           "brain": spec.brain, "repeat": spec.repeat, "agent": spec.agent, "model": spec.model,
           "run_dir": fwd(run_dir)}
    try:
        env = brain.setup(work, hub, seed)
        _git_baseline(work)
        mem_paths = brain.memory_paths(work, hub, seed)
        before = score.snapshot(mem_paths)
        t0 = time.time()
        rc, timed_out = _run_agent(_claude_cmd(task.full_prompt(), spec.model, env.add_dirs), work,
                                   {**os.environ, **env.extra_env}, run_dir, timeout)
        events = score.load_events(run_dir / "events.jsonl")
        after = score.snapshot(mem_paths)
        markers = [fwd(p).lower() for p in mem_paths] + [f"_projects/{seed.name}/".lower()] * bool(mem_paths)
        row.update(score.score_run(events, markers, before, after, task.memory_keywords, has_memory=bool(mem_paths)))
        row["wall_s"] = round(time.time() - t0, 1)
        row.update({k: v for k, v in task.check(work, events).items()})
        stderr = (run_dir / "stderr.txt").read_text(encoding="utf-8", errors="replace")
        row["error"] = (f"timeout {timeout}s" if timed_out else
                        None if row.get("ok") else f"agent rc={rc}: {stderr[-300:]}")
    except Exception as e:
        row.update({"ok": False, "pass": False, "error": f"{type(e).__name__}: {e}"[:600]})
    finally:
        brain.teardown(work, hub)
        _forget_claude_project(work)
    return row


def run_batch(tasks: list[Task], brains: list[str], repeats: int, model: str, label: str,
              jobs: int = 2, timeout: int = 900) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch_dir = RUNS_ROOT / f"{label}-{stamp}"
    batch_dir.mkdir(parents=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{stamp[:8]}-{label}.jsonl"
    specs = [RunSpec(t, b, r, model) for r in range(1, repeats + 1) for t in tasks for b in brains]
    lock = threading.Lock()
    done = 0

    def work(spec: RunSpec) -> None:
        nonlocal done
        row = run_one(spec, batch_dir, timeout)
        with lock:
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            done += 1
            mark = "✅" if row.get("pass") else ("⚠️" if row.get("error") else "❌")
            cost = row.get("cost_usd") or 0
            print(f"[{done}/{len(specs)}] {mark} {spec.task.id} {spec.brain} r{spec.repeat} "
                  f"${cost:.3f} {row.get('duration_s', '-')}s {row.get('error') or ''}", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        list(pool.map(work, specs))
    print(f"\nKết quả: {out}\nThư mục chạy: {batch_dir}")
    return out
