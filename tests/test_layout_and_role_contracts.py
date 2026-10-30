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

    def test_skill_with_nested_metadata_mapping_passes_layout(self) -> None:
        cases = (
            "metadata:\n  internal: true\n",
            "metadata:\n  internal: true\n  owner: \"platform\"\n  tags: [ops, ci]\n",
            "metadata: # harness extras\n  nested:\n    depth: 2\n  list:\n    - one\n",
        )
        for nested in cases:
            with self.subTest(frontmatter=nested), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                skill = root / ".claude/skills/validation-supervision/SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text(
                    "---\nname: validation-supervision\ndescription: Load when a ship starts.\n"
                    f"user-invocable: false\n{nested}---\n",
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

    def test_malformed_nested_metadata_is_still_rejected(self) -> None:
        cases = (
            "metadata:\n  internal: true\n    stray: indented\n",
            "metadata:\n  internal: [unterminated\n",
            "metadata:\n  internal: true\n  internal: false\n",
            "metadata:\n  internal: true\n  - mixed\n",
            "metadata:\n  key: Valid: bad\n",
        )
        for malformed in cases:
            with self.subTest(frontmatter=malformed), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                skill = root / ".agents/skills/probe/SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text(
                    f"---\nname: probe\ndescription: probe\n{malformed}---\n",
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

    def test_claude_opaque_metadata_accepts_nested_flow_collections(self) -> None:
        cases = (
            (
                'mcpServers: [{playwright: {type: stdio, command: npx, '
                'args: ["-y", "@playwright/mcp@latest"]}}]\n',
                True,
            ),
            (
                'hooks: {PreToolUse: [{matcher: "Bash,[{}]", hooks: '
                '[{type: command, command: "printf \'[ok], {done}\'"}]}]}\n',
                True,
            ),
            ('mcpServers: [{playwright: {type: stdio}]\n', False),
            ('hooks: {PreToolUse: [{matcher: "Bash"}]\n', False),
            ('tools: [Read, {name: nested}]\n', False),
        )
        for declaration, valid in cases:
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / ".claude/agents/reviewer.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    "---\nname: reviewer\ndescription: Reviews changes.\n"
                    f"{declaration}"
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
                self.assertEqual(valid, completed.returncode == 0, output)
                if not valid:
                    self.assertIn("invalid YAML frontmatter", output)

    def test_claude_opaque_nested_flows_preserve_quoted_hashes(self) -> None:
        declarations = (
            'mcpServers: [{playwright: {env: {TOKEN: "value # retained"}}}]\n',
            'hooks: {PreToolUse: [{matcher: "Bash # guarded", hooks: '
            '[{type: command, command: "printf #ok"}]}]}\n',
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                agent = root / ".claude/agents/reviewer.md"
                agent.parent.mkdir(parents=True)
                agent.write_text(
                    "---\nname: reviewer\ndescription: Reviews changes.\n"
                    f"{declaration}"
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

    def test_nested_hook_compact_mapping_uses_actual_key_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            agent = root / ".claude/agents/reviewer.md"
            agent.parent.mkdir(parents=True)
            agent.write_text(
                "---\nname: reviewer\ndescription: Reviews changes.\n"
                "hooks:\n"
                "  PreToolUse:\n"
                "    -   matcher: Bash\n"
                "        hooks:\n"
                "          - type: command\n"
                "            command: ./scripts/check-command.sh\n"
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

            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_nested_hook_container_comments_introduce_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            agent = root / ".claude/agents/reviewer.md"
            agent.parent.mkdir(parents=True)
            agent.write_text(
                "---\nname: reviewer\ndescription: Reviews changes.\n"
                "hooks: # lifecycle hooks\n"
                "  PreToolUse: # before commands\n"
                "    - matcher: Bash\n"
                "      hooks: # command hooks\n"
                "        - type: command\n"
                "          command: ./scripts/check-command.sh\n"
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

            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

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

    def test_nested_hook_distinguishes_content_and_indentation_tabs(self) -> None:
        cases = (
            ("            \tprintf valid\\n\n", True),
            ("          \tprintf invalid\\n\n", False),
        )
        for command, valid in cases:
            with self.subTest(valid=valid), tempfile.TemporaryDirectory() as tmp:
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
                    "          command: |2\n"
                    f"{command}"
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
                self.assertEqual(valid, completed.returncode == 0, output)
                if not valid:
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

    def test_pi_posture_subtracts_file_write_tools_instead_of_allowlisting(self) -> None:
        # pi-subagents `tools:` is a strict allowlist that also shuts out ambient
        # extensions (MCP). The contract is "no file writes", so pi subtracts.
        expected = {"none": ["write", "edit"], "drafts": ["edit"], "full": []}
        for writes, excluded in expected.items():
            with self.subTest(writes=writes):
                posture = effective_posture(writes, "pi")
                self.assertEqual(excluded, posture["denied_tools"])
                self.assertEqual([], posture["allowed_tools"])
                self.assertIn("shell access", posture["caveat"])

    def test_rendered_pi_roles_are_package_namespaced_with_excluded_tools(self) -> None:
        import yaml

        from scripts.role_contract import PI_PACKAGE_NAME

        self.assertEqual("crew", PI_PACKAGE_NAME)
        expected = {"none": "write, edit", "drafts": "edit", "full": None}
        for role_dir in sorted(
            p for p in (ROOT / "roles").iterdir() if p.is_dir() and not p.name.startswith("_")
        ):
            with self.subTest(role=role_dir.name):
                role = yaml.safe_load((role_dir / "role.yml").read_text(encoding="utf-8"))
                text = (ROOT / "pi-agents" / f"{role_dir.name}.md").read_text(encoding="utf-8")
                header = text.split("---\n", 2)[1]
                metadata = yaml.safe_load(header)
                # Bare local name + package => runtime identity `crew.<role>`.
                self.assertEqual(role_dir.name, metadata["name"])
                self.assertEqual("crew", metadata["package"])
                self.assertNotIn("tools", metadata)
                self.assertEqual(expected[role["writes"]], metadata.get("excludeTools"))
                self.assertEqual(
                    bool(role.get("dispatch")), metadata.get("allowNestedSubagents", False)
                )

    def test_pi_package_ships_skills_and_readable_roles_without_dispatch(self) -> None:
        import json

        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        # On pi Crew provides skills; roles ship as readable files, not dispatch.
        self.assertEqual({"skills": ["./skills"]}, package["pi"])
        self.assertIn("pi-agents", package["files"])
        self.assertNotIn("peerDependencies", package)
        self.assertNotIn("dependencies", package)
        self.assertFalse((ROOT / "pi-extension").exists())

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


class RoleReportingContractTests(unittest.TestCase):
    """The reporting contract has ONE source, included into every role body."""

    SHARED = ROOT / "roles" / "_shared" / "reporting-contract.md"
    MARKER = "<!-- include: reporting-contract -->"
    KEY_RULES = (
        "Lead with decisions, or say there are none.",
        "Already handled is not news.",
        "Detail below the fold.",
        "Separate, don't shrink.",
        "The work has no narrator.",
        "Chunk and pause.",
        "Batch review.",
        "Confirm before an external write.",
    )
    HOST_RULES = (
        "A supervising host's contract wins.",
        "Unattended, record and stop.",
    )

    def test_shared_source_carries_the_whole_contract(self) -> None:
        text = self.SHARED.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("## Reporting contract\n"))
        headings = [line for line in text.splitlines() if line.startswith("#")]
        self.assertEqual(["## Reporting contract"], headings)
        for phrase in ("Decisions needed", "If no reply", "auditability", *self.KEY_RULES):
            self.assertIn(phrase, text)

    def test_every_role_body_includes_the_contract_instead_of_copying_it(self) -> None:
        bodies = sorted((ROOT / "roles").glob("[!_]*/body.md"))
        self.assertEqual(7, len(bodies))
        for body in bodies:
            text = body.read_text(encoding="utf-8")
            with self.subTest(role=body.parent.name):
                self.assertEqual(1, text.count(self.MARKER))
                self.assertNotIn("## Reporting contract", text)

    def test_rendered_roles_carry_the_expanded_shared_text_once(self) -> None:
        shared = self.SHARED.read_text(encoding="utf-8").strip("\n")
        for tree in ("agents", "pi-agents"):
            for path in sorted((ROOT / tree).glob("*.md")):
                text = path.read_text(encoding="utf-8")
                with self.subTest(file=f"{tree}/{path.name}"):
                    self.assertEqual(1, text.count(shared))
                    self.assertNotIn("<!-- include:", text)
                    for rule in self.HOST_RULES:
                        self.assertEqual(1, text.count(f"**{rule}**"))

    def test_include_expands_in_place_and_rejects_unknown_targets(self) -> None:
        from scripts.render_roles import expand_includes

        with tempfile.TemporaryDirectory() as tmp:
            shared = pathlib.Path(tmp)
            (shared / "part.md").write_text("## Part\n\nShared text.\n", encoding="utf-8")
            body = "Intro.\n<!-- include: part -->\n\n## After\n"
            self.assertEqual(
                "Intro.\n## Part\n\nShared text.\n\n## After\n",
                expand_includes(body, "roles/x/body.md", shared),
            )
            with self.assertRaises(SystemExit) as raised:
                expand_includes("<!-- include: missing -->\n", "roles/x/body.md", shared)
            self.assertIn("missing", str(raised.exception))
            with self.assertRaises(SystemExit):
                expand_includes("<!-- include: ../part -->\n", "roles/x/body.md", shared)

    def test_shared_dir_is_not_mistaken_for_a_role(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/render_roles.py"), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("7 roles rendered clean", completed.stdout)

    def test_template_variant_keeps_every_key_rule(self) -> None:
        # templates/AGENTS.md speaks to the operator, so its wording differs on
        # purpose; it must still carry every rule the roles carry.
        from scripts.onboarding_contract import reporting_contract_section

        section = reporting_contract_section(
            (ROOT / "templates" / "AGENTS.md").read_text(encoding="utf-8")
        )
        for rule in (*self.KEY_RULES, *self.HOST_RULES):
            with self.subTest(rule=rule):
                self.assertIn(f"**{rule}**", section)


class QualifiedDispatchTests(unittest.TestCase):
    """Wherever a role or the template says whom to dispatch, it says the name is
    namespaced: on pi a bare `reviewer`/`researcher` is pi-subagents' built-in."""

    SENTENCE = (
        "Dispatch each role by the name your harness registers it under: Crew's roles are "
        "namespaced (e.g. `crew.reviewer` on pi, where a bare `reviewer` or `researcher` "
        "reaches a different, built-in agent)."
    )

    def test_routing_surfaces_carry_the_neutral_dispatch_sentence(self) -> None:
        for path in ("templates/AGENTS.md", "roles/lead/body.md", "roles/triage/body.md"):
            with self.subTest(path=path):
                text = (ROOT / path).read_text(encoding="utf-8")
                self.assertEqual(1, " ".join(text.split()).count(self.SENTENCE))


class ReviewBoundTests(unittest.TestCase):
    """The reviewer cites both delta-handling rules that bound review rounds, and
    the rules it cites exist there (crew#126)."""

    RULES = (
        "A review finding cannot amend the accepted ask",
        "Repeated same-theme findings",
    )
    ESCALATION = (
        "Original requirement",
        "Proposed expansion",
        "Smallest compliant alternative",
        "Consequences of each",
        "Recommendation",
    )

    @staticmethod
    def _section(text: str, heading: str) -> list[str]:
        lines = text.splitlines()
        start = lines.index(heading) + 1
        end = next(
            (i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines)
        )
        return lines[start:end]

    @staticmethod
    def _bold_leads(lines: list[str], marker: str) -> tuple[str, ...]:
        leads = []
        for line in lines:
            if line.startswith(marker + "**"):
                leads.append(line[len(marker) + 2 :].split("**", 1)[0].rstrip("."))
        return tuple(leads)

    def _numbered_bold_leads(self, lines: list[str]) -> tuple[str, ...]:
        return tuple(
            self._bold_leads([line.split(" ", 1)[1]], "")[0]
            for line in lines
            if line[:1].isdigit() and line.split(" ", 1)[0].rstrip(".").isdigit()
        )

    def test_delta_handling_defines_both_rules_and_the_escalation_shape(self) -> None:
        text = (ROOT / "skills/delta-handling/SKILL.md").read_text(encoding="utf-8")
        lines = text.splitlines()
        table_rows = [
            [cell.strip() for cell in line.strip("|").split("|")]
            for line in lines
            if line.startswith("|")
        ]
        self.assertEqual(1, [row[0] for row in table_rows].count(self.RULES[1]))
        self.assertIn(f"## {self.RULES[0]}", lines)
        escalation = self._section(text, "## Escalating a scope expansion or repeated findings")
        self.assertEqual(self.ESCALATION, self._numbered_bold_leads(escalation))

    def test_rendered_reviewers_cite_both_rules(self) -> None:
        for path in ("agents/reviewer.md", "pi-agents/reviewer.md"):
            text = (ROOT / path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                rules = self._section(text, "## Findings and the accepted ask")
                self.assertTrue(any("`delta-handling`" in line for line in rules))
                self.assertEqual(self.RULES, self._bold_leads(rules, "- "))
                output = self._section(text, "## Output format")
                escalations = next(
                    i for i, line in enumerate(output) if line.startswith("**Escalations:**")
                )
                self.assertEqual(
                    self.ESCALATION, self._numbered_bold_leads(output[escalations + 1 :])
                )


if __name__ == "__main__":
    unittest.main()
