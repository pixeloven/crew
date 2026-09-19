import json
import pathlib
import shutil
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
    if (
        path.as_posix().endswith("/.claude-plugin/plugin.json")
        and isinstance(value, dict)
        and "version" in value
        and "name" not in value
    ):
        value = {"name": "crew", **value}
    if (
        path.as_posix().endswith("/.claude-plugin/plugin.json")
        and isinstance(value, dict)
        and value.get("name") == "crew"
        and "skills" not in value
    ):
        value = {**value, "skills": "./skills"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    if (
        path.as_posix().endswith("/.claude-plugin/plugin.json")
        and isinstance(value, dict)
        and value.get("name") == "crew"
        and isinstance(value.get("version"), str)
    ):
        (path.parent.parent / "skills").mkdir(exist_ok=True)


def write_capability_skill(root: pathlib.Path, requirements: list[str]) -> None:
    skill = root / "skills/capability-fixture/SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        "---\nname: capability-fixture\ndescription: Declares fixture capabilities.\n"
        f"requires: [{', '.join(requirements)}]\n---\n",
        encoding="utf-8",
    )


def write_claude_marketplace_identity(home: pathlib.Path) -> None:
    write_json(
        home / ".claude/plugins/known_marketplaces.json",
        {
            "pixeloven": {
                "source": {"source": "github", "repo": "pixeloven/crew"},
            }
        },
    )


def write_codex_marketplace_identity(home: pathlib.Path) -> None:
    config = home / ".codex/config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\n",
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

        marketplace = home / ".claude/plugins/marketplaces/pixeloven"
        write_json(
            home / ".claude/settings.json",
            {
                "extraKnownMarketplaces": {
                    "pixeloven": {"source": {"source": "github", "repo": "pixeloven/crew"}}
                },
                "enabledPlugins": {"crew@pixeloven": True},
            },
        )
        write_json(
            home / ".claude/plugins/known_marketplaces.json",
            {
                "pixeloven": {
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
        cache = home / ".claude/plugins/cache/pixeloven/crew/0.30.0"
        write_json(cache / ".claude-plugin/plugin.json", {"name": "crew", "version": "0.30.0"})
        write_json(
            home / ".claude/plugins/installed_plugins.json",
            {
                "version": 2,
                "plugins": {
                    "crew@pixeloven": [
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

        codex_root = home / ".codex/plugins/cache/pixeloven/crew/0.29.0"
        write_json(
            codex_root / ".claude-plugin/plugin.json",
            {"name": "crew", "version": "0.29.0", "skills": "./skills"},
        )
        (codex_root / "skills/doctor").mkdir(parents=True)
        config = home / ".codex/config.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\nref = 'v0.29.0'\n\n"
            "[plugins.\"crew@pixeloven\"]\nenabled = true\n",
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

    def test_pi_prerelease_pin_predates_the_stable_role_discovery_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp), "v0.35.0-beta.1")

            pi = inspect_installations(project, home)["harnesses"]["pi"]

            self.assertEqual("DEGRADED", pi["status"])
            stale = next(item for item in pi["findings"] if "predates v0.35.0" in item["claim"])
            self.assertEqual(str(project / ".pi/settings.json"), stale["evidence"][0]["source"])

    def test_pi_requires_a_v_prefixed_semver_release_tag_for_healthy_reconciliation(self) -> None:
        for package, configured_ref in (
            ("git:github.com/pixeloven/crew", None),
            ("git:github.com/pixeloven/crew@main", "main"),
            ("git:github.com/pixeloven/crew@release/next", "release/next"),
            ("git:github.com/pixeloven/crew@0.36.0", "0.36.0"),
        ):
            with self.subTest(package=package), tempfile.TemporaryDirectory() as tmp:
                base = pathlib.Path(tmp)
                project = base / "project"
                home = base / "home"
                settings = project / ".pi/settings.json"
                write_json(settings, {"packages": [package]})
                root = home / ".pi/agent/git/github.com/pixeloven/crew"
                write_json(root / ".claude-plugin/plugin.json", {"version": "0.36.0"})

                pi = inspect_installations(project, home)["harnesses"]["pi"]

                self.assertEqual("present", pi["enablement"]["state"])
                self.assertEqual(configured_ref, pi["configured_ref"])
                self.assertIsNone(pi["configured_version"])
                self.assertEqual("0.36.0", pi["resolved_version"])
                self.assertEqual("DEGRADED", pi["status"])
                self.assertEqual(package, pi["registrations"][0]["package"])
                finding = next(
                    item
                    for item in pi["findings"]
                    if "not a published v-prefixed SemVer tag" in item["claim"]
                )
                self.assertEqual(str(settings), finding["evidence"][0]["source"])

        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp), "v0.35.0")
            pi = inspect_installations(project, home)["harnesses"]["pi"]
            self.assertEqual("v0.35.0", pi["configured_ref"])
            self.assertEqual("0.35.0", pi["configured_version"])
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
            self.assertIn(".codex/plugins/cache/pixeloven/crew/0.29.0", codex["installation"]["source"])
            self.assertEqual("not tested", codex["capabilities"]["state"])
            self.assertEqual("OK", codex["status"])

    def test_capabilities_come_only_from_declared_requirements_and_supplied_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            root = home / ".codex/plugins/cache/pixeloven/crew/0.29.0"
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
            installation = inspect_installations(project, home, capability_evidence=evidence)
            capable = installation["harnesses"]["codex"]
            self.assertEqual("present", capable["capabilities"]["state"])
            self.assertNotIn(
                "consumer:litellm", {item["name"] for item in capable["capability_checks"]}
            )
            github = next(
                item for item in capable["capability_checks"] if item["name"] == "external:github"
            )
            self.assertEqual("package", github["ownership"])
            report = compose_doctor_report(
                installation,
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=[],
                persona_evidence=[],
            )
            self.assertEqual("portable", report["profile"])

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

    def test_capability_evidence_boundary_rejects_malformed_shapes(self) -> None:
        malformed = (
            ([], "collection must be a mapping"),
            ({"codxe": []}, "unsupported harness codxe"),
            ({"codex": None}, "observations must be a sequence"),
            ({"codex": [None]}, "observation 0 must be a mapping"),
            (
                {"codex": [{"name": "cli:gh", "kind": "probe", "state": "working"}]},
                "observation 0 must be source-bearing",
            ),
        )
        for evidence, detail in malformed:
            with self.subTest(evidence=evidence), tempfile.TemporaryDirectory() as tmp:
                base = pathlib.Path(tmp)
                with self.assertRaises(ValueError) as raised:
                    inspect_installations(
                        base / "project",
                        base / "home",
                        capability_evidence=evidence,
                    )
                self.assertIn(detail, str(raised.exception))

    def test_installed_but_disabled_codex_is_degraded_not_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp))
            config = home / ".codex/config.toml"
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\nref = 'v0.29.0'\n",
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

    def test_forged_working_state_cannot_promote_unrelated_runtime_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            runtime = {
                "codex": {
                    "state": "working",
                    "version": "9.9.0",
                    "source": "captured Codex catalogue",
                    "skills": [
                        {
                            "name": "unrelated",
                            "description": "Unrelated skill.",
                            "path": "/unrelated/skills/example/SKILL.md",
                        }
                    ],
                }
            }

            codex = inspect_installations(
                base / "project", base / "home", runtime
            )["harnesses"]["codex"]

            self.assertEqual("omitted", codex["runtime"]["state"])
            self.assertIsNone(codex["loaded_version"])

    def test_validated_root_preserves_loaded_but_undiscoverable_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            root = home / ".codex/plugins/cache/pixeloven/crew/0.29.0"
            runtime = {
                "codex": {
                    "state": "loaded-but-undiscoverable",
                    "source": "captured Codex catalogue",
                    "skill_roots": [str(root / "skills")],
                    "skills": [],
                }
            }

            codex = inspect_installations(project, home, runtime)["harnesses"]["codex"]

            self.assertEqual("loaded-but-undiscoverable", codex["runtime"]["state"])
            self.assertEqual("DEGRADED", codex["status"])
            finding = next(
                item
                for item in codex["findings"]
                if "loaded-but-undiscoverable" in item["claim"]
            )
            self.assertEqual("captured Codex catalogue", finding["evidence"][0]["source"])

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
                    "extraKnownMarketplaces": {"pixeloven": {"source": "pixeloven/crew"}},
                    "enabledPlugins": {"crew@pixeloven": True},
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
            newer = home / ".codex/plugins/cache/pixeloven/crew/0.36.0"
            write_json(newer / ".claude-plugin/plugin.json", {"name": "crew", "version": "0.36.0"})
            (newer / "skills").mkdir(exist_ok=True)
            configured = inspect_installations(project, home)["harnesses"]["codex"]
            self.assertEqual("0.29.0", configured["resolved_version"])
            runtime = {
                "codex": {
                    "state": "working",
                    "source": "captured Codex catalogue for cache selection",
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

    def test_runtime_root_selection_uses_only_crew_attributed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            roots = {}
            for version in ("0.35.0", "0.36.0"):
                root = home / f".codex/plugins/cache/pixeloven/crew/{version}"
                write_json(root / ".claude-plugin/plugin.json", {"version": version})
                (root / "skills").mkdir(exist_ok=True)
                roots[version] = root
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\n"
                "ref = 'v0.35.0'\n[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )
            runtime = {
                "codex": {
                    "state": "working",
                    "source": "captured Codex catalogue",
                    "skills": [
                        {
                            "name": "crew:doctor",
                            "description": "Crew Doctor.",
                            "path": str(roots["0.36.0"] / "skills/doctor/SKILL.md"),
                        },
                        {
                            "name": "unrelated",
                            "description": "Unrelated.",
                            "path": str(roots["0.35.0"] / "skills/unrelated/SKILL.md"),
                        },
                    ],
                }
            }

            codex = inspect_installations(project, home, runtime)["harnesses"]["codex"]

            self.assertEqual("0.36.0", codex["resolved_version"])
            self.assertEqual(
                [str(roots["0.36.0"] / "skills/doctor/SKILL.md")],
                codex["runtime_paths"],
            )

    def test_multiple_runtime_roots_remain_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            roots = []
            for version in ("0.35.0", "0.36.0"):
                root = home / f".codex/plugins/cache/pixeloven/crew/{version}"
                write_json(root / ".claude-plugin/plugin.json", {"version": version})
                (root / "skills").mkdir(exist_ok=True)
                roots.append(root)
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\n"
                "ref = 'v0.35.0'\n[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )
            runtime = {
                "codex": {
                    "state": "working",
                    "source": "captured Codex catalogue",
                    "skills": [
                        {
                            "name": f"crew:{name}",
                            "description": name,
                            "path": str(root / f"skills/{name}/SKILL.md"),
                        }
                        for name, root in zip(("doctor", "onboarding"), roots)
                    ],
                }
            }

            codex = inspect_installations(project, home, runtime)["harnesses"]["codex"]

            self.assertIsNone(codex["resolved_version"])
            self.assertEqual({str(root) for root in roots}, set(codex["runtime_root_matches"]))
            self.assertTrue(
                any("match multiple accepted roots" in finding["claim"] for finding in codex["findings"])
            )

    def test_stale_or_ambiguous_roots_do_not_declare_active_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            roots = {
                version: home / f".codex/plugins/cache/pixeloven/crew/{version}"
                for version in ("0.35.0", "0.36.0")
            }
            for version, root in roots.items():
                write_json(root / ".claude-plugin/plugin.json", {"version": version})
                (root / "skills/doctor").mkdir(parents=True)
            write_capability_skill(roots["0.35.0"], ["cli:local-platform"])
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\n"
                "ref = 'v0.36.0'\n[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )
            evidence = {
                "codex": [
                    {
                        "name": "cli:local-platform",
                        "kind": "probe",
                        "state": "working",
                        "source": "free local platform probe",
                    }
                ]
            }

            resolved = inspect_installations(
                project,
                home,
                runtime_fixtures={
                    "codex": {
                        "source": "captured Codex catalogue",
                        "skills": [
                            {
                                "name": "crew:doctor",
                                "description": "Doctor.",
                                "path": str(
                                    roots["0.36.0"] / "skills/doctor/SKILL.md"
                                ),
                            }
                        ],
                    }
                },
                capability_evidence=evidence,
            )
            codex = resolved["harnesses"]["codex"]
            self.assertEqual([str(roots["0.36.0"])], codex["resolved_package_roots"])
            self.assertNotIn(
                "cli:local-platform",
                {item["name"] for item in codex["capability_checks"]},
            )
            report = compose_doctor_report(
                resolved,
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=[],
                persona_evidence=[],
            )
            self.assertEqual("portable", report["profile"])

            ambiguous = inspect_installations(
                project,
                home,
                runtime_fixtures={
                    "codex": {
                        "source": "captured Codex catalogue",
                        "skills": [
                            {
                                "name": f"crew:{name}",
                                "description": name,
                                "path": str(root / f"skills/{name}/SKILL.md"),
                            }
                            for name, root in zip(("doctor", "onboarding"), roots.values())
                        ],
                    }
                },
                capability_evidence=evidence,
            )["harnesses"]["codex"]
            self.assertEqual([], ambiguous["resolved_package_roots"])
            self.assertNotIn(
                "cli:local-platform",
                {item["name"] for item in ambiguous["capability_checks"]},
            )
            self.assertEqual("DEGRADED", ambiguous["status"])

    def test_loaded_vendored_root_blocks_configured_cache_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            vendored = project / ".agents/skills"
            shutil.copytree(ROOT / "skills", vendored)
            runtime = {
                "codex": {
                    "state": "working",
                    "version": "0.29.0",
                    "source": "captured Codex catalogue",
                    "skills": [
                        {
                            "name": "crew:doctor",
                            "description": "Crew Doctor.",
                            "path": str(vendored / "doctor/SKILL.md"),
                        }
                    ],
                }
            }

            codex = inspect_installations(project, home, runtime)["harnesses"]["codex"]

            self.assertIsNone(codex["resolved_version"])
            self.assertIsNone(codex["loaded_version"])
            self.assertEqual([str(vendored)], codex["runtime_root_matches"])
            self.assertTrue(
                any("vendored Crew version is unknown" in finding["claim"] for finding in codex["findings"])
            )

    def test_captured_runtime_versions_are_validated_against_selected_root(self) -> None:
        for captured_version, expected_claim in (
            (["0.29.0"], "must be a pure SemVer string"),
            ({"version": "0.29.0"}, "must be a pure SemVer string"),
            ("v0.29.0", "must be a pure SemVer string"),
            ("9.9.0", "differs from selected root version 0.29.0"),
        ):
            with self.subTest(captured_version=captured_version), tempfile.TemporaryDirectory() as tmp:
                base = pathlib.Path(tmp)
                project, home = self.make_install_tree(base)
                root = home / ".codex/plugins/cache/pixeloven/crew/0.29.0"
                runtime = {
                    "codex": {
                        "state": "working",
                        "version": captured_version,
                        "source": "captured Codex catalogue",
                        "skills": [
                            {
                                "name": "crew:doctor",
                                "description": "Crew Doctor.",
                                "path": str(root / "skills/doctor/SKILL.md"),
                            }
                        ],
                    }
                }

                codex = inspect_installations(project, home, runtime)["harnesses"]["codex"]

                self.assertIsNone(codex["loaded_version"])
                self.assertEqual("0.29.0", codex["resolved_version"])
                self.assertEqual("DEGRADED", codex["status"])
                finding = next(
                    finding
                    for finding in codex["findings"]
                    if expected_claim in finding["claim"]
                )
                self.assertEqual("captured Codex catalogue", finding["evidence"][0]["source"])

    def test_codex_cache_is_installed_even_when_resolution_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            for version in ("0.35.0", "0.36.0"):
                root = base / f"home/.codex/plugins/cache/pixeloven/crew/{version}"
                write_json(root / ".claude-plugin/plugin.json", {"name": "crew", "version": version})
                (root / "skills").mkdir(exist_ok=True)
            write_codex_marketplace_identity(base / "home")
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
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\nref = 'v0.36.0'\n\n"
                "[plugins.\"crew@pixeloven\"]\nenabled = true\n",
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
                    "skills": [
                        {
                            "name": "doctor",
                            "path": str(roots["b"] / "skills/doctor/SKILL.md"),
                        }
                    ],
                }
            }
            pi = inspect_installations(project, home, runtime)["harnesses"]["pi"]
            self.assertEqual("0.36.0", pi["resolved_version"])
            self.assertEqual(str(roots["b"]), pi["installation"]["source"])
            self.assertEqual([str(roots["a"])], [item["root"] for item in pi["stale_resolved_installations"]])
            self.assertFalse(any("differs from resolved" in item["claim"] for item in pi["findings"]))

    def test_pi_duplicate_configured_versions_remain_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                project / ".pi/settings.json",
                {"packages": ["git:github.com/pixeloven/crew@v0.36.0"]},
            )
            roots = []
            for agent in ("a", "b"):
                root = home / f".pi/{agent}/git/github.com/pixeloven/crew"
                write_json(
                    root / ".claude-plugin/plugin.json",
                    {"name": "crew", "version": "0.36.0"},
                )
                roots.append(root)
            write_capability_skill(roots[0], ["cli:local-platform"])

            pi = inspect_installations(
                project,
                home,
                capability_evidence={
                    "pi": [
                        {
                            "name": "cli:local-platform",
                            "kind": "probe",
                            "state": "working",
                            "source": "free local platform probe",
                        }
                    ]
                },
            )["harnesses"]["pi"]

            self.assertIsNone(pi["resolved_version"])
            self.assertEqual([], pi["resolved_package_roots"])
            self.assertEqual({str(root) for root in roots}, set(pi["package_roots"]))
            self.assertNotIn(
                "cli:local-platform",
                {item["name"] for item in pi["capability_checks"]},
            )
            self.assertEqual("DEGRADED", pi["status"])

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
            self.assertIn(".codex/plugins/cache/pixeloven/crew/0.29.0", codex_evidence["source"])

    def test_non_loading_runtime_states_cannot_establish_loaded_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp), "v0.35.0")
            for state in ("omitted", "unavailable", "not tested"):
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
                {"enabledPlugins": {"crew@pixeloven": True}},
            )
            claude_roots = []
            registrations = []
            for version in ("0.35.0", "0.36.0"):
                root = home / f".claude/plugins/cache/pixeloven/crew/{version}"
                write_json(root / ".claude-plugin/plugin.json", {"version": version})
                claude_roots.append(root)
                registrations.append(
                    {"scope": "user", "installPath": str(root), "version": version}
                )
            write_json(
                home / ".claude/plugins/installed_plugins.json",
                {"plugins": {"crew@pixeloven": registrations}},
            )
            write_claude_marketplace_identity(home)

            codex_roots = []
            for version in ("0.35.0", "0.36.0"):
                root = home / f".codex/plugins/cache/pixeloven/crew/{version}"
                write_json(root / ".claude-plugin/plugin.json", {"version": version})
                (root / "skills").mkdir(exist_ok=True)
                codex_roots.append(root)
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\nref = 'v0.35.0'\n"
                "[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )

            report = inspect_installations(
                project,
                home,
                {
                    "pi": {
                        "state": "omitted",
                        "source": "Pi catalogue omitted by the test harness",
                        "skill_roots": [str(pi_roots[1])],
                    },
                    "claude": {
                        "state": "unavailable",
                        "source": "Claude runtime unavailable to the test harness",
                        "skill_roots": [str(claude_roots[1])],
                    },
                    "codex": {
                        "state": "not tested",
                        "source": "Codex runtime not tested by this scenario",
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
            root = home / ".codex/plugins/cache/pixeloven/crew/0.29.0"
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
            root = home / ".codex/plugins/cache/pixeloven/crew/0.29.0"
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
            self.assertEqual(
                "unreadable",
                next(
                    read["state"]
                    for read in claude["configuration_reads"]
                    if read["source"] == str(claude_settings)
                ),
            )
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
                root = home / ".codex/plugins/cache/pixeloven/crew/0.36.0"
                manifest = root / ".claude-plugin/plugin.json"
                payload = {} if version is None else {"version": version}
                write_json(manifest, payload)
                (root / "skills").mkdir(exist_ok=True)
                config = home / ".codex/config.toml"
                config.parent.mkdir(parents=True, exist_ok=True)
                config.write_text(
                    "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\n"
                    "[plugins.\"crew@pixeloven\"]\nenabled = true\n",
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

    def test_non_crew_manifests_cannot_establish_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                project / ".pi/settings.json",
                {"packages": ["git:github.com/pixeloven/crew@v0.36.0"]},
            )
            pi_root = home / ".pi/agent/git/github.com/pixeloven/crew"
            write_json(
                pi_root / ".claude-plugin/plugin.json",
                {"name": "other-plugin", "version": "0.36.0"},
            )

            write_json(
                home / ".claude/settings.json",
                {
                    "extraKnownMarketplaces": {
                        "pixeloven": {"source": "pixeloven/crew"}
                    },
                    "enabledPlugins": {"crew@pixeloven": True},
                },
            )
            claude_root = home / ".claude/plugins/marketplaces/pixeloven"
            write_json(
                claude_root / ".claude-plugin/plugin.json",
                {"name": "other-plugin", "version": "0.36.0"},
            )
            write_json(
                home / ".claude/plugins/known_marketplaces.json",
                {
                    "pixeloven": {
                        "source": {"source": "github", "repo": "pixeloven/crew"},
                        "installLocation": str(claude_root),
                    }
                },
            )

            codex_root = home / ".codex/plugins/cache/pixeloven/crew/0.36.0"
            write_json(
                codex_root / ".claude-plugin/plugin.json",
                {"name": "other-plugin", "version": "0.36.0"},
            )
            (codex_root / "skills").mkdir(exist_ok=True)
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\n"
                "ref = 'v0.36.0'\n[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )

            report = inspect_installations(project, home)

            for harness, root in (
                ("pi", pi_root),
                ("claude", claude_root),
                ("codex", codex_root),
            ):
                with self.subTest(harness=harness):
                    result = report["harnesses"][harness]
                    self.assertEqual("unavailable", result["installation"]["state"])
                    self.assertEqual([], result["package_roots"])
                    self.assertEqual("DEGRADED", result["status"])
                    read = next(
                        item
                        for item in result["manifest_reads"]
                        if item["source"] == str(root / ".claude-plugin/plugin.json")
                    )
                    self.assertEqual("malformed", read["state"])
                    self.assertIn("name must identify Crew", read["detail"])

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

            codex_root = home / f".codex/plugins/cache/pixeloven/crew/{version}"
            write_json(codex_root / ".claude-plugin/plugin.json", {"version": version})
            (codex_root / "skills").mkdir(exist_ok=True)
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                f"[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\nref = 'v{version}'\n"
                "[plugins.\"crew@pixeloven\"]\nenabled = true\n",
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
            evidence = {
                harness: [
                    {
                        "name": "cli:local-platform",
                        "kind": "probe",
                        "state": "working",
                        "source": f"free {harness} local platform probe",
                    }
                ]
                for harness in ("claude", "codex", "pi")
            }
            installation = inspect_installations(
                project,
                base / "home",
                capability_evidence=evidence,
            )
            for harness in ("codex", "pi"):
                check = next(
                    item
                    for item in installation["harnesses"][harness]["capability_checks"]
                    if item["name"] == "cli:local-platform"
                )
                self.assertEqual("working", check["state"])
                self.assertEqual(
                    {str(local_skill), f"free {harness} local platform probe"},
                    {item["source"] for item in check["evidence"]},
                )
            self.assertNotIn(
                "cli:local-platform",
                {
                    item["name"]
                    for item in installation["harnesses"]["claude"]["capability_checks"]
                },
            )

            claude_skill = project / ".claude/skills/local-platform/SKILL.md"
            claude_skill.parent.mkdir(parents=True)
            claude_skill.write_text(local_skill.read_text(encoding="utf-8"), encoding="utf-8")
            installation = inspect_installations(
                project,
                base / "home",
                capability_evidence=evidence,
            )
            claude_check = next(
                item
                for item in installation["harnesses"]["claude"]["capability_checks"]
                if item["name"] == "cli:local-platform"
            )
            self.assertEqual("working", claude_check["state"])
            self.assertEqual(
                {str(claude_skill), "free claude local platform probe"},
                {item["source"] for item in claude_check["evidence"]},
            )

            report = compose_doctor_report(
                installation,
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=[],
                persona_evidence=[],
            )
            self.assertEqual("platform", report["profile"])

    def test_pi_project_overlay_replaces_package_capability_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base, "v0.35.0")
            package_root = home / ".pi/agent/git/github.com/pixeloven/crew"
            write_capability_skill(package_root, ["cli:package-only"])
            overlay = project / ".agents/skills/capability-fixture/SKILL.md"
            overlay.parent.mkdir(parents=True)
            overlay.write_text(
                "---\nname: capability-fixture\ndescription: Project capability override.\n"
                "requires: [cli:project-only]\n---\n",
                encoding="utf-8",
            )
            pi = inspect_installations(
                project,
                home,
                capability_evidence={
                    "pi": [
                        {
                            "name": name,
                            "kind": "probe",
                            "state": "working",
                            "source": f"free {name} probe",
                        }
                        for name in ("cli:package-only", "cli:project-only")
                    ]
                },
            )["harnesses"]["pi"]

            self.assertEqual(
                {"cli:project-only"},
                {item["name"] for item in pi["capability_checks"]},
            )
            self.assertEqual(
                {str(overlay), "free cli:project-only probe"},
                {item["source"] for item in pi["capability_checks"][0]["evidence"]},
            )

    def test_claude_symlinked_project_skill_retains_project_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            target = project / ".agents/skills/local-platform"
            skill = target / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: local-platform\ndescription: Local platform capability.\n"
                "requires: [cli:local-platform]\n---\n",
                encoding="utf-8",
            )
            link = project / ".claude/skills/local-platform"
            link.parent.mkdir(parents=True)
            link.symlink_to(target, target_is_directory=True)

            installation = inspect_installations(
                project,
                base / "home",
                capability_evidence={
                    "claude": [
                        {
                            "name": "cli:local-platform",
                            "kind": "probe",
                            "state": "working",
                            "source": "free local platform probe",
                        }
                    ]
                },
            )
            capability = next(
                item
                for item in installation["harnesses"]["claude"]["capability_checks"]
                if item["name"] == "cli:local-platform"
            )
            self.assertEqual("project", capability["ownership"])
            self.assertEqual(str(link / "SKILL.md"), capability["evidence"][0]["source"])
            report = compose_doctor_report(
                installation,
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=[],
                persona_evidence=[],
            )
            self.assertEqual("platform", report["profile"])

    def test_vendored_foundation_and_local_capability_origins_remain_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            vendored = project / ".agents/skills"
            shutil.copytree(ROOT / "skills", vendored)
            evidence = {
                "codex": [
                    {
                        "name": "external:github",
                        "kind": "probe",
                        "state": "working",
                        "source": "free GitHub probe",
                    }
                ]
            }

            foundation_installation = inspect_installations(
                project,
                base / "home",
                capability_evidence=evidence,
            )
            github = next(
                item
                for item in foundation_installation["harnesses"]["codex"]["capability_checks"]
                if item["name"] == "external:github"
            )
            self.assertEqual("package", github["ownership"])
            foundation_report = compose_doctor_report(
                foundation_installation,
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=[],
                persona_evidence=[],
            )
            self.assertEqual("portable", foundation_report["profile"])

            local_skill = vendored / "local-platform/SKILL.md"
            local_skill.parent.mkdir()
            local_skill.write_text(
                "---\nname: local-platform\ndescription: Local capability.\n"
                "requires: [external:github]\n---\n",
                encoding="utf-8",
            )
            local_installation = inspect_installations(
                project,
                base / "home",
                capability_evidence=evidence,
            )
            local = next(
                item
                for item in local_installation["harnesses"]["codex"]["capability_checks"]
                if item["name"] == "external:github"
            )
            self.assertEqual("project", local["ownership"])
            self.assertIn(str(local_skill), {item["source"] for item in local["evidence"]})
            local_report = compose_doctor_report(
                local_installation,
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=[],
                persona_evidence=[],
            )
            self.assertEqual("platform", local_report["profile"])

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

    def test_malformed_claude_install_locations_are_source_bearing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            registry_path = home / ".claude/plugins/known_marketplaces.json"
            installed_path = home / ".claude/plugins/installed_plugins.json"
            write_json(
                registry_path,
                {"pixeloven": {"installLocation": ["not", "a", "path"]}},
            )
            write_json(
                installed_path,
                {
                    "plugins": {
                        "crew@pixeloven": [
                            {"installPath": ["not", "a", "path"]},
                            {"installPath": str(base / "cache"), "projectPath": ["not", "a", "path"]},
                        ]
                    }
                },
            )

            claude = inspect_installations(project, home)["harnesses"]["claude"]

            reads = {item["source"]: item for item in claude["configuration_reads"]}
            self.assertEqual("malformed", reads[str(registry_path)]["state"])
            self.assertIn("installLocation", reads[str(registry_path)]["detail"])
            self.assertEqual("malformed", reads[str(installed_path)]["state"])
            self.assertIn("installPath", reads[str(installed_path)]["detail"])
            self.assertIn("projectPath", reads[str(installed_path)]["detail"])
            finding_sources = {
                evidence["source"]
                for finding in claude["findings"]
                for evidence in finding["evidence"]
            }
            self.assertTrue({str(registry_path), str(installed_path)} <= finding_sources)

    def test_malformed_claude_version_and_scope_are_excluded_from_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "home/.claude/plugins/cache/pixeloven/crew/0.36.0"
            write_json(root / ".claude-plugin/plugin.json", {"version": "0.36.0"})
            installed_path = base / "home/.claude/plugins/installed_plugins.json"
            write_claude_marketplace_identity(base / "home")
            write_json(
                installed_path,
                {
                    "plugins": {
                        "crew@pixeloven": [
                            {
                                "installPath": str(root),
                                "version": ["0.36.0"],
                                "scope": 7,
                            }
                        ]
                    }
                },
            )

            claude = inspect_installations(
                base / "project", base / "home"
            )["harnesses"]["claude"]

            read = next(
                item
                for item in claude["configuration_reads"]
                if item["source"] == str(installed_path)
            )
            self.assertEqual("malformed", read["state"])
            self.assertIn("version must be a SemVer string", read["detail"])
            self.assertIn("scope must be local, project, or user", read["detail"])
            self.assertEqual([], claude["installed_versions"])
            self.assertIsNone(claude["installed_version"])
            finding = next(
                item
                for item in claude["findings"]
                if item["evidence"][0]["source"] == str(installed_path)
            )
            self.assertIn("installed plugins configuration is malformed", finding["claim"])

    def test_malformed_codex_plugin_shapes_are_degraded_not_crashing(self) -> None:
        cases = (
            (
                "marketplaces = []\nplugins = false\n",
                ("marketplaces must be a mapping", "plugins must be a mapping"),
            ),
            (
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\nref = 36\n",
                ("marketplaces.pixeloven.ref must be a SemVer string",),
            ),
            (
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\nref = 'banana'\n",
                ("marketplaces.pixeloven.ref must be a SemVer string",),
            ),
        )
        for contents, expected_details in cases:
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as tmp:
                base = pathlib.Path(tmp)
                project = base / "project"
                home = base / "home"
                config = home / ".codex/config.toml"
                config.parent.mkdir(parents=True)
                config.write_text(contents, encoding="utf-8")

                codex = inspect_installations(project, home)["harnesses"]["codex"]

                read = next(
                    item
                    for item in codex["configuration_reads"]
                    if item["source"] == str(config)
                )
                self.assertEqual("malformed", read["state"])
                for detail in expected_details:
                    self.assertIn(detail, read["detail"])
                finding = next(
                    item for item in codex["findings"]
                    if item["evidence"][0]["source"] == str(config)
                )
                self.assertIn("Codex plugin configuration is malformed", finding["claim"])

    def test_claude_alias_cannot_attribute_an_unrelated_marketplace_to_crew(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            marketplace = home / ".claude/plugins/marketplaces/pixeloven"
            settings = home / ".claude/settings.json"
            registry = home / ".claude/plugins/known_marketplaces.json"
            write_json(
                settings,
                {
                    "extraKnownMarketplaces": {
                        "pixeloven": {
                            "source": {"source": "github", "repo": "someone-else/crew"}
                        }
                    },
                    "enabledPlugins": {"crew@pixeloven": True},
                },
            )
            write_json(
                registry,
                {
                    "pixeloven": {
                        "source": {"source": "github", "repo": "someone-else/crew"},
                        "installLocation": str(marketplace),
                    }
                },
            )

            claude = inspect_installations(project, home)["harnesses"]["claude"]

            self.assertEqual("unavailable", claude["installation"]["state"])
            self.assertEqual("unavailable", claude["enablement"]["state"])
            self.assertIsNone(claude["served_version"])
            sources = {
                evidence["source"]
                for finding in claude["findings"]
                for evidence in finding["evidence"]
            }
            self.assertTrue({str(settings), str(registry)} <= sources)

    def test_codex_invalid_alias_cannot_enable_or_resolve_crew(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            config = home / ".codex/config.toml"
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'someone-else/crew'\nref = 'v0.29.0'\n\n"
                "[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )

            codex = inspect_installations(project, home)["harnesses"]["codex"]

            self.assertEqual("present", codex["installation"]["state"])
            self.assertEqual("unavailable", codex["enablement"]["state"])
            self.assertIsNone(codex["resolved_version"])
            read = next(
                item
                for item in codex["configuration_reads"]
                if item["source"] == str(config)
            )
            self.assertEqual("malformed", read["state"])
            self.assertIn("git source identifying pixeloven/crew", read["detail"])

    def test_codex_marketplace_requires_git_kind_and_normalizes_git_sources(self) -> None:
        supported_sources = (
            "pixeloven/crew",
            "https://github.com/pixeloven/crew.git",
            "git+https://github.com/pixeloven/crew.git",
            "git@github.com:pixeloven/crew.git",
            "ssh://git@github.com/pixeloven/crew.git",
        )
        for source in supported_sources:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                base = pathlib.Path(tmp)
                project, home = self.make_install_tree(base)
                config = home / ".codex/config.toml"
                config.write_text(
                    "[marketplaces.pixeloven]\nsource_type = 'git'\n"
                    f"source = '{source}'\nref = 'v0.29.0'\n"
                    "[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                    encoding="utf-8",
                )

                codex = inspect_installations(project, home)["harnesses"]["codex"]

                self.assertEqual("present", codex["installation"]["state"])
                self.assertEqual("present", codex["enablement"]["state"])

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            config = home / ".codex/config.toml"
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'local'\n"
                "source = 'pixeloven/crew'\nref = 'v0.29.0'\n"
                "[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )

            codex = inspect_installations(project, home)["harnesses"]["codex"]

            self.assertEqual("present", codex["installation"]["state"])
            self.assertEqual("unavailable", codex["enablement"]["state"])
            self.assertIsNone(codex["resolved_version"])
            read = next(
                item for item in codex["configuration_reads"] if item["source"] == str(config)
            )
            self.assertEqual("malformed", read["state"])
            self.assertIn("must use a git source", read["detail"])

    def test_codex_cache_version_sources_must_agree(self) -> None:
        cases = (
            ("cache-name", "0.36.0"),
            ("v0.36.0", "0.36.0"),
            ("0.35.0", "0.36.0"),
        )
        for directory_version, manifest_version in cases:
            with self.subTest(directory_version=directory_version), tempfile.TemporaryDirectory() as tmp:
                base = pathlib.Path(tmp)
                home = base / "home"
                root = home / f".codex/plugins/cache/pixeloven/crew/{directory_version}"
                write_json(root / ".claude-plugin/plugin.json", {"version": manifest_version})
                (root / "skills").mkdir(exist_ok=True)
                config = home / ".codex/config.toml"
                config.parent.mkdir(parents=True, exist_ok=True)
                config.write_text(
                    "[marketplaces.pixeloven]\nsource_type = 'git'\n"
                    "source = 'https://github.com/pixeloven/crew.git'\n"
                    "ref = 'v0.36.0'\n[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                    encoding="utf-8",
                )

                codex = inspect_installations(base / "project", home)["harnesses"]["codex"]

                self.assertEqual("unavailable", codex["installation"]["state"])
                self.assertIsNone(codex["resolved_version"])
                self.assertEqual("DEGRADED", codex["status"])
                self.assertEqual("malformed", codex["cache_reads"][0]["state"])
                self.assertIn(
                    "cache directory",
                    next(
                        finding["claim"]
                        for finding in codex["findings"]
                        if "Codex plugin cache root is malformed" in finding["claim"]
                    ),
                )

    def test_codex_cache_missing_skills_is_reported_alongside_healthy_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp))
            corrupt_root = home / ".codex/plugins/cache/pixeloven/crew/0.30.0"
            write_json(
                corrupt_root / ".claude-plugin/plugin.json",
                {"name": "crew", "version": "0.30.0"},
            )
            (corrupt_root / "skills").rmdir()

            codex = inspect_installations(project, home)["harnesses"]["codex"]

            self.assertEqual("0.29.0", codex["resolved_version"])
            self.assertEqual("DEGRADED", codex["status"])
            self.assertIn(str(corrupt_root), codex["cache_roots"])
            self.assertNotIn(str(corrupt_root), codex["package_roots"])
            invalid_layout = next(
                item
                for item in codex["manifest_reads"]
                if item["source"] == str(corrupt_root / "skills")
            )
            self.assertEqual("malformed", invalid_layout["state"])
            self.assertEqual("required skills directory is missing", invalid_layout["detail"])
            finding = next(
                item
                for item in codex["findings"]
                if "required skills directory is missing" in item["claim"]
            )
            self.assertEqual(str(corrupt_root / "skills"), finding["evidence"][0]["source"])

    def test_codex_corrupt_cache_is_classified_without_valid_configuration(self) -> None:
        for config_value in (None, "[marketplaces.pixeloven]\nsource = 'someone/else'\n"):
            with self.subTest(config=config_value), tempfile.TemporaryDirectory() as tmp:
                base = pathlib.Path(tmp)
                home = base / "home"
                root = home / ".codex/plugins/cache/pixeloven/crew/0.36.0"
                write_json(
                    root / ".claude-plugin/plugin.json",
                    {"name": "crew", "version": "0.36.0"},
                )
                (root / "skills").rmdir()
                if config_value is not None:
                    config = home / ".codex/config.toml"
                    config.parent.mkdir(parents=True, exist_ok=True)
                    config.write_text(config_value, encoding="utf-8")

                codex = inspect_installations(base / "project", home)["harnesses"]["codex"]

                self.assertEqual([str(root)], codex["cache_roots"])
                self.assertEqual("unavailable", codex["installation"]["state"])
                self.assertEqual("DEGRADED", codex["status"])
                invalid_layout = next(
                    item
                    for item in codex["manifest_reads"]
                    if item["source"] == str(root / "skills")
                )
                self.assertEqual("malformed", invalid_layout["state"])

    def test_manifest_valid_roots_without_skills_are_rejected_for_every_harness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base, "v0.35.0")
            roots = {
                "pi": home / ".pi/agent/git/github.com/pixeloven/crew",
                "claude-marketplace": home / ".claude/plugins/marketplaces/pixeloven",
                "claude-cache": home / ".claude/plugins/cache/pixeloven/crew/0.30.0",
                "codex": home / ".codex/plugins/cache/pixeloven/crew/0.29.0",
            }
            for root in roots.values():
                shutil.rmtree(root / "skills")

            report = inspect_installations(project, home)

            for harness in ("pi", "claude", "codex"):
                result = report["harnesses"][harness]
                self.assertEqual("unavailable", result["installation"]["state"])
                self.assertEqual([], result["resolved_package_roots"])
                self.assertEqual("DEGRADED", result["status"])
            manifest_failures = {
                item["source"]
                for result in report["harnesses"].values()
                for item in result["manifest_reads"]
                if item["state"] == "malformed"
            }
            self.assertTrue(
                {str(root / "skills") for root in roots.values()} <= manifest_failures
            )

    def test_manifest_skills_path_must_be_canonical_and_contained(self) -> None:
        for declared_skills, valid in (
            ("./skills", True),
            ("./wrong", False),
            ("../skills", False),
            (None, False),
        ):
            with self.subTest(skills=declared_skills), tempfile.TemporaryDirectory() as tmp:
                base = pathlib.Path(tmp)
                project = base / "project"
                home = base / "home"
                write_json(
                    project / ".pi/settings.json",
                    {"packages": ["git:github.com/pixeloven/crew@v0.36.0"]},
                )
                root = home / ".pi/agent/git/github.com/pixeloven/crew"
                manifest = root / ".claude-plugin/plugin.json"
                write_json(
                    manifest,
                    {"name": "crew", "version": "0.36.0", "skills": "./skills"},
                )
                payload = {"name": "crew", "version": "0.36.0"}
                if declared_skills is not None:
                    payload["skills"] = declared_skills
                manifest.write_text(json.dumps(payload), encoding="utf-8")
                if declared_skills == "./wrong":
                    (root / "wrong").mkdir()
                elif declared_skills == "../skills":
                    (root.parent / "skills").mkdir()

                pi = inspect_installations(project, home)["harnesses"]["pi"]

                if valid:
                    self.assertEqual("present", pi["installation"]["state"])
                    self.assertEqual("0.36.0", pi["resolved_version"])
                else:
                    self.assertEqual("unavailable", pi["installation"]["state"])
                    self.assertIsNone(pi["resolved_version"])
                    malformed = next(
                        item
                        for item in pi["manifest_reads"]
                        if item["state"] == "malformed"
                    )
                    self.assertEqual(str(manifest), malformed["source"])
                    self.assertIn("normalized relative path ./skills", malformed["detail"])

    def test_non_pi_version_fields_reject_package_spec_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            config = home / ".codex/config.toml"
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\n"
                "ref = 'junk@v0.29.0'\n[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )

            codex = inspect_installations(project, home)["harnesses"]["codex"]

            self.assertIsNone(codex["configured_version"])
            self.assertEqual("DEGRADED", codex["status"])
            self.assertIn(
                "ref must be a SemVer string",
                next(
                    read["detail"]
                    for read in codex["configuration_reads"]
                    if read["source"] == str(config)
                ),
            )

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            home = base / "home"
            root = home / ".codex/plugins/cache/pixeloven/crew/junk@0.36.0"
            write_json(root / ".claude-plugin/plugin.json", {"version": "0.36.0"})
            (root / "skills").mkdir(exist_ok=True)
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\n"
                "ref = 'v0.36.0'\n[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )

            codex = inspect_installations(base / "project", home)["harnesses"]["codex"]

            self.assertEqual("unavailable", codex["installation"]["state"])
            self.assertEqual("malformed", codex["cache_reads"][0]["state"])

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            home = base / "home"
            root = home / ".claude/plugins/cache/pixeloven/crew/0.36.0"
            write_json(root / ".claude-plugin/plugin.json", {"version": "0.36.0"})
            write_claude_marketplace_identity(home)
            write_json(
                home / ".claude/plugins/installed_plugins.json",
                {
                    "plugins": {
                        "crew@pixeloven": [
                            {
                                "scope": "user",
                                "installPath": str(root),
                                "version": "junk@v0.36.0",
                            },
                            {
                                "scope": "user",
                                "installPath": str(root),
                                "version": "v0.36.0",
                            },
                        ]
                    }
                },
            )

            claude = inspect_installations(base / "project", home)["harnesses"]["claude"]

            self.assertEqual([], claude["installed_versions"])
            self.assertEqual("DEGRADED", claude["status"])

    def test_invalid_codex_identity_cannot_enable_or_resolve_cache_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            other = home / ".codex/plugins/cache/pixeloven/crew/0.36.0"
            write_json(other / ".claude-plugin/plugin.json", {"version": "0.36.0"})
            (other / "skills").mkdir(exist_ok=True)
            config = home / ".codex/config.toml"
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'someone-else/crew'\n"
                "ref = 'v0.36.0'\n[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )

            codex = inspect_installations(project, home)["harnesses"]["codex"]

            self.assertIsNone(codex["configured_version"])
            self.assertEqual(
                {
                    str(home / ".codex/plugins/cache/pixeloven/crew/0.29.0"),
                    str(other),
                },
                set(codex["cache_roots"]),
            )
            self.assertEqual(set(codex["cache_roots"]), set(codex["package_roots"]))
            self.assertEqual("present", codex["installation"]["state"])
            self.assertEqual("unavailable", codex["enablement"]["state"])
            self.assertIsNone(codex["resolved_version"])

    def test_unreadable_vendored_catalogue_is_degraded_source_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            vendored = project / ".agents/skills"
            shutil.copytree(ROOT / "skills", vendored)
            broken = vendored / "doctor/SKILL.md"
            broken.write_bytes(b"\xff")

            codex = inspect_installations(project, base / "home")["harnesses"]["codex"]

            read = next(item for item in codex["catalogue_reads"] if item["source"] == str(broken))
            self.assertEqual("unreadable", read["state"])
            self.assertEqual("DEGRADED", codex["status"])
            finding = next(
                item for item in codex["findings"]
                if item["evidence"][0]["source"] == str(broken)
            )
            self.assertIn("vendored catalogue skill is unreadable", finding["claim"])

    def test_malformed_vendored_catalogue_identity_is_degraded_source_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            vendored = project / ".agents/skills"
            shutil.copytree(ROOT / "skills", vendored)
            broken = vendored / "doctor/SKILL.md"
            broken.write_text(
                "---\nname: wrong-name\ndescription: Broken vendored identity.\n---\n",
                encoding="utf-8",
            )

            codex = inspect_installations(project, base / "home")["harnesses"]["codex"]

            read = next(item for item in codex["catalogue_reads"] if item["source"] == str(broken))
            self.assertEqual("malformed", read["state"])
            self.assertIn("name must be doctor", read["detail"])
            self.assertEqual("DEGRADED", codex["status"])

    def test_incomplete_vendored_catalogues_preserve_candidate_failures(self) -> None:
        cases = {
            "malformed": {"doctor": "malformed"},
            "unreadable": {"doctor": "unreadable"},
            "valid-only": {"doctor": "valid"},
            "mixed": {
                "doctor": "valid",
                "onboarding": "malformed",
                "intake-process": "unreadable",
            },
        }
        for case, candidates in cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                base = pathlib.Path(tmp)
                project = base / "project"
                vendored = project / ".agents/skills"
                for name, state in candidates.items():
                    skill = vendored / name / "SKILL.md"
                    skill.parent.mkdir(parents=True, exist_ok=True)
                    if state == "valid":
                        shutil.copyfile(ROOT / "skills" / name / "SKILL.md", skill)
                    elif state == "unreadable":
                        skill.write_bytes(b"\xff")
                    else:
                        skill.write_text(
                            f"---\nname: wrong-{name}\ndescription: Broken candidate.\n---\n",
                            encoding="utf-8",
                        )

                codex = inspect_installations(project, base / "home")["harnesses"]["codex"]

                self.assertEqual([], codex["vendored_catalogues"])
                self.assertEqual("DEGRADED", codex["status"])
                missing = next(
                    read
                    for read in codex["catalogue_reads"]
                    if read["source"] == str(vendored / "activation-contracts/SKILL.md")
                )
                self.assertEqual("unavailable", missing["state"])
                missing_finding = next(
                    finding
                    for finding in codex["findings"]
                    if finding["evidence"][0]["source"] == missing["source"]
                )
                self.assertIn("is unavailable", missing_finding["claim"])
                for name, state in candidates.items():
                    if state == "valid":
                        continue
                    source = str(vendored / name / "SKILL.md")
                    self.assertTrue(
                        any(
                            read["source"] == source and read["state"] == state
                            for read in codex["catalogue_reads"]
                        )
                    )

    def test_complete_vendored_catalogue_keeps_unverified_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            vendored = project / ".agents/skills"
            shutil.copytree(ROOT / "skills", vendored)

            codex = inspect_installations(project, base / "home")["harnesses"]["codex"]

            self.assertEqual("unavailable", codex["installation"]["state"])
            self.assertEqual("unavailable", codex["enablement"]["state"])
            self.assertEqual(
                [{"root": str(vendored), "capabilities": "present", "provenance": "unverified"}],
                codex["vendored_catalogues"],
            )
            self.assertEqual([str(vendored)], codex["capability_roots"])
            self.assertIsNone(codex["resolved_version"])
            self.assertTrue(
                any("provenance is unverified" in finding["claim"] for finding in codex["findings"])
            )

    def test_all_vendored_candidates_are_enumerated_without_crew_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            project_vendored = project / ".agents/skills"
            user_vendored = home / ".agents/skills"
            shutil.copytree(ROOT / "skills", project_vendored)
            shutil.copytree(ROOT / "skills", user_vendored)

            vendored = inspect_installations(project, home)["harnesses"]["codex"]

            self.assertEqual([], vendored["package_roots"])
            self.assertEqual(
                {str(project_vendored), str(user_vendored)},
                {item["root"] for item in vendored["vendored_catalogues"]},
            )
            unverified = next(
                finding
                for finding in vendored["findings"]
                if "provenance is unverified" in finding["claim"]
            )
            self.assertEqual(
                {str(project_vendored), str(user_vendored)},
                {item["source"] for item in unverified["evidence"]},
            )

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            vendored_root = project / ".agents/skills"
            shutil.copytree(ROOT / "skills", vendored_root)
            plugin_root = home / ".codex/plugins/cache/pixeloven/crew/0.29.0"

            mixed = inspect_installations(project, home)["harnesses"]["codex"]

            self.assertEqual([str(plugin_root)], mixed["package_roots"])
            self.assertEqual(
                [{"root": str(vendored_root), "capabilities": "present", "provenance": "unverified"}],
                mixed["vendored_catalogues"],
            )
            unverified = next(
                finding
                for finding in mixed["findings"]
                if "provenance is unverified" in finding["claim"]
            )
            self.assertEqual(
                {str(vendored_root)},
                {item["source"] for item in unverified["evidence"]},
            )

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

    def test_pi_packages_requires_a_string_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            settings = project / ".pi/settings.json"
            write_json(
                settings,
                {"packages": {"git:github.com/pixeloven/crew@v0.36.0": False}},
            )
            root = home / ".pi/agent/git/github.com/pixeloven/crew"
            write_json(root / ".claude-plugin/plugin.json", {"version": "0.36.0"})

            pi = inspect_installations(project, home)["harnesses"]["pi"]

            self.assertEqual("unavailable", pi["enablement"]["state"])
            self.assertEqual("DEGRADED", pi["status"])
            read = next(item for item in pi["configuration_reads"] if item["source"] == str(settings))
            self.assertEqual("malformed", read["state"])
            self.assertIn("packages must be a string sequence", read["detail"])

    def test_claude_duplicate_enablement_scopes_use_project_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            write_json(
                project / ".claude/settings.json",
                {"enabledPlugins": {"crew@pixeloven": True}},
            )

            claude = inspect_installations(project, home)["harnesses"]["claude"]

            self.assertEqual("project", claude["enabled_scope"])
            self.assertEqual(str(project / ".claude/settings.json"), claude["enablement"]["source"])
            self.assertEqual(["project", "user"], [row["scope"] for row in claude["enabled_scopes"]])
            duplicate = next(
                item for item in claude["findings"] if "multiple Claude settings scopes" in item["claim"]
            )
            self.assertEqual(
                {str(project / ".claude/settings.json"), str(home / ".claude/settings.json")},
                {item["source"] for item in duplicate["evidence"]},
            )

    def test_claude_duplicate_marketplace_scopes_report_selected_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            write_json(
                project / ".claude/settings.json",
                {
                    "extraKnownMarketplaces": {
                        "pixeloven": {"source": "pixeloven/crew"}
                    }
                },
            )

            claude = inspect_installations(project, home)["harnesses"]["claude"]

            self.assertEqual(
                ["project", "user"],
                [record["scope"] for record in claude["marketplace_scopes"]],
            )
            self.assertEqual("DEGRADED", claude["status"])
            duplicate = next(
                item
                for item in claude["findings"]
                if "marketplace is declared in multiple Claude settings scopes" in item["claim"]
            )
            self.assertIn("project precedence selected", duplicate["claim"])
            self.assertEqual(
                {str(project / ".claude/settings.json"), str(home / ".claude/settings.json")},
                {item["source"] for item in duplicate["evidence"]},
            )

    def test_claude_single_marketplace_scope_has_no_duplicate_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp))

            claude = inspect_installations(project, home)["harnesses"]["claude"]

            self.assertEqual(["user"], [row["scope"] for row in claude["marketplace_scopes"]])
            self.assertFalse(
                any(
                    "marketplace is declared in multiple Claude settings scopes" in item["claim"]
                    for item in claude["findings"]
                )
            )

    def test_claude_enablement_resolves_local_project_user_true_and_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project, home = self.make_install_tree(base)
            write_json(
                project / ".claude/settings.json",
                {"enabledPlugins": {"crew@pixeloven": False}},
            )

            project_disabled = inspect_installations(project, home)["harnesses"]["claude"]

            self.assertEqual("unavailable", project_disabled["enablement"]["state"])
            self.assertEqual("project", project_disabled["enabled_scope"])
            self.assertFalse(project_disabled["enabled_value"])
            self.assertEqual(
                str(project / ".claude/settings.json"),
                project_disabled["enablement"]["source"],
            )

            write_json(
                project / ".claude/settings.local.json",
                {"enabledPlugins": {"crew@pixeloven": True}},
            )
            local_enabled = inspect_installations(project, home)["harnesses"]["claude"]

            self.assertEqual("present", local_enabled["enablement"]["state"])
            self.assertEqual("local", local_enabled["enabled_scope"])
            self.assertTrue(local_enabled["enabled_value"])
            self.assertEqual(
                ["local", "project", "user"],
                [row["scope"] for row in local_enabled["enabled_scopes"]],
            )

    def test_claude_invalid_local_alias_cannot_inherit_valid_user_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                project / ".claude/settings.local.json",
                {
                    "extraKnownMarketplaces": {
                        "pixeloven": {"source": "someone-else/crew"}
                    },
                    "enabledPlugins": {"crew@pixeloven": True},
                },
            )
            write_json(
                home / ".claude/settings.json",
                {
                    "extraKnownMarketplaces": {
                        "pixeloven": {"source": "pixeloven/crew"}
                    },
                    "enabledPlugins": {"crew@pixeloven": True},
                },
            )
            root = home / ".claude/plugins/cache/pixeloven/crew/0.36.0"
            write_json(root / ".claude-plugin/plugin.json", {"version": "0.36.0"})
            write_json(
                home / ".claude/plugins/installed_plugins.json",
                {
                    "plugins": {
                        "crew@pixeloven": [
                            {
                                "scope": "user",
                                "installPath": str(root),
                                "version": "0.36.0",
                            }
                        ]
                    }
                },
            )

            claude = inspect_installations(project, home)["harnesses"]["claude"]

            self.assertEqual("unavailable", claude["enablement"]["state"])
            self.assertEqual("local", claude["enabled_scope"])
            self.assertTrue(claude["enabled_value"])
            self.assertEqual("unavailable", claude["installation"]["state"])
            self.assertEqual([], claude["installed_versions"])
            read = next(
                item
                for item in claude["configuration_reads"]
                if item["source"] == str(project / ".claude/settings.local.json")
            )
            self.assertEqual("malformed", read["state"])
            self.assertIn("source must identify pixeloven/crew", read["detail"])

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
            codex_root = home / ".codex/plugins/cache/pixeloven/crew/0.35.0"
            write_json(
                codex_root / ".claude-plugin/plugin.json",
                {"name": "crew", "version": "0.35.0"},
            )
            (codex_root / "skills").mkdir(exist_ok=True)
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\nref = 'v0.35.0'\n"
                "[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )
            write_json(
                home / ".claude/settings.json",
                {"enabledPlugins": {"crew@pixeloven": True}},
            )
            claude_root = home / ".claude/plugins/cache/pixeloven/crew/0.36.0"
            manifest = claude_root / ".claude-plugin/plugin.json"
            write_json(manifest, {"name": "crew", "version": "0.36.0"})
            write_json(
                home / ".claude/plugins/installed_plugins.json",
                {
                    "plugins": {
                        "crew@pixeloven": [
                            {
                                "scope": "user",
                                "installPath": str(claude_root),
                                "version": "0.36.0",
                            }
                        ]
                    }
                },
            )
            write_claude_marketplace_identity(home)

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
            root = base / "home/.claude/plugins/cache/pixeloven/crew/0.36.0"
            manifest = root / ".claude-plugin/plugin.json"
            write_json(manifest, {"name": "crew", "version": "0.36.0"})
            installed_path = base / "home/.claude/plugins/installed_plugins.json"
            write_claude_marketplace_identity(base / "home")
            write_json(
                installed_path,
                {
                    "plugins": {
                        "crew@pixeloven": [
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

    def test_claude_other_project_registration_is_not_an_installation_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                home / ".claude/settings.json",
                {
                    "extraKnownMarketplaces": {
                        "pixeloven": {"source": "pixeloven/crew"}
                    },
                    "enabledPlugins": {"crew@pixeloven": True},
                },
            )
            write_claude_marketplace_identity(home)
            root = home / ".claude/plugins/cache/pixeloven/crew/0.36.0"
            write_json(root / ".claude-plugin/plugin.json", {"version": "0.36.0"})
            installed_path = home / ".claude/plugins/installed_plugins.json"
            registration = {
                "scope": "project",
                "projectPath": str(base / "other-project"),
                "installPath": str(root),
                "version": "0.36.0",
            }
            write_json(installed_path, {"plugins": {"crew@pixeloven": [registration]}})

            claude = inspect_installations(project, home)["harnesses"]["claude"]

            self.assertEqual("unavailable", claude["installation"]["state"])
            self.assertEqual([], claude["installed_versions"])
            self.assertEqual([], claude["package_roots"])
            self.assertEqual(
                [{"registration": registration, "source": str(installed_path)}],
                claude["inapplicable_registrations"],
            )
            self.assertFalse(
                any(
                    "does not apply to the inspected project" in item["claim"]
                    for item in claude["findings"]
                )
            )

    def test_claude_unrelated_registration_does_not_degrade_current_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                home / ".claude/settings.json",
                {
                    "extraKnownMarketplaces": {
                        "pixeloven": {"source": "pixeloven/crew"}
                    },
                    "enabledPlugins": {"crew@pixeloven": True},
                },
            )
            write_claude_marketplace_identity(home)
            current_root = home / ".claude/plugins/cache/pixeloven/crew/0.36.0"
            unrelated_root = home / ".claude/plugins/cache/pixeloven/crew/0.37.0"
            write_json(current_root / ".claude-plugin/plugin.json", {"version": "0.36.0"})
            write_json(unrelated_root / ".claude-plugin/plugin.json", {"version": "0.37.0"})
            installed_path = home / ".claude/plugins/installed_plugins.json"
            unrelated = {
                "scope": "project",
                "projectPath": str(base / "other-project"),
                "installPath": str(unrelated_root),
                "version": "0.37.0",
            }
            write_json(
                installed_path,
                {
                    "plugins": {
                        "crew@pixeloven": [
                            {
                                "scope": "user",
                                "installPath": str(current_root),
                                "version": "0.36.0",
                            },
                            unrelated,
                        ]
                    }
                },
            )

            claude = inspect_installations(project, home)["harnesses"]["claude"]

            self.assertEqual("OK", claude["status"])
            self.assertEqual("0.36.0", claude["installed_version"])
            self.assertEqual([str(current_root)], claude["package_roots"])
            self.assertEqual(
                [{"registration": unrelated, "source": str(installed_path)}],
                claude["inapplicable_registrations"],
            )
            self.assertFalse(
                any("scope registrations" in item["claim"] for item in claude["findings"])
            )

    def test_claude_served_installed_disagreement_is_cross_harness_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                project / ".pi/settings.json",
                {"packages": ["git:github.com/pixeloven/crew@v0.35.0"]},
            )
            write_json(
                home / ".pi/agent/git/github.com/pixeloven/crew/.claude-plugin/plugin.json",
                {"version": "0.35.0"},
            )
            codex_root = home / ".codex/plugins/cache/pixeloven/crew/0.35.0"
            write_json(codex_root / ".claude-plugin/plugin.json", {"version": "0.35.0"})
            (codex_root / "skills").mkdir(exist_ok=True)
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\n"
                "ref = 'v0.35.0'\n[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )
            write_json(
                home / ".claude/settings.json",
                {
                    "extraKnownMarketplaces": {
                        "pixeloven": {"source": "pixeloven/crew"}
                    },
                    "enabledPlugins": {"crew@pixeloven": True},
                },
            )
            served_root = home / ".claude/plugins/marketplaces/pixeloven"
            write_json(served_root / ".claude-plugin/plugin.json", {"version": "0.36.0"})
            write_json(
                home / ".claude/plugins/known_marketplaces.json",
                {
                    "pixeloven": {
                        "source": {"source": "github", "repo": "pixeloven/crew"},
                        "installLocation": str(served_root),
                    }
                },
            )
            installed_root = home / ".claude/plugins/cache/pixeloven/crew/0.35.0"
            write_json(installed_root / ".claude-plugin/plugin.json", {"version": "0.35.0"})
            write_json(
                home / ".claude/plugins/installed_plugins.json",
                {
                    "plugins": {
                        "crew@pixeloven": [
                            {
                                "scope": "user",
                                "installPath": str(installed_root),
                                "version": "0.35.0",
                            }
                        ]
                    }
                },
            )

            report = inspect_installations(project, home)
            claude = report["harnesses"]["claude"]

            self.assertEqual("0.36.0", claude["served_version"])
            self.assertEqual("0.35.0", claude["installed_version"])
            self.assertIsNone(claude["loaded_version"])
            self.assertTrue(
                any("served/installed/loaded versions disagree" in item["claim"] for item in claude["findings"])
            )
            self.assertFalse(
                any(row["check"] == "cross-harness.version-skew" for row in report["checks"])
            )

            runtime_report = inspect_installations(
                project,
                home,
                {
                    "claude": {
                        "state": "working",
                        "source": "captured Claude catalogue",
                        "skills": [
                            {
                                "name": "crew:doctor",
                                "description": "Crew Doctor.",
                                "path": str(served_root / "skills/doctor/SKILL.md"),
                            }
                        ],
                    }
                },
            )
            runtime_claude = runtime_report["harnesses"]["claude"]
            self.assertEqual("0.36.0", runtime_claude["loaded_version"])
            self.assertIn(
                str(served_root / ".claude-plugin/plugin.json"),
                runtime_claude["loaded_version_source"],
            )
            skew = next(
                row
                for row in runtime_report["checks"]
                if row["check"] == "cross-harness.version-skew"
            )
            claude_evidence = next(
                item for item in skew["evidence"] if item["claim"].startswith("claude ")
            )
            self.assertEqual("claude selected Crew version is 0.36.0", claude_evidence["claim"])

    def test_claude_duplicate_roots_are_order_independent_and_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_json(
                home / ".claude/settings.json",
                {"enabledPlugins": {"crew@pixeloven": True}},
            )
            roots = []
            for version in ("0.35.0", "0.36.0"):
                root = home / f".claude/plugins/cache/pixeloven/crew/{version}"
                write_json(root / ".claude-plugin/plugin.json", {"name": "crew", "version": version})
                roots.append(root)
            codex_root = home / ".codex/plugins/cache/pixeloven/crew/0.35.0"
            write_json(
                codex_root / ".claude-plugin/plugin.json",
                {"name": "crew", "version": "0.35.0"},
            )
            (codex_root / "skills").mkdir(exist_ok=True)
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                "[marketplaces.pixeloven]\nsource_type = 'git'\nsource = 'pixeloven/crew'\nref = 'v0.35.0'\n"
                "[plugins.\"crew@pixeloven\"]\nenabled = true\n",
                encoding="utf-8",
            )
            installed_path = home / ".claude/plugins/installed_plugins.json"
            write_claude_marketplace_identity(home)
            registrations = [
                {"scope": "user", "installPath": str(root), "version": root.name}
                for root in roots
            ]

            def inspect_with(records: list[dict[str, str]]) -> dict[str, object]:
                write_json(installed_path, {"plugins": {"crew@pixeloven": records}})
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

            served_root = home / ".claude/plugins/marketplaces/pixeloven"
            write_json(served_root / ".claude-plugin/plugin.json", {"version": "0.36.0"})
            write_json(
                home / ".claude/plugins/known_marketplaces.json",
                {
                    "pixeloven": {
                        "source": {"source": "github", "repo": "pixeloven/crew"},
                        "installLocation": str(served_root),
                    }
                },
            )
            served_report = inspect_with(registrations)
            served = served_report["harnesses"]["claude"]
            self.assertEqual("0.36.0", served["served_version"])
            self.assertIsNone(served["installed_version"])
            self.assertFalse(
                any(
                    row["check"] == "cross-harness.version-skew"
                    for row in served_report["checks"]
                )
            )

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

    def test_claude_scope_resolution_uses_local_project_user_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            write_claude_marketplace_identity(home)
            installed_path = home / ".claude/plugins/installed_plugins.json"
            roots: dict[str, pathlib.Path] = {}
            for scope, version in (
                ("user", "0.35.0"),
                ("unrelated", "0.36.0"),
                ("project", "0.37.0"),
                ("local", "0.38.0"),
            ):
                root = home / f".claude/plugins/cache/pixeloven/crew/{version}"
                write_json(root / ".claude-plugin/plugin.json", {"version": version})
                roots[scope] = root
            registrations = [
                {
                    "scope": "user",
                    "installPath": str(roots["user"]),
                    "version": "0.35.0",
                },
                {
                    "scope": "project",
                    "projectPath": str(base / "other-project"),
                    "installPath": str(roots["unrelated"]),
                    "version": "0.36.0",
                },
                {
                    "scope": "project",
                    "projectPath": str(project),
                    "installPath": str(roots["project"]),
                    "version": "0.37.0",
                },
                {
                    "scope": "local",
                    "projectPath": str(project),
                    "installPath": str(roots["local"]),
                    "version": "0.38.0",
                },
            ]

            write_json(installed_path, {"plugins": {"crew@pixeloven": registrations}})
            local = inspect_installations(project, home)["harnesses"]["claude"]
            self.assertEqual("0.38.0", local["installed_version"])

            write_json(
                installed_path,
                {"plugins": {"crew@pixeloven": registrations[:2]}},
            )
            user = inspect_installations(project, home)["harnesses"]["claude"]
            self.assertEqual("0.35.0", user["installed_version"])

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
                    "source": "captured Claude registry catalogue",
                    "version": "0.30.0",
                    "skills": [
                        {
                            "name": "crew:doctor",
                            "description": "Crew Doctor.",
                            "path": str(
                                home
                                / ".claude/plugins/cache/pixeloven/crew/0.30.0/skills/doctor/SKILL.md"
                            ),
                        }
                    ],
                    "agents": [],
                }
            }
            claude = inspect_installations(project, home, runtime)["harnesses"]["claude"]
            self.assertEqual("0.30.0", claude["served_version"])
            self.assertEqual("0.30.0", claude["loaded_version"])
            self.assertEqual("user", claude["enabled_scope"])
            self.assertEqual(4, len(claude["registrations"]))
            self.assertEqual(3, len(claude["inapplicable_registrations"]))
            self.assertEqual("OK", claude["status"])
            self.assertTrue(all("version" not in item for item in claude["marketplace_registry_records"]))

    def test_absent_harnesses_degrade_without_inventing_runtime_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            report = inspect_installations(base / "project", base / "home")
            for harness in report["harnesses"].values():
                self.assertIn(harness["runtime"]["state"], {"unavailable", "not tested"})
            for row in report["checks"]:
                if row["fact"].endswith(("is unavailable", "is not tested")):
                    self.assertTrue(row["evidence"])
                    self.assertTrue(all(item["source"] for item in row["evidence"]))
            claude_installation = next(
                row for row in report["checks"] if row["check"] == "claude.installation"
            )
            self.assertEqual(
                {
                    str(base / "project/.claude/settings.local.json"),
                    str(base / "project/.claude/settings.json"),
                    str(base / "home/.claude/settings.json"),
                    str(base / "home/.claude/plugins/known_marketplaces.json"),
                    str(base / "home/.claude/plugins/installed_plugins.json"),
                },
                {item["source"] for item in claude_installation["evidence"]},
            )
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
                    self.assertTrue(item["source"])
                    self.assertIn(f"source: {item['source']}", rendered)

    def test_composed_absence_checks_preserve_inspection_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            package = base / "crew"
            report = compose_doctor_report(
                inspect_installations(project, home),
                runtime_comparisons=[],
                local_slots=declared_local_slots(package),
                role_postures=[],
                persona_evidence=[],
            )

            slots = next(
                row for row in report["checks"] if row["check"] == "local-slots.declarations"
            )
            missing_roles = [
                row
                for row in report["checks"]
                if row["check"].startswith("role.") and " is missing" in row["fact"]
            ]
            profile = next(
                row for row in report["checks"] if row["check"] == "operating-profile.selection"
            )

            self.assertIn(str(package / "skills"), {item["source"] for item in slots["evidence"]})
            self.assertEqual(14, len(missing_roles))
            self.assertTrue(
                all(item["source"] for row in missing_roles for item in row["evidence"])
            )
            self.assertTrue(profile["evidence"])
            self.assertTrue(all(item["source"] for item in profile["evidence"]))
            self.assertNotIn("source: not recorded", render_doctor_report(report))

    def test_missing_role_evidence_does_not_cite_a_sibling_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            installation = inspect_installations(project, home)
            lead = next(
                row
                for row in inspect_role_postures(ROOT, project)
                if row["harness"] == "claude" and row["name"] == "lead"
            )
            report = compose_doctor_report(
                installation,
                runtime_comparisons=[],
                local_slots=declared_local_slots(ROOT),
                role_postures=[lead],
                persona_evidence=[],
            )

            reviewer = next(
                row for row in report["checks"] if row["check"] == "role.claude.reviewer"
            )
            sources = [item["source"] for item in reviewer["evidence"]]

            self.assertEqual("DEGRADED", reviewer["status"])
            self.assertNotIn(lead["source"], sources)
            self.assertIn(str(project / ".claude/agents"), sources)
            self.assertEqual(
                [
                    str(project / ".claude/agents"),
                    *installation["harnesses"]["claude"]["inspection_paths"],
                ],
                sources,
            )

    def test_negative_dimension_preserves_direct_and_inspection_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            report = inspect_installations(
                base / "project",
                base / "home",
                runtime_fixtures={
                    "codex": {
                        "state": "unavailable",
                        "source": "codex debug prompt-input capture",
                    }
                },
            )

            runtime = next(row for row in report["checks"] if row["check"] == "codex.runtime")
            sources = {item["source"] for item in runtime["evidence"]}
            self.assertIn("codex debug prompt-input capture", sources)
            self.assertIn(str(base / "home/.codex/config.toml"), sources)
            self.assertIn(str(base / "home/.codex/plugins/cache/pixeloven/crew"), sources)

    def test_codex_prompt_command_reaches_runtime_and_version_report_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            root = home / ".codex/plugins/cache/pixeloven/crew/0.36.0"
            write_json(
                root / ".claude-plugin/plugin.json",
                {"name": "crew", "version": "0.36.0", "skills": "./skills"},
            )
            write_codex_marketplace_identity(home)
            runtime = parse_codex_prompt_capture(
                FIXTURES / "runtime/codex-prompt-raw.json"
            )
            runtime["version"] = "0.36.0"
            for entry in runtime["skills"]:
                if entry["name"].startswith("crew:"):
                    name = entry["name"].split(":", 1)[1]
                    entry["path"] = str(root / f"skills/{name}/SKILL.md")

            installation = inspect_installations(
                project,
                home,
                runtime_fixtures={"codex": runtime},
            )
            report = compose_doctor_report(
                installation,
                runtime_comparisons=[],
                local_slots=declared_local_slots(ROOT),
                role_postures=inspect_role_postures(ROOT, project),
                persona_evidence=[],
            )
            command = runtime["source_command"]
            runtime_check = next(
                row for row in report["checks"] if row["check"] == "codex.runtime"
            )

            self.assertEqual(command, installation["harnesses"]["codex"]["runtime"]["source"])
            self.assertEqual(command, installation["harnesses"]["codex"]["loaded_version_source"])
            self.assertEqual([command], [item["source"] for item in runtime_check["evidence"]])
            self.assertIn(f"source: {command}", render_doctor_report(report))

    def test_runtime_recording_preserves_tested_and_untested_fixture_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            tested_fixture = load_runtime_fixture(
                FIXTURES / "runtime/claude-catalog-capture.json"
            )
            tested_comparison = compare_runtime_catalog([], tested_fixture)
            tested_report = inspect_installations(
                project,
                home,
                runtime_fixtures={"claude": tested_fixture},
            )
            tested_check = next(
                row
                for row in tested_report["checks"]
                if row["check"] == "claude.runtime"
            )

            self.assertEqual(
                tested_comparison["capture"]["sources"],
                [item["source"] for item in tested_check["evidence"]],
            )
            self.assertEqual(
                str(FIXTURES / "runtime/claude-catalog-capture.json"),
                tested_report["harnesses"]["claude"]["runtime"]["source"],
            )

            capture_path = base / "untested-runtime.json"
            write_json(
                capture_path,
                {
                    "schema_version": 1,
                    "harness": "codex",
                    "tested": False,
                    "source_command": "captured skipped catalogue",
                },
            )
            untested_fixture = load_runtime_fixture(capture_path)
            untested_comparison = compare_runtime_catalog([], untested_fixture)
            untested_report = inspect_installations(
                project,
                home,
                runtime_fixtures={"codex": untested_fixture},
            )
            untested_check = next(
                row
                for row in untested_report["checks"]
                if row["check"] == "codex.runtime"
            )
            untested_sources = [item["source"] for item in untested_check["evidence"]]

            self.assertEqual("N/A", untested_check["status"])
            self.assertEqual(
                untested_comparison["capture"]["sources"],
                untested_sources[:2],
            )
            self.assertEqual(
                str(capture_path),
                untested_report["harnesses"]["codex"]["runtime"]["source"],
            )

    def test_top_action_does_not_mislabel_runtime_degradation_as_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self.make_install_tree(pathlib.Path(tmp), "v0.35.0")
            report = inspect_installations(
                project,
                home,
                runtime_fixtures={
                    "codex": {
                        "state": "unavailable",
                        "source": "codex debug prompt-input capture",
                    }
                },
            )

            self.assertEqual("present", report["harnesses"]["codex"]["installation"]["state"])
            self.assertEqual("unavailable", report["harnesses"]["codex"]["runtime"]["state"])
            self.assertEqual(
                ["Resolve the codex health findings, then rerun the free checks"],
                report["top_actions"],
            )


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

    def test_runtime_only_entries_reflect_description_visibility(self) -> None:
        fixture = {
            "harness": "codex",
            "source_command": "captured Codex catalogue",
            "skills": [
                {
                    "name": "described",
                    "description": "Visible runtime skill.",
                    "path": "/runtime/described/SKILL.md",
                },
                {
                    "name": "hidden",
                    "path": "/runtime/hidden/SKILL.md",
                },
            ],
        }

        result = compare_runtime_catalog([], fixture)
        entries = {row["runtime_name"]: row for row in result["entries"]}

        self.assertEqual("present", entries["described"]["state"])
        self.assertEqual("loaded-but-undiscoverable", entries["hidden"]["state"])
        self.assertEqual(
            "/runtime/hidden/SKILL.md",
            entries["hidden"]["runtime"]["path"],
        )
        self.assertEqual("captured Codex catalogue", result["capture"]["source_command"])

    def test_runtime_comparisons_preserve_fixture_and_untested_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            project = base / "project"
            home = base / "home"
            capture_path = base / "runtime-catalogue.json"
            write_json(
                capture_path,
                {
                    "schema_version": 1,
                    "harness": "codex",
                    "source_command": "captured session catalogue",
                    "skills": [
                        {
                            "name": "runtime-only",
                            "description": "Visible runtime-only skill.",
                        }
                    ],
                },
            )
            installation = inspect_installations(project, home)
            postures = inspect_role_postures(ROOT, project)

            observed = compose_doctor_report(
                installation,
                runtime_comparisons=[
                    compare_runtime_catalog(
                        [],
                        load_runtime_fixture(capture_path),
                    )
                ],
                local_slots=declared_local_slots(ROOT),
                role_postures=postures,
                persona_evidence=[],
            )
            observed_check = next(
                row
                for row in observed["checks"]
                if row["check"] == "runtime.codex.runtime-only"
            )

            self.assertEqual(
                [str(capture_path), "captured session catalogue"],
                [item["source"] for item in observed_check["evidence"]],
            )
            self.assertIn(
                f"source: {capture_path}",
                render_doctor_report(observed),
            )

            command = 'codex debug prompt-input "hi"'
            untested = compose_doctor_report(
                installation,
                runtime_comparisons=[
                    compare_runtime_catalog(
                        [],
                        {
                            "harness": "codex",
                            "tested": False,
                            "source_command": command,
                        },
                    )
                ],
                local_slots=declared_local_slots(ROOT),
                role_postures=postures,
                persona_evidence=[],
            )
            untested_checks = [
                row
                for row in untested["checks"]
                if row["check"].startswith("runtime.codex.")
            ]

            self.assertEqual(1, len(untested_checks))
            self.assertEqual("runtime.codex.catalogue", untested_checks[0]["check"])
            self.assertEqual("N/A", untested_checks[0]["status"])
            self.assertEqual(
                "codex runtime catalogue is not tested",
                untested_checks[0]["fact"],
            )
            self.assertEqual(
                [command],
                [item["source"] for item in untested_checks[0]["evidence"]],
            )
            self.assertIn(f"source: {command}", render_doctor_report(untested))

    def test_runtime_fixture_rejects_malformed_collections_with_source(self) -> None:
        malformed = (
            ({"schema_version": "1"}, "schema_version must be integer 1"),
            ({"schema_version": True}, "schema_version must be integer 1"),
            ({"schema_version": 2}, "schema_version must be integer 1"),
            ({"harness": []}, "harness must be claude, codex, or pi"),
            ({"harness": 7}, "harness must be claude, codex, or pi"),
            ({"tested": None}, "tested must be boolean"),
            ({"tested": "false"}, "tested must be boolean"),
            ({"state": "not-tested"}, "state must be a supported string"),
            ({"state": None}, "state must be a supported string"),
            ({"state": []}, "state must be a supported string"),
            ({"state": "mystery"}, "state must be a supported string"),
            ({"source": None}, "source must be a non-empty string"),
            ({"source": ["capture"]}, "source must be a non-empty string"),
            ({"source": "   "}, "source must be a non-empty string"),
            ({"source_path": None}, "source_path must be a non-empty string"),
            ({"source_path": []}, "source_path must be a non-empty string"),
            ({"skill_roots": None}, "skill_roots must be a string sequence"),
            ({"skill_roots": [7]}, "skill_roots must be a string sequence"),
            ({"skills": {}}, "skills must be a sequence"),
            ({"skills": [None]}, "skills entry 0 must be a mapping"),
            ({"skills": [{}]}, "skills entry 0 name must be a non-empty string"),
            (
                {"skills": [{"name": "doctor", "path": []}]},
                "skills entry 0 path must be a string",
            ),
        )
        for fields, detail in malformed:
            with self.subTest(fields=fields), tempfile.TemporaryDirectory() as tmp:
                path = pathlib.Path(tmp) / "runtime.json"
                write_json(
                    path,
                    {"schema_version": 1, "harness": "codex", **fields},
                )

                with self.assertRaises(ValueError) as raised:
                    load_runtime_fixture(path)

                self.assertIn(str(path), str(raised.exception))
                self.assertIn(detail, str(raised.exception))

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "runtime.json"
            write_json(
                path,
                {
                    "schema_version": 1,
                    "harness": "codex",
                    "tested": False,
                },
            )

            fixture = load_runtime_fixture(path)
            comparison = compare_runtime_catalog([], fixture)

            self.assertEqual(str(path), fixture["source_path"])
            self.assertEqual([str(path)], comparison["capture"]["sources"])
            self.assertEqual("N/A", comparison["status"])

    def test_public_runtime_capture_boundaries_reject_malformed_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            with self.assertRaises(ValueError) as installation_error:
                inspect_installations(
                    base / "project",
                    base / "home",
                    runtime_fixtures={"codex": {"skill_roots": None}},
                )
            self.assertIn("codex runtime capture", str(installation_error.exception))
            self.assertIn(
                "skill_roots must be a string sequence",
                str(installation_error.exception),
            )

        with self.assertRaises(ValueError) as comparison_error:
            compare_runtime_catalog(
                self.disk,
                {"harness": "codex", "skills": None},
            )
        self.assertIn("runtime catalogue capture", str(comparison_error.exception))
        self.assertIn("skills must be a sequence", str(comparison_error.exception))

    def test_generic_foundation_source_does_not_establish_crew_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            runtime = {
                "codex": {
                    "harness": "codex",
                    "source": "captured catalogue",
                    "skills": [
                        {
                            "name": "other:doctor",
                            "source": "foundation",
                            "description": "Another foundation's doctor.",
                            "path": "/unrelated/foundation/skills/doctor/SKILL.md",
                        }
                    ],
                }
            }

            codex = inspect_installations(
                base / "project",
                base / "home",
                runtime,
            )["harnesses"]["codex"]

            self.assertEqual("omitted", codex["runtime"]["state"])

    def test_raw_codex_prompt_parser_reproduces_description_truncation(self) -> None:
        fixture = parse_codex_prompt_capture(FIXTURES / "runtime/codex-prompt-raw.json")
        result = compare_runtime_catalog(self.disk[:-1], fixture)
        states = {row["runtime_name"]: row["state"] for row in result["entries"]}
        self.assertEqual("working", states["crew:doctor"])
        self.assertEqual("truncated", states["crew:onboarding"])

    def test_raw_codex_prompt_parser_rejects_malformed_message_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "codex-prompt.json"
            write_json(path, [{"role": "user", "content": None}])

            with self.assertRaises(ValueError) as raised:
                parse_codex_prompt_capture(path)

            self.assertIn(str(path), str(raised.exception))
            self.assertIn("message 0 content must be a sequence", str(raised.exception))

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

    def test_only_supported_untested_states_are_not_tested(self) -> None:
        for fields in (
            {"tested": False},
            {"state": "not tested"},
            {"tested": False, "state": "not tested"},
        ):
            with self.subTest(fields=fields):
                source = f"pi catalogue probe intentionally not run: {fields}"
                result = compare_runtime_catalog(
                    self.disk,
                    {
                        "harness": "pi",
                        "source_command": source,
                        **fields,
                    },
                )

                self.assertEqual("N/A", result["status"])
                self.assertTrue(result["entries"])
                self.assertEqual(
                    {"not tested"},
                    {row["state"] for row in result["entries"]},
                )
                self.assertEqual([source], result["capture"]["sources"])

        for state in ("omitted", "unavailable"):
            with self.subTest(state=state):
                result = compare_runtime_catalog(
                    self.disk,
                    {
                        "harness": "pi",
                        "state": state,
                        "source_command": f"pi catalogue probe reported {state}",
                    },
                )

                self.assertEqual("DEGRADED", result["status"])
                self.assertEqual({state}, {row["state"] for row in result["entries"]})

        contradictions = (
            {"tested": False, "state": "working"},
            {"tested": True, "state": "not tested"},
        )
        for fields in contradictions:
            with self.subTest(fields=fields), self.assertRaisesRegex(
                ValueError,
                "tested and state are inconsistent",
            ):
                compare_runtime_catalog(
                    self.disk,
                    {
                        "harness": "pi",
                        "source_command": "contradictory capture",
                        **fields,
                    },
                )

        for fields in ({"tested": "false"}, {"state": "failed"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                compare_runtime_catalog(
                    self.disk,
                    {
                        "harness": "pi",
                        "source_command": "invalid capture",
                        **fields,
                    },
                )

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            with self.assertRaisesRegex(
                ValueError,
                "source_path, source_command, or source is required",
            ):
                inspect_installations(
                    base / "project",
                    base / "home",
                    runtime_fixtures={
                        "codex": {
                            "skills": [
                                {
                                    "name": "crew:doctor",
                                    "description": "Visible Doctor skill.",
                                }
                            ]
                        }
                    },
                )

    def test_duplicate_or_wrong_root_runtime_entries_degrade(self) -> None:
        disk = [{**self.disk[0], "path": "/authorized/skills/doctor/SKILL.md"}]
        fixture = {
            "harness": "codex",
            "source_command": "captured duplicate-root catalogue",
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
                "source_command": "captured structured-namespace catalogue",
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
                    "source": "captured Codex catalogue with unrelated telemetry",
                    "skills": [
                        {
                            "name": "crew:doctor",
                            "description": "Complete Crew description.",
                            "path": "/fixture/cache/pixeloven/crew/0.36.0/skills/doctor/SKILL.md",
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

    def test_malformed_local_slot_declaration_degrades_the_composed_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            skill = root / "skills/example/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: example\ndescription: Example.\nexpects-local: topology\n---\n",
                encoding="utf-8",
            )

            slots = declared_local_slots(root)
            report = compose_doctor_report(
                inspect_installations(root, root / "home"),
                runtime_comparisons=[],
                local_slots=slots,
                role_postures=[],
                persona_evidence=[],
            )

            self.assertEqual([], slots["declared"])
            self.assertEqual("malformed", slots["reads"][0]["state"])
            check = next(row for row in report["checks"] if row["check"] == "local-slots.declarations")
            self.assertEqual("DEGRADED", check["status"])
            self.assertEqual(str(skill), check["evidence"][0]["source"])

    def test_local_slot_entries_are_trimmed_and_whitespace_entries_are_malformed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            skill = root / "skills/example/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: example\ndescription: Example.\n"
                "expects-local: [' topology ', '   ']\n---\n",
                encoding="utf-8",
            )

            slots = declared_local_slots(root)

            self.assertEqual([], slots["declared"])
            self.assertEqual("malformed", slots["reads"][0]["state"])
            self.assertEqual(str(skill), slots["reads"][0]["source"])

    def test_local_slot_entries_must_use_the_closed_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            skill = root / "skills/example/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: example\ndescription: Example.\n"
                "expects-local: [' topology ', vault-ops, topolgy]\n---\n",
                encoding="utf-8",
            )

            slots = declared_local_slots(root)

            self.assertEqual([], slots["declared"])
            self.assertEqual("malformed", slots["reads"][0]["state"])
            self.assertIn("accepted taxonomy", slots["reads"][0]["detail"])
            self.assertNotIn("topolgy", slots["declared"])

    def test_non_list_local_slot_declarations_are_malformed(self) -> None:
        declarations = (
            '"[topology, 42]"',
            "topology",
            "{slot: topology}",
            "null",
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                skill = root / "skills/example/SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text(
                    "---\nname: example\ndescription: Example.\n"
                    f"expects-local: {declaration}\n---\n",
                    encoding="utf-8",
                )

                slots = declared_local_slots(root)

                self.assertEqual([], slots["declared"])
                self.assertEqual([], slots["sources"])
                self.assertEqual("malformed", slots["reads"][0]["state"])
                self.assertEqual(str(skill), slots["reads"][0]["source"])

    def test_mixed_type_local_slot_list_is_rejected_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            skill = root / "skills/example/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: example\ndescription: Example.\n"
                "expects-local: [topology, 42]\n---\n",
                encoding="utf-8",
            )

            slots = declared_local_slots(root)

            self.assertEqual([], slots["declared"])
            self.assertEqual([], slots["sources"])
            self.assertEqual("malformed", slots["reads"][0]["state"])
            self.assertEqual(str(skill), slots["reads"][0]["source"])

    def test_flow_sequence_trailing_comma_and_empty_entries(self) -> None:
        cases = (
            ("[topology,]", ["topology"], None),
            ("[topology, , protected-seams]", [], "malformed"),
            ("[, topology]", [], "malformed"),
            ("[topology,,]", [], "malformed"),
            ("[,]", [], "malformed"),
        )
        for declaration, expected, read_state in cases:
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                skill = root / "skills/example/SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text(
                    "---\nname: example\ndescription: Example.\n"
                    f"expects-local: {declaration}\n---\n",
                    encoding="utf-8",
                )

                slots = declared_local_slots(root)

                self.assertEqual(expected, slots["declared"])
                if read_state is None:
                    self.assertEqual([], slots["reads"])
                    self.assertEqual([str(skill)], slots["sources"])
                else:
                    self.assertEqual(read_state, slots["reads"][0]["state"])
                    self.assertEqual(str(skill), slots["reads"][0]["source"])

    def test_unreadable_local_slot_source_retains_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            skill = root / "skills/example/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_bytes(b"\xff")

            slots = declared_local_slots(root)

            self.assertEqual([], slots["declared"])
            self.assertEqual([], slots["sources"])
            self.assertEqual("unreadable", slots["reads"][0]["state"])
            self.assertEqual(str(skill), slots["reads"][0]["source"])

    def test_m7_profile_taxonomy_has_deterministic_persona_precedence(self) -> None:
        self.assertEqual("portable", profile_for([], persona_evidence=[]))
        self.assertEqual("platform", profile_for(["github"], persona_evidence=[]))
        self.assertEqual("personas", profile_for(["github", "cluster"], persona_evidence=["openclaw manifest"]))

    def test_composed_report_covers_all_inputs_with_one_profile_and_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "home/.codex/plugins/cache/pixeloven/crew/0.36.0"
            write_json(root / ".claude-plugin/plugin.json", {"name": "crew", "version": "0.36.0"})
            write_capability_skill(root, ["external:github"])
            write_codex_marketplace_identity(base / "home")
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
            root = base / "home/.codex/plugins/cache/pixeloven/crew/0.36.0"
            write_json(root / ".claude-plugin/plugin.json", {"name": "crew", "version": "0.36.0"})
            write_capability_skill(root, ["configured", "proven", "failed", "skipped"])
            write_codex_marketplace_identity(base / "home")
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
            proven = next(
                item
                for item in installation["harnesses"]["codex"]["capability_checks"]
                if item["name"] == "proven"
            )
            self.assertEqual("package", proven["ownership"])
            self.assertEqual("portable", report["profile"])

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

    def test_role_readiness_rejects_missing_and_corrupt_rendered_roles(self) -> None:
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            package = pathlib.Path(tmp) / "package"
            shutil.copytree(ROOT / "agents", package / "agents")
            shutil.copytree(ROOT / "pi-agents", package / "pi-agents")
            (package / "agents/reviewer.md").unlink()
            (package / "pi-agents/reviewer.md").write_text(
                "---\nname: wrong\ndescription: Corrupt fixture.\nmodel: fixed\ntools: read\n---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(package)
            claude = next(
                row for row in rows if row["name"] == "reviewer" and row["harness"] == "claude"
            )
            pi = next(row for row in rows if row["name"] == "reviewer" and row["harness"] == "pi")
            self.assertFalse(claude["role_valid"])
            self.assertIn("unreadable", " ".join(claude["validation_errors"]))
            self.assertFalse(pi["role_valid"])
            self.assertIn("forbidden runtime keys", " ".join(pi["validation_errors"]))

            report = compose_doctor_report(
                inspect_installations(package, pathlib.Path(tmp) / "home"),
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=rows,
                persona_evidence=[],
            )
            role_checks = {
                row["check"]: row for row in report["checks"] if row["check"].startswith("role.")
            }
            self.assertEqual("DEGRADED", role_checks["role.claude.reviewer"]["status"])
            self.assertEqual("DEGRADED", role_checks["role.pi.reviewer"]["status"])

    def test_consumer_role_overlay_is_the_resolved_posture_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            overlay = consumer / ".claude/agents/reviewer.md"
            overlay.parent.mkdir(parents=True)
            overlay.write_text(
                "---\nname: reviewer\ndescription: Consumer override.\nmodel: fixed\n"
                "disallowedTools: Write, Edit, NotebookEdit\n---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            reviewer = next(
                row for row in rows if row["name"] == "reviewer" and row["harness"] == "claude"
            )
            self.assertEqual(str(overlay), reviewer["source"])
            self.assertFalse(reviewer["role_valid"])
            self.assertIn("forbidden runtime keys", " ".join(reviewer["validation_errors"]))

    def test_doctor_resolves_overlay_with_quoted_hash_in_opaque_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            overlay = consumer / ".claude/agents/reviewer.md"
            overlay.parent.mkdir(parents=True)
            overlay.write_text(
                "---\nname: reviewer\ndescription: Consumer override.\n"
                "tools: Read, Grep\n"
                'hooks: {PreToolUse: [{matcher: "Bash # guarded", hooks: '
                '[{type: command, command: "printf #ok"}]}]}\n'
                "---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            reviewer = next(
                row for row in rows if row["name"] == "reviewer" and row["harness"] == "claude"
            )

            self.assertTrue(reviewer["role_valid"])
            self.assertEqual(str(overlay), reviewer["source"])

    def test_pi_overlay_precedence_uses_validated_frontmatter_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            overlay = consumer / ".pi/agents/custom-file.md"
            overlay.parent.mkdir(parents=True)
            overlay.write_text(
                "---\nname: reviewer\ndescription: Consumer override.\n"
                "tools: read, bash, grep, find\n---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            reviewers = [
                row for row in rows if row["name"] == "reviewer" and row["harness"] == "pi"
            ]

            self.assertEqual(1, len(reviewers))
            self.assertEqual(str(overlay), reviewers[0]["source"])
            self.assertFalse(reviewers[0]["role_valid"])
            self.assertIn("name must be custom-file", reviewers[0]["validation_errors"])

    def test_malformed_pi_overlay_does_not_suppress_packaged_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            overlay = consumer / ".pi/agents/reviewer.md"
            overlay.parent.mkdir(parents=True)
            overlay.write_text(
                "---\nname: [reviewer]\ndescription: Broken override.\n"
                "tools: read, bash, grep, find\n---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            reviewers = [
                row for row in rows if row["name"] == "reviewer" and row["harness"] == "pi"
            ]
            unresolved = next(row for row in rows if row["source"] == str(overlay))

            self.assertEqual(1, len(reviewers))
            self.assertTrue(reviewers[0]["role_valid"])
            self.assertEqual(str(ROOT / "pi-agents/reviewer.md"), reviewers[0]["source"])
            self.assertIsNone(unresolved["name"])
            self.assertFalse(unresolved["role_valid"])

    def test_consumer_fleet_override_uses_resolved_consumer_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            override = consumer / ".claude/agents/reviewer.md"
            override.parent.mkdir(parents=True)
            override.write_text(
                "---\nname: reviewer\ndescription: Consumer reviewer.\n"
                "tools: Read, Grep\n---\n",
                encoding="utf-8",
            )

            report = compose_doctor_report(
                inspect_installations(consumer, pathlib.Path(tmp) / "home"),
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=inspect_role_postures(ROOT, consumer),
                persona_evidence=[],
            )
            consumer_check = next(
                row for row in report["checks"] if row["check"] == "role.claude.reviewer"
            )
            shipped_check = next(
                row for row in report["checks"] if row["check"] == "role.claude.lead"
            )

            self.assertEqual("OK", consumer_check["status"])
            self.assertEqual(
                "effective tool posture is the validated resolved-consumer posture",
                consumer_check["inference"],
            )
            self.assertNotIn("rendered role contract", consumer_check["inference"])
            self.assertEqual(
                "effective tool posture matches the rendered role contract",
                shipped_check["inference"],
            )

    def test_consumer_only_roles_are_enumerated_separately_from_the_crew_fleet(self) -> None:
        consumer = FIXTURES / "consumer-valid"

        postures = inspect_role_postures(ROOT, consumer)
        librarian_postures = {
            row["harness"]: row
            for row in postures
            if row["name"] == "librarian"
        }
        self.assertEqual({"claude", "pi", "neutral"}, set(librarian_postures))
        self.assertTrue(all(row["role_valid"] for row in librarian_postures.values()))
        self.assertTrue(
            all(
                "shell access" in row["caveat"]
                for harness, row in librarian_postures.items()
                if harness in {"claude", "pi"}
            )
        )
        self.assertIn("harness", librarian_postures["neutral"]["caveat"])

        report = compose_doctor_report(
            inspect_installations(consumer, pathlib.Path("/nonexistent-doctor-home")),
            runtime_comparisons=[],
            local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
            role_postures=postures,
            persona_evidence=[],
        )
        role_checks = {
            row["check"]: row
            for row in report["checks"]
            if row["check"].startswith("role.")
        }
        consumer_checks = {
            name: row for name, row in role_checks.items() if name.startswith("role.consumer.")
        }
        fleet_checks = {
            name: row for name, row in role_checks.items() if not name.startswith("role.consumer.")
        }

        self.assertEqual(14, len(fleet_checks))
        self.assertEqual(
            {
                "role.consumer.claude.librarian",
                "role.consumer.pi.librarian",
                "role.consumer.neutral.librarian",
            },
            set(consumer_checks),
        )
        self.assertEqual({"OK"}, {row["status"] for row in consumer_checks.values()})
        self.assertTrue(
            all(
                "shell access" in row["fact"]
                for name, row in consumer_checks.items()
                if ".neutral." not in name
            )
        )
        self.assertIn("harness", consumer_checks["role.consumer.neutral.librarian"]["fact"])
        rendered = render_doctor_report(report)
        self.assertTrue(all(check in rendered for check in consumer_checks))

    def test_claude_consumer_role_uses_frontmatter_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".claude/agents/custom-file.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: librarian\ndescription: Maintains references.\n"
                "tools: Read, Grep\n---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            librarian = next(
                row
                for row in rows
                if row["name"] == "librarian" and row["harness"] == "claude"
            )

            self.assertTrue(librarian["role_valid"])
            self.assertEqual(str(role), librarian["source"])
            report = compose_doctor_report(
                inspect_installations(consumer, pathlib.Path(tmp) / "home"),
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=rows,
                persona_evidence=[],
            )
            check = next(
                item
                for item in report["checks"]
                if item["check"] == "role.consumer.claude.librarian"
            )
            self.assertEqual("OK", check["status"])
            self.assertEqual(str(role), check["evidence"][0]["source"])

    def test_claude_consumer_role_identity_must_not_be_blank(self) -> None:
        for declaration, expected_name, valid in (
            ("' '", None, False),
            ('""', None, False),
            ("librarian", "librarian", True),
        ):
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as tmp:
                consumer = pathlib.Path(tmp) / "consumer"
                role = consumer / ".claude/agents/custom-file.md"
                role.parent.mkdir(parents=True)
                role.write_text(
                    f"---\nname: {declaration}\ndescription: Maintains references.\n"
                    "tools: Read, Grep\n---\n",
                    encoding="utf-8",
                )

                rows = inspect_role_postures(ROOT, consumer)
                posture = next(row for row in rows if row["source"] == str(role))

                self.assertEqual(expected_name, posture["name"])
                self.assertEqual(valid, posture["role_valid"])
                if not valid:
                    self.assertIn(
                        "resolved role identity is missing",
                        posture["validation_errors"],
                    )

    def test_invalid_claude_consumer_identity_retains_source_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".claude/agents/review/custom-file.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: custom:reviewer\ndescription: Reviews changes.\n"
                "tools: Read, Grep\n---\n",
                encoding="utf-8",
            )

            posture = next(
                row
                for row in inspect_role_postures(ROOT, consumer)
                if row["source"] == str(role)
            )

            self.assertIsNone(posture["name"])
            self.assertFalse(posture["role_valid"])
            self.assertIn(
                "name must use lowercase letters and hyphens",
                posture["validation_errors"],
            )

    def test_invalid_claude_overlay_does_not_suppress_packaged_fleet_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            overlay = consumer / ".claude/agents/reviewer.md"
            overlay.parent.mkdir(parents=True)
            overlay.write_text(
                "---\nname: custom:reviewer\ndescription: Invalid override.\n"
                "tools: Read, Grep\n---\n",
                encoding="utf-8",
            )

            postures = inspect_role_postures(ROOT, consumer)
            reviewer = next(
                row
                for row in postures
                if row["name"] == "reviewer" and row["harness"] == "claude"
            )
            unresolved = next(row for row in postures if row["source"] == str(overlay))

            self.assertTrue(reviewer["role_valid"])
            self.assertEqual("crew", reviewer["scope"])
            self.assertEqual(str(ROOT / "agents/reviewer.md"), reviewer["source"])
            self.assertIsNone(unresolved["name"])
            self.assertFalse(unresolved["role_valid"])

            report = compose_doctor_report(
                inspect_installations(consumer, pathlib.Path(tmp) / "home"),
                runtime_comparisons=[],
                local_slots={"declared": [], "recommended_vocabulary": [], "sources": []},
                role_postures=postures,
                persona_evidence=[],
            )
            checks = {row["check"]: row for row in report["checks"]}

            self.assertEqual("OK", checks["role.claude.reviewer"]["status"])
            unresolved_check = checks["role.consumer.claude.unresolved-1"]
            self.assertEqual("DEGRADED", unresolved_check["status"])
            self.assertEqual(str(overlay), unresolved_check["evidence"][0]["source"])

    def test_nested_claude_and_pi_consumer_roles_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            roles = (
                (
                    consumer / ".claude/agents/review/security.md",
                    "security-reviewer",
                    "claude",
                    "tools: Read, Grep\n",
                ),
                (
                    consumer / ".pi/agents/review/security.md",
                    "security",
                    "pi",
                    "tools: read, web\n",
                ),
            )
            for path, identity, _, tools in roles:
                path.parent.mkdir(parents=True)
                path.write_text(
                    f"---\nname: {identity}\ndescription: Reviews security.\n"
                    f"{tools}---\n",
                    encoding="utf-8",
                )

            rows = inspect_role_postures(ROOT, consumer)

            for path, identity, harness, _ in roles:
                with self.subTest(harness=harness):
                    posture = next(row for row in rows if row["source"] == str(path))
                    self.assertEqual(identity, posture["name"])
                    self.assertEqual(harness, posture["harness"])
                    self.assertTrue(posture["role_valid"])

    def test_claude_duplicate_frontmatter_identities_are_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            agents = consumer / ".claude/agents"
            agents.mkdir(parents=True)
            paths = [agents / "first.md", agents / "second.md"]
            for path in paths:
                path.write_text(
                    "---\nname: librarian\ndescription: Maintains references.\n"
                    "tools: Read, Grep\n---\n",
                    encoding="utf-8",
                )

            rows = inspect_role_postures(ROOT, consumer)
            librarians = [
                row
                for row in rows
                if row["name"] == "librarian" and row["harness"] == "claude"
            ]

            self.assertEqual(2, len(librarians))
            self.assertEqual({str(path) for path in paths}, {row["source"] for row in librarians})
            self.assertTrue(all(not row["role_valid"] for row in librarians))
            self.assertTrue(
                all(
                    "duplicate resolved role identity librarian" in row["validation_errors"]
                    for row in librarians
                )
            )

    def test_custom_consumer_tool_posture_is_reported_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".pi/agents/librarian.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: librarian\ndescription: Custom consumer role.\n"
                "tools: read, bash, web\n---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            librarian = next(
                row
                for row in rows
                if row["name"] == "librarian" and row["harness"] == "pi"
            )

            self.assertTrue(librarian["role_valid"])
            self.assertEqual("consumer", librarian["scope"])
            self.assertEqual(["read", "bash", "web"], librarian["allowed_tools"])
            self.assertIn("read, bash, web", librarian["write_effect"])
            self.assertIn("posture advisory", librarian["caveat"])

    def test_pi_consumer_without_bash_reports_shell_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".pi/agents/librarian.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: librarian\ndescription: Custom consumer role.\n"
                "tools: read, web\n---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            librarian = next(
                row
                for row in rows
                if row["name"] == "librarian" and row["harness"] == "pi"
            )

            self.assertTrue(librarian["role_valid"])
            self.assertEqual(["read", "web"], librarian["allowed_tools"])
            self.assertIn("shell access is unavailable", librarian["caveat"])
            self.assertNotIn("posture advisory", librarian["caveat"])

    def test_claude_consumer_posture_composes_both_tool_fields(self) -> None:
        cases = (
            (
                "tools: Read, Grep\n",
                ["Read", "Grep"],
                [],
                "Bash is unavailable",
                "effective write tools: none",
            ),
            (
                "disallowedTools: Write, Edit, NotebookEdit\n",
                [],
                ["Write", "Edit", "NotebookEdit"],
                "Bash is available",
                "effective write tools: none",
            ),
            (
                "tools: Read, Bash, Write\ndisallowedTools: Grep\n",
                ["Read", "Bash", "Write"],
                ["Grep"],
                "Bash is available",
                "effective write tools: Write",
            ),
            (
                "disallowedTools: Bash\n",
                [],
                ["Bash"],
                "Bash is unavailable",
                "effective write tools: Write, Edit, NotebookEdit",
            ),
            (
                "disallowedTools: Bash(git push *)\n",
                [],
                ["Bash(git push *)"],
                "Bash is available",
                "effective write tools: Write, Edit, NotebookEdit",
            ),
            (
                "disallowedTools: Bash, Bash(git push *)\n",
                [],
                ["Bash", "Bash(git push *)"],
                "Bash is unavailable",
                "effective write tools: Write, Edit, NotebookEdit",
            ),
        )
        for fields, allowed, denied, bash_state, write_state in cases:
            with self.subTest(fields=fields), tempfile.TemporaryDirectory() as tmp:
                consumer = pathlib.Path(tmp) / "consumer"
                role = consumer / ".claude/agents/librarian.md"
                role.parent.mkdir(parents=True)
                role.write_text(
                    "---\nname: librarian\ndescription: Claude consumer role.\n"
                    f"{fields}---\n",
                    encoding="utf-8",
                )

                rows = inspect_role_postures(ROOT, consumer)
                librarian = next(
                    row
                    for row in rows
                    if row["name"] == "librarian" and row["harness"] == "claude"
                )

                self.assertTrue(librarian["role_valid"])
                self.assertEqual(allowed, librarian["allowed_tools"])
                self.assertEqual(denied, librarian["denied_tools"])
                self.assertIn(bash_state, librarian["caveat"])
                self.assertIn(write_state, librarian["write_effect"])
                self.assertIn(write_state, librarian["caveat"])

    def test_scoped_claude_deny_rule_is_reported_as_a_constraint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".claude/agents/reviewer.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: reviewer\ndescription: Reviews changes.\n"
                "disallowedTools: Bash(git push *)\n---\n",
                encoding="utf-8",
            )

            reviewer = next(
                row
                for row in inspect_role_postures(ROOT, consumer)
                if row["name"] == "reviewer" and row["harness"] == "claude"
            )

            self.assertTrue(reviewer["role_valid"])
            self.assertIn("Bash is available", reviewer["caveat"])
            self.assertIn(
                "scoped denies: Bash(git push *)",
                reviewer["write_effect"],
            )

    def test_claude_bash_rules_preserve_bare_and_scoped_capabilities(self) -> None:
        cases = (
            (
                "tools: Bash\n",
                "bare allows: Bash",
                "Bash is available through a bare allow",
                True,
            ),
            (
                "tools: Bash(*)\n",
                "bare allows: Bash(*)",
                "Bash is available through a bare allow",
                True,
            ),
            (
                "tools: Bash(git status:*)\n",
                "scoped allows: Bash(git status:*)",
                "Bash is restricted to scoped allows: Bash(git status:*)",
                False,
            ),
            (
                "disallowedTools: Bash\n",
                "bare denies: Bash",
                "Bash is unavailable through a bare deny",
                False,
            ),
            (
                "disallowedTools: Bash(*)\n",
                "bare denies: Bash(*)",
                "Bash is unavailable through a bare deny",
                False,
            ),
            (
                "disallowedTools: Bash(git push:*)\n",
                "scoped denies: Bash(git push:*)",
                "Bash is available without an allowlist with scoped denies: Bash(git push:*)",
                True,
            ),
        )
        for fields, evidence, caveat, advisory in cases:
            with self.subTest(fields=fields), tempfile.TemporaryDirectory() as tmp:
                consumer = pathlib.Path(tmp) / "consumer"
                role = consumer / ".claude/agents/reviewer.md"
                role.parent.mkdir(parents=True)
                role.write_text(
                    "---\nname: reviewer\ndescription: Reviews changes.\n"
                    f"{fields}---\n",
                    encoding="utf-8",
                )

                reviewer = next(
                    row
                    for row in inspect_role_postures(ROOT, consumer)
                    if row["name"] == "reviewer" and row["harness"] == "claude"
                )

                self.assertTrue(reviewer["role_valid"])
                self.assertIn(evidence, reviewer["write_effect"])
                self.assertIn(caveat, reviewer["caveat"])
                self.assertEqual(advisory, "write posture advisory" in reviewer["caveat"])

    def test_claude_tool_rule_commas_preserve_permission_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".claude/agents/reviewer.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: reviewer\ndescription: Reviews changes.\n"
                "tools: Agent(worker, researcher), Read, Bash\n"
                "---\n",
                encoding="utf-8",
            )

            reviewer = next(
                row
                for row in inspect_role_postures(ROOT, consumer)
                if row["name"] == "reviewer" and row["harness"] == "claude"
            )

            self.assertTrue(reviewer["role_valid"])
            self.assertEqual(
                ["Agent(worker, researcher)", "Read", "Bash"],
                reviewer["allowed_tools"],
            )
            self.assertIn(
                "declared allowlist: Agent(worker, researcher), Read, Bash",
                reviewer["write_effect"],
            )

    def test_mcp_servers_frontmatter_preserves_role_resolution(self) -> None:
        cases = (
            (
                "mcpServers:\n"
                "  - playwright:\n"
                "      type: stdio\n"
                "      command: npx\n"
                "      env:\n"
                "        TOKEN: ${TOKEN:-missing}\n"
                "        _JAVA_OPTIONS: -Xmx512m\n",
                True,
            ),
            (
                "mcpServers:\n"
                "  - playwright:\n"
                "      type: [unterminated\n",
                False,
            ),
        )
        for declaration, valid in cases:
            with self.subTest(valid=valid), tempfile.TemporaryDirectory() as tmp:
                consumer = pathlib.Path(tmp) / "consumer"
                role = consumer / ".claude/agents/reviewer.md"
                role.parent.mkdir(parents=True)
                role.write_text(
                    "---\nname: reviewer\ndescription: Reviews changes.\n"
                    "tools: Read, Grep\n"
                    f"{declaration}"
                    "---\n",
                    encoding="utf-8",
                )

                rows = inspect_role_postures(ROOT, consumer)
                reviewer = next(
                    row
                    for row in rows
                    if row["name"] == "reviewer" and row["harness"] == "claude"
                )

                self.assertTrue(reviewer["role_valid"])
                self.assertEqual("consumer" if valid else "crew", reviewer["scope"])
                if valid:
                    self.assertEqual(str(role), reviewer["source"])
                    self.assertFalse(
                        any(
                            row["name"] is None and row["source"] == str(role)
                            for row in rows
                        )
                    )
                else:
                    unresolved = next(row for row in rows if row["source"] == str(role))
                    self.assertIsNone(unresolved["name"])
                    self.assertFalse(unresolved["role_valid"])
                    self.assertIn(
                        "invalid YAML frontmatter",
                        " ".join(unresolved["validation_errors"]),
                    )

    def test_nested_claude_hook_preserves_consumer_override_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".claude/agents/reviewer.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: reviewer\ndescription: Reviews changes.\n"
                "tools: Read, Grep\n"
                "hooks: # lifecycle hooks\n"
                "  PreToolUse: # before commands\n"
                "    -   matcher: Bash\n"
                "        hooks: # command hooks\n"
                "          - type: command\n"
                "            command: |2\n"
                "              \t./scripts/check-command.sh\n"
                "              ./scripts/report-result.sh\n"
                "---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            reviewer = next(
                row
                for row in rows
                if row["name"] == "reviewer" and row["harness"] == "claude"
            )

            self.assertTrue(reviewer["role_valid"])
            self.assertEqual("consumer", reviewer["scope"])
            self.assertEqual(str(role), reviewer["source"])
            self.assertFalse(
                any(row["name"] is None and row["source"] == str(role) for row in rows)
            )

    def test_commented_hook_sequence_item_preserves_consumer_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".claude/agents/reviewer.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: reviewer\ndescription: Reviews changes.\n"
                "tools: Read, Grep\n"
                "hooks:\n"
                "  PreToolUse:\n"
                "    - # command hook\n"
                "      type: command\n"
                "      command: ./scripts/check-command.sh\n"
                "---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            reviewer = next(
                row
                for row in rows
                if row["name"] == "reviewer" and row["harness"] == "claude"
            )

            self.assertTrue(reviewer["role_valid"])
            self.assertEqual("consumer", reviewer["scope"])
            self.assertEqual(str(role), reviewer["source"])
            self.assertFalse(
                any(row["name"] is None and row["source"] == str(role) for row in rows)
            )

    def test_malformed_nested_hook_cannot_suppress_packaged_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".claude/agents/reviewer.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: reviewer\ndescription: Invalid hook metadata.\n"
                "tools: Read, Grep\nhooks:\n [unterminated\n---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            reviewer = next(
                row
                for row in rows
                if row["name"] == "reviewer" and row["harness"] == "claude"
            )
            unresolved = next(row for row in rows if row["source"] == str(role))

            self.assertTrue(reviewer["role_valid"])
            self.assertEqual("crew", reviewer["scope"])
            self.assertIsNone(unresolved["name"])
            self.assertFalse(unresolved["role_valid"])
            self.assertIn(
                "invalid YAML frontmatter",
                " ".join(unresolved["validation_errors"]),
            )

    def test_hook_block_scalar_dedent_cannot_suppress_packaged_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".claude/agents/reviewer.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: reviewer\ndescription: Invalid hook metadata.\n"
                "tools: Read, Grep\n"
                "hooks:\n"
                "  PreToolUse:\n"
                "    - matcher: Bash\n"
                "      hooks:\n"
                "        - type: command\n"
                "          command: |\n"
                "              #!/bin/sh\n"
                "            ./scripts/report-result.sh\n"
                "---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            reviewer = next(
                row
                for row in rows
                if row["name"] == "reviewer" and row["harness"] == "claude"
            )
            unresolved = next(row for row in rows if row["source"] == str(role))

            self.assertTrue(reviewer["role_valid"])
            self.assertEqual("crew", reviewer["scope"])
            self.assertIsNone(unresolved["name"])
            self.assertFalse(unresolved["role_valid"])
            self.assertIn(
                "invalid YAML frontmatter",
                " ".join(unresolved["validation_errors"]),
            )

    def test_hook_block_scalar_over_indented_leading_blank_is_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".claude/agents/reviewer.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: reviewer\ndescription: Invalid hook metadata.\n"
                "tools: Read, Grep\n"
                "hooks:\n"
                "  PreToolUse:\n"
                "    - matcher: Bash\n"
                "      hooks:\n"
                "        - type: command\n"
                "          command: |\n"
                "              \n"
                "            ./scripts/report-result.sh\n"
                "---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            reviewer = next(
                row
                for row in rows
                if row["name"] == "reviewer" and row["harness"] == "claude"
            )
            unresolved = next(row for row in rows if row["source"] == str(role))

            self.assertTrue(reviewer["role_valid"])
            self.assertEqual("crew", reviewer["scope"])
            self.assertIsNone(unresolved["name"])
            self.assertFalse(unresolved["role_valid"])
            self.assertIn(
                "invalid YAML frontmatter",
                " ".join(unresolved["validation_errors"]),
            )

    def test_description_scalar_validates_leading_blank_indentation(self) -> None:
        cases = (
            ("    \n  Reviews changes.\n", False),
            ("  \n    Reviews changes.\n", True),
        )
        for description, valid in cases:
            with self.subTest(valid=valid), tempfile.TemporaryDirectory() as tmp:
                consumer = pathlib.Path(tmp) / "consumer"
                role = consumer / ".claude/agents/reviewer.md"
                role.parent.mkdir(parents=True)
                role.write_text(
                    "---\nname: reviewer\ndescription: |\n"
                    f"{description}"
                    "tools: Read, Grep\n"
                    "---\n",
                    encoding="utf-8",
                )

                rows = inspect_role_postures(ROOT, consumer)
                reviewer = next(
                    row
                    for row in rows
                    if row["name"] == "reviewer" and row["harness"] == "claude"
                )

                self.assertTrue(reviewer["role_valid"])
                self.assertEqual("consumer" if valid else "crew", reviewer["scope"])
                if valid:
                    self.assertEqual(str(role), reviewer["source"])
                    self.assertFalse(
                        any(
                            row["name"] is None and row["source"] == str(role)
                            for row in rows
                        )
                    )
                else:
                    unresolved = next(row for row in rows if row["source"] == str(role))
                    self.assertIsNone(unresolved["name"])
                    self.assertFalse(unresolved["role_valid"])
                    self.assertIn(
                        "invalid YAML frontmatter",
                        " ".join(unresolved["validation_errors"]),
                    )

    def test_malformed_claude_consumer_tool_fields_retain_source_evidence(self) -> None:
        fields = (
            "tools: {Read: true}\ndisallowedTools: [Write, 1]\n",
            "tools: Read, , Bash\ndisallowedTools: Write, , Edit\n",
        )
        for declarations in fields:
            with self.subTest(declarations=declarations), tempfile.TemporaryDirectory() as tmp:
                consumer = pathlib.Path(tmp) / "consumer"
                role = consumer / ".claude/agents/librarian.md"
                role.parent.mkdir(parents=True)
                role.write_text(
                    "---\nname: librarian\ndescription: Broken Claude consumer role.\n"
                    f"{declarations}---\n",
                    encoding="utf-8",
                )

                rows = inspect_role_postures(ROOT, consumer)
                librarian = next(
                    row
                    for row in rows
                    if row["name"] == "librarian" and row["harness"] == "claude"
                )

                self.assertFalse(librarian["role_valid"])
                self.assertEqual(str(role), librarian["source"])
                self.assertIn(
                    "tools must be a string sequence",
                    librarian["validation_errors"],
                )
                self.assertIn(
                    "disallowedTools must be a string sequence",
                    librarian["validation_errors"],
                )

    def test_malformed_consumer_tool_posture_retains_source_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "consumer"
            role = consumer / ".pi/agents/librarian.md"
            role.parent.mkdir(parents=True)
            role.write_text(
                "---\nname: librarian\ndescription: Broken consumer role.\n"
                "tools: {read: true}\n---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(ROOT, consumer)
            librarian = next(
                row
                for row in rows
                if row["name"] == "librarian" and row["harness"] == "pi"
            )

            self.assertFalse(librarian["role_valid"])
            self.assertEqual(str(role), librarian["source"])
            self.assertIn("tools must be a string sequence", librarian["validation_errors"])

    def test_shipped_roles_still_require_a_fixed_write_posture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = pathlib.Path(tmp) / "package"
            shutil.copytree(ROOT / "agents", package / "agents")
            shutil.copytree(ROOT / "pi-agents", package / "pi-agents")
            role = package / "pi-agents/lead.md"
            role.write_text(
                "---\nname: lead\ndescription: Altered shipped role.\n"
                "tools: read, bash, web\n---\n",
                encoding="utf-8",
            )

            rows = inspect_role_postures(package)
            lead = next(
                row for row in rows if row["name"] == "lead" and row["harness"] == "pi"
            )

            self.assertFalse(lead["role_valid"])
            self.assertIn(
                "tool posture does not match a supported write posture",
                lead["validation_errors"],
            )

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
