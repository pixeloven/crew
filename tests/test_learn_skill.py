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


def signal_sources(text: str) -> dict[str, str]:
    """signal -> provenance-source, from the markdown table whose last column is `provenance-source`."""
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in text.splitlines() if line.strip().startswith("|")]
    header = next(index for index, row in enumerate(rows) if row[-1] == "`provenance-source`")
    found = {}
    for row in rows[header + 2:]:
        if len(row) != len(rows[header]):
            break
        found[row[0]] = row[-1].strip("`")
    return found


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
        skill = signal_sources(body())
        doc = signal_sources((ROOT / "docs/LEARNING.md").read_text(encoding="utf-8"))
        self.assertEqual(
            {"correction", "repeated failure", "tool denial", "reviewer finding", "Doctor drift"}, set(skill)
        )
        self.assertEqual(skill, doc)
        for signal, source in skill.items():
            with self.subTest(signal=signal):
                self.assertTrue(PROVENANCE_SOURCE.match(source), source)


if __name__ == "__main__":
    unittest.main()
