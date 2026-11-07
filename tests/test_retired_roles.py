import pathlib
import tempfile
import unittest

from scripts.crew_doctor import (
    EXPECTED_ROLE_NAMES,
    RETIRED_ROLES,
    compose_doctor_report,
    declared_local_slots,
    inspect_installations,
    render_doctor_report,
    retired_role_references,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]


def write(path: pathlib.Path, text: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def checks_for(base: pathlib.Path) -> dict[str, dict]:
    report = compose_doctor_report(
        inspect_installations(base / "project", base / "home"),
        runtime_comparisons=[],
        local_slots=declared_local_slots(ROOT),
        role_postures=[],
        persona_evidence=[],
        retired_role_refs=retired_role_references(base / "project"),
    )
    render_doctor_report(report)
    return {row["check"]: row for row in report["checks"]}


class RetiredRoleTableTests(unittest.TestCase):
    def test_responder_retired_into_researcher(self) -> None:
        self.assertEqual(("researcher", "0.66.0"), RETIRED_ROLES["responder"])

    def test_retired_roles_have_no_source_and_successors_still_ship(self) -> None:
        for role, (successor, _version) in RETIRED_ROLES.items():
            with self.subTest(role=role):
                self.assertNotIn(role, EXPECTED_ROLE_NAMES)
                self.assertFalse((ROOT / "roles" / role).exists())
                self.assertFalse((ROOT / "agents" / f"{role}.md").exists())
                self.assertFalse((ROOT / "pi-agents" / f"{role}.md").exists())
                self.assertIn(successor, EXPECTED_ROLE_NAMES)
                self.assertTrue((ROOT / "roles" / successor / "role.yml").is_file())

    def test_expected_roles_match_role_sources(self) -> None:
        sources = sorted(
            p.name for p in (ROOT / "roles").iterdir() if p.is_dir() and not p.name.startswith("_")
        )
        self.assertEqual(sources, sorted(EXPECTED_ROLE_NAMES))


class RetiredRoleReferenceTests(unittest.TestCase):
    def test_doctor_points_a_stale_reference_at_the_successor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            write(
                base / "project/AGENTS.md",
                "| Fast read + draft | `responder` | trigger |\n"
                "Dispatch crew:responder for questions.\n"
                "An incident responder is a person, not a role.\n",
            )
            write(base / "project/.pi/agents/router.md", "Route questions to crew.responder.\n")
            refs = retired_role_references(base / "project")
            self.assertEqual(
                [("AGENTS.md", 1), ("AGENTS.md", 2), ("router.md", 1)],
                [(pathlib.Path(r["source"]).name, r["line"]) for r in refs["references"]],
            )
            row = checks_for(base)["retired-roles.responder"]
            self.assertEqual("DEGRADED", row["status"])
            self.assertIn("0.66.0", row["fact"])
            self.assertIn("`researcher`", row["recommendation"])
            self.assertEqual(3, len(row["evidence"]))

    def test_clean_consumer_gets_no_retired_role_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            write(base / "project/AGENTS.md", "Dispatch `researcher` for questions.\n")
            checks = checks_for(base)
            self.assertFalse([name for name in checks if name.startswith("retired-roles.")])


if __name__ == "__main__":
    unittest.main()
