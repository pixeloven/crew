import json
import pathlib
import tempfile
import unittest

from scripts.crew_doctor import (
    compare_runtime_catalog,
    declared_local_slots,
    inspect_installations,
    inspect_role_postures,
    load_runtime_fixture,
    parse_codex_prompt_capture,
    probe_plan,
    profile_for,
    render_doctor_report,
    validator_command,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def write_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class InstallationTruthTests(unittest.TestCase):
    def make_install_tree(self, base: pathlib.Path, pi_pin: str = "v0.34.0") -> tuple[pathlib.Path, pathlib.Path]:
        project = base / "project"
        home = base / "home"
        write_json(
            project / ".pi/settings.json",
            {"packages": [f"git:github.com/pixeloven/crew@{pi_pin}"]},
        )
        write_json(
            home / ".pi/agent/git/github.com/pixeloven/crew/.claude-plugin/plugin.json",
            {"name": "crew", "version": "0.35.0", "skills": "./skills"},
        )

        marketplace = home / ".claude/plugins/marketplaces/crew"
        write_json(
            home / ".claude/settings.json",
            {
                "extraKnownMarketplaces": {
                    "crew": {"source": {"source": "github", "repo": "pixeloven/crew"}}
                },
                "enabledPlugins": {"crew@crew": True},
            },
        )
        write_json(
            home / ".claude/plugins/known_marketplaces.json",
            {
                "crew": {
                    "source": {"source": "github", "repo": "pixeloven/crew"},
                    "installLocation": str(marketplace),
                    "lastUpdated": "2026-09-05T00:00:00Z",
                }
            },
        )
        write_json(
            marketplace / ".claude-plugin/plugin.json",
            {"name": "crew", "version": "0.30.0", "skills": "./skills"},
        )
        cache = home / ".claude/plugins/cache/crew/crew/0.30.0"
        write_json(cache / ".claude-plugin/plugin.json", {"name": "crew", "version": "0.30.0"})
        write_json(
            home / ".claude/plugins/installed_plugins.json",
            {
                "version": 2,
                "plugins": {
                    "crew@crew": [
                        {"scope": "user", "installPath": str(cache), "version": "0.30.0"},
                        {
                            "scope": "project",
                            "projectPath": "/fixture/a",
                            "installPath": str(cache),
                            "version": "0.30.0",
                        },
                        {
                            "scope": "project",
                            "projectPath": "/fixture/b",
                            "installPath": str(cache),
                            "version": "0.30.0",
                        },
                        {
                            "scope": "project",
                            "projectPath": "/fixture/c",
                            "installPath": str(cache),
                            "version": "0.30.0",
                        },
                    ]
                },
            },
        )

        codex_root = home / ".codex/plugins/cache/crew/crew/0.29.0"
        write_json(
            codex_root / ".claude-plugin/plugin.json",
            {"name": "crew", "version": "0.29.0", "skills": "./skills"},
        )
        (codex_root / "skills/doctor").mkdir(parents=True)
        config = home / ".codex/config.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            "[marketplaces.crew]\nsource = 'pixeloven/crew'\nref = 'v0.29.0'\n\n"
            "[plugins.\"crew@crew\"]\nenabled = true\n",
            encoding="utf-8",
        )
        return project, home

    def test_m1_pi_pin_and_resolved_manifest_version_are_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp), "v0.34.0")
            report = inspect_installations(project, home)
            pi = report["harnesses"]["pi"]
            self.assertEqual("present", pi["installation"]["state"])
            self.assertEqual("0.34.0", pi["configured_version"])
            self.assertEqual("0.35.0", pi["resolved_version"])
            self.assertEqual("DEGRADED", pi["status"])
            self.assertIn("fleet is silently invisible", " ".join(pi["findings"]))

            write_json(
                project / ".pi/settings.json",
                {"packages": ["git:github.com/pixeloven/crew@v0.35.0"]},
            )
            pi = inspect_installations(project, home)["harnesses"]["pi"]
            self.assertEqual("OK", pi["status"])

    def test_m2_codex_plugin_cache_is_installation_not_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp))
            codex = inspect_installations(project, home)["harnesses"]["codex"]
            self.assertEqual("present", codex["installation"]["state"])
            self.assertEqual("present", codex["enablement"]["state"])
            self.assertEqual("0.29.0", codex["resolved_version"])
            self.assertIn(".codex/plugins/cache/crew/crew/0.29.0", codex["installation"]["source"])
            self.assertEqual("unavailable", codex["capabilities"]["state"])
            self.assertEqual("OK", codex["status"])

    def test_installed_but_disabled_codex_is_degraded_not_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp))
            config = home / ".codex/config.toml"
            config.write_text(
                "[marketplaces.crew]\nsource = 'pixeloven/crew'\nref = 'v0.29.0'\n",
                encoding="utf-8",
            )
            codex = inspect_installations(project, home)["harnesses"]["codex"]
            self.assertEqual("present", codex["installation"]["state"])
            self.assertEqual("unavailable", codex["enablement"]["state"])
            self.assertEqual("DEGRADED", codex["status"])

    def test_pi_runtime_evidence_is_retained_when_settings_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            runtime = {"pi": {"source": "captured Pi catalogue", "skills": []}}
            pi = inspect_installations(base / "project", base / "home", runtime)["harnesses"]["pi"]
            self.assertEqual("unavailable", pi["installation"]["state"])
            self.assertEqual("working", pi["runtime"]["state"])
            self.assertEqual("MISSING", pi["status"])

    def test_m11_claude_registry_roles_are_not_conflated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp))
            runtime = {
                "claude": {
                    "harness": "claude",
                    "version": "0.30.0",
                    "skills": [],
                    "agents": [],
                }
            }
            claude = inspect_installations(project, home, runtime)["harnesses"]["claude"]
            self.assertEqual("0.30.0", claude["served_version"])
            self.assertEqual("0.30.0", claude["loaded_version"])
            self.assertEqual("user", claude["enabled_scope"])
            self.assertEqual(4, len(claude["registrations"]))
            self.assertEqual("DEGRADED", claude["status"])
            self.assertTrue(all("version" not in item for item in claude["marketplace_registry_records"]))

    def test_absent_harnesses_degrade_without_inventing_runtime_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            report = inspect_installations(base / "project", base / "home")
            for harness in report["harnesses"].values():
                self.assertIn(harness["runtime"]["state"], {"unavailable", "not tested"})
            self.assertEqual(1, len(report["top_actions"]))
            allowed_kinds = {"observed", "inference", "recommendation", "untested"}
            self.assertTrue(all(item["kind"] in allowed_kinds for item in report["evidence"]))
            rendered = render_doctor_report(report)
            self.assertIn("| fact | inference | recommendation | untested |", rendered)
            self.assertIn("Top action:", rendered)


class RuntimeDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.disk = [
            {
                "name": "doctor",
                "namespace": "crew",
                "source": "foundation",
                "description": "Use when checking Crew health. Report install and runtime truth.",
            },
            {
                "name": "onboarding",
                "namespace": "crew",
                "source": "foundation",
                "description": "Use when onboarding a project. Audit first and apply only with authorization.",
            },
            {
                "name": "omitted-skill",
                "namespace": "crew",
                "source": "foundation",
                "description": "Use when proving omitted discovery state.",
            },
            {
                "name": "local-bare",
                "namespace": None,
                "source": "project",
                "description": "Use when proving missing-description state.",
            },
        ]

    def test_m5_bidirectional_states_from_captured_codex_fixture(self) -> None:
        fixture = load_runtime_fixture(FIXTURES / "runtime/codex-prompt-capture.json")
        result = compare_runtime_catalog(self.disk, fixture)
        states = {row["runtime_name"]: row["state"] for row in result["entries"]}
        self.assertEqual("working", states["crew:doctor"])
        self.assertEqual("truncated", states["crew:onboarding"])
        self.assertEqual("loaded-but-undiscoverable", states["local-bare"])
        self.assertEqual("omitted", states["crew:omitted-skill"])
        self.assertEqual("present", states["runtime-only"])
        self.assertEqual("codex", result["harness"])
        self.assertNotIn("claude", result)
        self.assertNotIn("pi", result)
        self.assertEqual("DEGRADED", result["status"])

    def test_raw_codex_prompt_parser_reproduces_description_truncation(self) -> None:
        fixture = parse_codex_prompt_capture(FIXTURES / "runtime/codex-prompt-raw.json")
        result = compare_runtime_catalog(self.disk[:-1], fixture)
        states = {row["runtime_name"]: row["state"] for row in result["entries"]}
        self.assertEqual("working", states["crew:doctor"])
        self.assertEqual("truncated", states["crew:onboarding"])

    def test_namespaced_claude_collision_counts_as_two_entries(self) -> None:
        fixture = load_runtime_fixture(FIXTURES / "runtime/claude-catalog-capture.json")
        local = {
            **self.disk[0],
            "namespace": None,
            "source": "project",
            "description": "Use when checking this project's custom doctor.",
        }
        disk = [self.disk[0], local]
        result = compare_runtime_catalog(disk, fixture)
        self.assertEqual(2, result["expected_count"])
        self.assertEqual(2, result["visible_count"])
        self.assertEqual("OK", result["status"])

    def test_no_runtime_capture_is_not_tested(self) -> None:
        result = compare_runtime_catalog(self.disk, {"harness": "pi", "tested": False})
        self.assertTrue(result["entries"])
        self.assertEqual({"not tested"}, {row["state"] for row in result["entries"]})


class DerivedContractTests(unittest.TestCase):
    def test_m6_slots_are_derived_and_vocabulary_is_separate(self) -> None:
        contract = declared_local_slots(ROOT)
        self.assertEqual(
            {"agent-runtime", "platform-conventions", "protected-seams", "secret-paths", "topology"},
            set(contract["declared"]),
        )
        self.assertNotIn("litellm-access-map", contract["declared"])
        self.assertNotIn("vault-ops", contract["declared"])
        self.assertIn("litellm-access-map", contract["recommended_vocabulary"])
        self.assertIn("vault-ops", contract["recommended_vocabulary"])

    def test_m7_profile_taxonomy_has_deterministic_persona_precedence(self) -> None:
        self.assertEqual("portable", profile_for([], persona_evidence=[]))
        self.assertEqual("platform", profile_for(["github"], persona_evidence=[]))
        self.assertEqual("personas", profile_for(["github", "cluster"], persona_evidence=["openclaw manifest"]))

    def test_m8_validator_command_uses_package_root_not_consumer_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            source = FIXTURES / "consumer-valid"
            import shutil

            shutil.copytree(source, consumer)
            decoy = consumer / "scripts/check_skill_layout.py"
            decoy.parent.mkdir(parents=True)
            decoy.write_text("raise SystemExit('consumer decoy executed')\n", encoding="utf-8")
            command = validator_command(ROOT, consumer)
            self.assertEqual((ROOT / "scripts/check_skill_layout.py").resolve(), pathlib.Path(command[1]))
            import subprocess

            completed = subprocess.run(command, cwd=consumer, text=True, capture_output=True, check=False)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertNotIn("decoy", completed.stderr + completed.stdout)

    def test_m12_probe_plan_is_free_first_and_billed_requires_approval(self) -> None:
        probes = probe_plan()
        first_billed = next(i for i, probe in enumerate(probes) if probe["cost"] == "billed")
        self.assertTrue(all(probe["cost"] == "free" for probe in probes[:first_billed]))
        self.assertTrue(all(probe["approval_required"] for probe in probes[first_billed:]))
        free_commands = {probe["command"] for probe in probes if probe["cost"] == "free"}
        self.assertIn('codex debug prompt-input "hi"', free_commands)
        billed = " ".join(probe["command"] for probe in probes if probe["cost"] == "billed")
        self.assertIn("claude -p", billed)
        self.assertIn("pi -p", billed)
        self.assertIn("codex exec", billed)

    def test_m10_every_rendered_role_has_an_honest_effective_posture(self) -> None:
        rows = inspect_role_postures(ROOT)
        self.assertEqual(14, len(rows))
        lead = next(row for row in rows if row["name"] == "lead" and row["harness"] == "claude")
        self.assertTrue(lead["denied_tools"])
        self.assertIn("create and overwrite", lead["write_effect"])
        self.assertTrue(all("shell access" in row["caveat"] for row in rows))

    def test_validator_assets_are_in_the_dry_run_npm_tarball(self) -> None:
        import subprocess

        completed = subprocess.run(
            ["npm", "pack", "--dry-run", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        packed = json.loads(completed.stdout)[0]
        paths = {entry["path"] for entry in packed["files"]}
        self.assertIn("scripts/check_skill_layout.py", paths)
        self.assertIn("scripts/crew_doctor.py", paths)
        self.assertFalse(any("__pycache__" in path or path.endswith(".pyc") for path in paths))
        self.assertFalse(any(path.startswith("tests/") for path in paths))


if __name__ == "__main__":
    unittest.main()
