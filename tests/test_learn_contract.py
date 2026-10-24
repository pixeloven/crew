import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.check_skills import validate_local
from scripts.crew_doctor import (
    compose_doctor_report,
    declared_local_slots,
    inspect_installations,
    render_doctor_report,
)
from scripts.learn_contract import (
    BANNER,
    FIXTURE_SCHEMA,
    TRANSITIONS,
    check_fixture,
    check_proposal,
    check_queue,
    check_transition,
    context_leaks,
    git_remote_slugs,
    inspect_proposals,
    learned_markers,
    queue_location,
    queue_location_errors,
    verbatim_copies,
)
from scripts.onboarding_contract import (
    REQUIRED_SPINE_SECTIONS,
    audit_learning_section,
    ensure_learning_section,
    learning_section,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/proposals"
ORCHARD = FIXTURES / "orchard"
QUEUE = ORCHARD / ".agents/proposals"
VALID = QUEUE / "2026-10-21-gh-pr-checks.md"
INVALID = FIXTURES / "invalid/.agents/proposals"
TEMPLATE = (ROOT / "templates/AGENTS.md").read_text(encoding="utf-8")
LEARN = ROOT / "scripts/learn_contract.py"


def gates(path: pathlib.Path, **kwargs) -> set[str]:
    return {item["gate"] for item in check_proposal(path, **kwargs)}


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True, check=False)


def snapshot(root: pathlib.Path) -> dict[str, bytes]:
    return {str(path): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


class ProposalGateTests(unittest.TestCase):
    def test_every_valid_fixture_passes_every_gate(self) -> None:
        results = check_queue(QUEUE)
        self.assertEqual(5, len(results))  # queue-level + four proposals
        for path, found in results.items():
            with self.subTest(path=path):
                self.assertEqual([], found)

    def test_cli_check_passes_a_valid_proposal_and_its_queue(self) -> None:
        for target in (VALID, QUEUE):
            with self.subTest(target=target):
                completed = run(str(LEARN), "--check", str(target))
                self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
                self.assertIn("pass every gate", completed.stdout)

    def test_each_invalid_fixture_fails_its_own_gate_with_a_clear_message(self) -> None:
        expected = {
            "2026-10-21-missing-fields.md": ("fields", "missing required fields ['classification', 'provenance-crew']"),
            "2026-10-21-verbatim-copy.md": ("verbatim-promotion", "restate the fact in your own words"),
            "2026-10-21-short-description.md": ("new-skill-schema", "description too short"),
            "2026-10-21-no-banner.md": ("structure", "missing section ## Rollback"),
            "2026-10-21-leaky-methodology.md": ("methodology-context", "hostname 'ci.build.internal'"),
            "2026-10-21-recurrence-skipped.md": ("classification", "needs recurrence"),
            "2026-10-21-unmarked-promotion.md": ("learned-marker", "carries no crew:learned marker"),
            "2026-10-21-bad-fixture.md": ("fixture", "a model grader is a model call"),
        }
        self.assertEqual(set(expected), {path.name for path in INVALID.glob("*.md")})
        for name, (gate, message) in expected.items():
            with self.subTest(name=name):
                completed = run(str(LEARN), "--check", str(INVALID / name))
                self.assertEqual(1, completed.returncode, completed.stdout)
                self.assertIn(f"[{gate}]", completed.stdout)
                self.assertIn(message, completed.stdout)

    def test_a_queue_under_a_skills_directory_fails(self) -> None:
        path = FIXTURES / "invalid/skills/proposals/2026-10-21-in-skill-root.md"
        self.assertEqual({"queue"}, gates(path))
        completed = run(str(LEARN), "--check", str(path))
        self.assertEqual(1, completed.returncode)
        self.assertIn("is under a skills directory", completed.stdout)

    def test_a_proposal_named_skill_md_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "SKILL.md"
            shutil.copy(VALID, path)
            self.assertEqual({"queue"}, gates(path))

    def test_the_leaky_methodology_fixture_names_every_kind_of_leak(self) -> None:
        messages = " ".join(item["message"] for item in check_proposal(INVALID / "2026-10-21-leaky-methodology.md"))
        for leak in ("project name 'invalid'", "absolute path '/Users/sam/src/invalid/plans/retro.md'",
                     "IP address '10.0.4.17'", "hostname 'ci.build.internal'"):
            self.assertIn(leak, messages)

    def test_methodology_context_includes_the_git_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "shop"
            queue = root / ".agents/proposals"
            queue.mkdir(parents=True)
            (root / "AGENTS.md").write_text("`proposal-queue: .agents/proposals/`\n", encoding="utf-8")
            (root / ".git").mkdir()
            (root / ".git/config").write_text(
                '[remote "origin"]\n\turl = git@example.test:example-org/storefront.git\n', encoding="utf-8"
            )
            self.assertEqual(["example-org/storefront"], git_remote_slugs(root))
            source = (QUEUE / "2026-10-21-review-before-retro.md").read_text(encoding="utf-8")
            path = queue / "2026-10-21-review-before-retro.md"
            path.write_text(source.replace("out of the proposal queue.", "out of example-org/storefront's queue."),
                            encoding="utf-8")
            messages = [item["message"] for item in check_proposal(path)]
            self.assertTrue(any("git remote 'example-org/storefront'" in m for m in messages), messages)

    def test_portable_text_carries_no_false_leaks(self) -> None:
        text = "Run `gh pr checks --watch` from the branch; see AGENTS.md#git and scripts/check_skills.py."
        self.assertEqual([], context_leaks(text, project_names=["orchard"], remote_slugs=["example-org/orchard"]))

    def test_a_field_written_as_a_nested_block_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "AGENTS.md").write_text("", encoding="utf-8")
            path = root / VALID.name
            text = VALID.read_text(encoding="utf-8")
            line = next(line for line in text.splitlines() if line.startswith("observation:"))
            path.write_text(text.replace(line, "observation:\n  saw: a thing"), encoding="utf-8")
            messages = [item["message"] for item in check_proposal(path) if item["gate"] == "fields"]
            self.assertEqual(["invalid frontmatter: observation must be a flat scalar, not a nested block"],
                             messages)

    def test_verbatim_window_ignores_case_and_whitespace_and_stops_below_forty(self) -> None:
        excerpt = "Without an argument, the pull request that belongs to the current branch"
        copied = [(1, "WITHOUT an   argument, the pull request that belongs")]
        self.assertEqual(1, len(verbatim_copies(copied, [excerpt])))
        short = [(1, excerpt[:39])]
        self.assertEqual([], verbatim_copies(short, [excerpt]))

    def test_new_skill_diff_must_carry_a_marker_matching_tool_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "AGENTS.md").write_text("", encoding="utf-8")
            path = root / VALID.name
            path.write_text(VALID.read_text(encoding="utf-8").replace("tool=gh@2.81.0", "tool=gh@2.70.0"),
                            encoding="utf-8")
            messages = [item["message"] for item in check_proposal(path) if item["gate"] == "learned-marker"]
            self.assertEqual(["the marker must carry tool=gh@2.81.0 to match provenance"], messages)

    def test_learned_markers_parse_and_reject_malformed_tokens(self) -> None:
        markers, errors = learned_markers(
            "<!-- crew:learned proposal=2026-10-21-a tool=gh@2.81.0 date=2026-10-21 -->\n"
            "<!-- crew:learned proposal=nope date=yesterday -->\n"
        )
        self.assertEqual(("gh", "2.81.0"), (markers[0]["tool"], markers[0]["tool_version"]))
        self.assertEqual(2, len(errors))

    def test_transitions_end_at_operator_terminal_states(self) -> None:
        self.assertTrue(check_transition("draft", "reviewed"))
        self.assertTrue(check_transition("reviewed", "promoted"))
        self.assertTrue(check_transition("promoted", "rejected"))  # rollback
        self.assertFalse(check_transition("draft", "promoted"))  # review is not skippable
        self.assertFalse(check_transition("needs-recurrence", "reviewed"))
        self.assertEqual(frozenset(), TRANSITIONS["rejected"])
        self.assertEqual(frozenset(), TRANSITIONS["superseded"])

    def test_fixture_schema_is_provisional_and_documented(self) -> None:
        self.assertEqual("crew-lesson-fixture/1", FIXTURE_SCHEMA)
        self.assertEqual([], check_fixture(QUEUE / "fixtures/2026-10-21-gh-pr-checks.json", "2026-10-21-gh-pr-checks"))
        doc = (ROOT / "docs/LEARNING.md").read_text(encoding="utf-8")
        self.assertIn("PROVISIONAL", doc)
        self.assertIn("#72", doc)
        self.assertIn(BANNER, doc)

    def test_check_reads_only(self) -> None:
        before = snapshot(FIXTURES)
        check_queue(QUEUE)
        check_queue(INVALID)
        self.assertEqual(before, snapshot(FIXTURES))


class QueueLocationTests(unittest.TestCase):
    def test_template_declares_the_committed_default(self) -> None:
        self.assertEqual(".agents/proposals/", queue_location(TEMPLATE))
        self.assertEqual([], queue_location_errors(".agents/proposals/"))

    def test_absent_and_conflicting_declarations(self) -> None:
        self.assertIsNone(queue_location("# AGENTS.md\n"))
        with self.assertRaises(ValueError):
            queue_location("`proposal-queue: a/`\n`proposal-queue: b/`\n")

    def test_unusable_locations_are_named(self) -> None:
        for location, phrase in (
            ("/srv/proposals", "relative to the project root"),
            ("../elsewhere", "escapes the project root"),
            (".agents/skills/proposals", "under a skills directory"),
            ("skills", "under a skills directory"),
            ("queue/SKILL.md", "names a SKILL.md"),
        ):
            with self.subTest(location=location):
                self.assertTrue(any(phrase in error for error in queue_location_errors(location)))


class LocalSkillGateTests(unittest.TestCase):
    def test_only_learned_skills_are_checked(self) -> None:
        self.assertEqual(([], 1), validate_local(ORCHARD))
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            hand = root / ".agents/skills/hand-written/SKILL.md"
            hand.parent.mkdir(parents=True)
            hand.write_text("---\nname: hand-written\ndescription: short\n---\n", encoding="utf-8")
            self.assertEqual(([], 0), validate_local(root))
            learned = root / ".agents/skills/learned/SKILL.md"
            learned.parent.mkdir(parents=True)
            learned.write_text(
                "---\nname: learned\ndescription: short\ntier: subject\nrequires: []\nprovides: [topology]\n---\n"
                "<!-- crew:learned proposal=2026-10-21-learned date=2026-10-21 -->\n",
                encoding="utf-8",
            )
            errors, count = validate_local(root)
            self.assertEqual(1, count)
            self.assertTrue(any("description too short" in error for error in errors), errors)
            self.assertTrue(any("provides is pack-only" in error for error in errors), errors)

    def test_cli_local_mode_runs_alone(self) -> None:
        completed = run(str(ROOT / "scripts/check_skills.py"), "--local", str(ORCHARD))
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("1 learned skill(s) conform", completed.stdout)
        completed = run(str(ROOT / "scripts/check_skills.py"), "--local", str(ORCHARD), "--pack")
        self.assertEqual(2, completed.returncode)


class DoctorProposalTests(unittest.TestCase):
    def rows(self, consumer: pathlib.Path, **versions: str) -> dict[str, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            (base / "project").mkdir()
            (base / "home").mkdir()
            report = compose_doctor_report(
                inspect_installations(base / "project", base / "home"),
                runtime_comparisons=[],
                local_slots=declared_local_slots(ROOT),
                role_postures=[],
                persona_evidence=[],
                proposals=inspect_proposals(consumer, tool_versions=versions),
            )
        render_doctor_report(report)  # every row stays source-bearing
        return {row["check"]: row for row in report["checks"]}

    def test_current_tools_leave_drafts_fresh_and_flag_an_older_learned_skill(self) -> None:
        before = snapshot(ORCHARD)
        rows = self.rows(ORCHARD, gh="2.81.0")
        self.assertEqual(before, snapshot(ORCHARD))
        self.assertEqual("OK", rows["proposals.queue"]["status"])
        self.assertIn("2 needs-recurrence", rows["proposals.queue"]["fact"])
        self.assertEqual("OK", rows["proposals.staleness"]["status"])
        learned = rows["learned.skills"]
        self.assertEqual("DEGRADED", learned["status"])
        self.assertIn("orchard-gh-runs learned gh 2.79.0, now 2.81.0", learned["fact"])
        self.assertIn("3f2c1a9", learned["recommendation"])

    def test_a_newer_tool_makes_its_draft_stale(self) -> None:
        rows = self.rows(ORCHARD, gh="2.82.0")
        self.assertEqual("DEGRADED", rows["proposals.staleness"]["status"])
        self.assertIn("gh is 2.82.0; the evidence is from 2.81.0", rows["proposals.staleness"]["fact"])

    def test_unsupplied_versions_stay_untested(self) -> None:
        rows = self.rows(ORCHARD)
        self.assertEqual("N/A", rows["proposals.staleness"]["status"])
        self.assertIn("version not supplied", rows["proposals.staleness"]["untested"])
        self.assertEqual("N/A", rows["learned.skills"]["status"])

    def test_a_changed_target_makes_its_draft_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp) / "orchard"
            shutil.copytree(ORCHARD, consumer)
            agents = consumer / "AGENTS.md"
            agents.write_text(agents.read_text(encoding="utf-8") + "\n## Tripwires\n", encoding="utf-8")
            rows = self.rows(consumer, gh="2.81.0")
        self.assertEqual("DEGRADED", rows["proposals.staleness"]["status"])
        self.assertIn("2026-10-21-draft-pr-first: AGENTS.md changed", rows["proposals.staleness"]["fact"])

    def test_undeclared_queue_is_not_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp)
            (consumer / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
            rows = self.rows(consumer)
        self.assertEqual("N/A", rows["proposals.queue"]["status"])
        self.assertIn("report-only", rows["proposals.queue"]["fact"])
        self.assertNotIn("proposals.staleness", rows)

    def test_malformed_proposals_or_a_skill_root_queue_degrade(self) -> None:
        rows = self.rows(FIXTURES / "invalid")
        self.assertEqual("DEGRADED", rows["proposals.queue"]["status"])
        self.assertIn("learn_contract.py --check", rows["proposals.queue"]["recommendation"])
        with tempfile.TemporaryDirectory() as tmp:
            consumer = pathlib.Path(tmp)
            (consumer / "AGENTS.md").write_text("`proposal-queue: .agents/skills/queue/`\n", encoding="utf-8")
            rows = self.rows(consumer)
        self.assertEqual("DEGRADED", rows["proposals.queue"]["status"])
        self.assertIn("under a skills directory", rows["proposals.queue"]["fact"])

    def test_omitting_proposals_adds_no_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            report = compose_doctor_report(
                inspect_installations(base, base), runtime_comparisons=[],
                local_slots=declared_local_slots(ROOT), role_postures=[], persona_evidence=[],
            )
        self.assertFalse(any(row["check"].startswith(("proposals.", "learned.")) for row in report["checks"]))

    def test_cli_inspect_prints_doctor_evidence(self) -> None:
        completed = run(str(LEARN), "--inspect", str(ORCHARD), "--tool-version", "gh=2.81.0")
        self.assertEqual(0, completed.returncode, completed.stderr)
        data = json.loads(completed.stdout)
        self.assertTrue(data["declared"])
        self.assertEqual("3f2c1a9", data["learned_skills"][0]["promoted_in"])


class OnboardingLearningTests(unittest.TestCase):
    MATURE = (
        "# AGENTS.md\n\n## Autonomy\n\nProject posture.\n\n"
        "## Tripwires — load the skill before the action\n\nProject landmines.\n"
    )

    def test_learning_is_optional_spine(self) -> None:
        self.assertNotIn("learning", REQUIRED_SPINE_SECTIONS)
        self.assertEqual("N/A", audit_learning_section(self.MATURE)["status"])
        self.assertEqual("N/A", audit_learning_section(None)["status"])
        self.assertEqual("OK", audit_learning_section(TEMPLATE)["status"])

    def test_template_section_carries_the_fill_line(self) -> None:
        section = learning_section(TEMPLATE)
        self.assertTrue(section.startswith("## Learning"))
        self.assertIn("`proposal-queue: .agents/proposals/`", section)
        self.assertNotIn("## Tripwires", section)

    def test_insert_lands_before_tripwires_and_is_idempotent(self) -> None:
        merged = ensure_learning_section(self.MATURE, TEMPLATE)
        self.assertLess(merged.index("## Learning"), merged.index("## Tripwires"))
        self.assertIn("Project posture.", merged)
        self.assertEqual(merged, ensure_learning_section(merged, TEMPLATE))
        appended = ensure_learning_section("# AGENTS.md\n", TEMPLATE)
        self.assertEqual("OK", audit_learning_section(appended)["status"])

    def test_a_project_section_is_never_replaced(self) -> None:
        text = self.MATURE + "\n## Learning\n\nWe keep lessons in our tracker.\n"
        self.assertEqual(text, ensure_learning_section(text, TEMPLATE))
        self.assertEqual("N/A", audit_learning_section(text)["status"])

    def test_a_skill_root_queue_is_degraded(self) -> None:
        text = self.MATURE + "\n## Learning\n\n`proposal-queue: .agents/skills/q/`\n"
        self.assertEqual("DEGRADED", audit_learning_section(text)["status"])

    def test_cli_check_learning_is_read_only(self) -> None:
        completed = run(str(ROOT / "scripts/onboarding_contract.py"), "--check-learning",
                        str(ROOT / "templates/AGENTS.md"))
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("learning | OK | proposals queue at .agents/proposals/", completed.stdout)

    def test_cli_hosted_profile_keeps_a_degraded_queue_degraded_without_proposing_an_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = str(ROOT / "scripts/onboarding_contract.py")
            for name, learning in (("skill-root", "`proposal-queue: .agents/skills/q/`\n"),
                                   ("duplicate", "`proposal-queue: .agents/a/`\n`proposal-queue: .agents/b/`\n")):
                with self.subTest(case=name):
                    degraded = pathlib.Path(tmp) / f"{name}.md"
                    degraded.write_text(self.MATURE + "\n## Learning\n\n" + learning, encoding="utf-8")
                    standard = run(script, "--check-learning", str(degraded))
                    self.assertEqual(1, standard.returncode, standard.stdout + standard.stderr)
                    self.assertIn("| DEGRADED |", standard.stdout)
                    hosted = run(script, "--check-learning", str(degraded), "--audit-profile", "hosted")
                    self.assertEqual(1, hosted.returncode, hosted.stdout + hosted.stderr)
                    self.assertIn("learning | DEGRADED |", hosted.stdout)
                    self.assertIn("| the host decides whether the declared queue is fixed |", hosted.stdout)
                    self.assertNotIn(standard.stdout.split(" | ")[3], hosted.stdout)

    def test_cli_hosted_profile_reports_an_absent_learning_section_as_n_a_without_a_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = str(ROOT / "scripts/onboarding_contract.py")
            bare = pathlib.Path(tmp) / "AGENTS.md"
            bare.write_text(self.MATURE, encoding="utf-8")
            for path in (bare, pathlib.Path(tmp) / "absent.md"):
                with self.subTest(path=path):
                    hosted = run(script, "--check-learning", str(path), "--audit-profile", "hosted")
                    self.assertEqual(0, hosted.returncode, hosted.stdout + hosted.stderr)
                    self.assertIn("learning | N/A |", hosted.stdout)
                    self.assertIn("reserves AGENTS.md for humans |  |", hosted.stdout)

if __name__ == "__main__":
    unittest.main()
