// Fake stdio MCP server with one tool, probe_echo: proves a role reaches the
// operator's MCP servers. Line-delimited JSON-RPC on stdin/stdout.
import readline from "node:readline";

const reply = (id, result) => process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id, result }) + "\n");
readline.createInterface({ input: process.stdin }).on("line", (line) => {
	let msg;
	try {
		msg = JSON.parse(line);
	} catch {
		return;
	}
	if (msg.id === undefined) return; // notification
	if (msg.method === "initialize") {
		reply(msg.id, { protocolVersion: msg.params?.protocolVersion ?? "2025-06-18", capabilities: { tools: {} }, serverInfo: { name: "probe", version: "1.0.0" } });
	} else if (msg.method === "tools/list") {
		reply(msg.id, { tools: [{ name: "probe_echo", description: "Echo the input", inputSchema: { type: "object", properties: { text: { type: "string" } } } }] });
	} else if (msg.method === "tools/call") {
		reply(msg.id, { content: [{ type: "text", text: String(msg.params?.arguments?.text ?? "") }] });
	} else {
		process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id: msg.id, error: { code: -32601, message: "method not found" } }) + "\n");
	}
});
