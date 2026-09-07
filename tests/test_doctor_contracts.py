import json
import pathlib
import tempfile
import unittest
from unittest import mock

from scripts.crew_doctor import (
    compare_runtime_catalog,
    compose_doctor_report,
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


def write_capability_skill(root: pathlib.Path, requirements: list[str]) -> None:
    skill = root / "skills/capability-fixture/SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        "---\nname: capability-fixture\ndescription: Declares fixture capabilities.\n"
        f"requires: [{', '.join(requirements)}]\n---\n",
        encoding="utf-8",
    )


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
            self.assertIn("fleet is silently invisible", " ".join(item["claim"] for item in pi["findings"]))

            write_json(
                project / ".pi/settings.json",
                {"packages": ["git:github.com/pixeloven/crew@v0.35.0"]},
            )
            pi = inspect_installations(project, home)["harnesses"]["pi"]
            self.assertEqual("OK", pi["status"])

    def test_pi_checkout_without_registration_is_installed_but_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            checkout = base / "home/.pi/agent/git/github.com/pixeloven/crew"
            write_json(
                checkout / ".claude-plugin/plugin.json",
                {"name": "crew", "version": "0.36.0", "skills": "./skills"},
            )
            pi = inspect_installations(base / "project", base / "home")["harnesses"]["pi"]
            self.assertEqual("present", pi["installation"]["state"])
            self.assertEqual("unavailable", pi["enablement"]["state"])
            self.assertEqual("DEGRADED", pi["status"])
            self.assertIn("not enabled", pi["findings"][0]["claim"])

    def test_m2_codex_plugin_cache_is_installation_not_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp))
            codex = inspect_installations(project, home)["harnesses"]["codex"]
            self.assertEqual("present", codex["installation"]["state"])
            self.assertEqual("present", codex["enablement"]["state"])
            self.assertEqual("0.29.0", codex["resolved_version"])
            self.assertIn(".codex/plugins/cache/crew/crew/0.29.0", codex["installation"]["source"])
            self.assertEqual("not tested", codex["capabilities"]["state"])
            self.assertEqual("OK", codex["status"])

    def test_capabilities_come_only_from_declared_requirements_and_supplied_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            root = home / ".codex/plugins/cache/crew/crew/0.29.0"
            write_capability_skill(root, ["external:github", "cli:gh"])

            untested = inspect_installations(project, home)["harnesses"]["codex"]
            self.assertEqual("not tested", untested["capabilities"]["state"])
            self.assertEqual(
                {"external:github", "cli:gh"},
                {item["name"] for item in untested["capability_checks"]},
            )

            evidence = {
                "codex": [
                    {
                        "name": "external:github",
                        "kind": "probe",
                        "state": "working",
                        "source": "free GitHub probe",
                    },
                    {
                        "name": "cli:gh",
                        "kind": "grant",
                        "state": "present",
                        "source": "captured tool grant",
                    },
                    {
                        "name": "consumer:litellm",
                        "kind": "grant",
                        "state": "present",
                        "source": "unrelated config",
                    },
                ]
            }
            capable = inspect_installations(project, home, capability_evidence=evidence)["harnesses"]["codex"]
            self.assertEqual("present", capable["capabilities"]["state"])
            self.assertNotIn(
                "consumer:litellm", {item["name"] for item in capable["capability_checks"]}
            )

            config = home / ".codex/config.toml"
            config.write_text(
                config.read_text(encoding="utf-8")
                + "\n[mcp_servers.litellm]\nurl = 'https://example.invalid'\n"
                "bearer_token_env_var = 'UNGRANTED_TOKEN'\n",
                encoding="utf-8",
            )
            configured_only = inspect_installations(project, home)["harnesses"]["codex"]
            self.assertEqual("not tested", configured_only["capabilities"]["state"])

            with self.assertRaisesRegex(ValueError, "source-bearing"):
                inspect_installations(
                    project,
                    home,
                    capability_evidence={
                        "codex": [
                            {
                                "name": "external:github",
                                "kind": "grant",
                                "state": "present",
                            }
                        ]
                    },
                )

            evidence["codex"][1] = {
                "name": "cli:gh",
                "kind": "probe",
                "state": "unavailable",
                "source": "free gh failure",
            }
            unavailable = inspect_installations(
                project, home, capability_evidence=evidence
            )["harnesses"]["codex"]
            self.assertEqual("unavailable", unavailable["capabilities"]["state"])
            self.assertEqual("DEGRADED", unavailable["status"])

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

    def test_empty_pi_capture_does_not_invent_working_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            runtime = {"pi": {"source": "captured Pi catalogue", "skills": []}}
            pi = inspect_installations(base / "project", base / "home", runtime)["harnesses"]["pi"]
            self.assertEqual("unavailable", pi["installation"]["state"])
            self.assertEqual("omitted", pi["runtime"]["state"])
            self.assertEqual("MISSING", pi["status"])

    def test_configuration_without_package_files_is_not_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            write_json(
                base / "project/.pi/settings.json",
                {"packages": ["git:github.com/pixeloven/crew@v0.36.0"]},
            )
            write_json(
                base / "home/.claude/settings.json",
                {
                    "extraKnownMarketplaces": {"crew": {"source": "pixeloven/crew"}},
                    "enabledPlugins": {"crew@crew": True},
                },
            )
            report = inspect_installations(base / "project", base / "home")
            self.assertEqual("unavailable", report["harnesses"]["pi"]["installation"]["state"])
            self.assertEqual("present", report["harnesses"]["pi"]["enablement"]["state"])
            self.assertEqual("unavailable", report["harnesses"]["claude"]["installation"]["state"])
            self.assertEqual("present", report["harnesses"]["claude"]["enablement"]["state"])

    def test_codex_resolves_runtime_then_configured_root_not_newest_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            newer = home / ".codex/plugins/cache/crew/crew/0.36.0"
            write_json(newer / ".claude-plugin/plugin.json", {"name": "crew", "version": "0.36.0"})
            (newer / "skills").mkdir()
            configured = inspect_installations(project, home)["harnesses"]["codex"]
            self.assertEqual("0.29.0", configured["resolved_version"])
            runtime = {
                "codex": {
                    "state": "working",
                    "skills": [
                        {
                            "name": "crew:doctor",
                            "description": "doctor",
                            "path": str(newer / "skills/doctor/SKILL.md"),
                        }
                    ],
                }
            }
            selected = inspect_installations(project, home, runtime)["harnesses"]["codex"]
            self.assertEqual("0.36.0", selected["resolved_version"])

    def test_codex_cache_is_installed_even_when_resolution_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            for version in ("0.35.0", "0.36.0"):
                root = base / f"home/.codex/plugins/cache/crew/crew/{version}"
                write_json(root / ".claude-plugin/plugin.json", {"name": "crew", "version": version})
                (root / "skills").mkdir()
            codex = inspect_installations(base / "project", base / "home")["harnesses"]["codex"]
            self.assertEqual("present", codex["installation"]["state"])
            self.assertIsNone(codex["resolved_version"])
            self.assertEqual("DEGRADED", codex["status"])

    def test_codex_configured_pin_without_matching_cache_is_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            config = home / ".codex/config.toml"
            config.write_text(
                "[marketplaces.crew]\nsource = 'pixeloven/crew'\nref = 'v0.36.0'\n\n"
                "[plugins.\"crew@crew\"]\nenabled = true\n",
                encoding="utf-8",
            )
            codex = inspect_installations(project, home)["harnesses"]["codex"]
            self.assertEqual("present", codex["installation"]["state"])
            self.assertIsNone(codex["resolved_version"])
            self.assertEqual("DEGRADED", codex["status"])
            self.assertTrue(any("no matching resolved root" in item["claim"] for item in codex["findings"]))

    def test_pi_resolution_prefers_runtime_root_then_configured_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                project / ".pi/settings.json",
                {"packages": ["git:github.com/pixeloven/crew@v0.36.0"]},
            )
            roots = {}
            for agent, version in (("a", "0.35.0"), ("b", "0.36.0")):
                root = home / f".pi/{agent}/git/github.com/pixeloven/crew"
                roots[agent] = root
                write_json(root / ".claude-plugin/plugin.json", {"name": "crew", "version": version})
            runtime = {
                "pi": {
                    "state": "working",
                    "source": "captured Pi catalogue",
                    "skills": [{"path": str(roots["b"] / "skills/doctor/SKILL.md")}],
                }
            }
            pi = inspect_installations(project, home, runtime)["harnesses"]["pi"]
            self.assertEqual("0.36.0", pi["resolved_version"])
            self.assertEqual(str(roots["b"]), pi["installation"]["source"])
            self.assertEqual([str(roots["a"])], [item["root"] for item in pi["stale_resolved_installations"]])
            self.assertFalse(any("differs from resolved" in item["claim"] for item in pi["findings"]))

    def test_version_skew_sources_follow_selected_version_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp), "v0.35.0")
            report = inspect_installations(
                project,
                home,
                {"codex": {"state": "omitted", "source": "omitted runtime capture"}},
            )
            skew = next(row for row in report["checks"] if row["check"] == "cross-harness.version-skew")
            codex_evidence = next(
                item for item in skew["evidence"] if item["claim"].startswith("codex ")
            )
            self.assertNotIn("omitted runtime capture", codex_evidence["source"])
            self.assertIn(".codex/plugins/cache/crew/crew/0.29.0", codex_evidence["source"])

    def test_non_loading_runtime_states_cannot_establish_loaded_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp), "v0.35.0")
            for state in ("omitted", "unavailable", "not-tested"):
                with self.subTest(state=state):
                    report = inspect_installations(
                        project,
                        home,
                        {
                            "pi": {
                                "state": state,
                                "version": "9.9.0",
                                "source": f"{state} capture",
                            },
                            "claude": {
                                "state": state,
                                "version": "9.9.0",
                                "source": f"{state} capture",
                            },
                            "codex": {
                                "state": state,
                                "version": "9.9.0",
                                "source": f"{state} capture",
                            },
                        },
                    )
                    self.assertTrue(
                        all(
                            harness["loaded_version"] is None
                            for harness in report["harnesses"].values()
                        )
                    )
                    facts = " ".join(row["fact"] for row in report["checks"])
                    self.assertNotIn("9.9.0", facts)

    def test_non_loading_runtime_states_cannot_select_installations_by_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"

            write_json(
                project / ".pi/settings.json",
                {"packages": ["git:github.com/pixeloven/crew@v0.35.0"]},
            )
            pi_roots = []
            for agent, version in (("a", "0.35.0"), ("b", "0.36.0")):
                root = home / f".pi/{agent}/git/github.com/pixeloven/crew"
                write_json(root / ".claude-plugin/plugin.json", {"version": version})
                pi_roots.append(root)

            write_json(
                home / ".claude/settings.json",
                {"enabledPlugins": {"crew@crew": True}},
            )
            claude_roots = []
            registrations = []
            for version in ("0.35.0", "0.36.0"):
                root = home / f".claude/plugins/cache/crew/crew/{version}"
                write_json(root / ".claude-plugin/plugin.json", {"version": version})
                claude_roots.append(root)
                registrations.append(
                    {"scope": "user", "installPath": str(root), "version": version}
                )
            write_json(
                home / ".claude/plugins/installed_plugins.json",
                {"plugins": {"crew@crew": registrations}},
            )

            codex_roots = []
            for version in ("0.35.0", "0.36.0"):
                root = home / f".codex/plugins/cache/crew/crew/{version}"
                write_json(root / ".claude-plugin/plugin.json", {"version": version})
                (root / "skills").mkdir()
                codex_roots.append(root)
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.crew]\nref = 'v0.35.0'\n"
                "[plugins.\"crew@crew\"]\nenabled = true\n",
                encoding="utf-8",
            )

            report = inspect_installations(
                project,
                home,
                {
                    "pi": {"state": "omitted", "skill_roots": [str(pi_roots[1])]},
                    "claude": {
                        "state": "unavailable",
                        "skill_roots": [str(claude_roots[1])],
                    },
                    "codex": {
                        "state": "not-tested",
                        "skill_roots": [str(codex_roots[1])],
                    },
                },
            )
            self.assertEqual("0.35.0", report["harnesses"]["pi"]["resolved_version"])
            self.assertIsNone(report["harnesses"]["claude"]["installed_version"])
            self.assertEqual("0.35.0", report["harnesses"]["codex"]["resolved_version"])
            self.assertTrue(
                all(not harness["runtime_paths"] for harness in report["harnesses"].values())
            )

    def test_grant_and_probe_evidence_are_reconciled_by_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            root = home / ".codex/plugins/cache/crew/crew/0.29.0"
            write_capability_skill(root, ["external:github"])
            codex = inspect_installations(
                project,
                home,
                capability_evidence={
                    "codex": [
                        {
                            "name": "external:github",
                            "kind": "grant",
                            "state": "present",
                            "source": "captured grant",
                        },
                        {
                            "name": "external:github",
                            "kind": "probe",
                            "state": "working",
                            "source": "free successful probe",
                        },
                    ]
                },
            )["harnesses"]["codex"]
            check = codex["capability_checks"][0]
            self.assertEqual("working", check["state"])
            self.assertEqual(
                {
                    str(root / "skills/capability-fixture/SKILL.md"),
                    "captured grant",
                    "free successful probe",
                },
                {item["source"] for item in check["evidence"]},
            )
            self.assertEqual(
                {"is declared", "grant is present", "probe is working"},
                {item["claim"].rsplit(" capability external:github ", 1)[1] for item in check["evidence"]},
            )

    def test_multiple_capability_observations_retain_distinct_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            root = home / ".codex/plugins/cache/crew/crew/0.29.0"
            write_capability_skill(root, ["external:github"])
            grant = {
                "name": "external:github",
                "kind": "grant",
                "state": "present",
                "source": "captured grant one",
            }
            evidence = {
                "codex": [
                    grant,
                    grant.copy(),
                    {**grant, "source": "captured grant two"},
                    {
                        "name": "external:github",
                        "kind": "probe",
                        "state": "working",
                        "source": "free successful probe",
                    },
                    {
                        "name": "external:github",
                        "kind": "probe",
                        "state": "unavailable",
                        "source": "free failed probe",
                    },
                ]
            }

            codex = inspect_installations(
                project,
                home,
                capability_evidence=evidence,
            )["harnesses"]["codex"]
            check = codex["capability_checks"][0]

            self.assertEqual("unavailable", check["state"])
            self.assertEqual(
                {
                    str(root / "skills/capability-fixture/SKILL.md"),
                    "captured grant one",
                    "captured grant two",
                    "free successful probe",
                    "free failed probe",
                },
                {item["source"] for item in check["evidence"]},
            )
            self.assertEqual(5, len(check["evidence"]))

    def test_configuration_read_failures_are_distinct_degraded_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            pi_settings = project / ".pi/settings.json"
            pi_settings.write_text("{broken", encoding="utf-8")
            codex_config = home / ".codex/config.toml"
            codex_config.write_text("[broken", encoding="utf-8")
            claude_settings = home / ".claude/settings.json"
            original_read_text = pathlib.Path.read_text

            def read_text(path: pathlib.Path, *args: object, **kwargs: object) -> str:
                if path == claude_settings:
                    raise PermissionError("permission denied by fixture")
                return original_read_text(path, *args, **kwargs)

            with mock.patch.object(pathlib.Path, "read_text", read_text):
                report = inspect_installations(project, home)

            pi = report["harnesses"]["pi"]
            claude = report["harnesses"]["claude"]
            codex = report["harnesses"]["codex"]
            self.assertEqual("malformed", pi["configuration_reads"][0]["state"])
            self.assertEqual("unreadable", claude["configuration_reads"][1]["state"])
            self.assertEqual("malformed", codex["configuration_reads"][0]["state"])
            for harness, source in (
                (pi, pi_settings),
                (claude, claude_settings),
                (codex, codex_config),
            ):
                self.assertEqual("DEGRADED", harness["status"])
                failure = next(
                    finding
                    for finding in harness["findings"]
                    if finding["evidence"][0]["source"] == str(source)
                )
                self.assertIn(
                    harness["configuration_reads"][
                        next(
                            index
                            for index, read in enumerate(harness["configuration_reads"])
                            if read["source"] == str(source)
                        )
                    ]["state"],
                    failure["claim"],
                )
            self.assertTrue(
                any(read["state"] == "absent" for read in pi["configuration_reads"])
            )

    def test_malformed_configured_pi_manifest_is_source_bearing_degraded_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                project / ".pi/settings.json",
                {"packages": ["git:github.com/pixeloven/crew@v0.36.0"]},
            )
            manifest = (
                home
                / ".pi/agent/git/github.com/pixeloven/crew/.claude-plugin/plugin.json"
            )
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{broken", encoding="utf-8")

            pi = inspect_installations(project, home)["harnesses"]["pi"]

            self.assertEqual("DEGRADED", pi["status"])
            self.assertEqual(
                {
                    "label": "Crew plugin manifest",
                    "state": "malformed",
                    "source": str(manifest),
                    "detail": pi["manifest_reads"][0]["detail"],
                },
                pi["manifest_reads"][0],
            )
            failure = next(
                finding for finding in pi["findings"] if "manifest is malformed" in finding["claim"]
            )
            self.assertEqual(str(manifest), failure["evidence"][0]["source"])

    def test_manifest_version_must_be_a_semver_string(self) -> None:
        for version in (None, [], "release", "v0.36.0"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                base = pathlib.Path(tmp)
                home = base / "home"
                root = home / ".codex/plugins/cache/crew/crew/0.36.0"
                manifest = root / ".claude-plugin/plugin.json"
                payload = {} if version is None else {"version": version}
                write_json(manifest, payload)
                (root / "skills").mkdir()
                config = home / ".codex/config.toml"
                config.parent.mkdir(parents=True, exist_ok=True)
                config.write_text(
                    "[plugins.\"crew@crew\"]\nenabled = true\n",
                    encoding="utf-8",
                )

                codex = inspect_installations(base / "project", home)["harnesses"]["codex"]

                self.assertEqual("unavailable", codex["installation"]["state"])
                self.assertEqual("DEGRADED", codex["status"])
                self.assertEqual("malformed", codex["manifest_reads"][0]["state"])
                failure = next(
                    finding
                    for finding in codex["findings"]
                    if "manifest is malformed" in finding["claim"]
                )
                self.assertEqual(str(manifest), failure["evidence"][0]["source"])

    def test_prerelease_and_build_versions_remain_exact_across_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            version = "0.36.0-beta.1+build.5"
            write_json(
                project / ".pi/settings.json",
                {"packages": [f"git:github.com/pixeloven/crew@v{version}"]},
            )
            pi_root = home / ".pi/agent/git/github.com/pixeloven/crew"
            write_json(pi_root / ".claude-plugin/plugin.json", {"version": version})

            codex_root = home / f".codex/plugins/cache/crew/crew/{version}"
            write_json(codex_root / ".claude-plugin/plugin.json", {"version": version})
            (codex_root / "skills").mkdir()
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                f"[marketplaces.crew]\nref = 'v{version}'\n"
                "[plugins.\"crew@crew\"]\nenabled = true\n",
                encoding="utf-8",
            )

            report = inspect_installations(project, home)

            for harness_name in ("pi", "codex"):
                harness = report["harnesses"][harness_name]
                self.assertEqual(version, harness["configured_version"])
                self.assertEqual(version, harness["resolved_version"])
                self.assertFalse(
                    any("differs" in finding["claim"] for finding in harness["findings"])
                )

    def test_non_utf8_configuration_is_reported_without_aborting_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            pi_settings = project / ".pi/settings.json"
            codex_config = home / ".codex/config.toml"
            pi_settings.write_bytes(b"\xff")
            codex_config.write_bytes(b"\xff")

            report = inspect_installations(project, home)

            for harness_name, source in (("pi", pi_settings), ("codex", codex_config)):
                harness = report["harnesses"][harness_name]
                read = next(
                    item
                    for item in harness["configuration_reads"]
                    if item["source"] == str(source)
                )
                self.assertEqual("unreadable", read["state"])
                self.assertEqual("DEGRADED", harness["status"])
                failure = next(
                    finding
                    for finding in harness["findings"]
                    if finding["evidence"][0]["source"] == str(source)
                )
                self.assertIn("unreadable", failure["claim"])

    def test_consumer_overlay_requirements_participate_in_capability_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            local_skill = project / ".agents/skills/local-platform/SKILL.md"
            local_skill.parent.mkdir(parents=True)
            local_skill.write_text(
                "---\nname: local-platform\ndescription: Declares local platform access.\n"
                "requires: [cli:local-platform]\n---\n",
                encoding="utf-8",
            )
            installation = inspect_installations(
                project,
                base / "home",
                capability_evidence={
                    "codex": [
                        {
                            "name": "cli:local-platform",
                            "kind": "probe",
                            "state": "working",
                            "source": "free local platform probe",
                        }
                    ]
                },
            )
            check = next(
                item
                for item in installation["harnesses"]["codex"]["capability_checks"]
                if item["name"] == "cli:local-platform"
            )
            self.assertEqual("working", check["state"])
            self.assertEqual(
                {str(local_skill), "free local platform probe"},
                {item["source"] for item in check["evidence"]},
            )

            report = compose_doctor_report(
                installation,
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=[],
                persona_evidence=[],
            )
            self.assertEqual("platform", report["profile"])

    def test_malformed_capability_frontmatter_is_degraded_source_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            skill = project / ".agents/skills/broken/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: broken\ndescription: Broken requirement metadata.\n"
                "requires: [cli:local-platform\n---\n",
                encoding="utf-8",
            )
            installation = inspect_installations(
                project,
                base / "home",
                capability_evidence={
                    "codex": [
                        {
                            "name": "cli:local-platform",
                            "kind": "probe",
                            "state": "working",
                            "source": "free local platform probe",
                        }
                    ]
                },
            )
            codex = installation["harnesses"]["codex"]

            self.assertEqual("DEGRADED", codex["status"])
            self.assertEqual("malformed", codex["capability_declaration_reads"][0]["state"])
            failure = next(
                finding
                for finding in codex["findings"]
                if "Capability declaration frontmatter is malformed" in finding["claim"]
            )
            self.assertEqual(str(skill), failure["evidence"][0]["source"])
            report = compose_doctor_report(
                installation,
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=[],
                persona_evidence=[],
            )
            self.assertEqual("portable", report["profile"])

    def test_structurally_invalid_claude_settings_are_degraded_not_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            settings = home / ".claude/settings.json"
            write_json(
                settings,
                {
                    "enabledPlugins": [],
                    "extraKnownMarketplaces": [],
                },
            )

            claude = inspect_installations(project, home)["harnesses"]["claude"]

            read = next(
                item for item in claude["configuration_reads"] if item["source"] == str(settings)
            )
            self.assertEqual("malformed", read["state"])
            self.assertIn("enabledPlugins must be a mapping", read["detail"])
            self.assertIn("extraKnownMarketplaces must be a mapping", read["detail"])
            self.assertEqual("DEGRADED", claude["status"])
            failure = next(
                finding
                for finding in claude["findings"]
                if finding["evidence"][0]["source"] == str(settings)
            )
            self.assertIn("settings configuration is malformed", failure["claim"])

    def test_pi_registration_requires_exact_supported_repository_identity(self) -> None:
        supported = (
            "pixeloven/crew",
            "pixeloven/crew@v0.36.0",
            "github.com/pixeloven/crew@v0.36.0",
            "github:pixeloven/crew@v0.36.0",
            "git:github.com/pixeloven/crew@v0.36.0",
        )
        for package in supported:
            with self.subTest(package=package), tempfile.TemporaryDirectory() as tmp:
                base = pathlib.Path(tmp)
                project = base / "project"
                home = base / "home"
                write_json(project / ".pi/settings.json", {"packages": [package]})
                root = home / ".pi/agent/git/github.com/pixeloven/crew"
                write_json(root / ".claude-plugin/plugin.json", {"version": "0.36.0"})
                pi = inspect_installations(project, home)["harnesses"]["pi"]
                self.assertEqual("present", pi["enablement"]["state"])

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                project / ".pi/settings.json",
                {"packages": ["git:github.com/evilpixeloven/crew@v0.36.0"]},
            )
            root = home / ".pi/agent/git/github.com/pixeloven/crew"
            write_json(root / ".claude-plugin/plugin.json", {"version": "0.36.0"})
            pi = inspect_installations(project, home)["harnesses"]["pi"]
            self.assertEqual("unavailable", pi["enablement"]["state"])
            self.assertEqual("DEGRADED", pi["status"])

    def test_claude_installed_manifest_version_participates_in_cross_harness_skew(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                project / ".pi/settings.json",
                {"packages": ["git:github.com/pixeloven/crew@v0.35.0"]},
            )
            pi_root = home / ".pi/agent/git/github.com/pixeloven/crew"
            write_json(pi_root / ".claude-plugin/plugin.json", {"name": "crew", "version": "0.35.0"})
            codex_root = home / ".codex/plugins/cache/crew/crew/0.35.0"
            write_json(
                codex_root / ".claude-plugin/plugin.json",
                {"name": "crew", "version": "0.35.0"},
            )
            (codex_root / "skills").mkdir()
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.crew]\nref = 'v0.35.0'\n"
                "[plugins.\"crew@crew\"]\nenabled = true\n",
                encoding="utf-8",
            )
            write_json(
                home / ".claude/settings.json",
                {"enabledPlugins": {"crew@crew": True}},
            )
            claude_root = home / ".claude/plugins/cache/crew/crew/0.36.0"
            manifest = claude_root / ".claude-plugin/plugin.json"
            write_json(manifest, {"name": "crew", "version": "0.36.0"})
            write_json(
                home / ".claude/plugins/installed_plugins.json",
                {
                    "plugins": {
                        "crew@crew": [
                            {
                                "scope": "user",
                                "installPath": str(claude_root),
                                "version": "0.36.0",
                            }
                        ]
                    }
                },
            )

            report = inspect_installations(project, home)
            claude = report["harnesses"]["claude"]
            self.assertIsNone(claude["served_version"])
            self.assertIsNone(claude["loaded_version"])
            self.assertEqual("0.36.0", claude["installed_version"])
            self.assertEqual(str(manifest), claude["installed_version_source"])
            self.assertEqual(
                [{
                    "root": str(claude_root),
                    "version": "0.36.0",
                    "source": str(manifest),
                    "registration_versions": ["0.36.0"],
                }],
                claude["installed_versions"],
            )
            skew = next(row for row in report["checks"] if row["check"] == "cross-harness.version-skew")
            claude_evidence = next(
                item for item in skew["evidence"] if item["claim"].startswith("claude ")
            )
            self.assertEqual("claude selected Crew version is 0.36.0", claude_evidence["claim"])
            self.assertEqual(str(manifest), claude_evidence["source"])

    def test_claude_registration_version_is_reconciled_with_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "home/.claude/plugins/cache/crew/crew/0.36.0"
            manifest = root / ".claude-plugin/plugin.json"
            write_json(manifest, {"name": "crew", "version": "0.36.0"})
            installed_path = base / "home/.claude/plugins/installed_plugins.json"
            write_json(
                installed_path,
                {
                    "plugins": {
                        "crew@crew": [
                            {"installPath": str(root), "version": "0.35.0", "scope": "user"}
                        ]
                    }
                },
            )
            claude = inspect_installations(base / "project", base / "home")["harnesses"]["claude"]
            mismatch = next(
                finding for finding in claude["findings"] if "differs from installed manifest" in finding["claim"]
            )
            self.assertEqual(
                {str(installed_path), str(manifest)},
                {item["source"] for item in mismatch["evidence"]},
            )

    def test_claude_duplicate_roots_are_order_independent_and_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                home / ".claude/settings.json",
                {"enabledPlugins": {"crew@crew": True}},
            )
            roots = []
            for version in ("0.35.0", "0.36.0"):
                root = home / f".claude/plugins/cache/crew/crew/{version}"
                write_json(root / ".claude-plugin/plugin.json", {"name": "crew", "version": version})
                roots.append(root)
            codex_root = home / ".codex/plugins/cache/crew/crew/0.35.0"
            write_json(
                codex_root / ".claude-plugin/plugin.json",
                {"name": "crew", "version": "0.35.0"},
            )
            (codex_root / "skills").mkdir()
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.crew]\nref = 'v0.35.0'\n"
                "[plugins.\"crew@crew\"]\nenabled = true\n",
                encoding="utf-8",
            )
            installed_path = home / ".claude/plugins/installed_plugins.json"
            registrations = [
                {"scope": "user", "installPath": str(root), "version": root.name}
                for root in roots
            ]

            def inspect_with(records: list[dict[str, str]]) -> dict[str, object]:
                write_json(installed_path, {"plugins": {"crew@crew": records}})
                return inspect_installations(project, home)

            forward_report = inspect_with(registrations)
            reverse_report = inspect_with(list(reversed(registrations)))
            forward = forward_report["harnesses"]["claude"]
            reverse = reverse_report["harnesses"]["claude"]
            for result in (forward, reverse):
                self.assertIsNone(result["installed_version"])
                self.assertEqual("", result["installed_version_source"])
                duplicate = next(
                    finding
                    for finding in result["findings"]
                    if "validated installed roots" in finding["claim"]
                )
                self.assertIn("selection is ambiguous", duplicate["claim"])
                self.assertEqual(
                    {
                        str(installed_path),
                        *(str(root / ".claude-plugin/plugin.json") for root in roots),
                    },
                    {item["source"] for item in duplicate["evidence"]},
                )
            for report in (forward_report, reverse_report):
                self.assertFalse(
                    any(row["check"] == "cross-harness.version-skew" for row in report["checks"])
                )
            self.assertEqual(forward["installed_versions"], reverse["installed_versions"])
            self.assertEqual(forward["installation"], reverse["installation"])

            project_registration = [
                registrations[0],
                {
                    **registrations[1],
                    "scope": "project",
                    "projectPath": str(project),
                },
            ]
            selected = inspect_with(project_registration)["harnesses"]["claude"]
            self.assertEqual("0.36.0", selected["installed_version"])
            self.assertEqual(
                str(roots[1] / ".claude-plugin/plugin.json"),
                selected["installed_version_source"],
            )

    def test_findings_retain_only_claim_supporting_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp), "v0.34.0")
            pi = inspect_installations(project, home)["harnesses"]["pi"]
            stale = next(item for item in pi["findings"] if "predates v0.35.0" in item["claim"])
            self.assertEqual(
                [{"claim": stale["claim"], "source": str(project / ".pi/settings.json")}],
                stale["evidence"],
            )

    def test_two_colliding_local_skill_names_are_not_a_crew_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            for name in ("doctor", "onboarding"):
                path = base / f"project/.agents/skills/{name}/SKILL.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"---\nname: {name}\ndescription: local\n---\n", encoding="utf-8")
            codex = inspect_installations(base / "project", base / "home")["harnesses"]["codex"]
            self.assertEqual("unavailable", codex["installation"]["state"])

    def test_m11_claude_registry_roles_are_not_conflated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp))
            runtime = {
                "claude": {
                    "harness": "claude",
                    "state": "present",
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
            report = compose_doctor_report(
                report,
                runtime_comparisons=[],
                local_slots=declared_local_slots(ROOT),
                role_postures=[],
                persona_evidence=[],
            )
            rendered = render_doctor_report(report)
            self.assertIn(
                "| check | status | fact | inference | recommendation | untested | repeatable evidence |",
                rendered,
            )
            self.assertEqual(1, rendered.count("Top action:"))
            self.assertEqual(1, rendered.count("Profile:"))
            for row in report["checks"]:
                self.assertEqual(
                    {"check", "status", "fact", "inference", "recommendation", "untested", "evidence"},
                    set(row),
                )
                for item in row["evidence"]:
                    self.assertIn(f"source: {item['source'] or 'not recorded'}", rendered)


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

    def test_duplicate_or_wrong_root_runtime_entries_degrade(self) -> None:
        disk = [{**self.disk[0], "path": "/authorized/skills/doctor/SKILL.md"}]
        fixture = {
            "harness": "codex",
            "skills": [
                {
                    "name": "crew:doctor",
                    "description": self.disk[0]["description"],
                    "path": "/stale/skills/doctor/SKILL.md",
                },
                {
                    "name": "crew:doctor",
                    "description": self.disk[0]["description"],
                    "path": "/authorized/skills/doctor/SKILL.md",
                },
            ],
        }
        result = compare_runtime_catalog(disk, fixture)
        self.assertEqual(2, result["visible_count"])
        self.assertEqual(["working", "present"], [row["state"] for row in result["entries"]])
        self.assertEqual("DEGRADED", result["status"])

    def test_structured_runtime_namespace_is_normalized_before_matching(self) -> None:
        disk = [
            {
                **self.disk[0],
                "path": "/authorized/skills/doctor/SKILL.md",
            }
        ]
        result = compare_runtime_catalog(
            disk,
            {
                "harness": "codex",
                "skills": [
                    {
                        "name": "doctor",
                        "namespace": "crew",
                        "description": self.disk[0]["description"],
                        "path": "/authorized/skills/doctor/SKILL.md",
                    }
                ],
            },
        )
        self.assertEqual("OK", result["status"])
        self.assertEqual(
            [("crew:doctor", "working")],
            [(row["runtime_name"], row["state"]) for row in result["entries"]],
        )

    def test_unrelated_catalogue_telemetry_does_not_degrade_crew_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            runtime = {
                "codex": {
                    "skills": [
                        {
                            "name": "crew:doctor",
                            "description": "Complete Crew description.",
                            "path": "/fixture/cache/crew/crew/0.36.0/skills/doctor/SKILL.md",
                        },
                        {"name": "local", "description": "short", "path": "/fixture/local/SKILL.md"},
                    ],
                    "telemetry": {"truncated_skill_descriptions": 1},
                }
            }
            codex = inspect_installations(base / "project", base / "home", runtime)["harnesses"]["codex"]
            self.assertEqual("working", codex["runtime"]["state"])


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

    def test_block_sequence_local_slots_are_derived(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            skill = root / "skills/example/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: example\ndescription: Example.\nexpects-local:\n"
                "  - topology\n  - protected-seams\n---\n",
                encoding="utf-8",
            )
            contract = declared_local_slots(root)
            self.assertEqual(["protected-seams", "topology"], contract["declared"])
            self.assertEqual([str(skill)], contract["sources"])

    def test_m7_profile_taxonomy_has_deterministic_persona_precedence(self) -> None:
        self.assertEqual("portable", profile_for([], persona_evidence=[]))
        self.assertEqual("platform", profile_for(["github"], persona_evidence=[]))
        self.assertEqual("personas", profile_for(["github", "cluster"], persona_evidence=["openclaw manifest"]))

    def test_composed_report_covers_all_inputs_with_one_profile_and_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "home/.codex/plugins/cache/crew/crew/0.36.0"
            write_json(root / ".claude-plugin/plugin.json", {"name": "crew", "version": "0.36.0"})
            write_capability_skill(root, ["external:github"])
            installation = inspect_installations(
                base / "project",
                base / "home",
                capability_evidence={
                    "codex": [
                        {
                            "name": "external:github",
                            "kind": "probe",
                            "state": "working",
                            "source": "free probe",
                        }
                    ]
                },
            )
            disk = [
                {
                    "name": "doctor",
                    "namespace": "crew",
                    "source": "foundation",
                    "description": "Doctor description.",
                    "path": "/fixture/crew/skills/doctor/SKILL.md",
                }
            ]
            runtime = compare_runtime_catalog(
                disk,
                {
                    "harness": "codex",
                    "source_command": "captured free catalogue",
                    "skills": [
                        {
                            "name": "crew:doctor",
                            "description": "Doctor description.",
                            "path": "/fixture/crew/skills/doctor/SKILL.md",
                        }
                    ],
                },
            )
            report = compose_doctor_report(
                installation,
                runtime_comparisons=[runtime],
                local_slots=declared_local_slots(ROOT),
                role_postures=inspect_role_postures(ROOT)[:1],
                persona_evidence=["consumer persona manifest"],
            )
            prefixes = {row["check"].split(".", 1)[0] for row in report["checks"]}
            self.assertTrue(
                {"runtime", "local-slots", "capability", "role", "operating-profile"} <= prefixes
            )
            self.assertEqual("personas", report["profile"])
            self.assertEqual(1, len(report["top_actions"]))
            rendered = render_doctor_report(report)
            self.assertEqual(1, rendered.count("Profile: personas"))
            self.assertEqual(1, rendered.count("Top action:"))

    def test_capability_states_have_distinct_report_meanings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "home/.codex/plugins/cache/crew/crew/0.36.0"
            write_json(root / ".claude-plugin/plugin.json", {"name": "crew", "version": "0.36.0"})
            write_capability_skill(root, ["configured", "proven", "failed", "skipped"])
            installation = inspect_installations(
                base / "project",
                base / "home",
                capability_evidence={
                    "codex": [
                        {"name": "configured", "kind": "grant", "state": "present", "source": "config"},
                        {"name": "proven", "kind": "probe", "state": "working", "source": "free probe"},
                        {"name": "failed", "kind": "probe", "state": "unavailable", "source": "free probe"},
                    ]
                },
            )
            report = compose_doctor_report(
                installation,
                runtime_comparisons=[],
                local_slots=declared_local_slots(ROOT),
                role_postures=inspect_role_postures(ROOT),
                persona_evidence=[],
            )
            rows = {
                row["check"].removeprefix("capability.codex."): row
                for row in report["checks"]
                if row["check"].startswith("capability.codex.")
            }
            self.assertEqual(("OK", ""), (rows["configured"]["status"], rows["configured"]["recommendation"]))
            self.assertEqual(("OK", ""), (rows["proven"]["status"], rows["proven"]["recommendation"]))
            self.assertEqual("DEGRADED", rows["failed"]["status"])
            self.assertTrue(rows["failed"]["recommendation"])
            self.assertEqual(("N/A", rows["skipped"]["fact"]), (rows["skipped"]["status"], rows["skipped"]["untested"]))
            self.assertEqual("platform", report["profile"])

    def test_role_readiness_requires_complete_expected_fleets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)

            def role_rows(postures: list[dict[str, object]]) -> list[dict[str, object]]:
                report = compose_doctor_report(
                    inspect_installations(base / "project", base / "home"),
                    runtime_comparisons=[],
                    local_slots=declared_local_slots(ROOT),
                    role_postures=postures,
                    persona_evidence=[],
                )
                return [row for row in report["checks"] if row["check"].startswith("role.")]

            complete = role_rows(inspect_role_postures(ROOT))
            self.assertEqual(14, len(complete))
            self.assertEqual({"OK"}, {row["status"] for row in complete})

            missing = role_rows([])
            self.assertEqual(14, len(missing))
            self.assertEqual({"DEGRADED"}, {row["status"] for row in missing})
            self.assertTrue(all("missing" in row["fact"] for row in missing))

            incomplete = role_rows([{"name": "lead", "harness": "claude"}])
            lead = next(row for row in incomplete if row["check"] == "role.claude.lead")
            self.assertEqual("DEGRADED", lead["status"])
            self.assertIn("incomplete", lead["fact"])

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
