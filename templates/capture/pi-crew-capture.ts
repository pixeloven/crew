// Crew hook capture for pi (docs/LEARNING.md, "Hook capture"). Opt-in: load this
// file with `pi --extension <path>` or a settings `extensions` entry; Crew's pi
// package never loads it. It forwards pi's events to scripts/learn_capture.py,
// which makes every decision, and turns that script's Stop output into one
// continuation at agent_before_settle.
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const SCRIPT =
  process.env.CREW_CAPTURE_SCRIPT ?? join(dirname(fileURLToPath(import.meta.url)), "../../scripts/learn_capture.py");

type StopOutput = { decision?: string; reason?: unknown };

function send(ctx: ExtensionContext, event: Record<string, unknown>): StopOutput | undefined {
  const payload = {
    session_id: ctx.sessionManager.getSessionId(),
    transcript_path: ctx.sessionManager.getSessionFile() ?? null,
    cwd: ctx.cwd,
    ...event,
  };
  const run = spawnSync("python3", [SCRIPT, "--hook", "--harness", "pi"], {
    input: JSON.stringify(payload),
    encoding: "utf8",
    timeout: 10_000,
  });
  if (run.status !== 0 || !run.stdout?.trim()) return undefined;
  try {
    return JSON.parse(run.stdout) as StopOutput;
  } catch {
    return undefined;
  }
}

export default function (pi: ExtensionAPI) {
  // True while the agent runs the continuation this extension asked for, so the
  // script sees what Claude Code and Codex call stop_hook_active.
  let continued = false;

  pi.on("session_start", (event, ctx) => {
    continued = false;
    send(ctx, { hook_event_name: "SessionStart", source: event.reason });
  });

  pi.on("input", (event, ctx) => {
    if (event.source !== "extension") send(ctx, { hook_event_name: "UserPromptSubmit", prompt: event.text });
    return { action: "continue" };
  });

  pi.on("tool_result", (event, ctx) => {
    if (event.isError) {
      send(ctx, { hook_event_name: "PostToolUseFailure", tool_name: event.toolName, tool_input: event.input });
    }
  });

  pi.on("agent_before_settle", (event, ctx) => {
    const output = send(ctx, { hook_event_name: "Stop", stop_hook_active: continued });
    if (output?.decision === "block" && typeof output.reason === "string" && event.context.canContinue) {
      continued = true;
      return {
        entries: [{ type: "custom_message", customType: "crew-capture", content: output.reason, display: true }],
        continue: true,
      };
    }
    continued = false;
    return undefined;
  });
}
