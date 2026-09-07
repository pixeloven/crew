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
            ("12:34", "Valid description."),
            ("2026-09-07", "Valid description."),
            ("2026-09-07T12:30:00Z", "Valid description."),
            ("[librarian]", "Valid description."),
            ("{role: librarian}", "Valid description."),
            ("!role librarian", "Valid description."),
            ("librarian", "false"),
            ("librarian", "2026-09-07"),
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

    def test_invalid_double_quoted_yaml_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            agent = root / ".pi/agents/librarian.md"
            agent.parent.mkdir(parents=True)
            agent.write_text(
                '---\nname: librarian\ndescription: "bad\\q"\n---\n',
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
            self.assertIn("invalid YAML frontmatter", completed.stdout + completed.stderr)

    def test_malformed_yaml_cannot_pass_role_validation(self) -> None:
        cases = (
            "description: Valid: bad",
            "description: [broken",
            "description: {broken}",
            'description: "broken',
            "description:\n  nested: bad",
            "description: Valid description.\n  - unexpected",
        )
        for malformed in cases:
            with self.subTest(frontmatter=malformed), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / ".pi/agents/librarian.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    f"---\nname: librarian\n{malformed}\n---\n",
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
                self.assertIn("invalid YAML frontmatter", completed.stdout + completed.stderr)

    def test_reserved_plain_scalar_indicators_are_rejected(self) -> None:
        for value in ("-", "?", ">foo"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / ".pi/agents/librarian.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    f"---\nname: librarian\ndescription: {value}\n---\n",
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
                self.assertIn("invalid YAML frontmatter", completed.stdout + completed.stderr)

    def test_single_quoted_scalars_require_doubled_interior_quotes(self) -> None:
        for value, expected_success in (("'foo' bar'", False), ("'foo''s bar'", True)):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / ".pi/agents/librarian.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    f"---\nname: librarian\ndescription: {value}\n---\n",
                    encoding="utf-8",
                )
                completed = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if expected_success:
                    self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
                else:
                    self.assertNotEqual(0, completed.returncode)
                    self.assertIn("invalid YAML frontmatter", completed.stdout + completed.stderr)

    def test_double_quoted_scalars_reject_unescaped_interior_quotes(self) -> None:
        for value, expected_success in ((r'"foo" bar"', False), (r'"foo\" bar"', True)):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / ".pi/agents/librarian.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    f"---\nname: librarian\ndescription: {value}\n---\n",
                    encoding="utf-8",
                )
                completed = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if expected_success:
                    self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
                else:
                    self.assertNotEqual(0, completed.returncode)
                    self.assertIn("invalid YAML frontmatter", completed.stdout + completed.stderr)

    def test_distributed_pi_agents_require_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            agent = root / "pi-agents/reviewer.md"
            agent.parent.mkdir(parents=True)
            agent.write_text(
                "---\ndescription: Reviews changes.\n---\n",
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
            self.assertIn("silent Pi drop", completed.stdout + completed.stderr)


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
