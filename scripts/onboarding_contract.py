#!/usr/bin/env python3
"""Deterministic lifecycle boundary shared by the Onboarding skill and tests."""

from dataclasses import dataclass

try:
    from .crew_doctor import PROFILE_TAXONOMY
except ImportError:  # Direct script execution.
    from crew_doctor import PROFILE_TAXONOMY


class ApplyAuthorizationRequired(ValueError):
    """Raised when mutation is requested without a distinct authorization."""


@dataclass
class HostApplyAuthorizationSignal:
    """One-use host decision for one currently executing onboarding invocation."""

    invocation_id: str
    host_verified: bool
    scope: str = "current-invocation"
    persisted: bool = False
    _consumed: bool = False

    def consume(self, invocation_id: str) -> None:
        """Consume a fresh host-verified signal without authenticating or persisting it."""
        if (
            not self.host_verified
            or self.scope != "current-invocation"
            or self.persisted
            or self._consumed
            or not invocation_id
            or self.invocation_id != invocation_id
        ):
            raise ApplyAuthorizationRequired(
                "apply requires a fresh, non-persisted authorization signal verified by the "
                "supervising host for this invocation"
            )
        self._consumed = True


@dataclass(frozen=True)
class OnboardingMode:
    mode: str
    writes_allowed: bool
    authorization_verified: bool
    stop_boundary: str
    preserve: tuple[str, ...]
    destructive_change_interface: str
    implementation_validation_owner: str
    may_declare_delivery_complete: bool


PRESERVE = (
    "mature-entry-files",
    "safety-tripwires",
    "project-delivery-contracts",
    "runbook-pointers",
)


def resolve_mode(
    *,
    explicit_audit: bool = False,
    explicit_apply: bool = False,
    invocation_id: str | None = None,
    authorization: HostApplyAuthorizationSignal | None = None,
) -> OnboardingMode:
    """Resolve plain onboarding to audit; trust only a current host decision."""
    if explicit_audit and explicit_apply:
        raise ValueError("audit and apply are mutually exclusive")
    if explicit_apply:
        if not isinstance(authorization, HostApplyAuthorizationSignal) or not invocation_id:
            raise ApplyAuthorizationRequired(
                "apply requires a fresh current-invocation authorization signal from the supervising host"
            )
        authorization.consume(invocation_id)

    applying = explicit_apply
    return OnboardingMode(
        mode="apply" if applying else "audit",
        writes_allowed=applying,
        authorization_verified=applying,
        stop_boundary="implementation handed to host workflow" if applying else "audit report delivered",
        preserve=PRESERVE,
        destructive_change_interface="host escalation/decision interface",
        implementation_validation_owner="host project workflow",
        may_declare_delivery_complete=False,
    )


def consume_doctor_profile(profile: str) -> str:
    """Validate the typed Doctor → Onboarding handoff."""
    if profile not in PROFILE_TAXONOMY:
        raise ValueError(f"unknown Doctor profile {profile!r}; expected one of {PROFILE_TAXONOMY}")
    return profile
