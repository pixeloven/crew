#!/usr/bin/env python3
"""Deterministic lifecycle boundary shared by the Onboarding skill and tests."""

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Any

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
    required_spine_sections: tuple[str, ...]


PRESERVE = (
    "mature-entry-files",
    "safety-tripwires",
    "project-delivery-contracts",
    "runbook-pointers",
)

# Spine sections an onboarded AGENTS.md must carry even when it is mature and
# project-written. Doctor reports their absence as drift; apply inserts them.
REQUIRED_SPINE_SECTIONS = ("reporting-contract",)


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
        required_spine_sections=REQUIRED_SPINE_SECTIONS,
    )


def consume_doctor_profile(profile: str) -> str:
    """Validate the typed Doctor → Onboarding handoff."""
    if profile not in PROFILE_TAXONOMY:
        raise ValueError(f"unknown Doctor profile {profile!r}; expected one of {PROFILE_TAXONOMY}")
    return profile


_REPORTING_HEADING = re.compile(r"^#{2,3}[ \t]+reporting contract\b.*$", re.IGNORECASE | re.MULTILINE)
_DECISION_LINE = re.compile(r"decisions?\s+needed", re.IGNORECASE)
_TRIPWIRES_HEADING = re.compile(r"^##[ \t]+tripwires\b", re.IGNORECASE | re.MULTILINE)


def _section_bounds(text: str) -> tuple[int, int] | None:
    match = _REPORTING_HEADING.search(text)
    if not match:
        return None
    level = len(match.group(0)) - len(match.group(0).lstrip("#"))
    following = re.compile(rf"^#{{1,{level}}}[ \t]", re.MULTILINE)
    end = following.search(text, match.end())
    return match.start(), end.start() if end else len(text)


def reporting_contract_section(text: str) -> str:
    """Return the reporting-contract section of an entry file, or ``""``."""
    bounds = _section_bounds(text)
    return text[bounds[0]:bounds[1]].rstrip() + "\n" if bounds else ""


def audit_reporting_contract(text: str | None) -> dict[str, Any]:
    """Read-only presence check Doctor and audit share; never edits anything."""
    recommendation = "run onboarding apply to merge the reporting contract from templates/AGENTS.md"
    if text is None:
        return {
            "check": "reporting-contract",
            "status": "MISSING",
            "fact": "no AGENTS.md, so no reporting contract",
            "recommendation": recommendation,
        }
    section = reporting_contract_section(text)
    if not section:
        return {
            "check": "reporting-contract",
            "status": "MISSING",
            "fact": "AGENTS.md has no reporting contract section",
            "recommendation": recommendation,
        }
    if not _DECISION_LINE.search(section):
        return {
            "check": "reporting-contract",
            "status": "DEGRADED",
            "fact": "reporting contract section does not require a leading decisions line",
            "recommendation": "restore the decisions-first rule from templates/AGENTS.md",
        }
    return {
        "check": "reporting-contract",
        "status": "OK",
        "fact": "reporting contract present with a decisions-first rule",
        "recommendation": "",
    }


def ensure_reporting_contract(text: str, template: str) -> str:
    """Merge the template's section into an entry file; never replaces a project's own."""
    if _section_bounds(text):
        return text
    section = reporting_contract_section(template)
    if not section:
        raise ValueError("template carries no reporting contract section")
    anchor = _TRIPWIRES_HEADING.search(text)
    if anchor:
        return text[:anchor.start()] + section + "\n" + text[anchor.start():]
    return text.rstrip("\n") + "\n\n" + section


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-reporting", metavar="AGENTS_MD", type=pathlib.Path, required=True,
                        help="read-only: report whether this entry file carries the reporting contract")
    args = parser.parse_args(argv)
    path: pathlib.Path = args.check_reporting
    text = path.read_text(encoding="utf-8") if path.is_file() else None
    finding = audit_reporting_contract(text)
    print(f"{finding['check']} | {finding['status']} | {finding['fact']} | {finding['recommendation']} | {path}")
    return 0 if finding["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
