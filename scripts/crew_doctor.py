#!/usr/bin/env python3
"""Read-only, deterministic evidence helpers for the Crew Doctor skill.

This module never starts a model-mediated process. It reconciles configuration,
package manifests, captured/native runtime catalogues, and consumer trees. The
skill owns orchestration and prose judgment; this helper makes its factual
claims repeatable and fixture-testable.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import tomllib
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

try:
    from .check_skills import LOCAL_SLOT_VOCABULARY
    from .frontmatter import parse_simple_mapping, read_frontmatter
    from .role_contract import PI_PACKAGE_NAME
except ImportError:  # Direct script execution.
    from check_skills import LOCAL_SLOT_VOCABULARY
    from frontmatter import parse_simple_mapping, read_frontmatter
    from role_contract import PI_PACKAGE_NAME


CREW_REPO = "pixeloven/crew"
# Plugin identity is <plugin>@<marketplace>. The marketplace is the org so a
# single PixelOven marketplace can serve crew alongside its siblings.
# The catalogue lives in its own repo so one marketplace can serve every
# PixelOven plugin; this repo is only the plugin it points at.
MARKETPLACE_REPO = "pixeloven/marketplace"
MARKETPLACE_NAME = "pixeloven"
PLUGIN_NAME = "crew"
PLUGIN_ID = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"
FIRST_PI_ROLE_DISCOVERY_VERSION = (0, 35, 0, 1, ())
RECOMMENDED_LOCAL_VOCABULARY = ("litellm-access-map", "vault-ops")
PROFILE_TAXONOMY = ("portable", "platform", "personas")
EXPECTED_ROLE_NAMES = (
    "implementer",
    "investigator",
    "lead",
    "researcher",
    "responder",
    "reviewer",
    "triage",
)
# pi-subagents ships built-in agents under these bare names. A bare-named pi
# project agent replaces the built-in (project beats builtin); it never shadows
# Crew's `crew.<role>`.
PI_BUILTIN_AGENT_NAMES = ("researcher", "reviewer")
LOADED_RUNTIME_STATES = {"present", "working", "loaded-but-undiscoverable", "truncated"}
SEMVER = re.compile(
    r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?:(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
# Skills that left Crew for a pack, as skill -> pack. Historical migration
# metadata, not a dependency: Doctor and Onboarding use it only to point a
# consumer that still references a moved skill at its new home (MAINTAINERS.md).
MOVED_SKILLS = {
    "terraform-conventions": "infra-skills",
    "ansible-conventions": "infra-skills",
    "k8s-kustomize-conventions": "infra-skills",
    "k8s-workload-patterns": "infra-skills",
    "github-actions-conventions": "infra-skills",
}
# A moved skill named bare (pi's flat namespace) or as `<namespace>:<skill>`.
MOVED_SKILL_REFERENCE = re.compile(
    r"(?<![\w:.-])(?:(?P<namespace>[a-z0-9][a-z0-9-]*):)?"
    r"(?P<skill>" + "|".join(re.escape(name) for name in MOVED_SKILLS) + r")(?![\w-])"
)
# Pi has no marketplace: it installs this repo as a package and keys off its name.
PI_CREW_PACKAGE = re.compile(
    r"^(?:(?:git:)?github\.com/|github:)?" + re.escape(CREW_REPO) + r"(?:@[^@\s]+)?$"
)


@dataclass(frozen=True)
class ReadResult:
    value: Any
    state: str
    source: str
    detail: str = ""


def _read_json(path: pathlib.Path, default: Any) -> ReadResult:
    try:
        return ReadResult(json.loads(path.read_text(encoding="utf-8")), "present", str(path))
    except FileNotFoundError:
        return ReadResult(default, "absent", str(path))
    except json.JSONDecodeError as error:
        return ReadResult(default, "malformed", str(path), str(error))
    except UnicodeDecodeError as error:
        return ReadResult(default, "unreadable", str(path), str(error))
    except OSError as error:
        return ReadResult(default, "unreadable", str(path), str(error))


def _read_toml(path: pathlib.Path) -> ReadResult:
    try:
        return ReadResult(tomllib.loads(path.read_text(encoding="utf-8")), "present", str(path))
    except FileNotFoundError:
        return ReadResult({}, "absent", str(path))
    except tomllib.TOMLDecodeError as error:
        return ReadResult({}, "malformed", str(path), str(error))
    except UnicodeDecodeError as error:
        return ReadResult({}, "unreadable", str(path), str(error))
    except OSError as error:
        return ReadResult({}, "unreadable", str(path), str(error))


def _manifest_version(root: pathlib.Path) -> ReadResult:
    read = _read_json(root / ".claude-plugin/plugin.json", {})
    version = None
    if read.state == "present":
        if not isinstance(read.value, dict):
            return ReadResult(None, "malformed", read.source, "manifest must be a mapping")
        if read.value.get("name") != PLUGIN_NAME:
            return ReadResult(
                None,
                "malformed",
                read.source,
                "manifest name must identify Crew",
            )
        version = read.value.get("version")
        if not isinstance(version, str) or not SEMVER.fullmatch(version):
            return ReadResult(
                None,
                "malformed",
                read.source,
                "manifest version must be a valid SemVer string",
            )
        if read.value.get("skills") != "./skills":
            return ReadResult(
                None,
                "malformed",
                read.source,
                "manifest skills must be the normalized relative path ./skills",
            )
        skills = root / "skills"
        if not skills.is_dir():
            return ReadResult(
                None,
                "malformed",
                str(skills),
                "required skills directory is missing",
            )
    return ReadResult(
        version,
        read.state,
        read.source,
        read.detail,
    )


def _semver(value: Any, *, allow_v: bool = False) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = value
    if allow_v and candidate.startswith("v"):
        candidate = candidate[1:]
    return candidate if SEMVER.fullmatch(candidate) else None


def _lexically_within(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.absolute().relative_to(root.absolute())
        return True
    except ValueError:
        return False


def _pi_package_version(value: str) -> str | None:
    _, separator, ref = value.rpartition("@")
    if not separator or not ref.startswith("v"):
        return None
    return _semver(ref[1:])


def _pi_package_ref(value: str) -> str | None:
    _, separator, ref = value.rpartition("@")
    return ref if separator else None


def _version_tuple(
    value: Any,
) -> tuple[int, int, int, int, tuple[tuple[int, int | str], ...]] | None:
    clean = _semver(value)
    if not clean:
        return None
    without_build = clean.split("+", 1)[0]
    core, separator, prerelease = without_build.partition("-")
    major, minor, patch = map(int, core.split("."))
    identifiers = tuple(
        (0, int(identifier)) if identifier.isdigit() else (1, identifier)
        for identifier in prerelease.split(".")
    )
    return (major, minor, patch, 0 if separator else 1, identifiers)


def _is_marketplace_source(value: Any) -> bool:
    if value == MARKETPLACE_REPO:
        return True
    return (
        isinstance(value, dict)
        and value.get("source") == "github"
        and value.get("repo") == MARKETPLACE_REPO
    )


def _is_codex_marketplace_git_source(source_type: Any, source: Any) -> bool:
    if source_type != "git" or not isinstance(source, str):
        return False
    normalized = source.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    for prefix in (
        "git+https://github.com/",
        "https://github.com/",
        "ssh://git@github.com/",
        "git@github.com:",
    ):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    return normalized == MARKETPLACE_REPO


def _evidence(kind: str, claim: str, source: str = "") -> dict[str, str]:
    return {"kind": kind, "claim": claim, "source": source}


def _base_harness() -> dict[str, Any]:
    return {
        "status": "MISSING",
        "installation": {"state": "unavailable", "source": ""},
        "enablement": {"state": "unavailable", "source": ""},
        "runtime": {"state": "not tested", "source": ""},
        "loaded_version": None,
        "loaded_version_source": "",
        "capabilities": {"state": "not tested", "source": ""},
        "capability_checks": [],
        "capability_declaration_reads": [],
        "capability_roots": [],
        "runtime_paths": [],
        "runtime_root_matches": [],
        "runtime_validation_failures": [],
        "configuration_reads": [],
        "manifest_reads": [],
        "catalogue_reads": [],
        "cache_reads": [],
        "inspection_paths": [],
        "package_roots": [],
        "resolved_package_roots": [],
        "findings": [],
    }


def _add_finding(result: dict[str, Any], claim: str, *sources: str) -> None:
    evidence = [
        {"claim": claim, "source": source}
        for source in dict.fromkeys(source for source in sources if source)
    ]
    result["findings"].append(
        {"claim": claim, "evidence": evidence or [{"claim": claim, "source": ""}]}
    )


def _validate_runtime_provenance(runtime: Any, source: str) -> None:
    if not isinstance(runtime, dict):
        return
    for source_field in ("source", "source_command", "source_path"):
        if source_field in runtime and (
            not isinstance(runtime[source_field], str)
            or not runtime[source_field].strip()
        ):
            raise ValueError(
                f"invalid runtime capture {source}: {source_field} must be a non-empty string"
            )


def _validate_runtime_capture(
    runtime: Any,
    source: str,
    *,
    expected_harness: str | None = None,
    require_schema: bool = False,
    require_harness: bool = False,
) -> dict[str, Any]:
    if not isinstance(runtime, dict):
        raise ValueError(f"invalid runtime capture {source}: document must be a mapping")
    if require_schema or "schema_version" in runtime:
        if type(runtime.get("schema_version")) is not int or runtime["schema_version"] != 1:
            raise ValueError(
                f"invalid runtime capture {source}: schema_version must be integer 1"
            )
    harness = runtime.get("harness")
    if require_harness or harness is not None:
        if not isinstance(harness, str) or harness not in {"claude", "codex", "pi"}:
            raise ValueError(
                f"invalid runtime capture {source}: harness must be claude, codex, or pi"
            )
        if expected_harness and harness != expected_harness:
            raise ValueError(
                f"invalid runtime capture {source}: harness must be {expected_harness}"
            )
    if "tested" in runtime and not isinstance(runtime["tested"], bool):
        raise ValueError(f"invalid runtime capture {source}: tested must be boolean")
    supported_states = {
        "present",
        "working",
        "unavailable",
        "loaded-but-undiscoverable",
        "truncated",
        "omitted",
        "not tested",
    }
    if "state" in runtime and (
        not isinstance(runtime["state"], str) or runtime["state"] not in supported_states
    ):
        raise ValueError(
            f"invalid runtime capture {source}: state must be a supported string"
        )
    tested = runtime.get("tested")
    state = runtime.get("state")
    if (
        tested is False
        and state not in {None, "not tested"}
        or tested is True
        and state == "not tested"
    ):
        raise ValueError(
            f"invalid runtime capture {source}: tested and state are inconsistent"
        )
    _validate_runtime_provenance(runtime, source)
    if "skills" in runtime:
        skills = runtime["skills"]
        if not isinstance(skills, list):
            raise ValueError(f"invalid runtime capture {source}: skills must be a sequence")
        for index, entry in enumerate(skills):
            if not isinstance(entry, dict):
                raise ValueError(
                    f"invalid runtime capture {source}: skills entry {index} must be a mapping"
                )
            if not isinstance(entry.get("name"), str) or not entry["name"].strip():
                raise ValueError(
                    f"invalid runtime capture {source}: skills entry {index} name must be a non-empty string"
                )
            for field in ("description", "path", "namespace", "source"):
                if field in entry and entry[field] is not None and not isinstance(entry[field], str):
                    raise ValueError(
                        f"invalid runtime capture {source}: skills entry {index} {field} must be a string"
                    )
    if "skill_roots" in runtime:
        skill_roots = runtime["skill_roots"]
        if not isinstance(skill_roots, list) or any(
            not isinstance(root, str) or not root.strip() for root in skill_roots
        ):
            raise ValueError(
                f"invalid runtime capture {source}: skill_roots must be a string sequence"
            )
    if not _runtime_capture_sources(runtime):
        raise ValueError(
            f"invalid runtime capture {source}: source_path, source_command, or source is required"
        )
    return runtime


def _validate_capability_evidence(evidence: Any) -> dict[str, list[dict[str, str]]]:
    if not isinstance(evidence, dict):
        raise ValueError("invalid capability evidence: collection must be a mapping")
    unsupported_harnesses = set(evidence) - {"claude", "codex", "pi"}
    if unsupported_harnesses:
        harness = sorted(str(item) for item in unsupported_harnesses)[0]
        raise ValueError(f"invalid capability evidence: unsupported harness {harness}")
    for harness, observations in evidence.items():
        if not isinstance(observations, list):
            raise ValueError(
                f"invalid capability evidence for {harness}: observations must be a sequence"
            )
        for index, observation in enumerate(observations):
            if not isinstance(observation, dict):
                raise ValueError(
                    f"invalid capability evidence for {harness}: observation {index} must be a mapping"
                )
            values = tuple(
                observation.get(field) for field in ("name", "kind", "state", "source")
            )
            if not all(isinstance(value, str) and value for value in values):
                raise ValueError(
                    f"invalid capability evidence for {harness}: observation {index} must be source-bearing"
                )
            kind = observation["kind"]
            state = observation["state"]
            if kind == "grant" and state != "present":
                raise ValueError("grant evidence can only establish present")
            if kind == "probe" and state not in {"working", "unavailable"}:
                raise ValueError("probe evidence must establish working or unavailable")
            if kind not in {"grant", "probe"}:
                raise ValueError(f"unsupported capability evidence kind: {kind}")
    return evidence


def _runtime_capture_sources(runtime: dict[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(
            source
            for source in (
                runtime.get("source_path"),
                runtime.get("source_command"),
                runtime.get("source"),
            )
            if isinstance(source, str) and source.strip()
        )
    )


def _runtime_capture_is_untested(runtime: dict[str, Any]) -> bool:
    return runtime.get("tested") is False or runtime.get("state") == "not tested"


def _record_runtime(
    result: dict[str, Any],
    runtime: dict[str, Any] | None,
    validated_roots: list[pathlib.Path],
    candidate_roots: list[pathlib.Path] | None = None,
    root_versions: dict[pathlib.Path, str | None] | None = None,
) -> None:
    """Record only evidence supplied by this harness's capture."""
    if runtime is None:
        return
    runtime_sources = _runtime_capture_sources(runtime)
    runtime_source = runtime_sources[0]
    captured_state = runtime.get("state")
    if _runtime_capture_is_untested(runtime):
        result["runtime"] = {
            "state": "not tested",
            "source": runtime_source,
            "sources": runtime_sources,
        }
        return
    if captured_state not in {
        None,
        "present",
        "working",
        "unavailable",
        "loaded-but-undiscoverable",
        "truncated",
        "omitted",
    }:
        raise ValueError(f"unsupported runtime state: {captured_state}")
    if captured_state in {"unavailable", "omitted"}:
        state = captured_state
    else:
        skills = runtime.get("skills")
        expected_names = {
            path.name
            for path in (pathlib.Path(__file__).resolve().parents[1] / "skills").iterdir()
            if path.is_dir()
        }
        crew_entries = (
            [
                entry
                for entry in skills
                if isinstance(entry, dict)
                and (
                    str(entry.get("name", "")).startswith("crew:")
                    or entry.get("namespace") == "crew"
                    or entry.get("source") in {"crew", "pixeloven/crew"}
                    or (
                        isinstance(entry.get("path"), str)
                        and pathlib.Path(entry["path"]).parent.name in expected_names
                        and any(
                            _path_within(pathlib.Path(entry["path"]), root)
                            for root in validated_roots
                        )
                    )
                )
            ]
            if isinstance(skills, list)
            else []
        )
        skill_roots = [
            pathlib.Path(path)
            for path in runtime.get("skill_roots", [])
            if isinstance(path, str)
        ]
        validated_skill_roots = [
            path
            for path in skill_roots
            for root in validated_roots
            if _path_within(path, root)
        ]
        crew_paths = [
            pathlib.Path(entry["path"])
            for entry in crew_entries
            if isinstance(entry.get("path"), str)
        ]
        crew_paths.extend(validated_skill_roots)
        crew_paths = list(dict.fromkeys(crew_paths))
        if not crew_entries and not validated_skill_roots:
            state = "omitted" if isinstance(skills, list) else "unavailable"
        elif captured_state in {"loaded-but-undiscoverable", "truncated"}:
            state = captured_state
        elif any(not entry.get("description") for entry in crew_entries):
            state = "loaded-but-undiscoverable"
        elif captured_state == "present" or not crew_entries:
            state = "present"
        else:
            state = "working"
    result["runtime"] = {
        "state": state,
        "source": runtime_source,
        "sources": runtime_sources,
    }
    if state in LOADED_RUNTIME_STATES:
        result["runtime_paths"] = [str(path) for path in crew_paths]
        resolution_roots = list(dict.fromkeys([*validated_roots, *(candidate_roots or [])]))
        matched_roots = [
            root
            for root in resolution_roots
            if any(_path_within(path, root) for path in crew_paths)
        ]
        result["runtime_root_matches"] = [str(root) for root in matched_roots]
        raw_version = runtime.get("version")
        captured_version = _semver(raw_version) if "version" in runtime else None
        if "version" in runtime and captured_version is None:
            claim = "captured Crew runtime version must be a pure SemVer string"
            result["runtime_validation_failures"].append(claim)
            _add_finding(result, claim, result["runtime"]["source"])
        if len(matched_roots) > 1:
            claim = "captured Crew runtime paths match multiple accepted roots"
            result["runtime_validation_failures"].append(claim)
            _add_finding(
                result,
                claim,
                result["runtime"]["source"],
                *(str(root) for root in matched_roots),
            )
        elif len(matched_roots) == 1:
            selected_root = matched_roots[0]
            expected_version = (root_versions or {}).get(selected_root)
            if expected_version is None and selected_root in (candidate_roots or []):
                claim = "loaded vendored Crew version is unknown because provenance is unverified"
                result["runtime_validation_failures"].append(claim)
                _add_finding(result, claim, result["runtime"]["source"], str(selected_root))
            elif captured_version and expected_version and captured_version != expected_version:
                claim = (
                    f"captured Crew runtime version {captured_version} differs from "
                    f"selected root version {expected_version}"
                )
                result["runtime_validation_failures"].append(claim)
                _add_finding(result, claim, result["runtime"]["source"], str(selected_root))
            elif captured_version:
                result["loaded_version"] = captured_version
                result["loaded_version_source"] = result["runtime"]["source"]
            elif expected_version and "version" not in runtime:
                result["loaded_version"] = expected_version
                result["loaded_version_source"] = "; ".join(
                    (
                        result["runtime"]["source"],
                        str(selected_root / ".claude-plugin/plugin.json"),
                    )
                )
        elif captured_version:
            result["loaded_version"] = captured_version
            result["loaded_version_source"] = result["runtime"]["source"]


def _degrade_for_runtime(result: dict[str, Any]) -> None:
    if result["runtime_validation_failures"]:
        result["status"] = "DEGRADED"
    state = result["runtime"]["state"]
    if state in {"unavailable", "loaded-but-undiscoverable", "truncated", "omitted"}:
        if result["status"] == "OK":
            result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"captured Crew runtime state is {state}",
            result["runtime"].get("source", ""),
        )


def _declared_capabilities(
    roots: list[pathlib.Path],
    resolve_flat_overlays: bool = False,
) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    declared: dict[str, list[str]] = {}
    failures: list[dict[str, str]] = []
    catalogues = [
        root if root.name == "skills" else root / "skills"
        for root in dict.fromkeys(roots)
    ]
    if resolve_flat_overlays:
        effective_skills: dict[str, pathlib.Path] = {}
        for catalogue in catalogues:
            for skill in sorted(catalogue.glob("*/SKILL.md")):
                effective_skills[skill.parent.name] = skill
        skills = sorted(effective_skills.values())
    else:
        skills = [
            skill
            for catalogue in catalogues
            for skill in sorted(catalogue.glob("*/SKILL.md"))
        ]
    for skill in skills:
        try:
            metadata, error = read_frontmatter(skill)
        except (UnicodeDecodeError, OSError) as read_error:
            failures.append(
                {
                    "state": "unreadable",
                    "source": str(skill),
                    "detail": str(read_error),
                }
            )
            continue
        if error or not metadata:
            failures.append(
                {
                    "state": "malformed",
                    "source": str(skill),
                    "detail": error or "empty frontmatter",
                }
            )
            continue
        requirements = metadata.get("requires", [])
        if isinstance(requirements, str) or not isinstance(requirements, list):
            failures.append(
                {
                    "state": "malformed",
                    "source": str(skill),
                    "detail": "requires must be a string sequence",
                }
            )
            continue
        if any(not isinstance(requirement, str) or not requirement for requirement in requirements):
            failures.append(
                {
                    "state": "malformed",
                    "source": str(skill),
                    "detail": "requires entries must be non-empty strings",
                }
            )
            continue
        for requirement in requirements:
            declared.setdefault(requirement, []).append(str(skill))
    unique_failures = list(
        {
            (failure["state"], failure["source"], failure["detail"]): failure
            for failure in failures
        }.values()
    )
    return declared, unique_failures


def _record_capabilities(
    result: dict[str, Any],
    harness: str,
    supplied: list[dict[str, str]],
    consumer_skill_root: pathlib.Path,
) -> None:
    resolved_package_roots = [
        pathlib.Path(root) for root in result["resolved_package_roots"]
    ]
    vendored_roots = [pathlib.Path(root) for root in result["capability_roots"]]
    declared, declaration_failures = _declared_capabilities(
        resolved_package_roots + vendored_roots + [consumer_skill_root],
        resolve_flat_overlays=harness == "pi",
    )
    distributed = pathlib.Path(__file__).resolve().parents[1] / "skills"
    foundation_skill_names, _ = _catalogue_skill_names(distributed)
    package_catalogues = [
        root if root.name == "skills" else root / "skills"
        for root in resolved_package_roots
    ]

    def package_declaration(source: str) -> bool:
        path = pathlib.Path(source)
        return any(_lexically_within(path, root) for root in package_catalogues) or any(
            _lexically_within(path, root) and path.parent.name in foundation_skill_names
            for root in vendored_roots
        )

    result["capability_declaration_reads"] = declaration_failures
    for failure in declaration_failures:
        result["status"] = "DEGRADED"
        claim = f"Capability declaration frontmatter is {failure['state']}"
        if failure["detail"]:
            claim = f"{claim}: {failure['detail']}"
        _add_finding(result, claim, failure["source"])

    observations: dict[str, dict[str, list[dict[str, str]]]] = {}
    for observation in supplied:
        name = observation["name"]
        kind = observation["kind"]
        state = observation["state"]
        source = observation["source"]
        normalized_observation = {
            "name": name,
            "kind": kind,
            "state": state,
            "source": source,
        }
        by_kind = observations.setdefault(name, {}).setdefault(kind, [])
        if normalized_observation not in by_kind:
            by_kind.append(normalized_observation)

    checks: list[dict[str, Any]] = []
    for name, declaration_sources in sorted(declared.items()):
        capability_observations = observations.get(name, {})
        probes = sorted(
            capability_observations.get("probe", []),
            key=lambda item: (item["state"], item["source"]),
        )
        grants = sorted(
            capability_observations.get("grant", []),
            key=lambda item: item["source"],
        )
        if any(probe["state"] == "unavailable" for probe in probes):
            state = "unavailable"
        elif probes:
            state = "working"
        elif grants:
            state = "present"
        else:
            state = "not tested"
        observation_evidence = [
            {
                "claim": f"{harness} capability {name} is declared",
                "source": source,
            }
            for source in dict.fromkeys(declaration_sources)
        ]
        for grant in grants:
            observation_evidence.append(
                {
                    "claim": f"{harness} capability {name} grant is present",
                    "source": grant["source"],
                }
            )
        for probe in probes:
            observation_evidence.append(
                {
                    "claim": f"{harness} capability {name} probe is {probe['state']}",
                    "source": probe["source"],
                }
            )
        checks.append(
            {
                "harness": harness,
                "name": name,
                "state": state,
                "ownership": (
                    "project"
                    if any(
                        not package_declaration(source)
                        and _lexically_within(pathlib.Path(source), consumer_skill_root)
                        for source in declaration_sources
                    )
                    else "package"
                ),
                "evidence": observation_evidence,
            }
        )
    result["capability_checks"] = checks
    states = {check["state"] for check in checks}
    if "unavailable" in states:
        aggregate = "unavailable"
    elif not checks or "not tested" in states:
        aggregate = "not tested"
    elif states == {"working"}:
        aggregate = "working"
    else:
        aggregate = "present"
    sources = [item["source"] for check in checks for item in check["evidence"]]
    result["capabilities"] = {
        "state": aggregate,
        "source": "; ".join(dict.fromkeys(sources)),
    }
    if aggregate == "unavailable" and result["status"] != "MISSING":
        result["status"] = "DEGRADED"


def _record_config_read(result: dict[str, Any], label: str, read: ReadResult) -> Any:
    result["configuration_reads"].append(
        {
            "label": label,
            "state": read.state,
            "source": read.source,
            "detail": read.detail,
        }
    )
    return read.value


def _mark_config_malformed(result: dict[str, Any], source: pathlib.Path, detail: str) -> None:
    for read in result["configuration_reads"]:
        if read["source"] != str(source):
            continue
        if read["state"] == "present":
            read["state"] = "malformed"
            read["detail"] = detail
        elif read["state"] == "malformed" and detail not in read["detail"]:
            read["detail"] = f"{read['detail']}; {detail}"
        return


def _record_manifest_read(result: dict[str, Any], read: ReadResult) -> str | None:
    if not any(item["source"] == read.source for item in result["manifest_reads"]):
        result["manifest_reads"].append(
            {
                "label": "Crew plugin manifest",
                "state": read.state,
                "source": read.source,
                "detail": read.detail,
            }
        )
    return read.value


def _degrade_for_read_failures(result: dict[str, Any]) -> None:
    for read in (
        result["configuration_reads"]
        + result["manifest_reads"]
        + result["catalogue_reads"]
        + result["cache_reads"]
    ):
        if read["state"] not in {"malformed", "unreadable"} and not (
            read["state"] == "unavailable"
            and read in result["catalogue_reads"]
        ):
            continue
        result["status"] = "DEGRADED"
        claim = f"{read['label']} is {read['state']}"
        if read["detail"]:
            claim = f"{claim}: {read['detail']}"
        _add_finding(result, claim, read["source"])


def _has_config_read_failure(result: dict[str, Any], label_prefix: str = "") -> bool:
    return any(
        read["state"] in {"malformed", "unreadable"}
        and read["label"].startswith(label_prefix)
        for read in result["configuration_reads"]
    )


def _inspect_pi(project: pathlib.Path, home: pathlib.Path, runtime: dict[str, Any] | None) -> dict[str, Any]:
    result = _base_harness()
    settings_paths = [project / ".pi/settings.json", home / ".pi/settings.json"]
    settings_paths.extend(sorted((home / ".pi").glob("*/settings.json")))
    result["inspection_paths"] = [
        *(str(path) for path in dict.fromkeys(settings_paths)),
        str(home / ".pi"),
    ]
    registrations: list[dict[str, str | None]] = []
    for settings_path in dict.fromkeys(settings_paths):
        settings = _record_config_read(result, "Pi settings configuration", _read_json(settings_path, {}))
        if not isinstance(settings, dict):
            _mark_config_malformed(result, settings_path, "settings must be a mapping")
            settings = {}
        packages = settings.get("packages", [])
        if not isinstance(packages, list):
            _mark_config_malformed(result, settings_path, "packages must be a string sequence")
            packages = []
        for item in packages:
            if not isinstance(item, str):
                _mark_config_malformed(result, settings_path, "packages entries must be strings")
                continue
            if PI_CREW_PACKAGE.fullmatch(item):
                registrations.append(
                    {
                        "settings": str(settings_path),
                        "package": item,
                        "ref": _pi_package_ref(item),
                        "version": _pi_package_version(item),
                    }
                )
    result["registrations"] = registrations
    checkouts = sorted((home / ".pi").glob("*/git/github.com/pixeloven/crew"))
    resolved = []
    for checkout in checkouts:
        version = _record_manifest_read(result, _manifest_version(checkout))
        if version:
            resolved.append({"root": str(checkout), "version": version})
    _record_runtime(
        result,
        runtime,
        [pathlib.Path(item["root"]) for item in resolved],
        root_versions={pathlib.Path(item["root"]): item["version"] for item in resolved},
    )
    result["resolved_installations"] = resolved
    primary = next(
        (item for item in registrations if item["settings"] == str(project / ".pi/settings.json")),
        registrations[0] if registrations else None,
    )
    runtime_root_matches = set(result["runtime_root_matches"])
    runtime_matches = [item for item in resolved if item["root"] in runtime_root_matches]
    selected = runtime_matches[0] if len(runtime_matches) == 1 else None
    if selected is None and not result["runtime_paths"] and primary and primary["version"]:
        configured_matches = [
            item for item in resolved if item["version"] == primary["version"]
        ]
        selected = configured_matches[0] if len(configured_matches) == 1 else None
    if selected is None and not result["runtime_paths"] and len(resolved) == 1:
        selected = resolved[0]
    result["resolved_version"] = selected["version"] if selected else None
    result["resolved_version_source"] = (
        str(pathlib.Path(selected["root"]) / ".claude-plugin/plugin.json") if selected else ""
    )
    result["stale_resolved_installations"] = [item for item in resolved if item != selected]
    result["package_roots"] = (
        [selected["root"]] if selected else [item["root"] for item in resolved]
    )
    result["resolved_package_roots"] = [selected["root"]] if selected else []
    if resolved:
        source = selected["root"] if selected else "; ".join(item["root"] for item in resolved)
        result["installation"] = {"state": "present", "source": source}

    if primary:
        result["enablement"] = {"state": "present", "source": str(primary["settings"])}
    result["configured_ref"] = primary["ref"] if primary else None
    result["configured_version"] = primary["version"] if primary else None

    if resolved and not registrations:
        result["status"] = "DEGRADED"
        if not _has_config_read_failure(result, "Pi settings"):
            _add_finding(
                result,
                "Crew is installed for Pi but not enabled in an inspected settings scope",
                str(resolved[0]["root"]),
                *(str(path) for path in settings_paths),
            )
    if len(resolved) > 1:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"Pi has {len(resolved)} Crew checkouts; non-selected roots are stale or duplicate",
            *(item["root"] for item in resolved),
        )
    if not registrations:
        _degrade_for_runtime(result)
        return result

    non_release_pins = [item for item in registrations if item["version"] is None]
    if non_release_pins:
        result["status"] = "DEGRADED"
        displayed_ref = non_release_pins[0]["ref"] or "unpinned"
        _add_finding(
            result,
            f"configured Pi package ref {displayed_ref} is not a published v-prefixed SemVer tag",
            *(str(item["settings"]) for item in non_release_pins),
        )
    stale_pins = [
        item for item in registrations
        if _version_tuple(item["version"]) and _version_tuple(item["version"]) < FIRST_PI_ROLE_DISCOVERY_VERSION
    ]
    if stale_pins:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"configured pin v{stale_pins[0]['version']} predates v0.35.0; "
            "the Pi role fleet is silently invisible below v0.35.0",
            str(stale_pins[0]["settings"]),
        )
    if result["resolved_version"]:
        if result["status"] != "DEGRADED":
            result["status"] = "OK"
    else:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            "package is configured but its resolved checkout manifest was unavailable",
            str(primary["settings"]),
        )
    if len(registrations) > 1:
        result["status"] = "DEGRADED"
        claim = f"Crew is registered in {len(registrations)} Pi settings scopes"
        _add_finding(result, claim, *(str(item["settings"]) for item in registrations))
    if (
        result.get("configured_version")
        and result.get("resolved_version")
        and result["configured_version"] != result["resolved_version"]
    ):
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"configured Pi version {result['configured_version']} differs from resolved {result['resolved_version']}",
            str(primary["settings"]),
            str(selected["root"]),
        )
    _degrade_for_runtime(result)
    return result


def _inspect_claude(project: pathlib.Path, home: pathlib.Path, runtime: dict[str, Any] | None) -> dict[str, Any]:
    result = _base_harness()
    registry_path = home / ".claude/plugins/known_marketplaces.json"
    installed_path = home / ".claude/plugins/installed_plugins.json"
    settings_paths = (
        ("local", project / ".claude/settings.local.json"),
        ("project", project / ".claude/settings.json"),
        ("user", home / ".claude/settings.json"),
    )
    result["inspection_paths"] = [
        *(str(path) for _, path in settings_paths),
        str(registry_path),
        str(installed_path),
    ]
    settings_records: list[dict[str, Any]] = []
    enabled_records: list[dict[str, Any]] = []
    marketplace_records: list[dict[str, Any]] = []
    for scope, settings_path in settings_paths:
        settings = _record_config_read(
            result,
            f"Claude {scope} settings configuration",
            _read_json(settings_path, {}),
        )
        if not isinstance(settings, dict):
            _mark_config_malformed(result, settings_path, "settings must be a mapping")
            settings = {}
        enabled = settings.get("enabledPlugins", {})
        marketplaces = settings.get("extraKnownMarketplaces", {})
        if not isinstance(enabled, dict):
            _mark_config_malformed(result, settings_path, "enabledPlugins must be a mapping")
            enabled = {}
        if not isinstance(marketplaces, dict):
            _mark_config_malformed(
                result,
                settings_path,
                "extraKnownMarketplaces must be a mapping",
            )
            marketplaces = {}
        crew_marketplace = marketplaces.get(MARKETPLACE_NAME)
        if MARKETPLACE_NAME in marketplaces:
            source = (
                crew_marketplace.get("source")
                if isinstance(crew_marketplace, dict)
                else None
            )
            source_valid = isinstance(crew_marketplace, dict) and _is_marketplace_source(
                source
            )
            marketplace_records.append(
                {"scope": scope, "path": str(settings_path), "valid": source_valid}
            )
            if not source_valid:
                _mark_config_malformed(
                    result,
                    settings_path,
                    f"extraKnownMarketplaces.{MARKETPLACE_NAME} source must identify {MARKETPLACE_REPO}",
                )
        if MARKETPLACE_NAME in marketplaces or PLUGIN_ID in enabled:
            settings_records.append({"scope": scope, "path": str(settings_path)})
        if PLUGIN_ID in enabled:
            enabled_value = enabled[PLUGIN_ID]
            if not isinstance(enabled_value, bool):
                _mark_config_malformed(
                    result,
                    settings_path,
                    f"enabledPlugins.{PLUGIN_ID} must be boolean",
                )
            else:
                enabled_records.append(
                    {"scope": scope, "path": str(settings_path), "enabled": enabled_value}
                )
    result["settings_records"] = settings_records
    result["enabled_scopes"] = enabled_records
    result["marketplace_scopes"] = marketplace_records
    registry = _record_config_read(
        result,
        "Claude marketplace registry configuration",
        _read_json(registry_path, {}),
    )
    if not isinstance(registry, dict):
        _mark_config_malformed(result, registry_path, "marketplace registry must be a mapping")
        registry = {}
    record = registry.get(MARKETPLACE_NAME, {})
    if not isinstance(record, dict):
        _mark_config_malformed(result, registry_path, f"{MARKETPLACE_NAME} marketplace record must be a mapping")
        record = {}
    registry_source_valid = False
    if record:
        registry_source_valid = _is_marketplace_source(record.get("source"))
        if not registry_source_valid:
            _mark_config_malformed(
                result,
                registry_path,
                f"{MARKETPLACE_NAME} marketplace source must identify {MARKETPLACE_REPO}",
            )
    effective_marketplace = marketplace_records[0] if marketplace_records else None
    if effective_marketplace:
        crew_identity_valid = effective_marketplace["valid"] and (
            registry_source_valid or not record
        )
    else:
        crew_identity_valid = registry_source_valid
    if enabled_records:
        selected_enablement = enabled_records[0]
        result["enablement"] = {
            "state": (
                "present"
                if selected_enablement["enabled"] and crew_identity_valid
                else "unavailable"
            ),
            "source": selected_enablement["path"],
        }
        result["enabled_scope"] = selected_enablement["scope"]
        result["enabled_value"] = selected_enablement["enabled"]
    # This registry is location metadata. Never synthesize a version from it.
    result["marketplace_registry_records"] = [
        {key: record[key] for key in ("source", "installLocation", "lastUpdated") if key in record}
    ] if record else []
    raw_location = record.get("installLocation")
    if raw_location is not None and (
        not isinstance(raw_location, str) or not raw_location.strip()
    ):
        _mark_config_malformed(
            result,
            registry_path,
            f"{MARKETPLACE_NAME} marketplace installLocation must be a non-empty string",
        )
        raw_location = None
    location = pathlib.Path(raw_location) if raw_location else pathlib.Path()
    result["served_version"] = (
        _record_manifest_read(result, _manifest_version(location))
        if crew_identity_valid and registry_source_valid and str(location) not in {"", "."}
        else None
    )
    result["served_version_source"] = (
        str(location / ".claude-plugin/plugin.json") if result["served_version"] else ""
    )
    if result["served_version"]:
        result["installation"] = {"state": "present", "source": str(location)}

    installed = _record_config_read(
        result,
        "Claude installed plugins configuration",
        _read_json(installed_path, {}),
    )
    if not isinstance(installed, dict):
        _mark_config_malformed(result, installed_path, "installed plugins must be a mapping")
        installed = {}
    plugins = installed.get("plugins", {})
    if not isinstance(plugins, dict):
        _mark_config_malformed(result, installed_path, "plugins must be a mapping")
        plugins = {}
    registrations = plugins.get(PLUGIN_ID, [])
    if not isinstance(registrations, list):
        _mark_config_malformed(
            result,
            installed_path,
            f"{PLUGIN_ID} registrations must be a sequence",
        )
        registrations = []
    result["registrations"] = registrations
    applicable_registrations: list[dict[str, Any]] = []
    inapplicable_registrations: list[dict[str, Any]] = []
    installed_records: list[dict[str, Any]] = []
    by_root: dict[pathlib.Path, dict[str, Any]] = {}
    if registrations and not crew_identity_valid:
        _mark_config_malformed(
            result,
            installed_path,
            f"{PLUGIN_ID} registrations require a validated {MARKETPLACE_REPO} marketplace source",
        )
    for index, registration in enumerate(result["registrations"]):
        if not isinstance(registration, dict):
            _mark_config_malformed(
                result,
                installed_path,
                f"{PLUGIN_ID} registration {index} must be a mapping",
            )
            continue
        install_path = registration.get("installPath")
        if not isinstance(install_path, str) or not install_path.strip():
            _mark_config_malformed(
                result,
                installed_path,
                f"{PLUGIN_ID} registration {index} installPath must be a non-empty string",
            )
            continue
        valid = True
        scope = registration.get("scope")
        if scope not in {"local", "project", "user"}:
            _mark_config_malformed(
                result,
                installed_path,
                f"{PLUGIN_ID} registration {index} scope must be local, project, or user",
            )
            valid = False
        project_path = registration.get("projectPath")
        if project_path is not None and (
            not isinstance(project_path, str) or not project_path.strip()
        ):
            _mark_config_malformed(
                result,
                installed_path,
                f"{PLUGIN_ID} registration {index} projectPath must be a non-empty string",
            )
            valid = False
        if scope in {"local", "project"} and project_path is None:
            _mark_config_malformed(
                result,
                installed_path,
                f"{PLUGIN_ID} registration {index} projectPath is required for {scope} scope",
            )
            valid = False
        raw_registration_version = registration.get("version")
        if (
            not isinstance(raw_registration_version, str)
            or _semver(raw_registration_version) is None
        ):
            _mark_config_malformed(
                result,
                installed_path,
                f"{PLUGIN_ID} registration {index} version must be a SemVer string",
            )
            valid = False
        if not valid or not crew_identity_valid:
            continue
        applicable = scope == "user" or (
            pathlib.Path(project_path).resolve(strict=False)
            == project.resolve(strict=False)
        )
        if not applicable:
            inapplicable_registrations.append(
                {"registration": registration, "source": str(installed_path)}
            )
            continue
        applicable_registrations.append(registration)
        root = pathlib.Path(install_path)
        manifest_version = _record_manifest_read(result, _manifest_version(root))
        if not manifest_version:
            continue
        manifest_source = str(root / ".claude-plugin/plugin.json")
        record = by_root.setdefault(
            root,
            {
                "root": str(root),
                "version": manifest_version,
                "source": manifest_source,
                "registration_versions": [],
            },
        )
        if raw_registration_version:
            registration_version = _semver(raw_registration_version)
            record["registration_versions"].append(registration_version)
            if registration_version != manifest_version:
                result["status"] = "DEGRADED"
                _add_finding(
                    result,
                    f"Claude registration version {registration_version} differs from installed manifest "
                    f"{manifest_version} at {root}",
                    str(installed_path),
                    manifest_source,
                )
    installed_records.extend(sorted(by_root.values(), key=lambda item: item["root"]))
    for installed_record in installed_records:
        installed_record["registration_versions"] = sorted(
            set(installed_record["registration_versions"])
        )
    result["installed_versions"] = installed_records
    result["inapplicable_registrations"] = inapplicable_registrations
    validated_roots = [pathlib.Path(record["root"]) for record in installed_records]
    if result["served_version"]:
        validated_roots.append(location)
    root_versions = {
        pathlib.Path(record["root"]): record["version"]
        for record in installed_records
    }
    if result["served_version"]:
        root_versions[location] = result["served_version"]
    _record_runtime(result, runtime, validated_roots, root_versions=root_versions)
    runtime_root_matches = set(result["runtime_root_matches"])
    runtime_matches = [
        record
        for record in installed_records
        if record["root"] in runtime_root_matches
    ]
    selected_installed = runtime_matches[0] if len(runtime_matches) == 1 else None
    if selected_installed is None and not result["runtime_paths"] and result["served_version"]:
        marketplace_matches = [
            record
            for record in installed_records
            if pathlib.Path(record["root"]).resolve(strict=False)
            == location.resolve(strict=False)
        ]
        if len(marketplace_matches) == 1:
            selected_installed = marketplace_matches[0]
    if selected_installed is None and not result["runtime_paths"]:
        for scope in ("local", "project", "user"):
            scoped_roots = {
                pathlib.Path(registration["installPath"]).resolve(strict=False)
                for registration in applicable_registrations
                if registration["scope"] == scope
                and (
                    scope == "user"
                    or pathlib.Path(registration["projectPath"]).resolve(strict=False)
                    == project.resolve(strict=False)
                )
                and pathlib.Path(registration["installPath"]) in by_root
            }
            if scoped_roots:
                if len(scoped_roots) == 1:
                    selected_root = next(iter(scoped_roots))
                    selected_installed = next(
                        record
                        for record in installed_records
                        if pathlib.Path(record["root"]).resolve(strict=False)
                        == selected_root
                    )
                break
    result["installed_version"] = selected_installed["version"] if selected_installed else None
    result["installed_version_source"] = selected_installed["source"] if selected_installed else ""
    if installed_records:
        installation_sources = (
            [selected_installed["root"]]
            if selected_installed
            else [record["root"] for record in installed_records]
        )
        result["installation"] = {
            "state": "present",
            "source": "; ".join(installation_sources),
        }
    result["package_roots"] = [record["root"] for record in installed_records]
    if result.get("served_version") and location not in by_root:
        result["package_roots"].append(str(location))
    if len(runtime_root_matches) == 1:
        result["resolved_package_roots"] = list(runtime_root_matches)
    elif selected_installed:
        result["resolved_package_roots"] = [selected_installed["root"]]
    elif not result["runtime_paths"] and result["served_version"] and len(validated_roots) == 1:
        result["resolved_package_roots"] = [str(location)]

    if len(marketplace_records) > 1:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"Crew marketplace is declared in multiple Claude settings scopes; "
            f"{marketplace_records[0]['scope']} precedence selected",
            *(record["path"] for record in marketplace_records),
        )
    if result["installation"]["state"] != "present":
        _degrade_for_runtime(result)
        return result
    result["status"] = (
        "OK"
        if result["enablement"]["state"] == "present" and result["status"] != "DEGRADED"
        else "DEGRADED"
    )
    if len(enabled_records) > 1:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"Crew enablement is declared in multiple Claude settings scopes; "
            f"{enabled_records[0]['scope']} precedence selected",
            *(record["path"] for record in enabled_records),
        )
    if (
        result["enablement"]["state"] != "present"
        and not _has_config_read_failure(result, "Claude local settings")
        and not _has_config_read_failure(result, "Claude project settings")
        and not _has_config_read_failure(result, "Claude user settings")
    ):
        _add_finding(
            result,
            "Crew is installed for Claude but not enabled in an inspected scope",
            result["installation"].get("source", ""),
            *(record["path"] for record in settings_records),
        )
    if len(applicable_registrations) > 1:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"installed_plugins.json contains {len(applicable_registrations)} Crew scope registrations",
            str(installed_path),
        )
    if len(installed_records) > 1:
        result["status"] = "DEGRADED"
        selection = selected_installed["root"] if selected_installed else "ambiguous"
        _add_finding(
            result,
            f"Claude has {len(installed_records)} validated installed roots; selection is {selection}",
            str(installed_path),
            *(record["source"] for record in installed_records),
        )
    registration_versions = {
        _semver(registration.get("version"))
        for registration in applicable_registrations
        if registration.get("version")
    }
    manifest_versions = {record["version"] for record in installed_records}
    compared_versions = registration_versions | manifest_versions | {
        value for value in (result.get("served_version"), result.get("loaded_version")) if value
    }
    if len(compared_versions) > 1:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"Claude served/installed/loaded versions disagree: {', '.join(sorted(compared_versions))}",
            str(installed_path),
            *(record["source"] for record in installed_records),
            str(location) if result.get("served_version") else "",
            result["runtime"].get("source", "") if result.get("loaded_version") else "",
        )
    _degrade_for_runtime(result)
    return result


def _catalogue_skill_names(
    catalogue: pathlib.Path,
) -> tuple[set[str], list[dict[str, str]]]:
    names: set[str] = set()
    failures: list[dict[str, str]] = []
    if not catalogue.is_dir():
        return names, failures
    for skill in catalogue.glob("*/SKILL.md"):
        try:
            metadata, error = read_frontmatter(skill)
        except (OSError, UnicodeDecodeError) as exception:
            failures.append(
                {
                    "label": "Crew vendored catalogue skill",
                    "state": "unreadable",
                    "source": str(skill),
                    "detail": str(exception),
                }
            )
            continue
        if error or not isinstance(metadata, dict):
            failures.append(
                {
                    "label": "Crew vendored catalogue skill",
                    "state": "malformed",
                    "source": str(skill),
                    "detail": error or "frontmatter must be a mapping",
                }
            )
            continue
        if metadata.get("name") != skill.parent.name:
            failures.append(
                {
                    "label": "Crew vendored catalogue skill",
                    "state": "malformed",
                    "source": str(skill),
                    "detail": f"name must be {skill.parent.name}",
                }
            )
            continue
        names.add(skill.parent.name)
    return names, failures


def _inspect_crew_catalogue(
    catalogue: pathlib.Path,
) -> tuple[bool, list[dict[str, str]]]:
    distributed = pathlib.Path(__file__).resolve().parents[1] / "skills"
    expected, _ = _catalogue_skill_names(distributed)
    if len(expected) < 10 or not catalogue.is_dir():
        return False, []
    names, failures = _catalogue_skill_names(catalogue)
    failures.extend(
        {
            "label": "Crew vendored catalogue skill",
            "state": "unavailable",
            "source": str(catalogue / name / "SKILL.md"),
            "detail": "expected catalogue entry is missing or invalid",
        }
        for name in sorted(expected - names)
    )
    return expected <= names, failures


def _runtime_paths(runtime: dict[str, Any] | None) -> list[pathlib.Path]:
    if not runtime:
        return []
    values = list(runtime.get("skill_roots", []))
    values.extend(
        entry.get("path")
        for entry in runtime.get("skills", [])
        if isinstance(entry, dict) and entry.get("path")
    )
    return [pathlib.Path(value) for value in values if isinstance(value, str)]


def _path_within(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _inspect_codex(project: pathlib.Path, home: pathlib.Path, runtime: dict[str, Any] | None) -> dict[str, Any]:
    result = _base_harness()
    config_path = home / ".codex/config.toml"
    cache_base = home / f".codex/plugins/cache/{MARKETPLACE_NAME}/{PLUGIN_NAME}"
    vendored_paths = (project / ".agents/skills", home / ".agents/skills")
    result["inspection_paths"] = [
        str(config_path),
        str(cache_base),
        *(str(path) for path in vendored_paths),
    ]
    config = _record_config_read(result, "Codex plugin configuration", _read_toml(config_path))
    if not isinstance(config, dict):
        _mark_config_malformed(result, config_path, "configuration must be a mapping")
        config = {}
    marketplaces = config.get("marketplaces", {})
    plugins = config.get("plugins", {})
    if not isinstance(marketplaces, dict):
        _mark_config_malformed(result, config_path, "marketplaces must be a mapping")
        marketplaces = {}
    if not isinstance(plugins, dict):
        _mark_config_malformed(result, config_path, "plugins must be a mapping")
        plugins = {}
    crew_market = marketplaces.get(MARKETPLACE_NAME, {})
    crew_plugin = plugins.get(PLUGIN_ID, {})
    if not isinstance(crew_market, dict):
        _mark_config_malformed(result, config_path, f"marketplaces.{MARKETPLACE_NAME} must be a mapping")
        crew_market = {}
    if not isinstance(crew_plugin, dict):
        _mark_config_malformed(result, config_path, f'plugins."{PLUGIN_ID}" must be a mapping')
        crew_plugin = {}
    raw_source = crew_market.get("source")
    raw_source_type = crew_market.get("source_type")
    crew_source_valid = _is_codex_marketplace_git_source(raw_source_type, raw_source)
    if crew_market and not crew_source_valid:
        _mark_config_malformed(
            result,
            config_path,
            f"marketplaces.{MARKETPLACE_NAME} must use a git source identifying {MARKETPLACE_REPO}",
        )
    raw_ref = crew_market.get("ref")
    if raw_ref is not None and (
        not isinstance(raw_ref, str) or _semver(raw_ref, allow_v=True) is None
    ):
        _mark_config_malformed(
            result,
            config_path,
            f"marketplaces.{MARKETPLACE_NAME}.ref must be a SemVer string",
        )
        raw_ref = None
    raw_enabled = crew_plugin.get("enabled")
    if raw_enabled is not None and not isinstance(raw_enabled, bool):
        _mark_config_malformed(result, config_path, f'plugins."{PLUGIN_ID}".enabled must be boolean')
        raw_enabled = None
    discovered_cache_roots = sorted(
        (path for path in cache_base.glob("*") if path.is_dir()),
        key=lambda path: _version_tuple(path.name) or (0, 0, 0, 0, ()),
    )
    cache_roots = discovered_cache_roots
    result["configured_version"] = (
        _semver(raw_ref, allow_v=True) if crew_source_valid else None
    )
    manifest_versions: dict[pathlib.Path, str | None] = {}
    directory_versions: dict[pathlib.Path, str | None] = {}
    for root in cache_roots:
        directory_version = _semver(root.name)
        directory_versions[root] = directory_version
        manifest_version = _record_manifest_read(result, _manifest_version(root))
        manifest_versions[root] = manifest_version
        if directory_version is None:
            result["cache_reads"].append(
                {
                    "label": "Codex plugin cache root",
                    "state": "malformed",
                    "source": str(root),
                    "detail": "cache directory name must be a SemVer string",
                }
            )
        elif manifest_version and manifest_version != directory_version:
            result["cache_reads"].append(
                {
                    "label": "Codex plugin cache root",
                    "state": "malformed",
                    "source": str(root / ".claude-plugin/plugin.json"),
                    "detail": (
                        f"cache directory version {directory_version} differs from "
                        f"manifest version {manifest_version}"
                    ),
                }
            )
    valid_cache_roots = [
        root
        for root in cache_roots
        if manifest_versions.get(root)
        and directory_versions.get(root) == manifest_versions[root]
        and (root / "skills").is_dir()
    ]
    vendored_catalogues: list[pathlib.Path] = []
    for catalogue in vendored_paths:
        complete, reads = _inspect_crew_catalogue(catalogue)
        result["catalogue_reads"].extend(reads)
        if complete:
            vendored_catalogues.append(catalogue)
    result["vendored_catalogues"] = [
        {"root": str(root), "capabilities": "present", "provenance": "unverified"}
        for root in vendored_catalogues
    ]
    result["capability_roots"] = [str(root) for root in vendored_catalogues]
    _record_runtime(
        result,
        runtime,
        valid_cache_roots,
        candidate_roots=vendored_catalogues,
        root_versions={root: manifest_versions[root] for root in valid_cache_roots},
    )
    runtime_root_matches = set(result["runtime_root_matches"])
    matched_cache_roots = [root for root in valid_cache_roots if str(root) in runtime_root_matches]
    resolved_root = matched_cache_roots[0] if len(matched_cache_roots) == 1 else None
    if resolved_root is None and not result["runtime_paths"] and result["configured_version"]:
        configured_roots = [
            root
            for root in valid_cache_roots
            if manifest_versions[root] == result["configured_version"]
        ]
        resolved_root = configured_roots[0] if len(configured_roots) == 1 else None
    if (
        resolved_root is None
        and not result["runtime_paths"]
        and crew_source_valid
        and not result["configured_version"]
        and len(valid_cache_roots) == 1
    ):
        resolved_root = valid_cache_roots[0]
    accepted_roots = valid_cache_roots
    result["cache_roots"] = [str(path) for path in cache_roots]
    result["skill_roots"] = [
        *(str(path / "skills") for path in valid_cache_roots),
    ]
    result["stale_cache_roots"] = [str(path) for path in valid_cache_roots if path != resolved_root]
    result["package_roots"] = [str(path) for path in accepted_roots]
    result["resolved_package_roots"] = [str(resolved_root)] if resolved_root else []
    if resolved_root:
        result["resolved_version"] = manifest_versions[resolved_root]
        result["resolved_version_source"] = str(resolved_root / ".claude-plugin/plugin.json")
    else:
        result["resolved_version"] = None
        result["resolved_version_source"] = ""
    if accepted_roots:
        result["installation"] = {
            "state": "present",
            "source": "; ".join(result["skill_roots"]),
        }
    if raw_enabled is True and crew_source_valid:
        result["enablement"] = {"state": "present", "source": str(config_path)}
    if runtime is not None and runtime.get("tested") is not False:
        result["runtime_skill_roots"] = list(result["runtime_paths"])

    if result["installation"]["state"] == "present":
        if result["enablement"]["state"] == "present":
            result["status"] = "OK"
        else:
            result["status"] = "DEGRADED"
            if not _has_config_read_failure(result, "Codex plugin"):
                _add_finding(
                    result,
                    "Crew is installed for Codex but not enabled in inspected config",
                    result["installation"].get("source", ""),
                    str(config_path),
                )
    if len(accepted_roots) > 1:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"Codex has {len(accepted_roots)} accepted Crew skill roots; "
            "plugin-cache versions are stale or duplicate",
            *result["skill_roots"],
        )
    if vendored_catalogues:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            "vendored capabilities are present but PixelOven Crew provenance is unverified",
            *(str(root) for root in vendored_catalogues),
        )
    if result.get("configured_version") and resolved_root is None:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"configured Codex version {result['configured_version']} has no matching resolved root",
            str(config_path),
            *(str(root) for root in valid_cache_roots),
        )
    if (
        result.get("configured_version")
        and result.get("resolved_version")
        and result["configured_version"] != result["resolved_version"]
    ):
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"configured Codex version {result['configured_version']} differs "
            f"from resolved {result['resolved_version']}",
            str(config_path),
            str(resolved_root),
        )
    _degrade_for_runtime(result)
    return result


def inspect_installations(
    project_root: pathlib.Path,
    home: pathlib.Path,
    runtime_fixtures: dict[str, dict[str, Any]] | None = None,
    capability_evidence: dict[str, list[dict[str, str]]] | None = None,
) -> dict[str, Any]:
    """Reconcile configured, installed, enabled, runtime, and grant state."""
    project_root = pathlib.Path(project_root)
    home = pathlib.Path(home)
    if runtime_fixtures is None:
        runtime_fixtures = {}
    if not isinstance(runtime_fixtures, dict):
        raise ValueError("invalid runtime captures: collection must be a mapping")
    unsupported_harnesses = set(runtime_fixtures) - {"claude", "codex", "pi"}
    if unsupported_harnesses:
        harness = sorted(str(item) for item in unsupported_harnesses)[0]
        raise ValueError(f"invalid runtime captures: unsupported harness {harness}")
    for harness, runtime in runtime_fixtures.items():
        if runtime is not None:
            _validate_runtime_capture(
                runtime,
                f"{harness} runtime capture",
                expected_harness=harness,
            )
    if capability_evidence is None:
        capability_evidence = {}
    capability_evidence = _validate_capability_evidence(capability_evidence)
    harnesses = {
        "pi": _inspect_pi(project_root, home, runtime_fixtures.get("pi")),
        "claude": _inspect_claude(project_root, home, runtime_fixtures.get("claude")),
        "codex": _inspect_codex(project_root, home, runtime_fixtures.get("codex")),
    }
    for harness, result in harnesses.items():
        _degrade_for_read_failures(result)
        consumer_skill_root = project_root / (
            ".claude/skills" if harness == "claude" else ".agents/skills"
        )
        _record_capabilities(
            result,
            harness,
            capability_evidence.get(harness, []),
            consumer_skill_root,
        )
    evidence: list[dict[str, str]] = []
    checks: list[dict[str, Any]] = []
    for harness, result in harnesses.items():
        inspected_sources = list(
            dict.fromkeys(
                [
                    *result["inspection_paths"],
                    *(read["source"] for read in result["configuration_reads"]),
                    *(read["source"] for read in result["manifest_reads"]),
                    *result.get("cache_roots", []),
                ]
            )
        )
        for dimension in ("installation", "enablement", "runtime", "capabilities"):
            observation = result[dimension]
            state = observation["state"]
            if state in {"present", "working"}:
                status = "OK"
            elif state == "not tested":
                status = "N/A"
            elif dimension == "installation":
                status = "MISSING"
            else:
                status = "DEGRADED"
            fact = f"{harness} {dimension} is {state}"
            untested = fact if state == "not tested" else ""
            recommendation = ""
            if status in {"MISSING", "DEGRADED"}:
                recommendation = f"Resolve or verify {harness} {dimension}"
            observation_sources = observation.get("sources") or [
                observation.get("source", "")
            ]
            sources = (
                [*observation_sources, *inspected_sources]
                if state in {"unavailable", "not tested"}
                else list(observation_sources)
            )
            sources = [source for source in dict.fromkeys(sources) if source]
            row_evidence = [
                {"claim": fact, "source": source}
                for source in sources
            ]
            evidence.extend(
                _evidence("untested" if untested else "observed", fact, source)
                for source in sources
            )
            checks.append(
                {
                    "check": f"{harness}.{dimension}",
                    "status": status,
                    "fact": fact,
                    "inference": "" if untested else f"evidence supports {state}",
                    "recommendation": recommendation,
                    "untested": untested,
                    "evidence": row_evidence,
                }
            )
        for index, finding in enumerate(result["findings"], start=1):
            checks.append(
                {
                    "check": f"{harness}.finding.{index}",
                    "status": "DEGRADED",
                    "fact": finding["claim"],
                    "inference": "the harness evidence does not satisfy the healthy contract",
                    "recommendation": f"Resolve {finding['claim']}",
                    "untested": "",
                    "evidence": deepcopy(finding["evidence"]),
                }
            )
    version_evidence: dict[str, tuple[str | None, str]] = {}
    for name, result in harnesses.items():
        accepted_installed_versions = {
            record["version"] for record in result.get("installed_versions", [])
        }
        if result.get("loaded_version"):
            selected_version = result["loaded_version"]
            selected_source = result.get("loaded_version_source", "")
        elif result.get("resolved_version"):
            selected_version = result["resolved_version"]
            selected_source = result.get("resolved_version_source", "")
        elif (
            name == "claude"
            and accepted_installed_versions
            and result.get("served_version")
            and (
                (
                    result.get("installed_version")
                    and result["served_version"] != result["installed_version"]
                    and not result.get("runtime_paths")
                )
                or (
                    not result.get("installed_version")
                    and (
                        result.get("runtime_paths")
                        or accepted_installed_versions != {result["served_version"]}
                    )
                )
            )
        ):
            selected_version = None
            selected_source = ""
        else:
            selected_version = result.get("installed_version") or result.get("served_version")
            selected_source = (
                result.get("installed_version_source", "")
                if result.get("installed_version")
                else result.get("served_version_source", "")
            )
        version_evidence[name] = (selected_version, selected_source)
    versions = {name: value for name, (value, _) in version_evidence.items()}
    observed_versions = {value for value in versions.values() if value}
    if len(observed_versions) > 1:
        fact = "cross-harness Crew version skew: " + ", ".join(
            f"{name}={value or 'unknown'}" for name, value in versions.items()
        )
        version_sources = [
            {
                "claim": f"{name} selected Crew version is {value}",
                "source": source,
            }
            for name, (value, source) in version_evidence.items()
            if value
        ]
        item = _evidence(
            "observed",
            fact,
            "; ".join(entry["source"] for entry in version_sources if entry["source"]),
        )
        evidence.append(item)
        checks.append(
            {
                "check": "cross-harness.version-skew",
                "status": "DEGRADED",
                "fact": fact,
                "inference": "the harnesses do not resolve one Crew version",
                "recommendation": "Align resolved Crew versions across harnesses",
                "untested": "",
                "evidence": version_sources,
            }
        )
    missing = [name for name, result in harnesses.items() if result["installation"]["state"] != "present"]
    degraded = [name for name, result in harnesses.items() if result["status"] == "DEGRADED"]
    if missing:
        top = f"Install or locate Crew for {missing[0]}, then rerun the free checks"
    elif degraded:
        top = f"Resolve the {degraded[0]} health findings, then rerun the free checks"
    else:
        top = "Healthy installation evidence; run only authorized runtime probes still marked untested"
    return {
        "harnesses": harnesses,
        "checks": checks,
        "evidence": evidence,
        "top_actions": [top],
        "inspection_context": {"project_root": str(project_root)},
    }


def load_runtime_fixture(path: pathlib.Path) -> dict[str, Any]:
    fixture_path = pathlib.Path(path)
    fixture = _read_json(fixture_path, {}).value
    _validate_runtime_provenance(fixture, str(fixture_path))
    if isinstance(fixture, dict):
        fixture["source_path"] = str(fixture_path)
    fixture = _validate_runtime_capture(
        fixture,
        str(fixture_path),
        require_schema=True,
        require_harness=True,
    )
    return fixture


def parse_codex_prompt_capture(path: pathlib.Path) -> dict[str, Any]:
    """Parse the free `codex debug prompt-input` JSON protocol into a fixture."""
    capture_path = pathlib.Path(path)
    payload = _read_json(capture_path, None).value
    if not isinstance(payload, list):
        raise ValueError(
            f"invalid Codex prompt capture {capture_path}: document must be a message sequence"
        )
    source_text = None
    for index, message in enumerate(payload):
        if not isinstance(message, dict):
            continue
        content = message.get("content", [])
        if not isinstance(content, list):
            raise ValueError(
                f"invalid Codex prompt capture {capture_path}: message {index} content must be a sequence"
            )
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and "<skills_instructions>" in text:
                source_text = text
                break
        if source_text is not None:
            break
    if source_text is None:
        raise ValueError("Codex prompt capture has no <skills_instructions> block")

    skills: list[dict[str, Any]] = []
    in_catalogue = False
    for line in source_text.splitlines():
        if line.strip() == "### Available skills":
            in_catalogue = True
            continue
        if line.strip() == "</skills_instructions>":
            break
        if not in_catalogue or not line.startswith("- "):
            continue
        name, separator, remainder = line[2:].partition(": ")
        if not separator:
            continue
        description, locator_separator, locator = remainder.rpartition(" (")
        if not locator_separator or not locator.endswith(")"):
            raise ValueError(f"unparseable Codex skill entry: {line}")
        locator = locator[:-1]
        path_value = locator.removeprefix("file: ") if locator.startswith("file: ") else None
        skills.append({"name": name, "description": description or None, "path": path_value, "locator": locator})

    return {
        "schema_version": 1,
        "harness": "codex",
        "source_command": 'codex debug prompt-input "hi"',
        "cost": "free",
        "skills": skills,
        "telemetry": {},
    }


def _runtime_name(entry: dict[str, Any], harness: str) -> str:
    if harness in {"claude", "codex"} and entry.get("namespace"):
        return f"{entry['namespace']}:{entry['name']}"
    return str(entry["name"])


def _expected_catalog(disk_entries: list[dict[str, Any]], harness: str) -> list[tuple[str, dict[str, Any]]]:
    expected: dict[str, dict[str, Any]] = {}
    ordered = disk_entries
    if harness == "pi":
        # Pi is flat; the project overlay wins over the package on collision.
        ordered = sorted(disk_entries, key=lambda item: item.get("source") == "project")
    for entry in ordered:
        expected[_runtime_name(entry, harness)] = entry
    return list(expected.items())


def _runtime_path_matches(disk: dict[str, Any], runtime: dict[str, Any]) -> bool:
    runtime_path = runtime.get("path")
    if not runtime_path:
        return not disk.get("path") and not disk.get("root")
    if disk.get("path"):
        return pathlib.Path(str(runtime_path)).resolve(strict=False) == pathlib.Path(
            str(disk["path"])
        ).resolve(strict=False)
    if disk.get("root"):
        return _path_within(pathlib.Path(str(runtime_path)), pathlib.Path(str(disk["root"])))
    return True


def _runtime_description_visible(runtime: dict[str, Any]) -> bool:
    description = runtime.get("description")
    return isinstance(description, str) and bool(description.strip())


def compare_runtime_catalog(
    disk_entries: list[dict[str, Any]],
    runtime_fixture: dict[str, Any],
) -> dict[str, Any]:
    """Compare one harness's disk and runtime catalogues in both directions."""
    runtime_fixture = _validate_runtime_capture(
        runtime_fixture,
        "runtime catalogue capture",
        require_harness=True,
    )
    harness = runtime_fixture.get("harness")
    expected = _expected_catalog(disk_entries, harness)
    capture_sources = _runtime_capture_sources(runtime_fixture)
    capture = {
        "source": capture_sources[0],
        "sources": capture_sources,
        "source_command": runtime_fixture.get("source_command"),
        "source_path": runtime_fixture.get("source_path"),
        "captured_at": runtime_fixture.get("captured_at"),
        "cost": runtime_fixture.get("cost", "unknown"),
    }
    if _runtime_capture_is_untested(runtime_fixture):
        entries = [
            {"runtime_name": name, "state": "not tested", "disk": entry}
            for name, entry in expected
        ]
        if not entries:
            entries.append(
                {
                    "runtime_name": "catalogue",
                    "state": "not tested",
                    "disk": None,
                    "runtime": None,
                    "scope": "harness",
                }
            )
        return {
            "harness": harness,
            "status": "N/A",
            "expected_count": len(expected),
            "visible_count": 0,
            "entries": entries,
            "capture": capture,
        }

    visible = [
        entry
        for entry in runtime_fixture.get("skills", [])
        if isinstance(entry, dict) and entry.get("name")
    ]
    visible_names = [_runtime_name(entry, harness) for entry in visible]
    unused = set(range(len(visible)))
    rows: list[dict[str, Any]] = []
    absent_state = runtime_fixture.get("state", "omitted")
    if absent_state not in {"omitted", "unavailable", "truncated", "loaded-but-undiscoverable"}:
        absent_state = "omitted"
    for name, disk in expected:
        candidates = [
            index for index in unused if visible_names[index] == name
        ]
        matching_paths = [index for index in candidates if _runtime_path_matches(disk, visible[index])]
        if matching_paths:
            index = next(
                (
                    candidate
                    for candidate in matching_paths
                    if visible[candidate].get("description") == disk.get("description")
                ),
                matching_paths[0],
            )
            unused.remove(index)
            runtime = visible[index]
        else:
            runtime = visible[candidates[0]] if candidates else None

        if runtime is None:
            state = absent_state
        elif not matching_paths:
            state = "unavailable"
        elif not _runtime_description_visible(runtime):
            state = "loaded-but-undiscoverable"
        elif runtime.get("description") == disk.get("description"):
            state = "working"
        elif str(disk.get("description", "")).startswith(str(runtime.get("description", ""))):
            state = "truncated"
        else:
            state = "unavailable"
        rows.append({"runtime_name": name, "state": state, "disk": disk, "runtime": runtime})
    for index in sorted(unused):
        runtime = visible[index]
        rows.append(
            {
                "runtime_name": visible_names[index],
                "state": (
                    "present"
                    if _runtime_description_visible(runtime)
                    else "loaded-but-undiscoverable"
                ),
                "disk": None,
                "runtime": runtime,
            }
        )

    degraded = {"omitted", "truncated", "loaded-but-undiscoverable", "unavailable", "present"}
    return {
        "harness": harness,
        "status": "DEGRADED" if any(row["state"] in degraded for row in rows) else "OK",
        "expected_count": len(expected),
        "visible_count": len(visible),
        "entries": rows,
        "capture": capture,
    }


def declared_local_slots(package_root: pathlib.Path) -> dict[str, Any]:
    declared: set[str] = set()
    sources: list[str] = []
    reads: list[dict[str, str]] = []
    skills_root = pathlib.Path(package_root) / "skills"
    inspected_paths = sorted(skills_root.glob("*/SKILL.md"))
    for path in inspected_paths:
        try:
            frontmatter, error = read_frontmatter(path)
        except (OSError, UnicodeDecodeError) as exception:
            reads.append(
                {
                    "state": "unreadable",
                    "source": str(path),
                    "detail": str(exception),
                }
            )
            continue
        if error or not frontmatter:
            reads.append(
                {
                    "state": "malformed",
                    "source": str(path),
                    "detail": error or "frontmatter must be a mapping",
                }
            )
            continue
        if "expects-local" not in frontmatter:
            continue
        raw_slots = frontmatter["expects-local"]
        if not isinstance(raw_slots, list):
            reads.append(
                {
                    "state": "malformed",
                    "source": str(path),
                    "detail": "expects-local must be a list of strings",
                }
            )
            continue
        if any(not isinstance(slot, str) or not slot.strip() for slot in raw_slots):
            reads.append(
                {
                    "state": "malformed",
                    "source": str(path),
                    "detail": "expects-local entries must be non-empty strings",
                }
            )
            continue
        slots = [slot.strip() for slot in raw_slots]
        invalid_slots = sorted(set(slots) - LOCAL_SLOT_VOCABULARY)
        if invalid_slots:
            reads.append(
                {
                    "state": "malformed",
                    "source": str(path),
                    "detail": (
                        "expects-local entries must use the accepted taxonomy: "
                        + ", ".join(sorted(LOCAL_SLOT_VOCABULARY))
                    ),
                }
            )
            continue
        if slots:
            declared.update(slots)
            sources.append(str(path))
    return {
        "declared": sorted(declared),
        "recommended_vocabulary": list(RECOMMENDED_LOCAL_VOCABULARY),
        "sources": sources,
        "inspection_sources": [str(skills_root), *(str(path) for path in inspected_paths)],
        "reads": reads,
    }


def _skills_catalogue(root: pathlib.Path) -> pathlib.Path:
    root = pathlib.Path(root)
    return root if root.name == "skills" else root / "skills"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _read_skill_catalogue(
    root: pathlib.Path,
) -> tuple[list[tuple[pathlib.Path, dict[str, Any]]], list[dict[str, str]]]:
    skills: list[tuple[pathlib.Path, dict[str, Any]]] = []
    reads: list[dict[str, str]] = []
    for path in sorted(_skills_catalogue(root).glob("*/SKILL.md")):
        try:
            metadata, error = read_frontmatter(path)
        except (OSError, UnicodeDecodeError) as exception:
            reads.append({"state": "unreadable", "source": str(path), "detail": str(exception)})
            continue
        if error or not isinstance(metadata, dict):
            reads.append(
                {
                    "state": "malformed",
                    "source": str(path),
                    "detail": error or "frontmatter must be a mapping",
                }
            )
            continue
        skills.append((path, metadata))
    return skills, reads


def _package_label(root: pathlib.Path) -> str:
    for manifest in (".claude-plugin/plugin.json", "package.json"):
        read = _read_json(pathlib.Path(root) / manifest, {})
        if isinstance(read.value, dict) and isinstance(read.value.get("name"), str) and read.value["name"]:
            return read.value["name"]
    return pathlib.Path(root).name


# Always-on listing budgets are DATED evidence, never permanent limits
# (docs/MAINTAINERS.md). Claude Code is absent on purpose: it was not observed
# to cap the listing, though every description is still paid every session.
HARNESS_DESCRIPTION_BUDGETS = (
    {
        "harness": "codex",
        "budget_chars": 22_000,
        "measured": "2026-09-05",
        "evidence": "pixeloven/crew#72",
        "scope": "one ~22 KB skills-listing budget divided across every entry",
    },
)
CREW_REQUIREMENT = re.compile(r"^plugin:crew@>=(\S+)$")


def description_cost(package_root: pathlib.Path, label: str | None = None) -> dict[str, Any]:
    """Sum the always-on description characters one installed root contributes."""
    root = pathlib.Path(package_root)
    skills, reads = _read_skill_catalogue(root)
    rows = [
        {
            "name": path.parent.name,
            "chars": len(metadata["description"]) if isinstance(metadata.get("description"), str) else 0,
            "source": str(path),
        }
        for path, metadata in skills
    ]
    return {
        "label": label or _package_label(root),
        "root": str(root),
        "skills": rows,
        "total": sum(row["chars"] for row in rows),
        "reads": reads,
    }


def inspect_packs(candidate_roots: list[pathlib.Path], crew_root: pathlib.Path) -> list[dict[str, Any]]:
    """Identify packs among installed roots and verify their crew requirement.

    A root is a pack when a skill declares `plugin:crew@>=X` or `provides:`. The
    caller supplies the roots it already enumerated; this reads, never installs.
    """
    crew_root = pathlib.Path(crew_root)
    crew_version = _manifest_version(crew_root).value
    packs: list[dict[str, Any]] = []
    for root in dict.fromkeys(pathlib.Path(candidate) for candidate in candidate_roots):
        if _path_within(root, crew_root) and _path_within(crew_root, root):
            continue
        skills, reads = _read_skill_catalogue(root)
        minimums: set[str] = set()
        provides: dict[str, list[dict[str, str]]] = {}
        sources: list[str] = []
        for path, metadata in skills:
            declared = False
            for requirement in _string_list(metadata.get("requires")):
                match = CREW_REQUIREMENT.fullmatch(requirement)
                if match:
                    minimums.add(match.group(1))
                    declared = True
            for slot in _string_list(metadata.get("provides")):
                provides.setdefault(slot, []).append({"skill": path.parent.name, "source": str(path)})
                declared = True
            if declared:
                sources.append(str(path))
        if not minimums and not provides:
            continue
        current = _version_tuple(crew_version)
        if not minimums:
            state = "undeclared"
        elif current is None:
            state = "not tested"
        elif all(
            (minimum := _version_tuple(value)) is not None and minimum <= current
            for value in minimums
        ):
            state = "satisfied"
        else:
            state = "unsatisfied"
        packs.append(
            {
                "name": _package_label(root),
                "root": str(root),
                "requirements": sorted(f"plugin:crew@>={value}" for value in minimums),
                "crew_version": crew_version,
                "crew_source": str(crew_root / ".claude-plugin/plugin.json"),
                "state": state,
                "provides": provides,
                "sources": sources,
                "reads": reads,
            }
        )
    return packs


def slot_fills(
    declared: list[str],
    *,
    local_roots: list[pathlib.Path],
    packs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Report who fills each declared slot. A local overlay outranks a pack.

    A local skill fills a slot by declaring `provides:` or by the `<project>-<slot>`
    naming convention (templates/local-skills/README.md); a pack only by `provides:`.
    """
    slots: dict[str, dict[str, Any]] = {
        slot: {"local": [], "packs": [], "effective": None} for slot in declared
    }
    seen: set[pathlib.Path] = set()
    reads: list[dict[str, str]] = []
    inspection_sources: list[str] = []
    for root in local_roots:
        inspection_sources.append(str(_skills_catalogue(root)))
        skills, root_reads = _read_skill_catalogue(root)
        reads.extend(root_reads)
        for path, metadata in skills:
            # .claude/skills/<name> is usually a symlink into .agents/skills/.
            resolved = path.resolve(strict=False)
            if resolved in seen:
                continue
            seen.add(resolved)
            name = path.parent.name
            provided = set(_string_list(metadata.get("provides")))
            for slot, entry in slots.items():
                basis = (
                    "provides"
                    if slot in provided
                    else "name" if name == slot or name.endswith(f"-{slot}") else None
                )
                if basis:
                    entry["local"].append({"skill": name, "source": str(path), "basis": basis})
    for pack in packs:
        inspection_sources.append(pack["root"])
        for slot, fills in pack.get("provides", {}).items():
            if slot in slots:
                slots[slot]["packs"].extend({"pack": pack["name"], **fill} for fill in fills)
    for entry in slots.values():
        entry["effective"] = "local" if entry["local"] else "pack" if entry["packs"] else None
    return {"slots": slots, "reads": reads, "inspection_sources": inspection_sources}


def _slot_fill_check(slot: str, entry: dict[str, Any], fallback_sources: list[str]) -> dict[str, Any]:
    local = entry["local"]
    packs = entry["packs"]
    pack_names = ", ".join(f"`{name}`" for name in dict.fromkeys(fill["pack"] for fill in packs))
    if local:
        skill = local[0]
        convention = " (by naming convention)" if skill["basis"] == "name" else ""
        fact = f"slot `{slot}` filled by local skill `{skill['skill']}`{convention}"
        if packs:
            fact += f"; pack {pack_names} also provides it — local outranks pack"
    elif packs:
        fact = f"slot `{slot}` filled by pack {pack_names} (skill `{packs[0]['skill']}`)"
    else:
        fact = f"slot `{slot}` is unfilled"
    if local and packs:
        inference = (
            "pi loads the nearest entry; Claude and Codex load both copies, so the "
            "AGENTS.md concern map must point at the local skill"
        )
    elif local or packs:
        inference = "a declared slot has a filling skill"
    else:
        inference = "no local skill or pack provides this declared slot"
    sources = [fill["source"] for fill in [*local, *packs]] or fallback_sources
    return {
        "check": f"local-slots.fill.{slot}",
        "status": "OK" if local or packs else "MISSING",
        "fact": fact,
        "inference": inference,
        "recommendation": (
            "" if local or packs else f"Fill slot `{slot}` in the local overlay or install a pack that provides it"
        ),
        "untested": "",
        "evidence": [{"claim": fact, "source": source} for source in dict.fromkeys(sources) if source],
    }


def _pack_check(pack: dict[str, Any]) -> dict[str, Any]:
    name = pack["name"]
    state = pack["state"]
    requirements = ", ".join(pack["requirements"]) or "none"
    if state == "satisfied":
        status, fact = "OK", f"pack `{name}` requires {requirements}; installed crew is {pack['crew_version']}"
        recommendation = ""
    elif state == "unsatisfied":
        status, fact = "DEGRADED", f"pack `{name}` requires {requirements}; installed crew is {pack['crew_version']}"
        recommendation = f"Upgrade crew or pin an older `{name}` so {requirements} holds"
    elif state == "undeclared":
        status, fact = "DEGRADED", f"pack `{name}` provides slots but declares no plugin:crew requirement"
        recommendation = f"Ask `{name}` to declare requires: [plugin:crew@>=X.Y.Z]"
    else:
        status, fact = "N/A", f"pack `{name}` requires {requirements}; installed crew version is not tested"
        recommendation = ""
    sources = [*pack["sources"], pack["crew_source"], pack["root"]]
    return {
        "check": f"pack.{name}.requires",
        "status": status,
        "fact": fact,
        "inference": "" if status == "N/A" else "pack requirement compared with the resolved crew manifest",
        "recommendation": recommendation,
        "untested": fact if status == "N/A" else "",
        "evidence": [{"claim": fact, "source": source} for source in dict.fromkeys(sources) if source],
    }


def _description_cost_check(costs: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(cost["total"] for cost in costs)
    parts = "; ".join(
        f"{cost['label']} {cost['total']:,} across {len(cost['skills'])} skills" for cost in costs
    )
    fact = f"always-on description chars: {total:,} ({parts})"
    comparisons = []
    over = False
    for budget in HARNESS_DESCRIPTION_BUDGETS:
        share = total / budget["budget_chars"] * 100
        over = over or total > budget["budget_chars"]
        comparisons.append(
            f"{share:.0f}% of the ~{budget['budget_chars']:,}-char {budget['harness']} budget "
            f"measured {budget['measured']} ({budget['evidence']}; {budget['scope']}) — "
            "a dated measurement, not a permanent limit"
        )
    candidates = [
        cost["label"]
        for cost in sorted(costs, key=lambda cost: cost["total"], reverse=True)
        if cost["label"] != PLUGIN_NAME
    ]
    # Reported, never failed: the budget is the operator's to spend.
    return {
        "check": "description-cost.always-on",
        "status": "OK",
        "fact": fact,
        "inference": "; ".join(comparisons)
        + ("; over budget, so that harness shortens every description" if over else ""),
        "recommendation": (
            f"For headroom, candidates to disable: {', '.join(candidates)}" if over and candidates else ""
        ),
        "untested": "",
        "evidence": [
            {"claim": f"{cost['label']} descriptions total {cost['total']:,} chars", "source": cost["root"]}
            for cost in costs
        ],
    }


def _capability_map_check(inventory: dict[str, Any]) -> dict[str, Any]:
    """Compare the committed capability map with this machine's inventory. Read-only."""
    capability_map = inventory.get("capability_map") or {}
    recorded = capability_map.get("recorded")
    source = capability_map.get("source") or str(
        pathlib.Path(str(inventory.get("project_root") or ".")) / ".agents/skills"
    )
    recommendation = "Run onboarding to merge the capability map into the agent-runtime slot"
    if not recorded or not recorded.get("digest"):
        if capability_map.get("fill") is None:
            fact = "agent-runtime slot is unfilled, so there is no capability map"
        elif not recorded:
            fact = "agent-runtime slot carries no crew:capability-map markers"
        else:
            fact = "agent-runtime capability map markers carry no digest; the map was never generated"
        status, inference = "MISSING", "no committed capability map to compare with this machine"
    elif recorded["digest"] == inventory.get("map_digest"):
        fact = f"capability map matches this machine ({recorded['digest']})"
        status, inference, recommendation = "OK", "committed map and inventory digest agree", ""
    else:
        removals = set(recorded.get("removals", []))
        before = {
            row["capability"]: f"{row['provider']}/{row['kind']}/{row['state']}"
            for row in recorded.get("rows", [])
            if row["capability"] not in removals
        }
        after = {
            row["capability"]: f"{row['provider']}/{row['kind']}/{row['state']}"
            for row in capability_map.get("rows", [])
        }
        changed = [
            f"{name} ({before.get(name, 'not recorded')} -> {after.get(name, 'gone')})"
            for name in sorted(set(before) | set(after))
            if before.get(name) != after.get(name)
        ]
        shown = "; ".join(changed[:10]) + (f"; and {len(changed) - 10} more" if len(changed) > 10 else "")
        fact = f"capability map differs on this machine: {shown or 'digest only'}"
        status = "DEGRADED"
        inference = "the committed map records another machine or an older inventory"
        recommendation = (
            "Re-run onboarding to refresh the capability map, or keep it if this machine is the odd one out"
        )
    return {
        "check": "inventory.capability-map",
        "status": status,
        "fact": fact,
        "inference": inference,
        "recommendation": recommendation,
        "untested": "",
        "evidence": [{"claim": fact, "source": source}],
    }


def _proposal_checks(proposals: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows for `learn_contract.inspect_proposals` evidence. Read-only; no age knob."""
    agents_md = proposals["agents_md"]
    queue = proposals.get("queue") or agents_md
    entries = proposals.get("proposals", [])

    def row(check: str, status: str, fact: str, inference: str, recommendation: str,
            untested: str, sources: list[str]) -> dict[str, Any]:
        return {
            "check": check, "status": status, "fact": fact, "inference": inference,
            "recommendation": recommendation, "untested": untested,
            "evidence": [{"claim": fact, "source": source} for source in dict.fromkeys(sources) if source],
        }

    if not proposals.get("declared"):
        fact = "AGENTS.md declares no proposal-queue; learn is report-only"
        return [row("proposals.queue", "N/A", fact, "no queue, so learn writes nothing", "", "", [agents_md])]

    malformed = [entry for entry in entries if entry["errors"]]
    queue_errors = proposals.get("queue_errors", [])
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["status"] or "unknown"] = counts.get(entry["status"] or "unknown", 0) + 1
    summary = ", ".join(f"{count} {status}" for status, count in sorted(counts.items())) or "empty"
    if queue_errors or malformed:
        problems = [*queue_errors, *(
            f"{pathlib.Path(entry['path']).name}: {entry['errors'][0]}" for entry in malformed
        )]
        checks = [row(
            "proposals.queue", "DEGRADED", f"proposal queue {queue}: " + "; ".join(problems),
            "a queue in a skill root loads as instructions; a malformed proposal cannot be reviewed",
            f"Run learn_contract.py --check {queue} and fix each finding",
            "", [agents_md, queue, *(entry["path"] for entry in malformed)],
        )]
    else:
        checks = [row("proposals.queue", "OK", f"proposal queue {queue}: {summary}",
                      "every proposal passes the learn_contract gates", "", "", [agents_md, queue])]

    open_entries = [entry for entry in entries if entry["status"] in {"draft", "needs-recurrence", "reviewed"}]
    stale = [entry for entry in open_entries if entry["stale"]]
    untested = [entry for entry in open_entries if entry["untested"]]
    untested_text = "; ".join(f"{entry['id']}: {', '.join(entry['untested'])}" for entry in untested)
    if stale:
        fact = "; ".join(f"{entry['id']}: {', '.join(entry['stale'])}" for entry in stale)
        checks.append(row("proposals.staleness", "DEGRADED", fact,
                          "the evidence or the target moved after drafting",
                          "Re-learn or rebase each stale proposal before review", untested_text,
                          [entry["path"] for entry in stale]))
    elif untested:
        checks.append(row("proposals.staleness", "N/A", untested_text, "", "", untested_text,
                          [entry["path"] for entry in untested]))
    else:
        fact = f"{len(open_entries)} open proposal(s) match their tool version and target"
        checks.append(row("proposals.staleness", "OK" if open_entries else "N/A", fact, "", "", "",
                          [queue, *(entry["path"] for entry in open_entries)]))

    learned = proposals.get("learned_skills", [])
    drifted = [skill for skill in learned if skill["tool"] and skill["current_version"]
               and skill["current_version"] != skill["version"]]
    unknown = [skill for skill in learned if skill["tool"] and not skill["current_version"]]
    if drifted:
        fact = "; ".join(
            f"{pathlib.Path(skill['path']).parent.name} learned {skill['tool']} {skill['version']}, "
            f"now {skill['current_version']}"
            for skill in drifted
        )
        rollback = ", ".join(
            f"{pathlib.Path(skill['path']).parent.name}: "
            f"{skill['promoted_in'] or 'promoted-in unknown (no promoted proposal in the queue)'}"
            for skill in drifted
        )
        checks.append(row("learned.skills", "DEGRADED", fact,
                          "a learned skill describes a tool version this machine no longer runs",
                          f"Re-learn it, or roll back by reverting its promoted-in commit ({rollback})",
                          "", [skill["path"] for skill in drifted]))
    elif unknown:
        text = ", ".join(f"current {skill['tool']} version not supplied" for skill in unknown)
        checks.append(row("learned.skills", "N/A", text, "", "", text, [skill["path"] for skill in unknown]))
    else:
        fact = f"{len(learned)} learned skill marker(s) match the current tool versions"
        checks.append(row("learned.skills", "OK" if learned else "N/A", fact, "", "", "",
                          [skill["path"] for skill in learned] or [agents_md]))
    return checks


def moved_skill_references(consumer_root: pathlib.Path) -> dict[str, Any]:
    """Find consumer references to skills that moved out of Crew. Reads only.

    Scans the entry files, local skills, and role overlays a consumer owns.
    """
    root = pathlib.Path(consumer_root)
    candidates: list[pathlib.Path] = [root / "AGENTS.md", root / "CLAUDE.md"]
    candidates.extend(sorted((root / ".agents/skills").rglob("*.md")))
    # .claude/skills/<name> is usually a directory symlink into .agents/skills/.
    candidates.extend(sorted((root / ".claude/skills").glob("*/SKILL.md")))
    for agents in ("agents", ".claude/agents", ".pi/agents"):
        candidates.extend(sorted((root / agents).rglob("*.md")))
    references: list[dict[str, Any]] = []
    reads: list[dict[str, str]] = []
    seen: set[pathlib.Path] = set()
    for path in candidates:
        resolved = path.resolve(strict=False)
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exception:
            reads.append({"state": "unreadable", "source": str(path), "detail": str(exception)})
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for match in MOVED_SKILL_REFERENCE.finditer(line):
                references.append(
                    {
                        "skill": match.group("skill"),
                        "namespace": match.group("namespace") or "",
                        "pack": MOVED_SKILLS[match.group("skill")],
                        "source": str(path),
                        "line": number,
                    }
                )
    return {"references": references, "reads": reads, "inspection_sources": [str(root)]}


def _moved_skill_checks(moved: dict[str, Any], packs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_skill: dict[str, list[dict[str, Any]]] = {}
    for reference in moved["references"]:
        by_skill.setdefault(reference["skill"], []).append(reference)
    installed = {pack["name"] for pack in packs}
    carried = {
        path.parent.name
        for pack in packs
        for path in _skills_catalogue(pathlib.Path(pack["root"])).glob("*/SKILL.md")
    }
    checks = []
    for skill, references in sorted(by_skill.items()):
        pack = MOVED_SKILLS[skill]
        detected = pack in installed or skill in carried
        stale = any(ref["namespace"] == PLUGIN_NAME for ref in references)
        rename = f"update `{PLUGIN_NAME}:{skill}` to `{pack}:{skill}`"
        where = ", ".join(f"{pathlib.Path(ref['source']).name}:{ref['line']}" for ref in references)
        if not detected:
            status = "DEGRADED"
            fact = f"`{skill}` is referenced ({where}) but no installed pack carries it"
            recommendation = f"`{skill}` moved to pack {pack}; install it" + (f", then {rename}" if stale else "")
        elif stale:
            status = "DEGRADED"
            fact = f"pack {pack} carries `{skill}`, but references still name `{PLUGIN_NAME}:{skill}` ({where})"
            recommendation = rename[0].upper() + rename[1:]
        else:
            status = "OK"
            fact = f"`{skill}` moved to pack {pack}, which is installed ({where})"
            recommendation = ""
        checks.append(
            {
                "check": f"moved-skills.{skill}",
                "status": status,
                "fact": fact,
                "inference": "consumer references resolved against the moved-skills table and detected packs",
                "recommendation": recommendation,
                "untested": "",
                "evidence": [
                    {
                        "claim": f"line {ref['line']} names `{ref['namespace'] + ':' if ref['namespace'] else ''}{skill}`",
                        "source": ref["source"],
                    }
                    for ref in references
                ],
            }
        )
    return checks


def profile_for(working_capabilities: list[str], persona_evidence: list[str]) -> str:
    """One taxonomy: personas takes deterministic precedence over platform."""
    if persona_evidence:
        return "personas"
    if working_capabilities:
        return "platform"
    return "portable"


def _role_string_list(value: Any) -> list[str] | None:
    if isinstance(value, str):
        if not value.strip():
            return []
        items = value.split(",")
        if any(not item.strip() for item in items):
            return None
        return [item.strip() for item in items]
    if isinstance(value, list) and all(
        isinstance(item, str) and item.strip() for item in value
    ):
        return [item.strip() for item in value]
    return None


def _claude_role_string_list(value: Any) -> list[str] | None:
    if not isinstance(value, str):
        return _role_string_list(value)
    if not value.strip():
        return []
    items: list[str] = []
    start = 0
    depth = 0
    for index, character in enumerate(value):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return None
        elif character == "," and depth == 0:
            items.append(value[start:index].strip())
            start = index + 1
    if depth != 0:
        return None
    items.append(value[start:].strip())
    return items if all(items) else None


def _claude_tool_base(value: str) -> str:
    match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*)\([^()\r\n]+\)", value)
    return match.group(1) if match else value


def _claude_tool_is_bare(value: str) -> bool:
    base = _claude_tool_base(value)
    return value == base or value == f"{base}(*)"


def _consumer_role_posture(
    harness: str,
    allowed: list[str],
    denied: list[str],
    *,
    allowlist_declared: bool,
    denylist_declared: bool,
) -> dict[str, Any]:
    if harness == "claude":
        bare_allowed = [item for item in allowed if _claude_tool_is_bare(item)]
        scoped_allowed = [
            item for item in allowed if not _claude_tool_is_bare(item)
        ]
        bare_denied = [item for item in denied if _claude_tool_is_bare(item)]
        scoped_denied = [
            item for item in denied if not _claude_tool_is_bare(item)
        ]
        bare_allowed_tools = {_claude_tool_base(item) for item in bare_allowed}
        bare_denied_tools = {_claude_tool_base(item) for item in bare_denied}

        def unrestricted(tool: str) -> bool:
            return (
                not allowlist_declared or tool in bare_allowed_tools
            ) and tool not in bare_denied_tools

        def restricted(tool: str) -> list[str]:
            if tool in bare_denied_tools or unrestricted(tool):
                return []
            return [
                item for item in scoped_allowed if _claude_tool_base(item) == tool
            ]

        effective_writes = [
            tool for tool in ("Write", "Edit", "NotebookEdit") if unrestricted(tool)
        ]
        restricted_writes = [
            item
            for tool in ("Write", "Edit", "NotebookEdit")
            for item in restricted(tool)
        ]
        effect = (
            f"declared allowlist: {', '.join(allowed) if allowlist_declared else 'unrestricted'}; "
            f"declared denylist: {', '.join(denied) if denylist_declared else 'none'}; "
            f"bare allows: {', '.join(bare_allowed) or 'none'}; "
            f"scoped allows: {', '.join(scoped_allowed) or 'none'}; "
            f"bare denies: {', '.join(bare_denied) or 'none'}; "
            f"scoped denies: {', '.join(scoped_denied) or 'none'}; "
            f"effective write tools: {', '.join(effective_writes) or 'none'}; "
            f"restricted write tools: {', '.join(restricted_writes) or 'none'}"
        )
        bash_scoped_denies = [
            item for item in scoped_denied if _claude_tool_base(item) == "Bash"
        ]
        restricted_bash = restricted("Bash")
        if unrestricted("Bash"):
            route = (
                "through a bare allow"
                if allowlist_declared
                else "without an allowlist"
            )
            constraints = (
                f" with scoped denies: {', '.join(bash_scoped_denies)}"
                if bash_scoped_denies
                else ""
            )
            shell = (
                f"Bash is available {route}{constraints}; shell access makes the "
                "write posture advisory unless the host sandbox enforces it"
            )
        elif restricted_bash:
            shell = (
                f"Bash is restricted to scoped allows: {', '.join(restricted_bash)}; "
                "unrestricted shell access is unavailable"
            )
        elif "Bash" in bare_denied_tools:
            shell = "Bash is unavailable through a bare deny; shell access is unavailable"
        else:
            shell = (
                "Bash is unavailable; shell access is unavailable under the declared "
                "tool constraints"
            )
        caveat = (
            f"{shell}; effective write tools: "
            f"{', '.join(effective_writes) or 'none'}; restricted write tools: "
            f"{', '.join(restricted_writes) or 'none'}"
        )
    else:
        effect = f"declared allowed tools: {', '.join(allowed) or 'none'}"
        caveat = (
            "shell access makes the frontmatter posture advisory unless the host sandbox enforces it"
            if "bash" in allowed
            else "shell access is unavailable because bash is not in the declared allowlist"
        )
    return {
        "writes": "custom",
        "harness": harness,
        "allowed_tools": allowed,
        "denied_tools": denied,
        "allowlist_declared": allowlist_declared,
        "denylist_declared": denylist_declared,
        "write_effect": effect,
        "caveat": caveat,
    }


def inspect_role_postures(
    package_root: pathlib.Path,
    consumer_root: pathlib.Path | None = None,
) -> list[dict[str, Any]]:
    """Return effective posture evidence from resolved harness role files."""
    try:
        from .role_contract import (
            FORBIDDEN_RUNTIME_KEYS,
            PI_PACKAGE_NAME,
            WRITE_POSTURES,
            claude_role_identity,
            effective_posture,
        )
    except ImportError:
        from role_contract import (
            FORBIDDEN_RUNTIME_KEYS,
            PI_PACKAGE_NAME,
            WRITE_POSTURES,
            claude_role_identity,
            effective_posture,
        )

    package_root = pathlib.Path(package_root)
    has_consumer_root = consumer_root is not None
    consumer_root = pathlib.Path(consumer_root) if consumer_root else package_root
    rows: list[dict[str, Any]] = []
    harness_roots = (
        ("claude", package_root / "agents", consumer_root / ".claude/agents"),
        ("pi", package_root / "pi-agents", consumer_root / ".pi/agents"),
    )
    targets: list[tuple[str | None, str, pathlib.Path, bool, bool, bool]] = []
    for harness, distributed, overlay in harness_roots:
        consumer_roles: dict[str, list[pathlib.Path]] = {}
        unresolved_roles: list[pathlib.Path] = []
        if overlay.is_dir():
            for path in sorted(overlay.rglob("*.md")):
                try:
                    metadata, error = read_frontmatter(path)
                except (OSError, UnicodeDecodeError):
                    metadata, error = None, "unreadable"
                resolved_name = None
                if not error and isinstance(metadata, dict):
                    candidate = metadata.get("name")
                    if harness == "claude":
                        resolved_name = claude_role_identity(candidate)
                    elif isinstance(candidate, str) and candidate.strip():
                        resolved_name = candidate.strip()
                if not resolved_name:
                    unresolved_roles.append(path)
                    continue
                # pi-subagents registers `<package>.<name>`, or the bare name
                # when no package is declared. Only `package: crew` with the
                # same name shadows a Crew role; anything else is a separate
                # agent beside it.
                identity = resolved_name
                package = metadata.get("package") if harness == "pi" else None
                if isinstance(package, str) and package.strip():
                    identity = f"{package.strip()}.{resolved_name}"
                consumer_roles.setdefault(identity, []).append((resolved_name, path))
        for name in EXPECTED_ROLE_NAMES:
            identity = f"{PI_PACKAGE_NAME}.{name}" if harness == "pi" else name
            paths = consumer_roles.pop(identity, [])
            if paths:
                targets.extend(
                    (name, identity, harness, path, True, harness != "claude", len(paths) > 1)
                    for _, path in paths
                )
            else:
                targets.append(
                    (name, identity, harness, distributed / f"{name}.md", False, True, False)
                )
        for identity, paths in sorted(consumer_roles.items()):
            targets.extend(
                (name, identity, harness, path, True, harness != "claude", len(paths) > 1)
                for name, path in paths
            )
        targets.extend(
            (None, None, harness, path, True, False, False)
            for path in unresolved_roles
        )
    if has_consumer_root:
        neutral_root = consumer_root / "agents"
        targets.extend(
            (path.stem, path.stem, "neutral", path, True, True, False)
            for path in sorted(neutral_root.glob("*.md"))
        )

    for name, identity, harness, path, is_consumer_role, enforce_filename, duplicate in targets:
        pi_identity: dict[str, str] = {}
        if harness == "pi" and identity is not None:
            pi_identity["runtime_identity"] = identity
            if identity != f"{PI_PACKAGE_NAME}.{name}" and name in EXPECTED_ROLE_NAMES:
                pi_identity["separate_from"] = f"{PI_PACKAGE_NAME}.{name}"
            if identity == name and name in PI_BUILTIN_AGENT_NAMES:
                pi_identity["overrides_builtin"] = name
        errors: list[str] = []
        try:
            metadata, error = read_frontmatter(path)
        except (OSError, UnicodeDecodeError) as exception:
            metadata, error = None, f"role file is unreadable: {exception}"
        if error:
            errors.append(error)
        if not isinstance(metadata, dict):
            metadata = {}
        resolved_name = metadata.get("name")
        if not isinstance(resolved_name, str) or not resolved_name.strip():
            errors.append(
                f"name must be {name}"
                if name is not None
                else "resolved role identity is missing"
            )
        elif harness == "claude" and is_consumer_role and not claude_role_identity(
            resolved_name
        ):
            errors.append("name must use lowercase letters and hyphens")
        else:
            resolved_name = (
                claude_role_identity(resolved_name)
                if harness == "claude" and is_consumer_role
                else resolved_name.strip()
            )
            if enforce_filename and resolved_name != path.stem:
                errors.append(f"name must be {path.stem}")
        if duplicate:
            errors.append(f"duplicate resolved role identity {name}")
        if not isinstance(metadata.get("description"), str) or not metadata["description"].strip():
            errors.append("description must be a non-empty string")
        forbidden = sorted(key for key in metadata if key in FORBIDDEN_RUNTIME_KEYS)
        if forbidden:
            errors.append(f"forbidden runtime keys: {', '.join(forbidden)}")

        writes: str | None = None
        if harness == "neutral":
            writes = "neutral"
        elif harness == "claude":
            if is_consumer_role:
                allowlist_declared = "tools" in metadata
                denylist_declared = "disallowedTools" in metadata
                allowed = (
                    _claude_role_string_list(metadata["tools"])
                    if allowlist_declared
                    else []
                )
                denied = (
                    _claude_role_string_list(metadata["disallowedTools"])
                    if denylist_declared
                    else []
                )
                if allowed is None:
                    errors.append("tools must be a string sequence")
                if denied is None:
                    errors.append("disallowedTools must be a string sequence")
                if allowed is not None and denied is not None:
                    writes = "custom"
            else:
                denied = _claude_role_string_list(
                    metadata.get("disallowedTools", "")
                )
                if denied is None:
                    errors.append("disallowedTools must be a string sequence")
                matches = [
                    mode
                    for mode, contract in WRITE_POSTURES.items()
                    if denied is not None
                    and set(denied) == set(contract["claude"]["denied"])
                ]
                writes = matches[0] if len(matches) == 1 else None
        elif is_consumer_role:
            allowed = _role_string_list(metadata.get("tools"))
            if allowed is None:
                errors.append("tools must be a string sequence")
            else:
                writes = "custom"
        else:
            # Shipped pi roles subtract with `excludeTools` and carry
            # `package: crew` (runtime identity `crew.<role>`); a `tools:`
            # allowlist is the pre-0.38.0 shape and matches no posture.
            if metadata.get("package") != PI_PACKAGE_NAME:
                errors.append(f"package must be {PI_PACKAGE_NAME}")
            excluded = _role_string_list(metadata.get("excludeTools", ""))
            if excluded is None:
                errors.append("excludeTools must be a string sequence")
            elif "tools" not in metadata:
                matches = [
                    mode
                    for mode, contract in WRITE_POSTURES.items()
                    if set(excluded) == set(contract["pi"]["denied"])
                ]
                writes = matches[0] if len(matches) == 1 else None
        if writes is None and not any("string sequence" in item for item in errors):
            errors.append("tool posture does not match a supported write posture")

        if errors:
            rows.append(
                {
                    "name": name,
                    "harness": harness,
                    "source": str(path),
                    "scope": "consumer" if is_consumer_role else "crew",
                    "role_valid": False,
                    "validation_errors": errors,
                    **pi_identity,
                }
            )
        else:
            if harness == "neutral":
                rows.append(
                    {
                        "name": name,
                        "harness": harness,
                        "allowed_tools": [],
                        "denied_tools": [],
                        "write_effect": "no harness-specific tool posture is declared",
                        "caveat": "effective tools depend on the harness that resolves this neutral role",
                        "source": str(path),
                        "scope": "consumer",
                        "role_valid": True,
                    }
                )
                continue
            if is_consumer_role and harness == "claude":
                posture = _consumer_role_posture(
                    harness,
                    allowed,
                    denied,
                    allowlist_declared=allowlist_declared,
                    denylist_declared=denylist_declared,
                )
            elif is_consumer_role:
                posture = _consumer_role_posture(
                    harness,
                    allowed,
                    [],
                    allowlist_declared=True,
                    denylist_declared=False,
                )
            else:
                posture = effective_posture(writes, harness)
            rows.append(
                {
                    "name": name,
                    **posture,
                    "source": str(path),
                    "scope": "consumer" if is_consumer_role else "crew",
                    "role_valid": True,
                    **pi_identity,
                }
            )
    return rows


def _complete_role_posture(posture: dict[str, Any], harness: str, name: str) -> bool:
    try:
        from .role_contract import effective_posture
    except ImportError:
        from role_contract import effective_posture

    if harness == "neutral":
        return (
            posture.get("role_valid") is True
            and posture.get("name") == name
            and posture.get("harness") == harness
            and isinstance(posture.get("source"), str)
            and bool(posture["source"])
        )
    if posture.get("scope") == "consumer":
        allowed = posture.get("allowed_tools")
        denied = posture.get("denied_tools")
        return (
            posture.get("role_valid") is True
            and posture.get("name") == name
            and posture.get("harness") == harness
            and posture.get("writes") == "custom"
            and isinstance(allowed, list)
            and all(isinstance(tool, str) and tool for tool in allowed)
            and isinstance(denied, list)
            and all(isinstance(tool, str) and tool for tool in denied)
            and isinstance(posture.get("allowlist_declared"), bool)
            and isinstance(posture.get("denylist_declared"), bool)
            and (harness != "pi" or not denied)
            and isinstance(posture.get("write_effect"), str)
            and bool(posture["write_effect"])
            and isinstance(posture.get("caveat"), str)
            and bool(posture["caveat"])
            and isinstance(posture.get("source"), str)
            and bool(posture["source"])
        )
    writes = posture.get("writes")
    if not isinstance(writes, str):
        return False
    try:
        expected = effective_posture(writes, harness)
    except ValueError:
        return False
    return (
        posture.get("role_valid") is True
        and posture.get("name") == name
        and posture.get("harness") == harness
        and all(posture.get(key) == value for key, value in expected.items())
        and isinstance(posture.get("source"), str)
        and bool(posture["source"])
    )


def compose_doctor_report(
    installation_report: dict[str, Any],
    *,
    runtime_comparisons: list[dict[str, Any]],
    local_slots: dict[str, Any],
    role_postures: list[dict[str, Any]],
    persona_evidence: list[str],
    slot_fills: dict[str, Any] | None = None,
    packs: list[dict[str, Any]] | None = None,
    description_costs: list[dict[str, Any]] | None = None,
    moved_skill_refs: dict[str, Any] | None = None,
    inventory: dict[str, Any] | None = None,
    proposals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose all Doctor checks into one deterministic, non-persisted report.

    `slot_fills`, `packs`, `description_costs`, and `moved_skill_refs` are
    optional: omitted, the report carries no fill, pack, cost, or moved-skill rows.
    `inventory` (a `crew-inventory/1` document) adds `inventory.capability-map`.
    `proposals` (from `learn_contract.inspect_proposals`) adds the proposals.* and
    learned.skills rows; omitted, it adds none.
    """
    report = deepcopy(installation_report)
    checks = report["checks"]

    project_root = str(report.get("inspection_context", {}).get("project_root") or "")
    role_inspection_sources: dict[str, list[str]] = {"claude": [], "pi": []}
    for harness, suffix in (("claude", ".claude/agents"), ("pi", ".pi/agents")):
        harness_report = report["harnesses"][harness]
        candidates: list[str] = []
        if project_root:
            candidates.append(str(pathlib.Path(project_root) / suffix))
        package_suffix = "agents" if harness == "claude" else "pi-agents"
        candidates.extend(
            str(pathlib.Path(root) / package_suffix)
            for root in [
                *harness_report.get("resolved_package_roots", []),
                *harness_report.get("package_roots", []),
            ]
        )
        candidates.extend(str(source) for source in harness_report.get("inspection_paths", []))
        role_inspection_sources[harness] = list(
            dict.fromkeys(source for source in candidates if source)
        )
    report_inspection_sources = list(
        dict.fromkeys(
            source
            for harness_report in report["harnesses"].values()
            for source in harness_report.get("inspection_paths", [])
            if source
        )
    )

    for comparison in runtime_comparisons:
        capture = comparison.get("capture", {})
        capture_sources = [str(source) for source in capture["sources"]]
        for entry in comparison["entries"]:
            state = entry["state"]
            status = "OK" if state == "working" else "N/A" if state == "not tested" else "DEGRADED"
            if entry.get("scope") == "harness":
                fact = f"{comparison['harness']} runtime catalogue is {state}"
            else:
                fact = f"{entry['runtime_name']} runtime entry is {state}"
            sources = list(capture_sources)
            for side in (entry.get("disk"), entry.get("runtime")):
                if isinstance(side, dict) and side.get("path"):
                    sources.append(str(side["path"]))
            checks.append(
                {
                    "check": f"runtime.{comparison['harness']}.{entry['runtime_name']}",
                    "status": status,
                    "fact": fact,
                    "inference": "" if status == "N/A" else f"catalogue comparison supports {state}",
                    "recommendation": "" if status in {"OK", "N/A"} else f"Resolve {fact}",
                    "untested": fact if status == "N/A" else "",
                    "evidence": [
                        {"claim": fact, "source": source} for source in dict.fromkeys(sources)
                    ],
                }
            )

    slot_fact = (
        f"declared local slots: {', '.join(local_slots['declared']) or 'none'}; "
        f"recommended vocabulary: {', '.join(local_slots['recommended_vocabulary']) or 'none'}"
    )
    slot_reads = local_slots.get("reads", [])
    slot_status = "DEGRADED" if slot_reads else "OK"
    slot_evidence = [
        {
            "claim": f"local-slot declaration is {read['state']}: {read['detail']}",
            "source": read["source"],
        }
        for read in slot_reads
    ]
    if not slot_evidence:
        slot_sources = (
            local_slots.get("sources")
            or local_slots.get("inspection_sources")
            or report_inspection_sources
        )
        slot_evidence = [
            {"claim": slot_fact, "source": source}
            for source in dict.fromkeys(str(source) for source in slot_sources if source)
        ]
    checks.append(
        {
            "check": "local-slots.declarations",
            "status": slot_status,
            "fact": slot_fact,
            "inference": (
                "local-slot declarations could not be fully derived"
                if slot_reads
                else "declared slots remain separate from recommended vocabulary"
            ),
            "recommendation": "Resolve malformed local-slot declarations" if slot_reads else "",
            "untested": "",
            "evidence": slot_evidence,
        }
    )
    if slot_fills is not None:
        # An unfilled slot's evidence is where Doctor looked for a fill.
        fallback = (
            slot_fills.get("inspection_sources")
            or local_slots.get("sources")
            or local_slots.get("inspection_sources")
            or report_inspection_sources
        )
        for slot, entry in sorted(slot_fills["slots"].items()):
            checks.append(_slot_fill_check(slot, entry, fallback))
    for pack in packs or []:
        checks.append(_pack_check(pack))
    if description_costs:
        checks.append(_description_cost_check(description_costs))
    if moved_skill_refs is not None:
        checks.extend(_moved_skill_checks(moved_skill_refs, packs or []))
    if inventory is not None:
        checks.append(_capability_map_check(inventory))
    if proposals is not None:
        checks.extend(_proposal_checks(proposals))

    capability_checks = [
        capability
        for harness in ("pi", "claude", "codex")
        for capability in report["harnesses"][harness].get("capability_checks", [])
    ]
    for capability in capability_checks:
        state = capability["state"]
        state_contract = {
            "present": ("OK", "grant evidence is present", ""),
            "working": ("OK", "probe evidence supports working", ""),
            "unavailable": ("DEGRADED", "probe evidence supports unavailable", "resolve"),
            "not tested": ("N/A", "", ""),
        }
        if state not in state_contract:
            raise ValueError(f"unsupported capability state: {state}")
        status, inference, action = state_contract[state]
        harness = capability["harness"]
        fact = f"{harness} capability {capability['name']} is {state}"
        checks.append(
            {
                "check": f"capability.{harness}.{capability['name']}",
                "status": status,
                "fact": fact,
                "inference": inference,
                "recommendation": f"Resolve {fact}" if action else "",
                "untested": fact if status == "N/A" else "",
                "evidence": deepcopy(capability["evidence"]),
            }
        )

    posture_index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    unresolved_postures: list[dict[str, Any]] = []
    for posture in role_postures:
        name = posture.get("name")
        if posture.get("scope") == "consumer" and not isinstance(name, str):
            unresolved_postures.append(posture)
            continue
        harness_name = str(posture.get("harness") or "")
        identity = str(name or "")
        if harness_name == "pi":
            # pi registers by runtime identity, so a bare `reviewer` overlay and
            # Crew's `crew.reviewer` are two agents, not a collision.
            identity = str(posture.get("runtime_identity") or f"{PI_PACKAGE_NAME}.{identity}")
        posture_index.setdefault((harness_name, identity), []).append(posture)

    def fleet_identity(harness: str, name: str) -> str:
        return f"{PI_PACKAGE_NAME}.{name}" if harness == "pi" else name

    for harness in ("claude", "pi"):
        for name in EXPECTED_ROLE_NAMES:
            matches = posture_index.get((harness, fleet_identity(harness, name)), [])
            ready = len(matches) == 1 and _complete_role_posture(matches[0], harness, name)
            if ready:
                posture = matches[0]
                fact = f"{harness} role {name}: {posture['write_effect']}; {posture['caveat']}"
                inference = (
                    "effective tool posture is the validated resolved-consumer posture"
                    if posture.get("scope") == "consumer"
                    else "effective tool posture matches the rendered role contract"
                )
            elif not matches:
                fact = f"{harness} role {name} is missing"
                inference = "the expected seven-role fleet is incomplete"
            else:
                fact = f"{harness} role {name} posture evidence is incomplete or duplicated"
                inference = "role readiness cannot be established"
            sources = [
                str(posture.get("source", ""))
                for posture in matches
                if posture.get("source")
            ]
            if not sources:
                sources = role_inspection_sources[harness]
            checks.append(
                {
                    "check": f"role.{harness}.{name}",
                    "status": "OK" if ready else "DEGRADED",
                    "fact": fact,
                    "inference": inference,
                    "recommendation": "" if ready else f"Resolve {harness} role {name}",
                    "untested": "",
                    "evidence": [
                        {"claim": fact, "source": source} for source in dict.fromkeys(sources)
                    ],
                }
            )

    fleet_keys = {
        (harness, fleet_identity(harness, name))
        for harness in ("claude", "pi")
        for name in EXPECTED_ROLE_NAMES
    }
    consumer_keys = sorted(
        key
        for key, postures in posture_index.items()
        if key not in fleet_keys
        and key[0] in {"claude", "pi", "neutral"}
        and any(posture.get("scope") == "consumer" for posture in postures)
    )
    for harness, name in consumer_keys:
        matches = posture_index[(harness, name)]
        local_name = str(matches[0].get("name")) if harness == "pi" else name
        ready = len(matches) == 1 and _complete_role_posture(matches[0], harness, local_name)
        if ready:
            posture = matches[0]
            fact = f"{harness} consumer role {name}: {posture['write_effect']}; {posture['caveat']}"
            if posture.get("separate_from"):
                fact += (
                    f"; registers as {name}, a separate agent that does not shadow "
                    f"{posture['separate_from']} (declare package: {PI_PACKAGE_NAME} to shadow it)"
                )
            if posture.get("overrides_builtin"):
                fact += f"; it overrides pi-subagents' built-in {posture['overrides_builtin']}"
            inference = (
                "neutral role metadata is valid; effective tools remain harness-dependent"
                if harness == "neutral"
                else "effective tool posture is the validated resolved-consumer posture"
            )
        else:
            fact = f"{harness} consumer role {name} posture evidence is incomplete or duplicated"
            inference = "consumer role readiness cannot be established"
        sources = [
            str(posture.get("source", ""))
            for posture in matches
            if posture.get("source")
        ]
        if not sources:
            sources = role_inspection_sources.get(harness, report_inspection_sources)
        checks.append(
            {
                "check": f"role.consumer.{harness}.{name}",
                "status": "OK" if ready else "DEGRADED",
                "fact": fact,
                "inference": inference,
                "recommendation": "" if ready else f"Resolve {harness} consumer role {name}",
                "untested": "",
                "evidence": [
                    {"claim": fact, "source": source} for source in dict.fromkeys(sources)
                ],
            }
        )

    for index, posture in enumerate(
        sorted(unresolved_postures, key=lambda item: str(item.get("source", ""))),
        start=1,
    ):
        harness = str(posture.get("harness") or "unknown")
        errors = posture.get("validation_errors", [])
        detail = "; ".join(str(error) for error in errors) or "identity is unresolved"
        fact = f"{harness} consumer role identity is unresolved: {detail}"
        source = str(posture.get("source") or "")
        checks.append(
            {
                "check": f"role.consumer.{harness}.unresolved-{index}",
                "status": "DEGRADED",
                "fact": fact,
                "inference": "the file does not resolve to a consumer role identity",
                "recommendation": f"Resolve the {harness} consumer role identity",
                "untested": "",
                "evidence": [{"claim": fact, "source": source}],
            }
        )

    working = [
        item["name"]
        for item in capability_checks
        if item["state"] == "working" and item.get("ownership") == "project"
    ]
    report["profile"] = profile_for(working, persona_evidence)
    profile_fact = f"operating profile is {report['profile']}"
    if persona_evidence:
        profile_sources = persona_evidence
    else:
        profile_sources = [
            evidence["source"]
            for item in capability_checks
            for evidence in item["evidence"]
        ]
        profile_sources.extend(report_inspection_sources)
    checks.append(
        {
            "check": "operating-profile.selection",
            "status": "OK",
            "fact": profile_fact,
            "inference": "persona evidence takes precedence over working platform capabilities",
            "recommendation": "",
            "untested": "",
            "evidence": [
                {"claim": profile_fact, "source": source}
                for source in dict.fromkeys(source for source in profile_sources if source)
            ],
        }
    )
    actionable = [row for row in checks if row["status"] in {"MISSING", "DEGRADED"} and row["recommendation"]]
    actionable.sort(key=lambda row: 0 if row["status"] == "MISSING" else 1)
    if actionable:
        report["top_actions"] = [actionable[0]["recommendation"]]
    elif any(row["status"] == "N/A" for row in checks):
        report["top_actions"] = ["Run only authorized free checks still marked untested"]
    else:
        report["top_actions"] = ["healthy — nothing to do"]
    return report


def validator_command(package_root: pathlib.Path, consumer_root: pathlib.Path) -> list[str]:
    validator = pathlib.Path(package_root).resolve() / "scripts/check_skill_layout.py"
    if not validator.is_file():
        raise FileNotFoundError(f"Crew validator is not distributed at {validator}")
    return [sys.executable, str(validator), str(pathlib.Path(consumer_root).resolve())]


def probe_plan() -> list[dict[str, object]]:
    """Return probes in execution order; this function executes none of them."""
    return [
        {"command": "claude plugin validate <crew-root> --strict", "cost": "free", "approval_required": False},
        {"command": "claude --plugin-dir <crew-root> plugin details crew", "cost": "free", "approval_required": False},
        {"command": 'codex debug prompt-input "hi"', "cost": "free", "approval_required": False},
        {
            "command": "python3 <crew-root>/scripts/check_skill_layout.py <repo-root>",
            "cost": "free",
            "approval_required": False,
        },
        {"command": "claude -p <verification-prompt>", "cost": "billed", "approval_required": True},
        {"command": "pi -p <verification-prompt>", "cost": "billed", "approval_required": True},
        {"command": "codex exec <verification-prompt>", "cost": "billed", "approval_required": True},
    ]


def render_doctor_report(report: dict[str, Any]) -> str:
    top_actions = report.get("top_actions", [])
    if len(top_actions) != 1:
        raise ValueError("Doctor reports require exactly one top action")
    if report.get("profile") not in PROFILE_TAXONOMY:
        raise ValueError("Doctor reports require exactly one valid profile")
    if any(
        not item.get("source")
        for row in report["checks"]
        for item in row.get("evidence", [])
    ):
        raise ValueError("Doctor report evidence must be source-bearing")
    lines = [
        "| check | status | fact | inference | recommendation | untested | repeatable evidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report["checks"]:
        fields = [
            row["check"],
            row["status"],
            row["fact"],
            row["inference"],
            row["recommendation"],
            row["untested"],
            "; ".join(
                f"{item['claim']} (source: {item['source']})"
                for item in row["evidence"]
            ),
        ]
        lines.append("| " + " | ".join(str(field).replace("|", "\\|") or "—" for field in fields) + " |")
    lines.append("")
    lines.append(f"Profile: {report['profile']}")
    lines.append("")
    lines.append(f"Top action: {top_actions[0]}")
    return "\n".join(lines) + "\n"
