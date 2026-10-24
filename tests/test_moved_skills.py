import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from scripts.crew_doctor import (
    MOVED_SKILLS,
    compose_doctor_report,
    declared_local_slots,
    inspect_installations,
    inspect_packs,
    moved_skill_references,
    render_doctor_report,
)
from scripts.onboarding_contract import (
    audit_moved_skill_references,
    rewrite_moved_skill_references,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
DESCRIPTION = "Use when exercising the moved-skills fixture so that this fixture description comfortably clears the schema-v2 minimum length."
INFRA_MOVES = (
    "terraform-conventions",
    "ansible-conventions",
    "k8s-kustomize-conventions",
    "k8s-workload-patterns",
    "github-actions-conventions",
)


def write(path: pathlib.Path, text: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_skill(root: pathlib.Path, name: str, body: str = "", requires: str = "[]") -> pathlib.Path:
    return write(
        root / "skills" / name / "SKILL.md",
        f"---\nname: {name}\ndescription: {DESCRIPTION}\ntier: subject\nrequires: {requires}\n---\n\n# {name}\n{body}",
    )


def write_manifest(root: pathlib.Path, name: str, version: str) -> None:
    write(
        root / ".claude-plugin/plugin.json",
        json.dumps({"name": name, "version": version, "skills": "./skills"}),
    )
    (root / "skills").mkdir(exist_ok=True)


def snapshot(root: pathlib.Path) -> dict[str, bytes]:
    return {str(path): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def report_for(base: pathlib.Path, crew: pathlib.Path, packs: list[pathlib.Path]) -> dict[str, dict]:
    report = compose_doctor_report(
        inspect_installations(base / "project", base / "home"),
        runtime_comparisons=[],
        local_slots=declared_local_slots(crew),
        role_postures=[],
        persona_evidence=[],
        packs=inspect_packs(packs, crew),
        moved_skill_refs=moved_skill_references(base / "project"),
    )
    render_doctor_report(report)
    return {row["check"]: row for row in report["checks"]}


class MovedSkillsTableTests(unittest.TestCase):
    def test_stack_skills_moved_to_infra_skills_and_python_to_language_skills(self) -> None:
        expected = {name: "infra-skills" for name in INFRA_MOVES}
        expected["python-conventions"] = "language-skills"
        self.assertEqual(expected, MOVED_SKILLS)

    def test_moved_skills_are_gone_from_crew_and_kept_skills_remain(self) -> None:
        for name in MOVED_SKILLS:
            self.assertFalse((ROOT / "skills" / name).exists(), name)
        for kept in ("mcp-server-design",):
            self.assertTrue((ROOT / "skills" / kept / "SKILL.md").is_file(), kept)

    def test_shipped_content_names_neither_a_moved_skill_nor_its_pack(self) -> None:
        # Crew never names a pack; the migration map in scripts/ is the one exception.
        forbidden = (*MOVED_SKILLS, *set(MOVED_SKILLS.values()))
        for tree in ("roles", "agents", "pi-agents", "skills", "templates"):
            for path in sorted((ROOT / tree).rglob("*")):
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8")
                for token in forbidden:
                    self.assertNotIn(token, text, f"{path.relative_to(ROOT)} names {token}")


class DoctorMovedSkillTests(unittest.TestCase):
    def consumer(self, base: pathlib.Path) -> pathlib.Path:
        project = base / "project"
        write(
            project / "AGENTS.md",
            "# Project\n\n| Concern | Skill |\n|---|---|\n| Terraform | `crew:terraform-conventions` |\n",
        )
        write_skill(project / ".agents", "project-platform-conventions", "See `k8s-workload-patterns`.\n")
        write(project / ".claude/agents/ops.md", "---\nname: ops\ndescription: x\n---\nLoad crew:ansible-conventions.\n")
        write(project / ".pi/agents/ops.md", "---\nname: ops\ndescription: x\n---\nNothing moved here; terraform-conventions-extra is not one.\n")
        return project

    def test_references_are_found_bare_and_prefixed_across_consumer_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.consumer(pathlib.Path(tmp))
            refs = moved_skill_references(project)
            found = {(ref["skill"], ref["namespace"], pathlib.Path(ref["source"]).name) for ref in refs["references"]}
            self.assertEqual(
                {
                    ("terraform-conventions", "crew", "AGENTS.md"),
                    ("k8s-workload-patterns", "", "SKILL.md"),
                    ("ansible-conventions", "crew", "ops.md"),
                },
                found,
            )
            self.assertTrue(all(ref["line"] > 0 for ref in refs["references"]))

    def test_missing_pack_is_degraded_with_an_install_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            self.consumer(base)
            crew = base / "crew"
            write_manifest(crew, "crew", "0.41.0")
            before = snapshot(base)
            rows = report_for(base, crew, [])
            self.assertEqual(before, snapshot(base), "Doctor must stay read-only")
            row = rows["moved-skills.terraform-conventions"]
            self.assertEqual("DEGRADED", row["status"])
            self.assertIn("moved to pack infra-skills; install it", row["fact"] + row["recommendation"])
            self.assertTrue(row["evidence"])
            self.assertNotIn("moved-skills.github-actions-conventions", rows)

    def test_installed_pack_clears_bare_references_but_not_crew_prefixed_ones(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            self.consumer(base)
            crew = base / "crew"
            write_manifest(crew, "crew", "0.41.0")
            pack = base / "infra"
            write_manifest(pack, "infra-skills", "0.1.0")
            for name in INFRA_MOVES:
                write_skill(pack, name, requires="[plugin:crew@>=0.38.0]")
            rows = report_for(base, crew, [pack])
            self.assertEqual("OK", rows["moved-skills.k8s-workload-patterns"]["status"])
            prefixed = rows["moved-skills.terraform-conventions"]
            self.assertEqual("DEGRADED", prefixed["status"])
            self.assertIn("infra-skills:terraform-conventions", prefixed["recommendation"])

    def test_consumer_without_references_gets_no_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            write(base / "project/AGENTS.md", "# Project\n")
            crew = base / "crew"
            write_manifest(crew, "crew", "0.41.0")
            rows = report_for(base, crew, [])
            self.assertFalse(any(check.startswith("moved-skills.") for check in rows))


class OnboardingMovedSkillTests(unittest.TestCase):
    TEXT = (
        "| Terraform | `crew:terraform-conventions` |\n"
        "| Workloads | `k8s-workload-patterns` |\n"
        "| Already | `infra-skills:ansible-conventions` |\n"
        "| Kept | `crew:mcp-server-design` |\n"
    )

    def test_audit_proposes_namespace_updates_and_never_edits(self) -> None:
        proposals = audit_moved_skill_references(self.TEXT)
        self.assertEqual(
            [
                {
                    "line": 1,
                    "skill": "terraform-conventions",
                    "pack": "infra-skills",
                    "from": "crew:terraform-conventions",
                    "to": "infra-skills:terraform-conventions",
                },
                {
                    "line": 2,
                    "skill": "k8s-workload-patterns",
                    "pack": "infra-skills",
                    "from": "k8s-workload-patterns",
                    "to": "k8s-workload-patterns",
                },
            ],
            proposals,
        )

    def test_apply_rewrites_only_crew_prefixed_moved_references(self) -> None:
        rewritten = rewrite_moved_skill_references(self.TEXT)
        self.assertIn("`infra-skills:terraform-conventions`", rewritten)
        self.assertIn("`k8s-workload-patterns`", rewritten)
        self.assertIn("`crew:mcp-server-design`", rewritten)
        self.assertEqual(rewritten, rewrite_moved_skill_references(rewritten))

    def test_cli_reports_moved_references_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write(pathlib.Path(tmp) / "AGENTS.md", self.TEXT)
            before = path.read_bytes()
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/onboarding_contract.py"), "--check-moved-skills", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            self.assertIn("crew:terraform-conventions -> infra-skills:terraform-conventions", result.stdout)
            self.assertEqual(before, path.read_bytes())
            clean = write(pathlib.Path(tmp) / "CLEAN.md", "# nothing moved\n")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/onboarding_contract.py"), "--check-moved-skills", str(clean)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_cli_hosted_profile_reports_entry_file_references_as_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            entry = write(pathlib.Path(tmp) / "AGENTS.md", self.TEXT)
            skill = write(pathlib.Path(tmp) / ".agents/skills/local/SKILL.md", self.TEXT)
            for path, code in ((entry, 0), (skill, 1)):
                with self.subTest(path=path):
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "scripts/onboarding_contract.py"),
                         "--check-moved-skills", str(path), "--audit-profile", "hosted"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(code, result.returncode, result.stdout + result.stderr)
                    self.assertIn("crew:terraform-conventions -> infra-skills:terraform-conventions", result.stdout)
                    self.assertEqual(code == 1, "install pack" in result.stdout)
            self.assertEqual(self.TEXT, entry.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
