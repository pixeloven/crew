"""The reusable pack-checks workflow stays in step with the scripts it runs.

A pack's CI is one `uses:` line pointing at .github/workflows/pack-checks.yml,
so a renamed script or a dropped step breaks every pack at once. These tests
parse the workflow, check what it references exists, and run its shell steps
against a synthetic pack exactly as the runner would.
"""

import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

from scripts.check_skills import description_costs, yaml_module


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pack-checks.yml"
# Every check a pack must pass. Adding one here without a workflow step fails.
PACK_CHECKS = {"check_skills.py", "check_skill_layout.py", "check_links.py", "check_versions.py"}
DESCRIPTION = "Use when exercising the reusable pack workflow fixture so that this description clears the schema-v2 minimum length."


def load_workflow() -> dict:
    return yaml_module().safe_load(WORKFLOW.read_text(encoding="utf-8"))


def steps() -> list[dict]:
    return load_workflow()["jobs"]["pack-checks"]["steps"]


class PackWorkflowShapeTests(unittest.TestCase):
    def test_is_a_reusable_workflow_with_its_inputs(self) -> None:
        workflow = load_workflow()
        # PyYAML reads the bare key `on` as boolean True.
        trigger = workflow.get("on", workflow.get(True))
        inputs = trigger["workflow_call"]["inputs"]
        self.assertEqual({"crew-ref", "pack-root"}, set(inputs))
        self.assertEqual("", inputs["crew-ref"]["default"])
        self.assertEqual(".", inputs["pack-root"]["default"])
        self.assertEqual({"contents": "read"}, workflow["permissions"])

    def test_runs_every_pack_check_and_only_scripts_that_exist(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        run = set(re.findall(r'"\$CREW/scripts/([a-z_]+\.py)"', text))
        self.assertEqual(PACK_CHECKS, run)
        guard = next(step for step in steps() if step.get("name") == "Crew ships every check this workflow runs")
        self.assertEqual(PACK_CHECKS, set(re.search(r"for script in ([^;]+);", guard["run"]).group(1).split()))
        for script in PACK_CHECKS:
            self.assertTrue((ROOT / "scripts" / script).is_file(), script)

    def test_actions_are_referenced_by_major_tag_like_ci(self) -> None:
        for step in steps():
            if "uses" in step:
                self.assertRegex(step["uses"], r"^[\w.-]+/[\w./-]+@v\d+$")

    def test_crew_is_checked_out_into_a_dot_directory(self) -> None:
        crew = next(step for step in steps() if step.get("with", {}).get("repository") == "pixeloven/crew")
        path = crew["with"]["path"]
        self.assertTrue(path.startswith(".") and path.strip("./"), path)
        self.assertEqual(f"${{{{ github.workspace }}}}/{path}", load_workflow()["jobs"]["pack-checks"]["env"]["CREW"])


class PackWorkflowRunTests(unittest.TestCase):
    def make_pack(self, base: pathlib.Path) -> pathlib.Path:
        pack = base / "example-skills"
        skill = pack / "skills/example-skill/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            f"---\nname: example-skill\ndescription: {DESCRIPTION}\ntier: subject\n"
            "requires: [plugin:crew@>=0.38.0]\n---\n\n# example-skill\n\nSee [the README](../../README.md).\n",
            encoding="utf-8",
        )
        (pack / ".claude-plugin").mkdir()
        for manifest in (".claude-plugin/plugin.json", "package.json"):
            (pack / manifest).write_text(json.dumps({"name": "example-skills", "version": "1.0.0"}), encoding="utf-8")
        total = sum(chars for _, chars in description_costs(pack))
        (pack / "README.md").write_text(
            "# example-skills\n\n## Description cost\n\n```text\n"
            f"example-skill  {total}\ntotal always-on description chars: {total} (1 skills)\n```\n",
            encoding="utf-8",
        )
        # Crew sits inside the workspace, as actions/checkout puts it.
        shutil.copytree(ROOT / "scripts", pack / ".crew/scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "roles", pack / ".crew/roles")
        return pack

    def run_check_steps(self, pack: pathlib.Path, summary: pathlib.Path) -> list[subprocess.CompletedProcess]:
        env = {
            **os.environ,
            "PACK_ROOT": f"{pack}/.",
            "CREW": str(pack / ".crew"),
            "RESOLVED": "test-ref",
            "GITHUB_STEP_SUMMARY": str(summary),
        }
        results = []
        # The steps after Crew is checked out need no network.
        names = [step.get("name") for step in steps()]
        for step in steps()[names.index("Check out Crew") + 1 :]:
            results.append(
                subprocess.run(
                    ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]],
                    cwd=pack,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            )
        return results

    def test_a_conforming_pack_passes_every_step_and_gets_a_cost_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = self.make_pack(pathlib.Path(tmp))
            summary = pathlib.Path(tmp) / "summary.md"
            for result in self.run_check_steps(pack, summary):
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertNotIn("::warning::", result.stdout)
            text = summary.read_text(encoding="utf-8")
            self.assertIn("## Description cost", text)
            self.assertIn("at Crew test-ref:", text)
            self.assertIn("total always-on description chars:", text)

    def test_a_stale_readme_total_warns_but_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = self.make_pack(pathlib.Path(tmp))
            (pack / "README.md").write_text("# example-skills\n", encoding="utf-8")
            cost = self.run_check_steps(pack, pathlib.Path(tmp) / "summary.md")[-1]
            self.assertEqual(0, cost.returncode, cost.stdout + cost.stderr)
            self.assertIn("::warning::README.md does not carry the current total line", cost.stdout)


if __name__ == "__main__":
    unittest.main()
