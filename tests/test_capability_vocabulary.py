import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

from scripts.check_skills import capability_vocabulary, capability_warnings, validate_root
from tests.test_inventory_contract import InventoryTestCase
from tests.test_pack_contract import write_pack, write_skill


ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/CAPABILITIES.md"
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|")


def documented_names() -> list[str]:
    """First-column names of the vocabulary table in docs/CAPABILITIES.md."""
    text = DOC.read_text(encoding="utf-8")
    table = text.split("## Vocabulary", 1)[1].split("\n## ", 1)[0]
    return [match.group(1) for line in table.splitlines() if (match := ROW.match(line))]


def write_stub(root: pathlib.Path, slot: str, capability: str) -> None:
    stub = root / "templates/local-skills" / f"{slot}.md"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(
        f"# {slot}\n\n## Fields\n\n<!-- crew:discoverable capability={capability} -->\n\n> **▸ Fill:** x\n",
        encoding="utf-8",
    )


class VocabularySourceTests(unittest.TestCase):
    def test_doc_table_and_machine_list_agree(self) -> None:
        names = documented_names()
        self.assertTrue(names, "docs/CAPABILITIES.md has no vocabulary table")
        self.assertEqual(sorted(names), sorted(capability_vocabulary()))
        self.assertEqual(len(names), len(set(names)), "a name is documented twice")

    def test_every_name_is_a_valid_requires_capability(self) -> None:
        from scripts.check_skills import REQUIRES_RE

        for name in capability_vocabulary():
            self.assertRegex(name, REQUIRES_RE)
            self.assertFalse(name.startswith("plugin:"), name)

    def test_crew_itself_names_only_known_capabilities(self) -> None:
        self.assertEqual([], capability_warnings(ROOT))


class CapabilityWarningTests(unittest.TestCase):
    def test_unknown_mcp_in_requires_warns_but_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            write_pack(pack)
            write_skill(pack, "known", requires="[mcp:tracker, plugin:crew@>=0.38.0]")
            write_skill(pack, "unknown", requires="[mcp:jira, plugin:crew@>=0.38.0]")
            self.assertEqual([], validate_root(pack, pack=True))
            warnings = capability_warnings(pack)
            self.assertEqual(1, len(warnings), warnings)
            self.assertIn("skills/unknown/SKILL.md", warnings[0])
            self.assertIn("mcp:jira", warnings[0])

    def test_unknown_mcp_in_a_discoverable_marker_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            write_pack(pack)
            write_skill(pack, "pack-skill", requires="[plugin:crew@>=0.38.0]")
            write_stub(pack, "known-slot", "mcp:warehouse")
            write_stub(pack, "odd-slot", "mcp:snowflake")
            warnings = capability_warnings(pack)
            self.assertEqual(1, len(warnings), warnings)
            self.assertIn("templates/local-skills/odd-slot.md", warnings[0])
            self.assertIn("mcp:snowflake", warnings[0])

    def test_cli_names_are_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            write_pack(pack)
            write_skill(pack, "pack-skill", requires="[cli:terraform, plugin:crew@>=0.38.0]")
            self.assertEqual([], capability_warnings(pack))

    def test_cli_prints_the_warning_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            write_pack(pack)
            write_skill(pack, "pack-skill", requires="[mcp:jira, plugin:crew@>=0.38.0]")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/check_skills.py"), "--pack", "--root", str(pack)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("warning:", result.stdout)
            self.assertIn("mcp:jira", result.stdout)
            self.assertIn("docs/CAPABILITIES.md", result.stdout)


class InventoryUnknownCapabilityTests(InventoryTestCase):
    def test_a_gap_on_an_unknown_capability_says_so(self) -> None:
        skill = self.fixture.home / ".claude/skills/user-jira/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "---\nname: user-jira\ndescription: Use when exercising the inventory contract fixture "
            "so that this fixture description comfortably clears the schema-v2 minimum length.\n"
            "tier: subject\nrequires: [mcp:jira]\n---\n\n# user-jira\n",
            encoding="utf-8",
        )
        inventory = self.fixture.build(clis=["jq"], which=lambda name: None)
        found = {(gap["kind"], gap["name"]): gap for gap in inventory["gaps"]}
        for name in ("mcp:jira", "external:linear"):
            gap = found[("capability-unprovided", name)]
            self.assertIn("not in Crew's capability vocabulary", gap["evidence"], gap)
        for name in ("cli:jq", "external:github"):
            gap = found[("capability-unprovided", name)]
            self.assertNotIn("vocabulary", gap["evidence"], gap)


if __name__ == "__main__":
    unittest.main()
