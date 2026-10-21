import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from scripts.check_skills import (
    description_costs,
    expected_local_slots,
    validate_root,
)
from scripts.crew_doctor import (
    HARNESS_DESCRIPTION_BUDGETS,
    compose_doctor_report,
    declared_local_slots,
    description_cost,
    inspect_installations,
    inspect_packs,
    render_doctor_report,
    slot_fills,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
DESCRIPTION = "Use when exercising the pack contract fixture so that this fixture description comfortably clears the schema-v2 minimum length."


def write_skill(root: pathlib.Path, name: str, extra: str = "", requires: str = "[]") -> pathlib.Path:
    skill = root / "skills" / name / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"---\nname: {name}\ndescription: {DESCRIPTION}\ntier: subject\n"
        f"requires: {requires}\n{extra}---\n\n# {name}\n",
        encoding="utf-8",
    )
    return skill


def write_pack(root: pathlib.Path, name: str = "example-skills", *, package_json: bool = False) -> None:
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin/plugin.json").write_text(
        json.dumps({"name": name, "version": "1.0.0", "skills": "./skills"}), encoding="utf-8"
    )
    if package_json:
        (root / "package.json").write_text(json.dumps({"name": name, "version": "1.0.0"}), encoding="utf-8")


def write_crew(root: pathlib.Path, version: str) -> None:
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin/plugin.json").write_text(
        json.dumps({"name": "crew", "version": version, "skills": "./skills"}), encoding="utf-8"
    )
    (root / "skills").mkdir(exist_ok=True)


class ProvidesFieldTests(unittest.TestCase):
    def test_slot_list_resolves_from_crew_install_not_the_pack(self) -> None:
        listed = {
            line.strip()
            for line in (ROOT / "roles/expected-local-skills.txt").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertEqual(listed, expected_local_slots())
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            write_pack(pack)
            (pack / "roles").mkdir()
            (pack / "roles/expected-local-skills.txt").write_text("pack-invented-slot\n", encoding="utf-8")
            write_skill(pack, "pack-skill", "provides: [pack-invented-slot]\n", "[plugin:crew@>=0.38.0]")
            errors = validate_root(pack, pack=True)
            self.assertTrue(any("provides" in error for error in errors), errors)

    def test_provides_accepts_declared_slots_and_rejects_everything_else(self) -> None:
        cases = {
            "provides: [protected-seams]\n": False,
            "provides: [topology, secret-paths]\n": False,
            "provides: []\n": True,
            "provides: protected-seams\n": True,
            "provides: [not-a-slot]\n": True,
            # Recommended vocabulary is not an expected-local slot roles cite.
            "provides: [vault-ops]\n": True,
        }
        for extra, should_fail in cases.items():
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as tmp:
                pack = pathlib.Path(tmp)
                write_pack(pack)
                write_skill(pack, "pack-skill", extra, "[plugin:crew@>=0.38.0]")
                errors = validate_root(pack, pack=True)
                self.assertEqual(should_fail, any("provides" in error for error in errors), errors)

    def test_crew_fills_no_slots_itself(self) -> None:
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            self.assertNotIn("\nprovides:", path.read_text(encoding="utf-8").split("---", 2)[1], str(path))

    def test_plugin_requirement_vocabulary(self) -> None:
        cases = {
            "[plugin:crew@>=0.38.0]": False,
            "[plugin:crew@>=0.38.0, cli:gh]": False,
            "[plugin:crew]": True,
            "[plugin:crew@^0.38.0]": True,
            "[plugin:crew@>=0.38]": True,
        }
        for requires, should_fail in cases.items():
            with self.subTest(requires=requires), tempfile.TemporaryDirectory() as tmp:
                pack = pathlib.Path(tmp)
                write_pack(pack)
                write_skill(pack, "pack-skill", requires=requires)
                errors = validate_root(pack, pack=True)
                self.assertEqual(
                    should_fail, any("invalid requires entry" in error for error in errors), errors
                )


class PackModeTests(unittest.TestCase):
    def test_conforming_pack_passes_with_a_single_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            write_pack(pack)
            write_skill(pack, "pack-skill", "provides: [protected-seams]\n", "[plugin:crew@>=0.38.0]")
            write_skill(pack, "pack-utility")
            self.assertEqual([], validate_root(pack, pack=True))

    def test_pack_must_declare_its_crew_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            write_pack(pack)
            write_skill(pack, "pack-skill")
            errors = validate_root(pack, pack=True)
            self.assertTrue(any("plugin:crew@>=" in error for error in errors), errors)

    def test_pack_ships_no_roles(self) -> None:
        for directory in ("roles", "agents", "pi-agents"):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as tmp:
                pack = pathlib.Path(tmp)
                write_pack(pack)
                write_skill(pack, "pack-skill", requires="[plugin:crew@>=0.38.0]")
                (pack / directory).mkdir()
                errors = validate_root(pack, pack=True)
                self.assertTrue(any("ships no roles" in error for error in errors), errors)

    def test_pack_needs_at_least_one_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            write_skill(pack, "pack-skill", requires="[plugin:crew@>=0.38.0]")
            errors = validate_root(pack, pack=True)
            self.assertTrue(any("manifest" in error for error in errors), errors)

    def test_default_mode_still_requires_both_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            write_pack(pack)
            write_skill(pack, "pack-skill")
            errors = validate_root(pack)
            self.assertTrue(any(error.startswith("package.json: invalid JSON") for error in errors), errors)

    def test_no_arg_invocation_is_unchanged(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/check_skills.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            "manifests valid; all SKILL.md frontmatter conforms to schema v2 "
            "and the 300-character description budget\n",
            result.stdout,
        )


class DescriptionCostReportTests(unittest.TestCase):
    def test_costs_are_per_skill_and_total(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            write_pack(pack)
            write_skill(pack, "alpha")
            write_skill(pack, "beta")
            costs = description_costs(pack)
            self.assertEqual([("alpha", len(DESCRIPTION)), ("beta", len(DESCRIPTION))], costs)

    def test_report_cost_never_fails_a_valid_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            write_pack(pack)
            for index in range(200):
                write_skill(pack, f"skill-{index:03}", requires="[plugin:crew@>=0.38.0]")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/check_skills.py"),
                    "--root",
                    str(pack),
                    "--pack",
                    "--report-cost",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn(f"skill-000  {len(DESCRIPTION)}", result.stdout)
            self.assertIn(f"total always-on description chars: {200 * len(DESCRIPTION)} (200 skills)", result.stdout)


class DoctorPackTests(unittest.TestCase):
    def test_pack_requirement_is_verified_against_installed_crew(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            crew = base / "crew"
            write_crew(crew, "0.38.0")
            satisfied = base / "satisfied"
            write_pack(satisfied, "satisfied-skills")
            write_skill(satisfied, "one", requires="[plugin:crew@>=0.38.0]")
            ahead = base / "ahead"
            write_pack(ahead, "ahead-skills")
            write_skill(ahead, "two", requires="[plugin:crew@>=1.0.0]")
            undeclared = base / "undeclared"
            write_pack(undeclared, "undeclared-skills")
            write_skill(undeclared, "three", "provides: [topology]\n")
            unrelated = base / "unrelated"
            write_pack(unrelated, "unrelated-plugin")
            write_skill(unrelated, "four")

            packs = inspect_packs([satisfied, ahead, undeclared, unrelated, crew], crew)
            self.assertEqual(
                {
                    "satisfied-skills": "satisfied",
                    "ahead-skills": "unsatisfied",
                    "undeclared-skills": "undeclared",
                },
                {pack["name"]: pack["state"] for pack in packs},
            )

    def test_local_overlay_outranks_pack_fill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            crew = base / "crew"
            write_crew(crew, "0.38.0")
            overlay = base / "project/.agents"
            write_skill(overlay, "project-topology")
            write_skill(overlay, "seams-notes", "provides: [protected-seams]\n")
            pack = base / "pack"
            write_pack(pack, "example-skills")
            write_skill(pack, "pack-seams", "provides: [protected-seams, secret-paths]\n", "[plugin:crew@>=0.38.0]")

            fills = slot_fills(
                ["topology", "protected-seams", "secret-paths", "agent-runtime"],
                local_roots=[overlay / "skills"],
                packs=inspect_packs([pack], crew),
            )
            slots = fills["slots"]
            self.assertEqual("local", slots["topology"]["effective"])
            self.assertEqual("name", slots["topology"]["local"][0]["basis"])
            self.assertEqual("local", slots["protected-seams"]["effective"])
            self.assertEqual("example-skills", slots["protected-seams"]["packs"][0]["pack"])
            self.assertEqual("pack", slots["secret-paths"]["effective"])
            self.assertIsNone(slots["agent-runtime"]["effective"])

            report = compose_doctor_report(
                inspect_installations(base / "project", base / "home"),
                runtime_comparisons=[],
                local_slots=declared_local_slots(crew),
                role_postures=[],
                persona_evidence=[],
                slot_fills=fills,
                packs=inspect_packs([pack], crew),
            )
            rows = {row["check"]: row for row in report["checks"]}
            self.assertIn(
                "slot `secret-paths` filled by pack `example-skills`",
                rows["local-slots.fill.secret-paths"]["fact"],
            )
            self.assertIn("local outranks pack", rows["local-slots.fill.protected-seams"]["fact"])
            self.assertEqual("MISSING", rows["local-slots.fill.agent-runtime"]["status"])
            self.assertEqual("OK", rows["pack.example-skills.requires"]["status"])
            render_doctor_report(report)

    def test_description_cost_is_reported_against_dated_budgets(self) -> None:
        codex = next(budget for budget in HARNESS_DESCRIPTION_BUDGETS if budget["harness"] == "codex")
        self.assertEqual("2026-09-05", codex["measured"])
        self.assertIn("#72", codex["evidence"])
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            crew = base / "crew"
            write_crew(crew, "0.38.0")
            write_skill(crew, "crew-skill")
            pack = base / "pack"
            write_pack(pack, "example-skills")
            for index in range(250):
                write_skill(pack, f"pack-{index:03}", requires="[plugin:crew@>=0.38.0]")

            crew_cost = description_cost(crew)
            self.assertEqual(len(DESCRIPTION), crew_cost["total"])
            report = compose_doctor_report(
                inspect_installations(base / "project", base / "home"),
                runtime_comparisons=[],
                local_slots=declared_local_slots(crew),
                role_postures=[],
                persona_evidence=[],
                description_costs=[crew_cost, description_cost(pack, label="example-skills")],
            )
            row = next(row for row in report["checks"] if row["check"] == "description-cost.always-on")
            self.assertEqual("OK", row["status"])
            self.assertIn(f"{251 * len(DESCRIPTION):,}", row["fact"])
            self.assertIn("example-skills", row["fact"])
            self.assertIn("2026-09-05", row["inference"])
            self.assertIn("example-skills", row["recommendation"])
            self.assertNotEqual([row["recommendation"]], report["top_actions"])

    def test_report_without_pack_inputs_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            report = compose_doctor_report(
                inspect_installations(base / "project", base / "home"),
                runtime_comparisons=[],
                local_slots=declared_local_slots(ROOT),
                role_postures=[],
                persona_evidence=[],
            )
            checks = {row["check"] for row in report["checks"]}
            self.assertFalse(any(check.startswith(("pack.", "description-cost", "local-slots.fill")) for check in checks))


if __name__ == "__main__":
    unittest.main()
