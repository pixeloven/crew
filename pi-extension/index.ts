/**
 * Crew's own agent runtime for pi (EXPERIMENTAL, opt-in with CREW_PI_AGENT=1).
 *
 * Registers one tool, `crew_agent { agent, task, cwd? }`, that runs a Crew role in an
 * isolated child `pi` process. It is written only against pi's extension API and CLI,
 * so pi itself supplies posture (`--exclude-tools`) and MCP (the child is an ordinary
 * pi process and connects the same mcp.json servers). Without the opt-in it registers
 * nothing, and Crew roles stay reachable through pi-subagents as `crew.<role>`.
 *
 * Contract (crew#92):
 *  - define:   roles are the rendered pi-agents/*.md beside this file; a
 *              `.pi/agents/<role>.md` inside the session's project that declares
 *              `package: crew` overrides one, behind pi's project trust.
 *  - dispatch: bare Crew role names; parallel dispatch is several calls in one turn.
 *  - posture:  the role's `excludeTools` is subtracted from the child's default tools.
 *  - nesting:  only `allowNestedSubagents` roles keep `crew_agent`; depth is capped.
 *  - model:    the child inherits the dispatching session's model and thinking level.
 *  - trust:    the child is trusted only when the session trusts the project and the
 *              role runs inside it; it never gains trust the session lacks.
 *  - handoff:  the child's final assistant text is the tool result; failures are tool
 *              errors; large output spills to a file; abort and timeout kill the child.
 */
import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// Host packages are imported only after the opt-in check, so without the opt-in this
// file loads nothing from pi and cannot fail on a pi it was never tested with.
type Host = typeof import("@earendil-works/pi-coding-agent");
let parseFrontmatter: Host["parseFrontmatter"];

const TOOL = "crew_agent";
const PACKAGE = "crew";
const OPT_IN_ENV = "CREW_PI_AGENT";
const DEPTH_ENV = "CREW_AGENT_DEPTH";
const TIMEOUT_ENV = "CREW_AGENT_TIMEOUT_SECONDS";
// Operator session is depth 0; a lead child (1) may dispatch workers (2), which may not.
const MAX_DEPTH = 2;
// The oldest pi this was tested on. --exclude-tools needs 0.77, built-in MCP 0.99.
const MIN_PI = "1.4.0";
const MAX_RESULT_BYTES = 50 * 1024;
// pi-subagents' tools are never a Crew role's: excluding them keeps posture the same
// whether or not pi-subagents is also installed.
const PI_SUBAGENTS_TOOLS = ["subagent", "subagent_supervisor", "bg_wait", "contact_supervisor"];

export interface Role {
	name: string;
	description: string;
	excludeTools: string[];
	dispatch: boolean;
	prompt: string;
	source: string;
}

function list(value: unknown): string[] {
	const raw = Array.isArray(value) ? value : typeof value === "string" ? value.split(",") : [];
	return raw
		.filter((v): v is string => typeof v === "string")
		.map((v) => v.trim())
		.filter(Boolean);
}

function readRole(file: string): Role | undefined {
	const { frontmatter: fm, body } = parseFrontmatter<Record<string, unknown>>(fs.readFileSync(file, "utf-8"));
	if (typeof fm.name !== "string" || typeof fm.description !== "string") return undefined;
	return {
		name: fm.name,
		description: fm.description,
		excludeTools: list(fm.excludeTools),
		dispatch: fm.allowNestedSubagents === true,
		prompt: body,
		source: file,
	};
}

function loadRoles(dir: string): Map<string, Role> {
	const roles = new Map<string, Role>();
	for (const file of fs.existsSync(dir) ? fs.readdirSync(dir).sort() : []) {
		if (!file.endsWith(".md")) continue;
		const role = readRole(path.join(dir, file));
		if (role) roles.set(role.name, role);
	}
	return roles;
}

// A project shadows a Crew role the same way it does under pi-subagents: the file
// must declare `package: crew`, or it is some other agent and the packaged role stays.
// The search walks up from cwd but never above root.
function findOverlay(cwd: string, root: string, name: string): string | undefined {
	for (let dir = cwd; ; dir = path.dirname(dir)) {
		const file = path.join(dir, ".pi", "agents", `${name}.md`);
		if (fs.existsSync(file)) {
			const { frontmatter } = parseFrontmatter<Record<string, unknown>>(fs.readFileSync(file, "utf-8"));
			return frontmatter.package === PACKAGE && frontmatter.name === name ? file : undefined;
		}
		if (dir === root || path.dirname(dir) === dir) return undefined;
	}
}

function within(root: string, dir: string): boolean {
	const rel = path.relative(root, dir);
	return rel !== ".." && !rel.startsWith(`..${path.sep}`) && !path.isAbsolute(rel);
}

export function versionAtLeast(version: string, floor: string): boolean {
	const parse = (v: string) => v.split("-")[0].split(".").map((n) => Number.parseInt(n, 10) || 0);
	const [a, b] = [parse(version), parse(floor)];
	for (let i = 0; i < 3; i++) if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) > (b[i] ?? 0);
	return true;
}

// Run the child on the same pi the parent runs on, never whatever `pi` is on PATH.
// process.execPath is the Node (or Bun) binary and argv[1] pi's CLI script, on Windows too.
function piInvocation(args: string[]): { command: string; args: string[] } {
	const script = process.argv[1];
	if (script && fs.existsSync(script)) return { command: process.execPath, args: [script, ...args] };
	const exec = path.basename(process.execPath).toLowerCase();
	if (!/^(node|bun)(\.exe)?$/.test(exec)) return { command: process.execPath, args };
	return { command: "pi", args };
}

function assistantText(message: any): string {
	if (message?.role !== "assistant") return "";
	return (message.content ?? [])
		.filter((c: any) => c.type === "text")
		.map((c: any) => c.text)
		.join("");
}

function finalText(messages: any[]): string {
	for (let i = messages.length - 1; i >= 0; i--) {
		const text = assistantText(messages[i]);
		if (text) return text;
	}
	return "";
}

export function deniedTools(role: Role): string[] {
	const denied = [...role.excludeTools, ...PI_SUBAGENTS_TOOLS];
	if (!role.dispatch) denied.push(TOOL);
	return [...new Set(denied)];
}

interface RunOptions {
	cwd: string;
	depth: number;
	model?: string;
	thinking?: string;
	trusted: boolean;
	timeoutMs?: number;
	signal?: AbortSignal;
	onText?: (text: string) => void;
}

interface RunResult {
	failed: boolean;
	text: string;
	error: string;
	code: number;
}

async function runRole(role: Role, task: string, opts: RunOptions): Promise<RunResult> {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), "crew-agent-"));
	const promptFile = path.join(dir, `${role.name}.md`);
	fs.writeFileSync(promptFile, role.prompt, { mode: 0o600 });
	const args = ["--mode", "json", "-p", "--no-session", "--append-system-prompt", promptFile];
	if (opts.model) args.push("--model", opts.model);
	if (opts.thinking) args.push("--thinking", opts.thinking);
	args.push(opts.trusted ? "--approve" : "--no-approve");
	args.push("--exclude-tools", deniedTools(role).join(","));
	args.push(`Task: ${task}`);

	const messages: any[] = [];
	let stderr = "";
	let stopped = "";
	try {
		const code = await new Promise<number>((resolve) => {
			const inv = piInvocation(args);
			const proc = spawn(inv.command, inv.args, {
				cwd: opts.cwd,
				shell: false,
				stdio: ["ignore", "pipe", "pipe"],
				env: { ...process.env, [DEPTH_ENV]: String(opts.depth + 1) },
			});
			const stop = (why: string) => {
				if (stopped) return;
				stopped = why;
				proc.kill("SIGTERM");
				setTimeout(() => proc.exitCode === null && proc.kill("SIGKILL"), 5000).unref();
			};
			const timer = opts.timeoutMs ? setTimeout(() => stop("timed out"), opts.timeoutMs) : undefined;
			let buf = "";
			const onLine = (line: string) => {
				if (!line.trim()) return;
				let ev: any;
				try {
					ev = JSON.parse(line);
				} catch {
					return; // not a record
				}
				if (ev.type === "message_end" && ev.message) {
					messages.push(ev.message);
					const text = assistantText(ev.message);
					if (text) opts.onText?.(text);
				}
			};
			// JSON mode is LF-framed; split on LF only (pi docs/json.md).
			proc.stdout.on("data", (d) => {
				buf += d.toString();
				let i: number;
				while ((i = buf.indexOf("\n")) >= 0) {
					onLine(buf.slice(0, i).replace(/\r$/, ""));
					buf = buf.slice(i + 1);
				}
			});
			proc.stderr.on("data", (d) => (stderr += d.toString()));
			proc.on("close", (c) => {
				if (timer) clearTimeout(timer);
				onLine(buf);
				resolve(c ?? 1);
			});
			proc.on("error", (e) => {
				stderr += String(e);
				resolve(1);
			});
			if (opts.signal?.aborted) stop("aborted");
			else opts.signal?.addEventListener("abort", () => stop("aborted"), { once: true });
		});
		const last = [...messages].reverse().find((m) => m.role === "assistant");
		const failed = !!stopped || code !== 0 || last?.stopReason === "error" || last?.stopReason === "aborted";
		const error = stopped || last?.errorMessage || stderr.trim();
		return { failed, text: finalText(messages), error, code };
	} finally {
		fs.rmSync(dir, { recursive: true, force: true });
	}
}

// Keep the model-facing result bounded; the whole output stays readable on disk.
function bound(name: string, text: string): string {
	if (Buffer.byteLength(text, "utf-8") <= MAX_RESULT_BYTES) return text;
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), "crew-agent-output-"));
	const file = path.join(dir, `${name}.md`);
	fs.writeFileSync(file, text, { mode: 0o600 });
	const head = Buffer.from(text, "utf-8").subarray(0, MAX_RESULT_BYTES).toString("utf-8");
	return `${head}\n\n[truncated at ${MAX_RESULT_BYTES} bytes; full output: ${file}]`;
}

export default async function (pi: ExtensionAPI) {
	if (process.env[OPT_IN_ENV] !== "1") return;
	const host = await import("@earendil-works/pi-coding-agent");
	const { Type } = await import("typebox");
	parseFrontmatter = host.parseFrontmatter;
	const VERSION = host.VERSION;
	if (!versionAtLeast(VERSION, MIN_PI)) {
		pi.on("session_start", (_event, ctx) => {
			ctx.ui.notify(`Crew's ${TOOL} needs pi >= ${MIN_PI} (running ${VERSION}); it is not loaded.`, "warning");
		});
		return;
	}
	const depth = Number(process.env[DEPTH_ENV] ?? "0") || 0;
	if (depth >= MAX_DEPTH) return;
	const here = path.dirname(fileURLToPath(import.meta.url));
	const roles = loadRoles(path.join(here, "..", "pi-agents"));
	if (roles.size === 0) return;
	const timeoutSeconds = Number(process.env[TIMEOUT_ENV] ?? "0");
	const timeoutMs = timeoutSeconds > 0 ? timeoutSeconds * 1000 : undefined;

	const roster = [...roles.values()].map((r) => `- ${r.name}: ${r.description}`).join("\n");
	pi.registerTool({
		name: TOOL,
		label: "Crew agent",
		description:
			`Delegate a scoped task to a Crew role, which runs in its own isolated pi process and returns ` +
			`its final report. Use bare role names. Call it several times in one turn to run roles in parallel. ` +
			`Roles:\n${roster}`,
		promptSnippet: "Delegate scoped work to a Crew role (lead, implementer, reviewer, ...)",
		parameters: Type.Object({
			agent: Type.String({ description: "Crew role name, e.g. reviewer" }),
			task: Type.String({ description: "The scoped task, with acceptance criteria" }),
			cwd: Type.Optional(Type.String({ description: "Working directory for the role" })),
		}),
		async execute(_id, params, signal, onUpdate, ctx) {
			let role = roles.get(params.agent);
			if (!role) throw new Error(`Unknown Crew role "${params.agent}". Roles: ${[...roles.keys()].join(", ")}`);
			const project = fs.realpathSync(path.resolve(ctx.cwd));
			const cwd = fs.realpathSync(path.resolve(project, params.cwd ?? ""));
			// The session's trust covers only its own project, so an overlay from a cwd
			// outside it is never used, and the child is trusted only inside it.
			const inProject = within(project, cwd);
			const trusted = inProject && ctx.isProjectTrusted();
			let note = "";
			const overlay = findOverlay(cwd, inProject ? project : cwd, role.name);
			if (overlay && !inProject) {
				note = `\n\n[${overlay} was not used: it is outside the session's project, so Crew's packaged ${role.name} ran]`;
			} else if (overlay) {
				const use =
					trusted ||
					(ctx.hasUI &&
						(await ctx.ui.confirm(
							`Run the project's ${role.name} role?`,
							`${overlay} overrides Crew's ${role.name}. Project roles are repo-controlled; only continue for a trusted repository.`,
						)));
				if (use) role = readRole(overlay) ?? role;
				else note = `\n\n[${overlay} was not used: the project is not trusted, so Crew's packaged ${role.name} ran]`;
			}
			const r = await runRole(role, params.task, {
				cwd,
				depth,
				model: ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : undefined,
				thinking: ctx.thinkingLevel,
				trusted,
				timeoutMs,
				signal,
				onText: (text) => onUpdate?.({ content: [{ type: "text", text }], details: undefined }),
			});
			if (r.failed) {
				const why = r.error ? r.error.slice(-2000) : "no output";
				throw new Error(`crew ${role.name} failed (exit ${r.code}): ${why}`);
			}
			return { content: [{ type: "text", text: bound(role.name, r.text || "(no output)") + note }], details: undefined };
		},
	});
}
