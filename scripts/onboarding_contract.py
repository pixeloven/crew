#!/usr/bin/env python3
"""Deterministic lifecycle boundary shared by the Onboarding skill and tests."""

from dataclasses import dataclass

try:
    from .crew_doctor import PROFILE_TAXONOMY
except ImportError:  # Direct script execution.
    from crew_doctor import PROFILE_TAXONOMY


class ApplyAuthorizationRequired(ValueError):
    """Raised when mutation is requested without a distinct authorization."""


@dataclass(frozen=True)
class OnboardingMode:
    mode: str
    writes_allowed: bool
    authorization: str | None
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
    authorization: str | None = None,
) -> OnboardingMode:
    """Resolve plain onboarding to audit; allow apply only with a recorded grant."""
    if explicit_audit and explicit_apply:
        raise ValueError("audit and apply are mutually exclusive")
    if explicit_apply and not authorization:
        raise ApplyAuthorizationRequired(
            "apply requires a distinct per-run authorization from the host escalation/decision interface"
        )

    applying = explicit_apply and bool(authorization)
    return OnboardingMode(
        mode="apply" if applying else "audit",
        writes_allowed=applying,
        authorization=authorization if applying else None,
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
