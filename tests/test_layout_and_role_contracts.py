import pathlib
import subprocess
import sys
import unittest

from scripts.role_contract import FORBIDDEN_RUNTIME_KEYS, effective_posture


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


class RolePostureTests(unittest.TestCase):
    def test_m10_drafts_posture_reports_overwrite_and_shell_caveat(self) -> None:
        posture = effective_posture("drafts", "claude")
        self.assertIn("create and overwrite", posture["write_effect"])
        self.assertIn("Edit", posture["denied_tools"])
        self.assertNotIn("Write", posture["denied_tools"])
        self.assertIn("shell access", posture["caveat"])

    def test_runtime_knob_contract_is_shared_and_complete(self) -> None:
        self.assertEqual(
            {"model", "thinking", "effort", "model_reasoning_effort", "turnBudget", "maxTurns"},
            set(FORBIDDEN_RUNTIME_KEYS),
        )


if __name__ == "__main__":
    unittest.main()
