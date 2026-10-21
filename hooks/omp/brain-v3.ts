// Second Brain v3 hooks for omp (ADR-004). Same CLI as the Claude Code hooks, called with python3.
// Load per run:   omp --hook /mnt/d/SecondBrainV3/Brain/hooks/omp/brain-v3.ts
// Events used (omp extension API): before_agent_start → message, tool_call → additionalContext,
// agent_end → sendMessage(nextTurn) once when code changed but memory did not.
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const BRAIN = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "bin", "brain.py");
const SESSION = `omp-${process.pid}-${Date.now()}`;

function brain(args: string[], payload: Record<string, unknown>, cwd: string): string {
  try {
    return execFileSync(process.env.BRAIN_PYTHON || "python3", [BRAIN, ...args], {
      cwd,
      input: JSON.stringify({ session_id: SESSION, cwd, ...payload }),
      encoding: "utf8",
      timeout: 30_000,
      stdio: ["pipe", "pipe", "ignore"],
    }).trim();
  } catch {
    return ""; // a broken hook must never break the session
  }
}

function contextOf(out: string): string {
  if (!out) return "";
  try {
    return JSON.parse(out)?.hookSpecificOutput?.additionalContext ?? "";
  } catch {
    return "";
  }
}

export default function (pi: any) {
  let started = false;

  pi.on("before_agent_start", async (_event: any, ctx: any) => {
    if (started) return;
    started = true;
    const out = brain(["start", "--hook"], {}, ctx.cwd);
    if (!out) return;
    return { message: { customType: "brain-start", content: out, display: false } };
  });

  pi.on("tool_call", async (event: any, ctx: any) => {
    const extra = contextOf(
      brain(["trap-check", "--hook"], { tool_name: event.toolName, tool_input: event.input ?? {} }, ctx.cwd),
    );
    if (extra) return { additionalContext: extra };
  });

  pi.on("agent_end", async (_event: any, ctx: any) => {
    const out = brain(["end", "--check", "--hook"], {}, ctx.cwd);
    if (!out) return;
    try {
      const r = JSON.parse(out);
      if (r.decision === "block") {
        pi.sendMessage(
          { customType: "brain-end", content: r.reason, display: false },
          { deliverAs: "nextTurn", triggerTurn: true },
        );
      }
    } catch {
      /* not JSON: nothing to do */
    }
  });
}
