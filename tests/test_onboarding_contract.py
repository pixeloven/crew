import pathlib
import subprocess
import sys
import tempfile
import unittest

from scripts.onboarding_contract import (
    REQUIRED_SPINE_SECTIONS,
    ApplyAuthorizationRequired,
    HostApplyAuthorizationSignal,
    audit_reporting_contract,
    consume_doctor_profile,
    ensure_reporting_contract,
    reporting_contract_section,
    resolve_mode,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates/AGENTS.md").read_text(encoding="utf-8")


class OnboardingLifecycleTests(unittest.TestCase):
    def test_m3_plain_and_explicit_audit_are_non_mutating(self) -> None:
        for explicit_audit in (False, True):
            contract = resolve_mode(explicit_audit=explicit_audit)
            self.assertEqual("audit", contract.mode)
            self.assertFalse(contract.writes_allowed)
            self.assertEqual("audit report delivered", contract.stop_boundary)

    def test_m3_apply_requires_a_fresh_current_invocation_host_signal(self) -> None:
        with self.assertRaises(ApplyAuthorizationRequired):
            resolve_mode(explicit_apply=True)
        with self.assertRaises(ApplyAuthorizationRequired):
            resolve_mode(explicit_apply=True, invocation_id="run-42", authorization="old-token")
        signal = HostApplyAuthorizationSignal(invocation_id="run-42", host_verified=True)
        contract = resolve_mode(explicit_apply=True, invocation_id="run-42", authorization=signal)
        self.assertEqual("apply", contract.mode)
        self.assertTrue(contract.writes_allowed)
        self.assertTrue(contract.authorization_verified)
        with self.assertRaises(ApplyAuthorizationRequired):
            resolve_mode(explicit_apply=True, invocation_id="run-42", authorization=signal)

    def test_m3_rejects_saved_standing_and_prior_run_authority(self) -> None:
        rejected = (
            HostApplyAuthorizationSignal(invocation_id="prior-run", host_verified=True),
            HostApplyAuthorizationSignal(invocation_id="run-42", host_verified=True, persisted=True),
            HostApplyAuthorizationSignal(invocation_id="run-42", host_verified=True, scope="standing"),
            HostApplyAuthorizationSignal(invocation_id="run-42", host_verified=False),
        )
        for signal in rejected:
            with self.subTest(signal=signal), self.assertRaises(ApplyAuthorizationRequired):
                resolve_mode(explicit_apply=True, invocation_id="run-42", authorization=signal)

    def test_m3_mature_safety_and_delivery_contracts_are_preservation_requirements(self) -> None:
        contract = resolve_mode()
        self.assertEqual(
            {
                "mature-entry-files",
                "safety-tripwires",
                "project-delivery-contracts",
                "runbook-pointers",
            },
            set(contract.preserve),
        )
        self.assertEqual("host escalation/decision interface", contract.destructive_change_interface)

    def test_lifecycle_stops_at_audit_and_defers_delivery(self) -> None:
        contract = resolve_mode()
        self.assertEqual("host project workflow", contract.implementation_validation_owner)
        self.assertFalse(contract.may_declare_delivery_complete)

    def test_apply_hands_implementation_validation_to_host_workflow(self) -> None:
        signal = HostApplyAuthorizationSignal(invocation_id="run-42", host_verified=True)
        contract = resolve_mode(
            explicit_apply=True,
            invocation_id="run-42",
            authorization=signal,
        )

        self.assertEqual("implementation handed to host workflow", contract.stop_boundary)
        self.assertEqual("host project workflow", contract.implementation_validation_owner)
        self.assertFalse(contract.may_declare_delivery_complete)

    def test_doctor_profile_handoff_has_one_shared_type(self) -> None:
        for profile in ("portable", "platform", "personas"):
            self.assertEqual(profile, consume_doctor_profile(profile))
        with self.assertRaises(ValueError):
            consume_doctor_profile("platform-personas")


class ReportingContractTests(unittest.TestCase):
    MATURE = (
        "# AGENTS.md\n\n## Autonomy\n\nProject posture.\n\n"
        "## Tripwires — load the skill before the action\n\nProject landmines.\n"
    )

    def test_template_carries_a_complete_reporting_contract(self) -> None:
        self.assertEqual("OK", audit_reporting_contract(TEMPLATE)["status"])
        section = reporting_contract_section(TEMPLATE)
        self.assertTrue(section.startswith("## Reporting contract"))
        self.assertIn("Decisions needed", section)
        self.assertNotIn("## Tripwires", section)

    def test_onboarding_requires_the_reporting_contract_section(self) -> None:
        self.assertIn("reporting-contract", REQUIRED_SPINE_SECTIONS)
        self.assertEqual(REQUIRED_SPINE_SECTIONS, resolve_mode().required_spine_sections)

    def test_absent_entry_file_or_section_is_missing_drift(self) -> None:
        for text in (None, self.MATURE):
            with self.subTest(text=text):
                finding = audit_reporting_contract(text)
                self.assertEqual("MISSING", finding["status"])
                self.assertIn("reporting contract", finding["fact"])
                self.assertIn("onboarding", finding["recommendation"])

    def test_heading_without_decision_block_is_degraded(self) -> None:
        text = self.MATURE + "\n## Reporting contract\n\nBe concise.\n"
        self.assertEqual("DEGRADED", audit_reporting_contract(text)["status"])

    def test_project_phrasing_of_the_decision_line_is_accepted(self) -> None:
        text = self.MATURE + "\n### Reporting Contract\n\nOpen with **1 decision needed.**\n"
        self.assertEqual("OK", audit_reporting_contract(text)["status"])

    def test_insert_lands_before_tripwires_preserves_content_and_is_idempotent(self) -> None:
        merged = ensure_reporting_contract(self.MATURE, TEMPLATE)
        self.assertEqual("OK", audit_reporting_contract(merged)["status"])
        self.assertLess(merged.index("## Reporting contract"), merged.index("## Tripwires"))
        self.assertIn("Project posture.", merged)
        self.assertIn("Project landmines.", merged)
        self.assertEqual(merged, ensure_reporting_contract(merged, TEMPLATE))

    def test_insert_appends_when_there_is_no_tripwires_anchor(self) -> None:
        merged = ensure_reporting_contract("# AGENTS.md\n\nProject text.\n", TEMPLATE)
        self.assertTrue(merged.startswith("# AGENTS.md\n\nProject text.\n"))
        self.assertEqual("OK", audit_reporting_contract(merged)["status"])

    def test_existing_project_section_is_never_replaced(self) -> None:
        text = self.MATURE + "\n## Reporting contract\n\nOur own words.\n"
        self.assertEqual(text, ensure_reporting_contract(text, TEMPLATE))

    def test_cli_check_is_read_only_and_exit_coded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "AGENTS.md"
            target.write_text(self.MATURE, encoding="utf-8")
            cases = ((target, 1, "MISSING"), (ROOT / "templates/AGENTS.md", 0, "OK"),
                     (pathlib.Path(tmp) / "absent.md", 1, "MISSING"))
            for path, code, status in cases:
                with self.subTest(path=path):
                    completed = subprocess.run(
                        [sys.executable, str(ROOT / "scripts/onboarding_contract.py"),
                         "--check-reporting", str(path)],
                        cwd=ROOT, text=True, capture_output=True, check=False,
                    )
                    self.assertEqual(code, completed.returncode, completed.stdout + completed.stderr)
                    self.assertIn(status, completed.stdout)
            self.assertEqual(self.MATURE, target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
