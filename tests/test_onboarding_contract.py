import unittest

from scripts.onboarding_contract import (
    ApplyAuthorizationRequired,
    HostApplyAuthorizationSignal,
    consume_doctor_profile,
    resolve_mode,
)


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

    def test_doctor_profile_handoff_has_one_shared_type(self) -> None:
        for profile in ("portable", "platform", "personas"):
            self.assertEqual(profile, consume_doctor_profile(profile))
        with self.assertRaises(ValueError):
            consume_doctor_profile("platform-personas")


if __name__ == "__main__":
    unittest.main()
