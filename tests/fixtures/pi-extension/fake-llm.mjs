// Fake OpenAI-compatible model for the crew_agent contract tests. No billed calls.
// Instead of a reply it reports what the request carried: which Crew role prompt
// arrived, which tools were declared, and which model and thinking level were asked for.
//   "DISPATCH <role> [IN <cwd>] :: <task>"  calls crew_agent (or subagent) once
//   "BIG <bytes>"               replies with that many bytes
//   "FAIL"                      answers HTTP 500
//   "SLOW"                      never answers (timeout and abort tests)
// Prints the port it listens on, then serves until killed.
import http from "node:http";

const DISPATCH_TOOLS = ["crew_agent", "subagent"];
const text = (c) => (typeof c === "string" ? c : JSON.stringify(c ?? ""));

const server = http.createServer((req, res) => {
	let body = "";
	req.on("data", (c) => (body += c));
	req.on("end", () => {
		const j = JSON.parse(body || "{}");
		const tools = (j.tools || []).map((t) => t.function?.name).filter(Boolean).sort();
		const msgs = j.messages || [];
		const sys = msgs.filter((m) => m.role === "system" || m.role === "developer").map((m) => text(m.content)).join("\n");
		const lastUser = [...msgs].reverse().find((m) => m.role === "user");
		const userText = text(lastUser?.content);
		const toolResults = msgs.filter((m) => m.role === "tool");
		const role = (sys.match(/You are (\w+) —/) || [])[1] || "none";
		const dispatch = userText.match(/DISPATCH (\S+)(?: IN (\S+))? :: ([^"\\]+)/);
		const tool = DISPATCH_TOOLS.find((t) => tools.includes(t));
		const first = toolResults.length === 0;
		// Directives act only on a role's own first request, never on one that dispatches.
		const directive = first && !(dispatch && tool);
		if (directive && /\bSLOW\b/.test(userText)) return; // hold the request open
		if (directive && /\bFAIL\b/.test(userText)) {
			res.writeHead(500, { "content-type": "application/json" });
			return res.end(JSON.stringify({ error: { message: "fake model failure" } }));
		}
		res.writeHead(200, { "content-type": "text/event-stream" });
		const send = (o) => res.write(`data: ${JSON.stringify(o)}\n\n`);
		const base = { id: "c1", object: "chat.completion.chunk", created: 0, model: j.model };
		const usage = { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 };
		if (dispatch && tool && first) {
			const args = JSON.stringify({ agent: dispatch[1], task: dispatch[3].trim(), ...(dispatch[2] && { cwd: dispatch[2] }) });
			send({ ...base, choices: [{ index: 0, delta: { role: "assistant", tool_calls: [{ index: 0, id: "call_1", type: "function", function: { name: tool, arguments: args } }] }, finish_reason: null }] });
			send({ ...base, choices: [{ index: 0, delta: {}, finish_reason: "tool_calls" }], usage });
		} else {
			const big = userText.match(/BIG (\d+)/);
			const child = toolResults.map((t) => text(t.content)).join(" | ").slice(0, 2000);
			const content = big && directive
				? "x".repeat(Number(big[1]))
				: `ROLE=${role} MODEL=${j.model} TOOLS=${tools.join(",")} THINKING=${j.reasoning_effort ?? "none"}` + (child ? ` CHILD=[${child}]` : "");
			send({ ...base, choices: [{ index: 0, delta: { role: "assistant", content }, finish_reason: null }] });
			send({ ...base, choices: [{ index: 0, delta: {}, finish_reason: "stop" }], usage });
		}
		res.write("data: [DONE]\n\n");
		res.end();
	});
});
server.listen(0, "127.0.0.1", () => console.log(server.address().port));
