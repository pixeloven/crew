"""Contract tests for Crew's experimental pi agent extension (pi-extension/index.ts).

They run the real pi CLI against a fake model and a fake MCP server, so they make no
billed calls. Point PI_CLI at pi's CLI script (for example
node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js); without it the
tests skip, unless CREW_REQUIRE_PI=1 makes a missing pi a failure, as CI does.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "pi-extension"
PI_CLI = os.environ.get("PI_CLI", "")
NODE = shutil.which("node")
REQUIRED = os.environ.get("CREW_REQUIRE_PI") == "1"
PI_SUBAGENTS_TOOLS = {"subagent", "subagent_supervisor", "bg_wait", "contact_supervisor"}
MCP_TOOL = "mcp__probe__probe_echo"
REPLY = re.compile(r"ROLE=(\S+) MODEL=(\S+) TOOLS=(\S*)")


def roles() -> dict[str, dict]:
    """The rendered pi roles, read the way the extension reads them."""
    import yaml

    found = {}
    for path in sorted((ROOT / "pi-agents").glob("*.md")):
        meta = yaml.safe_load(path.read_text(encoding="utf-8").split("---\n", 2)[1])
        excluded = meta.get("excludeTools") or ""
        meta["excluded"] = {t.strip() for t in str(excluded).split(",") if t.strip()}
        found[meta["name"]] = meta
    return found


def marker(name: str) -> str:
    """The `You are <Name> —` marker the fake model reports for a role's prompt."""
    body = (ROOT / "pi-agents" / f"{name}.md").read_text(encoding="utf-8")
    return re.search(r"You are (\w+) —", body).group(1)


@unittest.skipUnless(PI_CLI or REQUIRED, "set PI_CLI to run the pi extension contract tests")
class PiExtensionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (PI_CLI and pathlib.Path(PI_CLI).is_file() and NODE):
            raise AssertionError(f"CREW_REQUIRE_PI=1 but PI_CLI={PI_CLI!r} or node is missing")
        cls.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(cls.tmp.name)
        cls.llm = subprocess.Popen(
            [NODE, str(FIXTURES / "fake-llm.mjs")], stdout=subprocess.PIPE, text=True
        )
        port = int(cls.llm.stdout.readline())
        agent_dir = base / "agent"
        agent_dir.mkdir()
        (agent_dir / "models.json").write_text(json.dumps({
            "providers": {
                "fake": {
                    "baseUrl": f"http://127.0.0.1:{port}/v1",
                    "api": "openai-completions",
                    "apiKey": "fake",
                    "models": [{"id": "fake-model", "reasoning": True}],
                }
            }
        }))
        (agent_dir / "mcp.json").write_text(json.dumps({
            "mcpServers": {
                "probe": {
                    "command": NODE,
                    "args": [str(FIXTURES / "fake-mcp.mjs")],
                    "exposure": "direct",
                }
            }
        }))
        # Crew installed as a local package, exactly as a consumer installs it.
        (agent_dir / "settings.json").write_text(json.dumps({
            "defaultProvider": "fake",
            "defaultModel": "fake-model",
            "packages": [str(ROOT)],
        }))
        cls.project = base / "project"
        cls.project.mkdir()
        cls.elsewhere = base / "elsewhere"
        cls.elsewhere.mkdir()
        cls.env = {
            **os.environ,
            "PI_CODING_AGENT_DIR": str(agent_dir),
            "PI_OFFLINE": "1",
            "PI_SKIP_VERSION_CHECK": "1",
            "PI_TELEMETRY": "0",
            "CREW_PI_AGENT": "1",
        }
        for key in ("CREW_AGENT_DEPTH", "CREW_AGENT_TIMEOUT_SECONDS"):
            cls.env.pop(key, None)
        cls.roles = roles()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.llm.kill()
        cls.llm.wait()
        cls.tmp.cleanup()

    def pi(self, prompt: str, env: dict[str, str] | None = None, *flags: str):
        """Run one non-interactive operator turn; return its messages."""
        proc = subprocess.run(
            [NODE, PI_CLI, "--mode", "json", "-p", "--no-session", *flags, prompt],
            cwd=self.project,
            env={**self.env, **(env or {})},
            capture_output=True,
            text=True,
            timeout=120,
        )
        messages = []
        for line in proc.stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "message_end" and event.get("message"):
                messages.append(event["message"])
        if not messages:
            self.fail(f"pi produced no messages (exit {proc.returncode}): {proc.stderr[-2000:]}")
        return messages

    @staticmethod
    def text(message: dict) -> str:
        return "".join(c.get("text", "") for c in message.get("content", []) if c.get("type") == "text")

    def operator_tools(self, env: dict[str, str] | None = None) -> list[str]:
        reply = self.text(self.pi("hello", env)[-1])
        return REPLY.search(reply).group(3).split(",")

    def dispatch(self, role: str, task: str, env: dict[str, str] | None = None, *flags: str) -> dict:
        """The crew_agent tool result for one dispatch from the operator session."""
        messages = self.pi(f"DISPATCH {role} :: {task}", env, *flags)
        results = [m for m in messages if m.get("role") == "toolResult"]
        self.assertEqual(1, len(results), "expected exactly one crew_agent call")
        self.assertEqual("crew_agent", results[0].get("toolName"))
        return results[0]

    def test_without_the_opt_in_nothing_is_registered(self) -> None:
        self.assertNotIn("crew_agent", self.operator_tools({"CREW_PI_AGENT": ""}))

    def test_opt_in_registers_crew_agent_beside_mcp(self) -> None:
        tools = self.operator_tools()
        self.assertIn("crew_agent", tools)
        self.assertIn(MCP_TOOL, tools)

    def test_each_role_gets_its_posture_mcp_and_the_session_model(self) -> None:
        default_tools = set(self.operator_tools({"CREW_PI_AGENT": ""})) - {MCP_TOOL}
        for name, meta in self.roles.items():
            with self.subTest(role=name):
                result = self.dispatch(name, "report your tools")
                self.assertFalse(result.get("isError"), self.text(result))
                role, model, tools = REPLY.search(self.text(result)).groups()
                self.assertEqual(marker(name), role)
                self.assertEqual("fake-model", model)
                expected = default_tools - meta["excluded"] - PI_SUBAGENTS_TOOLS
                if meta.get("allowNestedSubagents"):
                    expected |= {"crew_agent"}
                self.assertEqual(expected | {MCP_TOOL}, set(tools.split(",")))

    def test_role_inherits_the_session_thinking_level(self) -> None:
        for level in ("low", "high"):
            with self.subTest(thinking=level):
                reply = self.text(self.dispatch("reviewer", "report", None, "--thinking", level))
                self.assertIn(f"ROLE={marker('reviewer')} ", reply)
                self.assertIn(f"THINKING={level}", reply)

    def test_lead_dispatches_a_worker_and_the_result_returns_up_two_levels(self) -> None:
        reply = self.text(self.dispatch("lead", "DISPATCH reviewer :: review it"))
        self.assertIn(f"ROLE={marker('lead')} ", reply)
        nested = re.search(r"CHILD=\[(.*)\]", reply).group(1)
        role, _, tools = REPLY.search(nested).groups()
        self.assertEqual(marker("reviewer"), role)
        self.assertNotIn("crew_agent", tools.split(","))

    def test_unknown_role_is_a_tool_error_naming_the_roster(self) -> None:
        result = self.dispatch("nosuch", "anything")
        self.assertTrue(result.get("isError"))
        self.assertIn('Unknown Crew role "nosuch"', self.text(result))
        self.assertIn("reviewer", self.text(result))

    def test_child_failure_is_a_tool_error(self) -> None:
        result = self.dispatch("reviewer", "FAIL")
        self.assertTrue(result.get("isError"))
        self.assertIn("crew reviewer failed", self.text(result))

    def test_timeout_kills_the_child_and_reports_it(self) -> None:
        result = self.dispatch("reviewer", "SLOW", {"CREW_AGENT_TIMEOUT_SECONDS": "3"})
        self.assertTrue(result.get("isError"))
        self.assertIn("timed out", self.text(result))

    def test_large_output_is_bounded_and_spilled_to_a_file(self) -> None:
        text = self.text(self.dispatch("reviewer", "BIG 60000"))
        found = re.search(r"\[truncated at 51200 bytes; full output: (\S+)\]", text)
        self.assertIsNotNone(found, text[-300:])
        spilled = pathlib.Path(found.group(1))
        try:
            self.assertEqual(60000, len(spilled.read_text(encoding="utf-8")))
        finally:
            shutil.rmtree(spilled.parent, ignore_errors=True)

    def test_project_overlay_applies_only_in_a_trusted_project(self) -> None:
        overlay = self.project / ".pi" / "agents" / "reviewer.md"
        overlay.parent.mkdir(parents=True)
        overlay.write_text(
            "---\nname: reviewer\npackage: crew\ndescription: overlay\n---\n\nYou are Overlay — a project role.\n",
            encoding="utf-8",
        )
        try:
            trusted = self.text(self.dispatch("reviewer", "report", None, "--approve"))
            untrusted = self.text(self.dispatch("reviewer", "report", None, "--no-approve"))
        finally:
            shutil.rmtree(self.project / ".pi")
        self.assertIn("ROLE=Overlay ", trusted)
        self.assertIn(f"ROLE={marker('reviewer')} ", untrusted)
        self.assertIn("was not used: the project is not trusted", untrusted)

    def test_child_inherits_the_session_project_trust_and_never_more(self) -> None:
        settings = self.project / ".pi" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({"extensions": [str(FIXTURES / "project-tool.mjs")]}), encoding="utf-8")
        try:
            trusted = self.text(self.dispatch("lead", "DISPATCH reviewer :: report", None, "--approve"))
            untrusted = self.text(self.dispatch("lead", "DISPATCH reviewer :: report", None, "--no-approve"))
        finally:
            shutil.rmtree(self.project / ".pi")
        for reply, expected in ((trusted, True), (untrusted, False)):
            nested = re.search(r"CHILD=\[(.*)\]", reply).group(1)
            for tools in (REPLY.search(reply).group(3), REPLY.search(nested).group(3)):
                self.assertEqual(expected, "project_probe" in tools.split(","), reply)

    def test_overlay_outside_the_session_project_is_never_used(self) -> None:
        outside = self.elsewhere / ".pi" / "agents" / "reviewer.md"
        above = self.project.parent / ".pi" / "agents" / "reviewer.md"
        for overlay in (outside, above):
            overlay.parent.mkdir(parents=True)
            overlay.write_text(
                "---\nname: reviewer\npackage: crew\ndescription: overlay\n---\n\nYou are Overlay — a project role.\n",
                encoding="utf-8",
            )
        try:
            elsewhere = self.text(self.dispatch(f"reviewer IN {self.elsewhere}", "report", None, "--approve"))
            here = self.text(self.dispatch("reviewer", "report", None, "--approve"))
        finally:
            shutil.rmtree(self.elsewhere / ".pi")
            shutil.rmtree(self.project.parent / ".pi")
        self.assertIn(f"ROLE={marker('reviewer')} ", elsewhere)
        self.assertIn(f"{outside} was not used: it is outside the session's project", elsewhere)
        self.assertIn(f"ROLE={marker('reviewer')} ", here)
        self.assertNotIn("was not used", here)


if __name__ == "__main__":
    unittest.main()
