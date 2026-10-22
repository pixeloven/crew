import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import crew_inventory
from scripts.crew_doctor import compose_doctor_report, inspect_installations, render_doctor_report
from scripts.crew_inventory import (
    build_inventory,
    capability_map_rows,
    gaps,
    inventory_digest,
    load_observations,
    parse_capability_map,
    render_capability_map,
)
from scripts.onboarding_contract import (
    ApplyAuthorizationRequired,
    HostApplyAuthorizationSignal,
    capability_map_proposal,
    merge_capability_map,
    pack_slot_proposals,
    resolve_mode,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/inventory"
SCRIPT = ROOT / "scripts/crew_inventory.py"
AGENT_RUNTIME_STUB = (ROOT / "templates/local-skills/agent-runtime.md").read_text(encoding="utf-8")
ON_PATH = {"gh": "/fake/bin/gh", "make": "/fake/bin/make", "shellcheck": "/fake/bin/shellcheck"}
MCP_FIELDS = {"name", "transport", "scope", "source", "state", "command", "tools", "tools_source"}


def fake_which(name: str) -> str | None:
    return ON_PATH.get(name)


class Fixture:
    """A temporary copy of the fake homes with @HOME@/@PROJECT@ made absolute."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self._tmp.name).resolve()
        shutil.copytree(FIXTURES, self.base, dirs_exist_ok=True)
        self.home = self.base / "home"
        self.project = self.base / "project"
        for path in self.base.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                path.write_text(
                    text.replace("@HOME@", str(self.home)).replace("@PROJECT@", str(self.project)),
                    encoding="utf-8",
                )

    def build(self, **kwargs):
        kwargs.setdefault("which", fake_which)
        kwargs.setdefault("now", "2026-10-21T12:00:00Z")
        return build_inventory(self.project, self.home, **kwargs)

    def observations(self):
        return load_observations(self.base / "observations/claude-session.json")

    def close(self) -> None:
        self._tmp.cleanup()


class InventoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)

    def servers(self, inventory, harness):
        return {server["name"]: server for server in inventory["harnesses"][harness]["mcp_servers"]}


class SecretTests(InventoryTestCase):
    def test_no_secret_reaches_any_output_format(self) -> None:
        inventory = self.fixture.build(observations=self.fixture.observations(), clis=["jq"])
        outputs = [
            json.dumps(inventory),
            render_capability_map(inventory),
            crew_inventory.render_gaps(inventory),
        ]
        for output in outputs:
            self.assertNotIn("canary", output)
        for fmt in ("json", "map", "gaps"):
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--project", str(self.fixture.project),
                 "--home", str(self.fixture.home), "--format", fmt,
                 "--observations", str(self.fixture.base / "observations/claude-session.json")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn("canary", result.stdout + result.stderr)

    def test_mcp_records_carry_only_name_transport_scope_command_basename_and_source(self) -> None:
        inventory = self.fixture.build()
        for harness in ("claude", "codex"):
            for server in inventory["harnesses"][harness]["mcp_servers"]:
                self.assertLessEqual(set(server), MCP_FIELDS, server)
        claude = self.servers(inventory, "claude")
        self.assertEqual("npx", claude["tracker"]["command"])
        self.assertEqual("notes-server", claude["notes"]["command"])
        self.assertIsNone(claude["localdb"]["command"])
        self.assertEqual("http", claude["localdb"]["transport"])
        self.assertEqual("sse", claude["tracker-cloud"]["transport"])
        codex = self.servers(inventory, "codex")
        self.assertEqual("http", codex["remote"]["transport"])
        self.assertEqual("projtool", codex["projtool"]["command"])

    def test_pi_package_userinfo_is_stripped(self) -> None:
        inventory = self.fixture.build()
        ids = [plugin["id"] for plugin in inventory["harnesses"]["pi"]["plugins"]]
        self.assertIn("git:https://github.com/acme/pi-git@v1.0.0", ids)
        self.assertNotIn("canary", json.dumps(ids))


class PackageRefTests(unittest.TestCase):
    def test_userinfo_query_and_fragment_never_survive(self) -> None:
        _safe_package_ref = crew_inventory._safe_package_ref

        for spec, expected in [
            ("git:user:canary-token@github.com/acme/pack@v1", "git:github.com/acme/pack@v1"),
            ("git:github.com/acme/pack?token=canary#frag", "git:github.com/acme/pack"),
            ("git:canary@host", "git:host"),
            ("npm:@scope/pkg@1.2.3", "npm:@scope/pkg@1.2.3"),
            ("git:https://user:canary@github.com/acme/pack.git?x=canary", "git:https://github.com/acme/pack.git"),
        ]:
            self.assertEqual(expected, _safe_package_ref(spec))
            self.assertNotIn("canary", _safe_package_ref(spec))


class HarnessObservationTests(InventoryTestCase):
    def test_claude_plugins_scopes_and_mcp_config(self) -> None:
        inventory = self.fixture.build()
        claude = inventory["harnesses"]["claude"]
        plugins = {plugin["id"]: plugin for plugin in claude["plugins"]}
        self.assertEqual({"toolkit@acme"}, set(plugins), "another project's plugin must not apply")
        self.assertEqual("1.2.0", plugins["toolkit@acme"]["version"])
        self.assertTrue(plugins["toolkit@acme"]["enabled"])
        servers = self.servers(inventory, "claude")
        self.assertEqual("project", servers["tracker"]["scope"])
        self.assertEqual("user", servers["notes"]["scope"])
        self.assertEqual("local", servers["localdb"]["scope"])
        self.assertEqual("plugin:toolkit@acme", servers["tracker-cloud"]["scope"])
        self.assertEqual("disabled", servers["retired"]["state"])
        self.assertNotIn("other-project-only", servers)
        self.assertTrue(all(server["tools"] is None for server in servers.values()))
        roots = {root["scope"] for root in claude["skill_roots"]}
        self.assertEqual({"user", "plugin:toolkit@acme"}, roots, "a root that does not exist is not listed")

    def test_codex_reads_trusted_project_config_and_enabled_plugins(self) -> None:
        inventory = self.fixture.build()
        servers = self.servers(inventory, "codex")
        self.assertEqual("project", servers["projtool"]["scope"])
        self.assertEqual("plugin:helper@acme", servers["helper-mcp"]["scope"])
        self.assertEqual("disabled", servers["parked"]["state"])
        self.assertEqual(["helper@acme"], [plugin["id"] for plugin in inventory["harnesses"]["codex"]["plugins"]])
        config = self.fixture.home / ".codex/config.toml"
        config.write_text(config.read_text().replace('trust_level = "trusted"', 'trust_level = "untrusted"'))
        self.assertNotIn("projtool", self.servers(self.fixture.build(), "codex"))

    def test_pi_mcp_is_not_observable_and_codex_mcp_list_is_marked_unverified(self) -> None:
        inventory = self.fixture.build()
        self.assertEqual([], inventory["harnesses"]["pi"]["mcp_servers"])
        whats = {entry["what"]: entry["why"] for entry in inventory["not_observable"]}
        self.assertIn("pi MCP servers", whats)
        self.assertIn("unverified", whats["codex MCP tool lists"])
        self.assertIn("claude mcp list", whats["claude MCP tool lists"])
        pi_skills = {skill["name"] for skill in inventory["skills"]}
        self.assertIn("pi-pack-linear", pi_skills)

    def test_skills_record_requires_and_capabilities_name_their_declarers(self) -> None:
        inventory = self.fixture.build(clis=["jq"])
        skills = {skill["name"]: skill for skill in inventory["skills"]}
        self.assertEqual(["cli:gh", "mcp:tracker"], skills["toolkit-gh"]["requires"])
        capabilities = inventory["capabilities"]
        self.assertIn("toolkit-gh", capabilities["cli:gh"]["declared_by"])
        self.assertIn("--cli", capabilities["cli:jq"]["declared_by"])
        self.assertEqual("absent", capabilities["cli:jq"]["providers"][0]["state"])
        self.assertEqual("/fake/bin/gh", capabilities["cli:gh"]["providers"][0]["path"])
        self.assertIn("cli:make", capabilities, "workflow run: first tokens are candidate CLIs")
        self.assertIn("cli:shellcheck", capabilities)
        self.assertIn("cli:python3", capabilities)
        self.assertIn("cli:tar", capabilities)
        for not_a_cli in ("cli:echo", "cli:if", "cli:FOO=bar", "cli:import", "cli:bad", "cli:PY",
                          "cli:show", "cli:vendored-arg"):
            self.assertNotIn(not_a_cli, capabilities)
        self.assertIn("cli:gh", capabilities)
        tracker = [p for p in capabilities["mcp:tracker"]["providers"] if p["state"] == "present"]
        self.assertEqual(["tracker"], sorted({p["name"] for p in tracker}))


class ProbeTests(InventoryTestCase):
    def test_no_subprocess_runs_without_probe_versions(self) -> None:
        with mock.patch("subprocess.run", side_effect=AssertionError("subprocess.run")), mock.patch(
            "subprocess.Popen", side_effect=AssertionError("subprocess.Popen")
        ):
            inventory = self.fixture.build(observations=self.fixture.observations())
        self.assertIsNone(inventory["capabilities"]["cli:gh"]["providers"][0]["version"])

    def test_probe_versions_records_a_version_but_not_in_the_digest(self) -> None:
        calls = []

        def runner(command):
            calls.append(command)
            return "gh version 2.81.0 (2026-10-01)"

        plain = self.fixture.build()
        probed = self.fixture.build(probe_versions=True, version_runner=runner, now="2027-01-01T00:00:00Z")
        self.assertIn(["/fake/bin/gh", "--version"], calls)
        self.assertEqual("gh version 2.81.0 (2026-10-01)", probed["capabilities"]["cli:gh"]["providers"][0]["version"])
        self.assertEqual(plain["map_digest"], probed["map_digest"])
        self.assertEqual(inventory_digest(plain), plain["map_digest"])


    def test_workflow_only_clis_are_inventoried_but_never_probed(self) -> None:
        calls = []

        def runner(command):
            calls.append(command)
            return "v1"

        inventory = self.fixture.build(probe_versions=True, version_runner=runner)
        workflow_only = [
            name for name, entry in inventory["capabilities"].items()
            if name.startswith("cli:") and entry["declared_by"]
            and all(source.startswith("workflow:") for source in entry["declared_by"])
        ]
        self.assertTrue(workflow_only, "fixture should declare a CLI only from a workflow")
        probed = {pathlib.Path(command[0]).name for command in calls}
        for name in workflow_only:
            self.assertNotIn(name.split(":", 1)[1], probed)

    def test_a_binary_inside_the_project_is_never_probed(self) -> None:
        calls = []
        planted = str(self.fixture.project / "bin" / "gh")
        inventory = self.fixture.build(
            probe_versions=True,
            version_runner=lambda command: calls.append(command) or "v1",
            which=lambda name: planted if name == "gh" else fake_which(name),
            clis=["gh"],
        )
        self.assertNotIn([planted, "--version"], calls)
        self.assertIsNone(inventory["capabilities"]["cli:gh"]["providers"][0]["version"])


class ObservationTests(InventoryTestCase):
    def test_observations_raise_to_present_never_working(self) -> None:
        inventory = self.fixture.build(observations=self.fixture.observations())
        servers = self.servers(inventory, "claude")
        self.assertEqual(["create_issue", "list_issues"], servers["tracker"]["tools"])
        self.assertEqual("session", servers["tracker"]["tools_source"])
        self.assertEqual("session", servers["connector-docs"]["scope"])
        self.assertEqual("present", servers["connector-docs"]["state"])
        states = {
            provider["state"]
            for capability in inventory["capabilities"].values()
            for provider in capability["providers"]
        }
        self.assertNotIn("working", states)
        self.assertNotIn("working", json.dumps(inventory["harnesses"]))
        observed = inventory["observations"][0]
        self.assertTrue(observed["source"].endswith("claude-session.json"))
        self.assertNotIn("env", observed["mcp_servers"][0])

    def test_observation_can_raise_an_absent_cli_to_present(self) -> None:
        observation = {
            "schema_version": 1, "harness": "codex", "captured_at": "2026-10-21T00:00:00Z",
            "source_command": "in-session", "capabilities": [{"name": "cli:jq", "state": "working"}],
        }
        inventory = self.fixture.build(observations=load_observations(io.StringIO(json.dumps(observation))))
        states = [provider["state"] for provider in inventory["capabilities"]["cli:jq"]["providers"]]
        self.assertIn("present", states)

    def test_invalid_observations_and_project_exit_2(self) -> None:
        with self.assertRaises(ValueError):
            load_observations(self.fixture.base / "observations/invalid.json")
        for extra in (
            ["--observations", str(self.fixture.base / "observations/invalid.json")],
            ["--observations", str(self.fixture.base / "observations/missing.json")],
        ):
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--project", str(self.fixture.project),
                 "--home", str(self.fixture.home), *extra],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(2, result.returncode, result.stdout)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--project", str(self.fixture.base / "nope")],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(2, result.returncode)

    def test_observations_read_from_stdin(self) -> None:
        capture = (self.fixture.base / "observations/claude-session.json").read_text()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--project", str(self.fixture.project),
             "--home", str(self.fixture.home), "--observations", "-"],
            input=capture, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("stdin", json.loads(result.stdout)["observations"][0]["source"])


class DigestAndGapTests(InventoryTestCase):
    def test_digest_ignores_paths_versions_and_time_but_tracks_state(self) -> None:
        first = self.fixture.build(now="2026-10-21T00:00:00Z")
        second = self.fixture.build(now="2030-01-01T00:00:00Z", which=lambda name: {
            key: f"/elsewhere/{key}" for key in ON_PATH
        }.get(name))
        self.assertEqual(first["map_digest"], second["map_digest"])
        self.assertTrue(first["map_digest"].startswith("sha256:"))
        third = self.fixture.build(which=lambda name: None)
        self.assertNotEqual(first["map_digest"], third["map_digest"])

    def test_gaps_label_fact_and_inference(self) -> None:
        inventory = self.fixture.build(clis=["jq"])
        found = {(gap["kind"], gap["name"]): gap for gap in gaps(inventory)}
        self.assertEqual("fact", found[("capability-unprovided", "cli:jq")]["label"])
        self.assertEqual("inference", found[("capability-unprovided", "external:linear")]["label"])
        self.assertIn(("capability-unprovided", "external:github"), found,
                      "a pi package hosted on github.com does not provide external:github")
        self.assertEqual("fact", found[("slot-unfilled", "agent-runtime")]["label"])
        self.assertNotIn(("slot-unfilled", "topology"), found)
        self.assertEqual("inference", found[("tool-unskilled", "cli:make")]["label"])
        self.assertNotIn(("tool-unskilled", "cli:gh"), found)
        self.assertEqual("inference", found[("mcp-unskilled", "search")]["label"])
        self.assertNotIn(("mcp-unskilled", "tracker"), found)
        self.assertTrue(all(gap["evidence"] for gap in found.values()))
        self.assertEqual(sorted(found), sorted((gap["kind"], gap["name"]) for gap in inventory["gaps"]))

    def test_pack_declared_slots_are_inventoried_with_their_owner(self) -> None:
        toolkit = self.fixture.home / ".claude/plugins/cache/acme/toolkit/1.2.0"
        (toolkit / "slots.txt").write_text("tracker-fields\n", encoding="utf-8")
        skill = toolkit / "skills/toolkit-gh/SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace(
                "requires: [cli:gh, mcp:tracker]\n",
                "requires: [cli:gh, mcp:tracker, plugin:crew@>=0.38.0]\nexpects-local: [tracker-fields]\n",
            ),
            encoding="utf-8",
        )
        inventory = self.fixture.build()
        self.assertIsNone(inventory["slots"]["slots"]["tracker-fields"]["effective"])
        self.assertEqual({"tracker-fields": ["toolkit"]}, inventory["slots"]["pack_slots"])
        found = {(gap["kind"], gap["name"]): gap for gap in inventory["gaps"]}
        self.assertIn("pack `toolkit`", found[("slot-unfilled", "tracker-fields")]["evidence"])
        self.assertEqual([], inventory["slots"]["collisions"])

    def test_onboarding_proposes_a_pack_slot_fill_from_the_inventory(self) -> None:
        toolkit = self.fixture.home / ".claude/plugins/cache/acme/toolkit/1.2.0"
        (toolkit / "slots.txt").write_text("tracker-fields\n", encoding="utf-8")
        stub = toolkit / "templates/local-skills/tracker-fields.md"
        stub.parent.mkdir(parents=True)
        stub.write_text(
            "---\nname: <project>-tracker-fields\n---\n\n## Fields\n\n"
            "<!-- crew:discoverable capability=mcp:tracker -->\n\n> **▸ Fill:** fields.\n",
            encoding="utf-8",
        )
        skill = toolkit / "skills/toolkit-gh/SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace(
                "requires: [cli:gh, mcp:tracker]\n",
                "requires: [cli:gh, mcp:tracker, plugin:crew@>=0.38.0]\nexpects-local: [tracker-fields]\n",
            ),
            encoding="utf-8",
        )
        proposals = {
            proposal["slot"]: proposal
            for proposal in pack_slot_proposals(self.fixture.build(), resolve_mode(), crew_root=ROOT)
        }
        tracker = proposals["tracker-fields"]
        self.assertEqual(("create", "toolkit", str(stub)), (tracker["action"], tracker["pack"], tracker["stub"]))
        self.assertEqual([{"heading": "Fields", "capability": "mcp:tracker", "capabilities": ["mcp:tracker"]}], tracker["discoverable_sections"])
        self.assertNotIn("agent-runtime", proposals, "capability_map_proposal creates that fill")

    def test_engine_writes_nothing(self) -> None:
        def snapshot():
            return {
                str(path): (path.stat().st_mtime_ns, path.stat().st_size)
                for path in self.fixture.base.rglob("*")
            }

        before = snapshot()
        for fmt in ("json", "map", "gaps"):
            subprocess.run(
                [sys.executable, str(SCRIPT), "--project", str(self.fixture.project),
                 "--home", str(self.fixture.home), "--format", fmt],
                capture_output=True, text=True, check=True,
            )
        self.assertEqual(before, snapshot())

    def test_schema_shape(self) -> None:
        inventory = self.fixture.build()
        self.assertEqual("crew-inventory/1", inventory["schema"])
        for key in ("generated_at", "crew_version", "project_root", "harnesses", "packs", "skills",
                    "capabilities", "slots", "observations", "not_observable", "gaps", "map_digest"):
            self.assertIn(key, inventory)
        self.assertEqual({"claude", "codex", "pi"}, set(inventory["harnesses"]))


def write_runtime_skill(project: pathlib.Path, body: str) -> pathlib.Path:
    path = project / ".agents/skills/demo-agent-runtime/SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


class CapabilityMapMergeTests(InventoryTestCase):
    def test_template_carries_an_empty_capabilities_section(self) -> None:
        self.assertIn("## Capabilities", AGENT_RUNTIME_STUB)
        self.assertIn("<!-- crew:capability-map begin -->", AGENT_RUNTIME_STUB)
        self.assertIn("<!-- crew:capability-map end -->", AGENT_RUNTIME_STUB)

    def test_merge_appends_a_section_when_markers_are_missing_and_is_idempotent(self) -> None:
        inventory = self.fixture.build()
        text = "---\nname: demo-agent-runtime\n---\n\n## Runtime architecture\n\nArgo.\n"
        merged = merge_capability_map(text, inventory, today="2026-10-21")
        self.assertTrue(merged.startswith(text.rstrip("\n")))
        self.assertIn("## Capabilities", merged)
        self.assertIn(f"digest={inventory['map_digest']} generated=2026-10-21", merged)
        self.assertIn("| Capability | Provider | Kind | State | Fallback (operator command) |", merged)
        self.assertIn("| `cli:gh` | gh | cli | present | ▸ Fill |", merged)
        self.assertEqual(merged, merge_capability_map(merged, inventory, today="2026-10-21"))
        self.assertEqual(merged, merge_capability_map(merged, inventory, today="2027-03-01"),
                         "an unchanged map does not churn its date")

    def test_merge_fills_empty_template_markers_and_keeps_operator_fallbacks(self) -> None:
        inventory = self.fixture.build()
        merged = merge_capability_map(AGENT_RUNTIME_STUB, inventory, today="2026-10-21")
        self.assertEqual(1, merged.count("## Capabilities"))
        edited = merged.replace("| `cli:gh` | gh | cli | present | ▸ Fill |",
                                "| `cli:gh` | gh | cli | present | `gh auth login` then retry |")
        changed = self.fixture.build(which=lambda name: None)
        remerged = merge_capability_map(edited, changed, today="2026-10-22")
        self.assertIn("| `cli:gh` | — | cli | absent | `gh auth login` then retry |", remerged)
        self.assertIn(f"digest={changed['map_digest']} generated=2026-10-22", remerged)

    def test_vanished_capability_stays_absent_and_is_listed_for_removal(self) -> None:
        inventory = self.fixture.build()
        merged = merge_capability_map(AGENT_RUNTIME_STUB, inventory, today="2026-10-21")
        legacy = merged.replace(
            "<!-- crew:capability-map end -->",
            "| `cli:retired-tool` | retired-tool | cli | present | ask ops |\n<!-- crew:capability-map end -->",
        )
        remerged = merge_capability_map(legacy, inventory, today="2026-10-21")
        self.assertIn("| `cli:retired-tool` | retired-tool | cli | absent | ask ops |", remerged)
        recorded = parse_capability_map(remerged)
        self.assertEqual(["cli:retired-tool"], recorded["removals"])

    def test_proposal_audit_reports_a_diff_and_apply_creates_the_fill(self) -> None:
        inventory = self.fixture.build()
        audit = capability_map_proposal(inventory, resolve_mode(), template_text=AGENT_RUNTIME_STUB,
                                        today="2026-10-21")
        self.assertEqual("create", audit["action"])
        self.assertEqual(
            str(self.fixture.project / ".agents/skills/project-agent-runtime/SKILL.md"), audit["target"]
        )
        self.assertIn("+## Capabilities", audit["diff"])
        self.assertIsNone(audit["text"])
        with self.assertRaises(ApplyAuthorizationRequired):
            resolve_mode(explicit_apply=True)
        signal = HostApplyAuthorizationSignal(invocation_id="run-1", host_verified=True)
        apply = capability_map_proposal(
            inventory, resolve_mode(explicit_apply=True, invocation_id="run-1", authorization=signal),
            template_text=AGENT_RUNTIME_STUB, today="2026-10-21",
        )
        self.assertIn("name: project-agent-runtime", apply["text"])
        self.assertFalse((self.fixture.project / ".agents/skills/project-agent-runtime").exists(),
                         "the contract returns text; it never writes")

    def test_proposal_merges_into_an_existing_local_fill(self) -> None:
        path = write_runtime_skill(self.fixture.project, "---\nname: demo-agent-runtime\n---\n\n## Commands\n\nrun.\n")
        inventory = self.fixture.build()
        audit = capability_map_proposal(inventory, resolve_mode(), template_text=AGENT_RUNTIME_STUB,
                                        today="2026-10-21")
        self.assertEqual("merge", audit["action"])
        self.assertEqual(str(path), audit["target"])
        current = merge_capability_map(path.read_text(), inventory, today="2026-10-21")
        path.write_text(current)
        self.assertEqual("unchanged", capability_map_proposal(
            self.fixture.build(), resolve_mode(), template_text=AGENT_RUNTIME_STUB, today="2026-10-21"
        )["action"])


class DoctorCapabilityMapTests(InventoryTestCase):
    def doctor_row(self, inventory):
        installation = inspect_installations(self.fixture.project, self.fixture.home)
        report = compose_doctor_report(
            installation,
            runtime_comparisons=[],
            local_slots={"declared": [], "recommended_vocabulary": [], "sources": [], "reads": []},
            role_postures=[],
            persona_evidence=[],
            inventory=inventory,
        )
        render_doctor_report(report)
        rows = [row for row in report["checks"] if row["check"] == "inventory.capability-map"]
        return rows

    def test_no_inventory_no_row(self) -> None:
        self.assertEqual([], self.doctor_row(None))

    def test_missing_when_no_markers(self) -> None:
        (row,) = self.doctor_row(self.fixture.build())
        self.assertEqual("MISSING", row["status"])
        self.assertIn("onboarding", row["recommendation"])
        write_runtime_skill(self.fixture.project, AGENT_RUNTIME_STUB)
        (row,) = self.doctor_row(self.fixture.build())
        self.assertEqual("MISSING", row["status"], "empty template markers are not a map")

    def test_ok_when_digest_matches_and_degraded_naming_rows_otherwise(self) -> None:
        inventory = self.fixture.build()
        path = write_runtime_skill(self.fixture.project, merge_capability_map(
            AGENT_RUNTIME_STUB, inventory, today="2026-10-21"))
        (row,) = self.doctor_row(self.fixture.build())
        self.assertEqual("OK", row["status"], row)
        self.assertEqual(str(path), row["evidence"][0]["source"])
        (row,) = self.doctor_row(self.fixture.build(which=lambda name: None))
        self.assertEqual("DEGRADED", row["status"])
        self.assertIn("differs on this machine", row["fact"])
        self.assertIn("cli:gh", row["fact"])
        self.assertIn("onboarding", row["recommendation"])
        self.assertEqual(path.read_text(), merge_capability_map(
            AGENT_RUNTIME_STUB, inventory, today="2026-10-21"), "Doctor never edits the slot")


class CapabilityRowsTests(InventoryTestCase):
    def test_rows_are_keyed_by_capability_and_sorted(self) -> None:
        rows = capability_map_rows(self.fixture.build())
        names = [row["capability"] for row in rows]
        self.assertEqual(sorted(names), names)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual({"capability", "provider", "kind", "state"}, set(rows[0]))


if __name__ == "__main__":
    unittest.main()
