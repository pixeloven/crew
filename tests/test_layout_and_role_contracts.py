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

    def test_claude_consumer_role_identity_is_frontmatter_owned(self) -> None:
        for filename in ("librarian.md", "custom-file.md"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / f".claude/agents/{filename}"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    "---\nname: librarian\ndescription: Maintains references.\n---\n",
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

    def test_claude_consumer_role_identity_must_not_be_blank(self) -> None:
        for declaration, valid in (("' '", False), ('""', False), ("librarian", True)):
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / ".claude/agents/custom-file.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    f"---\nname: {declaration}\ndescription: Maintains references.\n---\n",
                    encoding="utf-8",
                )

                completed = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                output = completed.stdout + completed.stderr
                self.assertEqual(valid, completed.returncode == 0, output)
                if not valid:
                    self.assertIn(".claude/agents/custom-file.md", output)
                    self.assertIn("no `name:` in frontmatter", output)

    def test_claude_consumer_role_identity_uses_supported_syntax(self) -> None:
        for identity, valid in (
            ("reviewer", True),
            ("security-reviewer", True),
            ("custom:reviewer", False),
            ("security_reviewer", False),
            ("Security-reviewer", False),
            ("reviewer2", False),
        ):
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / ".claude/agents/custom-file.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    f"---\nname: {identity}\ndescription: Maintains references.\n---\n",
                    encoding="utf-8",
                )

                completed = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                output = completed.stdout + completed.stderr
                self.assertEqual(valid, completed.returncode == 0, output)
                if not valid:
                    self.assertIn(str(agent.relative_to(root)), output)
                    self.assertIn("invalid Claude role name", output)

    def test_nested_consumer_roles_follow_harness_discovery_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            roles = (
                (root / ".claude/agents/review/security.md", "security-reviewer"),
                (root / ".pi/agents/review/security.md", "security"),
            )
            for path, identity in roles:
                path.parent.mkdir(parents=True)
                path.write_text(
                    f"---\nname: {identity}\ndescription: Reviews security.\n---\n",
                    encoding="utf-8",
                )
            neutral = root / "agents/review/ignored.md"
            neutral.parent.mkdir(parents=True)
            neutral.write_text("not frontmatter\n", encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_claude_consumer_role_accepts_nested_hook_metadata(self) -> None:
        for header in ("|", "|2", "| # shell command"):
            with self.subTest(header=header), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / ".claude/agents/reviewer.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    "---\nname: reviewer\ndescription: Reviews changes.\n"
                    "hooks:\n"
                    "  PreToolUse:\n"
                    "    - matcher: Bash\n"
                    "      hooks:\n"
                    "        - type: command\n"
                    f"          command: {header}\n"
                    "            ./scripts/check-command.sh\n"
                    "            ./scripts/report-result.sh\n"
                    "---\n",
                    encoding="utf-8",
                )

                completed = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(
                    0,
                    completed.returncode,
                    completed.stdout + completed.stderr,
                )

    def test_claude_consumer_role_rejects_malformed_nested_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            agent = root / ".claude/agents/reviewer.md"
            agent.parent.mkdir(parents=True)
            agent.write_text(
                "---\nname: reviewer\ndescription: Reviews changes.\n"
                "hooks:\n [unterminated\n---\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            output = completed.stdout + completed.stderr
            self.assertNotEqual(0, completed.returncode)
            self.assertIn(".claude/agents/reviewer.md", output)
            self.assertIn("invalid YAML frontmatter", output)

    def test_claude_consumer_role_rejects_block_scalar_dedent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            agent = root / ".claude/agents/reviewer.md"
            agent.parent.mkdir(parents=True)
            agent.write_text(
                "---\nname: reviewer\ndescription: Reviews changes.\n"
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

            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            output = completed.stdout + completed.stderr
            self.assertNotEqual(0, completed.returncode)
            self.assertIn(".claude/agents/reviewer.md", output)
            self.assertIn("invalid YAML frontmatter", output)

    def test_claude_duplicate_resolved_role_identities_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            agents = root / ".claude/agents"
            agents.mkdir(parents=True)
            for filename in ("first.md", "second.md"):
                (agents / filename).write_text(
                    "---\nname: librarian\ndescription: Maintains references.\n---\n",
                    encoding="utf-8",
                )

            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            output = completed.stdout + completed.stderr
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("duplicate resolved role identity 'librarian'", output)
            self.assertIn("first.md", output)
            self.assertIn("second.md", output)

    def test_pi_consumer_role_identity_remains_filename_owned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            agent = root / ".pi/agents/custom-file.md"
            agent.parent.mkdir(parents=True)
            agent.write_text(
                "---\nname: librarian\ndescription: Maintains references.\n---\n",
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
            self.assertIn("filename/name mismatch", completed.stdout + completed.stderr)

    def test_unreadable_frontmatter_is_a_source_bearing_validation_error(self) -> None:
        for relative_path in (
            ".agents/skills/broken/SKILL.md",
            ".pi/agents/broken.md",
        ):
            with self.subTest(relative_path=relative_path), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                target = root / relative_path
                target.parent.mkdir(parents=True)
                target.write_bytes(b"\xff")

                completed = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/check_skill_layout.py"), str(root)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                output = completed.stdout + completed.stderr
                self.assertNotEqual(0, completed.returncode)
                self.assertIn(relative_path, output)
                self.assertIn("could not read frontmatter", output)
                self.assertNotIn("Traceback", output)


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
