import pathlib
import tempfile
import unittest

from scripts.check_skills import MAX_DESC, validate_root
from scripts.frontmatter import read_frontmatter


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DescriptionContractTests(unittest.TestCase):
    def test_m4_all_catalog_descriptions_front_load_trigger_and_fit_policy(self) -> None:
        self.assertLessEqual(MAX_DESC, 300)
        self.assertGreaterEqual(MAX_DESC, 200)
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            frontmatter, error = read_frontmatter(path)
            self.assertIsNone(error)
            assert frontmatter is not None
            description = frontmatter["description"]
            self.assertLessEqual(len(description), MAX_DESC, str(path))
            self.assertTrue(
                description.startswith(("Use when ", "Load when ")),
                f"{path}: trigger language must lead the model-visible description",
            )

    def test_description_gate_rejects_policy_regression_without_platform_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / ".claude-plugin").mkdir()
            (root / ".claude-plugin/plugin.json").write_text('{"version":"1.0.0"}', encoding="utf-8")
            (root / ".claude-plugin/marketplace.json").write_text("{}", encoding="utf-8")
            (root / "package.json").write_text('{"version":"1.0.0"}', encoding="utf-8")
            skill = root / "skills/too-long/SKILL.md"
            skill.parent.mkdir(parents=True)
            description = "Use when validating the documented Crew description policy. " + ("x" * MAX_DESC)
            skill.write_text(
                "---\nname: too-long\ndescription: " + description + "\ntier: concept\nrequires: []\n---\n",
                encoding="utf-8",
            )
            errors = validate_root(root)
            self.assertTrue(any("description too long" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
