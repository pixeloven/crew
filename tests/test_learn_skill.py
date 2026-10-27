"""The learn skill can't drift from the scripts it drives.

Every command-line flag the skill body names must be one the scripts actually
define (read from their own `--help`), every command must pair a script with
its own flags, and every script and JSON key it relies on must exist.
"""

import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

from scripts.frontmatter import read_frontmatter
from scripts.learn_contract import PROVENANCE_SOURCE, inspect_proposals


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/learn/SKILL.md"
FLAG = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*)")
SCRIPT = re.compile(r"scripts/([a-z_]+\.py)")
FENCED = re.compile(r"^```[^\n]*\n(.*?)^```", re.DOTALL | re.MULTILINE)
INLINE = re.compile(r"`([^`]+)`")
# Flags of the tool being learned (`<tool> --version`) or of the eval runner
# (`claude plugin eval --scaffold`), not of a Crew script.
TOOL_FLAGS = {"--version", "--scaffold"}


def body() -> str:
    text = SKILL.read_text(encoding="utf-8")
    return text.split("\n---\n", 1)[1]


def help_text(script: str) -> str:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), "--help"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def script_flags(script: str) -> set[str]:
    return set(FLAG.findall(help_text(script)))


def commands(text: str) -> list[str]:
    """Each fenced-block line and each inline code span, newlines folded."""
    found = [line for block in FENCED.findall(text) for line in block.splitlines()]
    prose = FENCED.sub("", text)
    found.extend(" ".join(span.split()) for span in INLINE.findall(prose))
    return found


class LearnSkillContractTests(unittest.TestCase):
    def test_frontmatter_is_the_planned_concept_skill(self) -> None:
        frontmatter, error = read_frontmatter(SKILL)
        self.assertIsNone(error)
        assert frontmatter is not None
        self.assertEqual("concept", frontmatter["tier"])
        self.assertEqual([], frontmatter["requires"])
        self.assertEqual(["agent-runtime"], frontmatter["expects-local"])

    def test_every_named_script_exists(self) -> None:
        for script in set(SCRIPT.findall(body())):
            with self.subTest(script=script):
                self.assertTrue((ROOT / "scripts" / script).is_file(), script)

    def test_every_flag_in_the_body_is_defined_by_a_script_it_drives(self) -> None:
        scripts = set(SCRIPT.findall(body()))
        self.assertIn("crew_inventory.py", scripts)
        self.assertIn("learn_contract.py", scripts)
        known = set().union(*(script_flags(script) for script in scripts)) | TOOL_FLAGS
        unknown = sorted(set(FLAG.findall(body())) - known)
        self.assertEqual([], unknown, "the learn skill names flags no script defines")

    def test_each_command_pairs_a_script_with_its_own_flags(self) -> None:
        checked = 0
        for command in commands(body()):
            match = SCRIPT.search(command)
            if not match:
                continue
            checked += 1
            flags = set(FLAG.findall(command[match.end():]))
            with self.subTest(command=command):
                self.assertEqual(set(), flags - script_flags(match.group(1)))
        self.assertGreaterEqual(checked, 4)

    def test_format_values_are_choices_the_inventory_accepts(self) -> None:
        choices = re.search(r"--format \{([^}]*)\}", help_text("crew_inventory.py"))
        assert choices is not None
        allowed = set(choices.group(1).split(","))
        used = set(re.findall(r"--format (\w+)", body()))
        self.assertIn("gaps", used)
        self.assertEqual(set(), used - allowed)

    def test_inspect_keys_and_gap_kinds_the_skill_reads_exist(self) -> None:
        text = body()
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect_proposals(pathlib.Path(tmp))
        for key in ("declared", "queue", "queue_errors", "proposals"):
            with self.subTest(key=key):
                self.assertIn(f"`{key}", text)
                self.assertIn(key, result)
        self.assertFalse(result["declared"])
        inventory = (ROOT / "scripts/crew_inventory.py").read_text(encoding="utf-8")
        for kind in ("tool-unskilled", "mcp-unskilled"):
            with self.subTest(kind=kind):
                self.assertIn(kind, text)
                self.assertIn(f'"{kind}"', inventory)


    def test_experience_signals_map_to_provenance_sources_the_contract_accepts(self) -> None:
        text = body()
        doc = (ROOT / "docs/LEARNING.md").read_text(encoding="utf-8")
        for signal, source in (("correction", "session"), ("repeated failure", "session"),
                               ("tool denial", "denial"), ("reviewer finding", "review"),
                               ("Doctor drift", "doctor")):
            row = re.compile(rf"^ *\| {signal} \|.*\| `{source}` \|$", re.MULTILINE)
            with self.subTest(signal=signal):
                self.assertRegex(text, row)
                self.assertRegex(doc, row)
                self.assertTrue(PROVENANCE_SOURCE.match(source))

    def test_lesson_as_test_is_drafted_but_never_run_by_the_agent(self) -> None:
        text = body()
        self.assertIn("Lesson-as-test", text)
        self.assertIn("--eval-case", text)
        self.assertIn("You write the fixture; you never run it.", text)
        self.assertIn("run a fixture or `claude plugin eval` unasked", text)


    def test_plan_validation_retro_hands_every_signal_to_learn_and_never_holds_a_gate(self) -> None:
        retro = (ROOT / "skills/plan-validation/SKILL.md").read_text(encoding="utf-8").split("## Retro", 1)[1]
        self.assertIn("`learn`", retro)
        self.assertTrue((ROOT / "skills/learn/SKILL.md").is_file())
        for signal in ("corrections", "failed more than once", "tool denials", "reviewer findings", "Doctor rows"):
            with self.subTest(signal=signal):
                self.assertIn(signal, retro)
        self.assertIn("after any\nreviewer pass", retro)
        self.assertIn("never holds a gate", retro)
        self.assertIn("**Retro:**", retro)


if __name__ == "__main__":
    unittest.main()
