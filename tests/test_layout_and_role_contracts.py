import pathlib
import subprocess
import sys
import tempfile
import unittest

from scripts.role_contract import effective_posture


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class LayoutContractTests(unittest.TestCase):
    def run_layout(self, fixture: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(FIXTURES / fixture)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_m9_frontmatter_and_consumer_agents_are_validated(self) -> None:
        completed = self.run_layout("consumer-invalid")
        self.assertNotEqual(0, completed.returncode)
        output = completed.stdout + completed.stderr
        self.assertIn("frontmatter", output)
        self.assertIn("silent Pi drop", output)
        self.assertIn("filename/name mismatch", output)
        for key in ("model", "thinking", "turnBudget"):
            self.assertIn(key, output)

    def test_all_three_consumer_agent_roots_can_pass(self) -> None:
        completed = self.run_layout("consumer-valid")
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("consumer role layout ok", completed.stdout)

    def test_yaml_plain_scalar_comment_is_not_part_of_role_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            agent = root / ".pi/agents/librarian.md"
            agent.parent.mkdir(parents=True)
            agent.write_text(
                "---\nname: librarian # role identity\ndescription: 'Keeps # references' # note\n---\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_yaml_non_string_identity_and_description_scalars_are_rejected(self) -> None:
        cases = (
            ("null", "Valid description."),
            ("false", "Valid description."),
            ("yes", "Valid description."),
            ("42", "Valid description."),
            ("3.14", "Valid description."),
            ("!role librarian", "Valid description."),
            ("librarian", "false"),
        )
        for name, description in cases:
            with self.subTest(name=name, description=description), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / ".pi/agents/librarian.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    f"---\nname: {name}\ndescription: {description}\n---\n",
                    encoding="utf-8",
                )
                completed = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(0, completed.returncode)


class RolePostureTests(unittest.TestCase):
    def test_m10_drafts_posture_reports_overwrite_and_shell_caveat(self) -> None:
        posture = effective_posture("drafts", "claude")
        self.assertIn("create and overwrite", posture["write_effect"])
        self.assertIn("Edit", posture["denied_tools"])
        self.assertNotIn("Write", posture["denied_tools"])
        self.assertIn("shell access", posture["caveat"])

    def test_every_runtime_knob_is_observably_rejected(self) -> None:
        for key in ("model", "thinking", "effort", "model_reasoning_effort", "turnBudget", "maxTurns"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / ".pi/agents/reviewer.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    f"---\nname: reviewer\ndescription: Reviews changes.\n{key}: fixture-value\n---\n",
                    encoding="utf-8",
                )
                completed = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(0, completed.returncode)
                self.assertIn(f"forbidden runtime knob '{key}'", completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
