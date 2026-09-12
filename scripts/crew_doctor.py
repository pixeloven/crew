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
    from .frontmatter import parse_inline_list, parse_simple_mapping, read_frontmatter
except ImportError:  # Direct script execution.
    from frontmatter import parse_inline_list, parse_simple_mapping, read_frontmatter


CREW_REPO = "pixeloven/crew"
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
LOADED_RUNTIME_STATES = {"present", "working", "loaded-but-undiscoverable", "truncated"}
SEMVER = re.compile(
    r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?:(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
PI_CREW_PACKAGE = re.compile(
    r"^(?:(?:git:)?github\.com/|github:)?pixeloven/crew(?:@[^@/\s]+)?$"
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
    version = read.value.get("version") if isinstance(read.value, dict) else None
    if read.state == "present" and (
        not isinstance(version, str) or not SEMVER.fullmatch(version)
    ):
        return ReadResult(
            None,
            "malformed",
            read.source,
            "manifest version must be a valid SemVer string",
        )
    return ReadResult(
        version,
        read.state,
        read.source,
        read.detail,
    )


def _clean_version(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = value.rsplit("@", 1)[-1]
    if candidate.startswith("v"):
        candidate = candidate[1:]
    return candidate if SEMVER.fullmatch(candidate) else None


def _version_tuple(
    value: Any,
) -> tuple[int, int, int, int, tuple[tuple[int, int | str], ...]] | None:
    clean = _clean_version(value)
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


def _is_crew_marketplace_source(value: Any) -> bool:
    if value == CREW_REPO:
        return True
    return (
        isinstance(value, dict)
        and value.get("source") == "github"
        and value.get("repo") == CREW_REPO
    )


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
        "runtime_paths": [],
        "configuration_reads": [],
        "manifest_reads": [],
        "catalogue_reads": [],
        "package_roots": [],
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


def _record_runtime(
    result: dict[str, Any],
    runtime: dict[str, Any] | None,
    validated_roots: list[pathlib.Path],
) -> None:
    """Record only evidence supplied by this harness's capture."""
    if runtime is None or runtime.get("tested") is False:
        return
    captured_state = runtime.get("state")
    if captured_state in {"not-tested", "not tested"}:
        result["runtime"] = {
            "state": "not tested",
            "source": runtime.get("source", "captured runtime"),
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
        crew_entries = (
            [
                entry
                for entry in skills
                if isinstance(entry, dict)
                and (
                    str(entry.get("name", "")).startswith("crew:")
                    or entry.get("namespace") == "crew"
                    or entry.get("source") in {"crew", "pixeloven/crew"}
                    or any(
                        _path_within(pathlib.Path(str(entry.get("path", ""))), root)
                        for root in validated_roots
                        if entry.get("path")
                    )
                )
            ]
            if isinstance(skills, list)
            else []
        )
        validated_runtime_root = any(
            _path_within(path, root)
            for path in _runtime_paths(runtime)
            for root in validated_roots
        )
        if not crew_entries and not validated_runtime_root:
            state = "omitted" if isinstance(skills, list) else "unavailable"
        elif captured_state in {"loaded-but-undiscoverable", "truncated"}:
            state = captured_state
        elif any(not entry.get("description") for entry in crew_entries):
            state = "loaded-but-undiscoverable"
        elif captured_state == "present" or not crew_entries:
            state = "present"
        else:
            state = "working"
    result["runtime"] = {"state": state, "source": runtime.get("source", "captured runtime")}
    if state in LOADED_RUNTIME_STATES:
        result["runtime_paths"] = [str(path) for path in _runtime_paths(runtime)]
        if runtime.get("version"):
            result["loaded_version"] = runtime["version"]
            result["loaded_version_source"] = result["runtime"]["source"]


def _degrade_for_runtime(result: dict[str, Any]) -> None:
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
) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    declared: dict[str, list[str]] = {}
    failures: list[dict[str, str]] = []
    for root in dict.fromkeys(roots):
        catalogue = root if root.name == "skills" else root / "skills"
        for skill in sorted(catalogue.glob("*/SKILL.md")):
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
            if isinstance(requirements, str):
                failures.append(
                    {
                        "state": "malformed",
                        "source": str(skill),
                        "detail": "requires must be a string sequence",
                    }
                )
                continue
            if not isinstance(requirements, list):
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
    declared, declaration_failures = _declared_capabilities(
        [pathlib.Path(root) for root in result["package_roots"]] + [consumer_skill_root]
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
        name = observation.get("name")
        kind = observation.get("kind")
        state = observation.get("state")
        source = observation.get("source")
        if not all(isinstance(value, str) and value for value in (name, kind, state, source)):
            raise ValueError(f"{harness} capability evidence must be source-bearing")
        if kind == "grant" and state != "present":
            raise ValueError("grant evidence can only establish present")
        if kind == "probe" and state not in {"working", "unavailable"}:
            raise ValueError("probe evidence must establish working or unavailable")
        if kind not in {"grant", "probe"}:
            raise ValueError(f"unsupported capability evidence kind: {kind}")
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
    ):
        if read["state"] not in {"malformed", "unreadable"}:
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
                    {"settings": str(settings_path), "package": item, "version": _clean_version(item)}
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
    )
    result["resolved_installations"] = resolved
    primary = next(
        (item for item in registrations if item["settings"] == str(project / ".pi/settings.json")),
        registrations[0] if registrations else None,
    )
    runtime_paths = [pathlib.Path(path) for path in result["runtime_paths"]]
    selected = next(
        (
            item for item in resolved
            if any(_path_within(path, pathlib.Path(item["root"])) for path in runtime_paths)
        ),
        None,
    )
    if selected is None and primary and primary["version"]:
        selected = next(
            (item for item in resolved if item["version"] == primary["version"]),
            None,
        )
    if selected is None and len(resolved) == 1:
        selected = resolved[0]
    result["resolved_version"] = selected["version"] if selected else None
    result["resolved_version_source"] = (
        str(pathlib.Path(selected["root"]) / ".claude-plugin/plugin.json") if selected else ""
    )
    result["stale_resolved_installations"] = [item for item in resolved if item != selected]
    result["package_roots"] = (
        [selected["root"]] if selected else [item["root"] for item in resolved]
    )
    if resolved:
        source = selected["root"] if selected else "; ".join(item["root"] for item in resolved)
        result["installation"] = {"state": "present", "source": source}

    if primary:
        result["enablement"] = {"state": "present", "source": str(primary["settings"])}
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
    elif result["resolved_version"]:
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
    settings_records: list[dict[str, str]] = []
    enabled_records: list[dict[str, str]] = []
    valid_settings_sources: list[str] = []
    for scope, settings_path in (
        ("project", project / ".claude/settings.json"),
        ("user", home / ".claude/settings.json"),
    ):
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
        crew_marketplace = marketplaces.get("crew")
        if "crew" in marketplaces:
            source = (
                crew_marketplace.get("source")
                if isinstance(crew_marketplace, dict)
                else None
            )
            if not isinstance(crew_marketplace, dict) or not _is_crew_marketplace_source(
                source
            ):
                _mark_config_malformed(
                    result,
                    settings_path,
                    f"extraKnownMarketplaces.crew source must identify {CREW_REPO}",
                )
            else:
                valid_settings_sources.append(str(settings_path))
        if "crew" in marketplaces or "crew@crew" in enabled:
            settings_records.append({"scope": scope, "path": str(settings_path)})
        if enabled.get("crew@crew") is True:
            enabled_records.append({"scope": scope, "path": str(settings_path)})
    result["settings_records"] = settings_records
    result["enabled_scopes"] = enabled_records
    registry_path = home / ".claude/plugins/known_marketplaces.json"
    registry = _record_config_read(
        result,
        "Claude marketplace registry configuration",
        _read_json(registry_path, {}),
    )
    if not isinstance(registry, dict):
        _mark_config_malformed(result, registry_path, "marketplace registry must be a mapping")
        registry = {}
    record = registry.get("crew", {})
    if not isinstance(record, dict):
        _mark_config_malformed(result, registry_path, "crew marketplace record must be a mapping")
        record = {}
    registry_source_valid = False
    if record:
        registry_source_valid = _is_crew_marketplace_source(record.get("source"))
        if not registry_source_valid:
            _mark_config_malformed(
                result,
                registry_path,
                f"crew marketplace source must identify {CREW_REPO}",
            )
    crew_identity_valid = registry_source_valid or (
        not record and bool(valid_settings_sources)
    )
    if enabled_records and (crew_identity_valid or valid_settings_sources):
        selected_enablement = next(
            (record for record in enabled_records if record["scope"] == "project"),
            enabled_records[0],
        )
        result["enablement"] = {
            "state": "present",
            "source": selected_enablement["path"],
        }
        result["enabled_scope"] = selected_enablement["scope"]
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
            "crew marketplace installLocation must be a non-empty string",
        )
        raw_location = None
    location = pathlib.Path(raw_location) if raw_location else pathlib.Path()
    result["served_version"] = (
        _record_manifest_read(result, _manifest_version(location))
        if registry_source_valid and str(location) not in {"", "."}
        else None
    )
    result["served_version_source"] = (
        str(location / ".claude-plugin/plugin.json") if result["served_version"] else ""
    )
    if result["served_version"]:
        result["installation"] = {"state": "present", "source": str(location)}

    installed_path = home / ".claude/plugins/installed_plugins.json"
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
    registrations = plugins.get("crew@crew", [])
    if not isinstance(registrations, list):
        _mark_config_malformed(
            result,
            installed_path,
            "crew@crew registrations must be a sequence",
        )
        registrations = []
    result["registrations"] = registrations
    valid_registrations: list[dict[str, Any]] = []
    installed_records: list[dict[str, Any]] = []
    by_root: dict[pathlib.Path, dict[str, Any]] = {}
    if registrations and not crew_identity_valid:
        _mark_config_malformed(
            result,
            installed_path,
            f"crew@crew registrations require a validated {CREW_REPO} marketplace source",
        )
    for index, registration in enumerate(result["registrations"]):
        if not isinstance(registration, dict):
            _mark_config_malformed(
                result,
                installed_path,
                f"crew@crew registration {index} must be a mapping",
            )
            continue
        install_path = registration.get("installPath")
        if not isinstance(install_path, str) or not install_path.strip():
            _mark_config_malformed(
                result,
                installed_path,
                f"crew@crew registration {index} installPath must be a non-empty string",
            )
            continue
        valid = True
        scope = registration.get("scope")
        if scope not in {"local", "project", "user"}:
            _mark_config_malformed(
                result,
                installed_path,
                f"crew@crew registration {index} scope must be local, project, or user",
            )
            valid = False
        project_path = registration.get("projectPath")
        if project_path is not None and (
            not isinstance(project_path, str) or not project_path.strip()
        ):
            _mark_config_malformed(
                result,
                installed_path,
                f"crew@crew registration {index} projectPath must be a non-empty string",
            )
            valid = False
        if scope in {"local", "project"} and project_path is None:
            _mark_config_malformed(
                result,
                installed_path,
                f"crew@crew registration {index} projectPath is required for {scope} scope",
            )
            valid = False
        raw_registration_version = registration.get("version")
        if (
            not isinstance(raw_registration_version, str)
            or _clean_version(raw_registration_version) is None
        ):
            _mark_config_malformed(
                result,
                installed_path,
                f"crew@crew registration {index} version must be a SemVer string",
            )
            valid = False
        if not valid or not crew_identity_valid:
            continue
        valid_registrations.append(registration)
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
            registration_version = _clean_version(raw_registration_version)
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
    validated_roots = [pathlib.Path(record["root"]) for record in installed_records]
    if result["served_version"]:
        validated_roots.append(location)
    _record_runtime(result, runtime, validated_roots)
    runtime_paths = [pathlib.Path(path) for path in result["runtime_paths"]]
    runtime_matches = [
        record
        for record in installed_records
        if any(_path_within(path, pathlib.Path(record["root"])) for path in runtime_paths)
    ]
    selected_installed = runtime_matches[0] if len(runtime_matches) == 1 else None
    if selected_installed is None and result["served_version"]:
        marketplace_matches = [
            record
            for record in installed_records
            if pathlib.Path(record["root"]).resolve(strict=False)
            == location.resolve(strict=False)
        ]
        if len(marketplace_matches) == 1:
            selected_installed = marketplace_matches[0]
    if selected_installed is None:
        for scope in ("local", "project", "user"):
            scoped_roots = {
                pathlib.Path(registration["installPath"]).resolve(strict=False)
                for registration in valid_registrations
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

    if result["installation"]["state"] != "present":
        return result
    result["status"] = "OK" if result["enablement"]["state"] == "present" else "DEGRADED"
    if len(enabled_records) > 1:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            "Crew is enabled in multiple Claude settings scopes; project precedence selected",
            *(record["path"] for record in enabled_records),
        )
    if (
        result["enablement"]["state"] != "present"
        and not _has_config_read_failure(result, "Claude project settings")
        and not _has_config_read_failure(result, "Claude user settings")
    ):
        _add_finding(
            result,
            "Crew is installed for Claude but not enabled in an inspected scope",
            result["installation"].get("source", ""),
            *(record["path"] for record in settings_records),
        )
    if len(valid_registrations) > 1:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"installed_plugins.json contains {len(valid_registrations)} Crew scope registrations",
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
        _clean_version(registration.get("version"))
        for registration in valid_registrations
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
    candidate_directories = (
        {path.parent.name for path in catalogue.glob("*/SKILL.md")}
        if catalogue.is_dir()
        else set()
    )
    if len(expected) < 10 or not expected <= candidate_directories:
        return False, []
    names, failures = _catalogue_skill_names(catalogue)
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
    crew_market = marketplaces.get("crew", {})
    crew_plugin = plugins.get("crew@crew", {})
    if not isinstance(crew_market, dict):
        _mark_config_malformed(result, config_path, "marketplaces.crew must be a mapping")
        crew_market = {}
    if not isinstance(crew_plugin, dict):
        _mark_config_malformed(result, config_path, 'plugins."crew@crew" must be a mapping')
        crew_plugin = {}
    raw_source = crew_market.get("source")
    crew_source_valid = _is_crew_marketplace_source(raw_source)
    if crew_market and not crew_source_valid:
        _mark_config_malformed(
            result,
            config_path,
            f"marketplaces.crew.source must identify {CREW_REPO}",
        )
    raw_ref = crew_market.get("ref")
    if raw_ref is not None and (
        not isinstance(raw_ref, str) or _clean_version(raw_ref) is None
    ):
        _mark_config_malformed(
            result,
            config_path,
            "marketplaces.crew.ref must be a SemVer string",
        )
        raw_ref = None
    raw_enabled = crew_plugin.get("enabled")
    if raw_enabled is not None and not isinstance(raw_enabled, bool):
        _mark_config_malformed(result, config_path, 'plugins."crew@crew".enabled must be boolean')
        raw_enabled = None
    cache_base = home / ".codex/plugins/cache/crew/crew"
    cache_roots = sorted(
        (path for path in cache_base.glob("*") if path.is_dir()),
        key=lambda path: _version_tuple(path.name) or (0, 0, 0, 0, ()),
    )
    result["configured_version"] = _clean_version(raw_ref)
    manifest_versions = {
        root: _record_manifest_read(result, _manifest_version(root))
        for root in cache_roots
        if crew_source_valid
    }
    valid_cache_roots = [
        root
        for root in cache_roots
        if manifest_versions.get(root) and (root / "skills").is_dir()
    ]
    vendored_catalogues: list[pathlib.Path] = []
    for catalogue in (project / ".agents/skills", home / ".agents/skills"):
        complete, reads = _inspect_crew_catalogue(catalogue)
        result["catalogue_reads"].extend(reads)
        if complete:
            vendored_catalogues.append(catalogue)
    _record_runtime(result, runtime, [*valid_cache_roots, *vendored_catalogues])
    runtime_paths = [pathlib.Path(path) for path in result["runtime_paths"]]
    resolved_root = next(
        (root for root in valid_cache_roots if any(_path_within(path, root) for path in runtime_paths)),
        None,
    )
    if resolved_root is None and result["configured_version"]:
        resolved_root = next(
            (
                root
                for root in valid_cache_roots
                if (manifest_versions[root] or _clean_version(root.name)) == result["configured_version"]
            ),
            None,
        )
    if resolved_root is None and not result["configured_version"] and len(valid_cache_roots) == 1:
        resolved_root = valid_cache_roots[0]
    result["cache_roots"] = [str(path) for path in cache_roots]
    result["stale_cache_roots"] = [str(path) for path in valid_cache_roots if path != resolved_root]
    result["package_roots"] = (
        [str(resolved_root)] if resolved_root else [str(path) for path in valid_cache_roots]
    )
    if resolved_root:
        result["installation"] = {"state": "present", "source": str(resolved_root / "skills")}
        result["resolved_version"] = manifest_versions[resolved_root] or _clean_version(resolved_root.name)
        result["resolved_version_source"] = str(resolved_root / ".claude-plugin/plugin.json")
    else:
        result["resolved_version"] = None
        result["resolved_version_source"] = ""
        if valid_cache_roots:
            result["installation"] = {
                "state": "present",
                "source": "; ".join(str(root / "skills") for root in valid_cache_roots),
            }
        if vendored_catalogues:
            result["installation"] = {
                "state": "present",
                "source": str(vendored_catalogues[0]),
            }
            result["package_roots"].append(str(vendored_catalogues[0]))
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
    if len(cache_roots) > 1:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"Codex has {len(cache_roots)} Crew plugin-cache versions",
            *(str(root) for root in cache_roots),
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
    runtime_fixtures = runtime_fixtures or {}
    capability_evidence = capability_evidence or {}
    harnesses = {
        "pi": _inspect_pi(project_root, home, runtime_fixtures.get("pi")),
        "claude": _inspect_claude(project_root, home, runtime_fixtures.get("claude")),
        "codex": _inspect_codex(project_root, home, runtime_fixtures.get("codex")),
    }
    for harness, result in harnesses.items():
        _degrade_for_read_failures(result)
        _record_capabilities(
            result,
            harness,
            capability_evidence.get(harness, []),
            project_root / ".agents/skills",
        )
    evidence: list[dict[str, str]] = []
    checks: list[dict[str, Any]] = []
    for harness, result in harnesses.items():
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
            item = _evidence("untested" if untested else "observed", fact, observation.get("source", ""))
            evidence.append(item)
            checks.append(
                {
                    "check": f"{harness}.{dimension}",
                    "status": status,
                    "fact": fact,
                    "inference": "" if untested else f"evidence supports {state}",
                    "recommendation": recommendation,
                    "untested": untested,
                    "evidence": [{"claim": fact, "source": observation.get("source", "")}],
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
        if result.get("loaded_version"):
            selected_version = result["loaded_version"]
            selected_source = result.get("loaded_version_source", "")
        elif result.get("resolved_version"):
            selected_version = result["resolved_version"]
            selected_source = result.get("resolved_version_source", "")
        else:
            selected_version = result.get("served_version") or result.get("installed_version")
            selected_source = (
                result.get("served_version_source", "")
                if result.get("served_version")
                else result.get("installed_version_source", "")
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
        top = f"Resolve the {degraded[0]} installation finding, then rerun the free checks"
    else:
        top = "Healthy installation evidence; run only authorized runtime probes still marked untested"
    return {"harnesses": harnesses, "checks": checks, "evidence": evidence, "top_actions": [top]}


def load_runtime_fixture(path: pathlib.Path) -> dict[str, Any]:
    fixture = _read_json(pathlib.Path(path), {}).value
    if fixture.get("schema_version") != 1 or fixture.get("harness") not in {"claude", "codex", "pi"}:
        raise ValueError(f"unsupported runtime fixture: {path}")
    return fixture


def parse_codex_prompt_capture(path: pathlib.Path) -> dict[str, Any]:
    """Parse the free `codex debug prompt-input` JSON protocol into a fixture."""
    payload = _read_json(pathlib.Path(path), None).value
    if not isinstance(payload, list):
        raise ValueError("Codex prompt capture must be the top-level JSON message array")
    source_text = None
    for message in payload:
        if not isinstance(message, dict):
            continue
        for part in message.get("content", []):
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


def compare_runtime_catalog(
    disk_entries: list[dict[str, Any]],
    runtime_fixture: dict[str, Any],
) -> dict[str, Any]:
    """Compare one harness's disk and runtime catalogues in both directions."""
    harness = runtime_fixture.get("harness")
    if harness not in {"claude", "codex", "pi"}:
        raise ValueError("runtime fixture must name exactly one supported harness")
    expected = _expected_catalog(disk_entries, harness)
    if runtime_fixture.get("tested") is False:
        return {
            "harness": harness,
            "status": "N/A",
            "expected_count": len(expected),
            "visible_count": 0,
            "entries": [
                {"runtime_name": name, "state": "not tested", "disk": entry}
                for name, entry in expected
            ],
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
        elif not runtime.get("description"):
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
                "state": "present",
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
        "capture": {
            "source_command": runtime_fixture.get("source_command", "captured runtime catalogue"),
            "captured_at": runtime_fixture.get("captured_at"),
            "cost": runtime_fixture.get("cost", "unknown"),
        },
    }


def declared_local_slots(package_root: pathlib.Path) -> dict[str, Any]:
    declared: set[str] = set()
    sources: list[str] = []
    reads: list[dict[str, str]] = []
    for path in pathlib.Path(package_root).glob("skills/*/SKILL.md"):
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
        raw_slots = frontmatter.get("expects-local", "")
        if isinstance(raw_slots, list):
            if any(not isinstance(slot, str) or not slot.strip() for slot in raw_slots):
                reads.append(
                    {
                        "state": "malformed",
                        "source": str(path),
                        "detail": "expects-local entries must be non-empty strings",
                    }
                )
            slots = [
                slot.strip()
                for slot in raw_slots
                if isinstance(slot, str) and slot.strip()
            ]
        else:
            if not isinstance(raw_slots, str):
                reads.append(
                    {
                        "state": "malformed",
                        "source": str(path),
                        "detail": "expects-local must be a string sequence",
                    }
                )
                continue
            slots = parse_inline_list(raw_slots)
            if raw_slots and not slots:
                reads.append(
                    {
                        "state": "malformed",
                        "source": str(path),
                        "detail": "expects-local must be a string sequence",
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
        "reads": reads,
    }


def profile_for(working_capabilities: list[str], persona_evidence: list[str]) -> str:
    """One taxonomy: personas takes deterministic precedence over platform."""
    if persona_evidence:
        return "personas"
    if working_capabilities:
        return "platform"
    return "portable"


def _role_string_list(value: Any) -> list[str] | None:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return None


def inspect_role_postures(
    package_root: pathlib.Path,
    consumer_root: pathlib.Path | None = None,
) -> list[dict[str, Any]]:
    """Return effective posture evidence from resolved harness role files."""
    try:
        from .role_contract import FORBIDDEN_RUNTIME_KEYS, WRITE_POSTURES, effective_posture
    except ImportError:
        from role_contract import FORBIDDEN_RUNTIME_KEYS, WRITE_POSTURES, effective_posture

    package_root = pathlib.Path(package_root)
    has_consumer_root = consumer_root is not None
    consumer_root = pathlib.Path(consumer_root) if consumer_root else package_root
    rows: list[dict[str, Any]] = []
    harness_roots = (
        ("claude", package_root / "agents", consumer_root / ".claude/agents"),
        ("pi", package_root / "pi-agents", consumer_root / ".pi/agents"),
    )
    targets = [
        (name, harness, distributed, overlay)
        for name in EXPECTED_ROLE_NAMES
        for harness, distributed, overlay in harness_roots
    ]
    targets.extend(
        (path.stem, harness, distributed, overlay)
        for harness, distributed, overlay in harness_roots
        if overlay.is_dir()
        for path in sorted(overlay.glob("*.md"))
        if path.stem not in EXPECTED_ROLE_NAMES
    )
    if has_consumer_root:
        neutral_root = consumer_root / "agents"
        targets.extend(
            (path.stem, "neutral", neutral_root, neutral_root)
            for path in sorted(neutral_root.glob("*.md"))
        )

    for name, harness, distributed, overlay in targets:
        overlay_path = overlay / f"{name}.md"
        is_consumer_role = overlay_path.is_file()
        path = overlay_path if is_consumer_role else distributed / f"{name}.md"
        errors: list[str] = []
        try:
            metadata, error = read_frontmatter(path)
        except (OSError, UnicodeDecodeError) as exception:
            metadata, error = None, f"role file is unreadable: {exception}"
        if error:
            errors.append(error)
        if not isinstance(metadata, dict):
            metadata = {}
        if metadata.get("name") != name:
            errors.append(f"name must be {name}")
        if not isinstance(metadata.get("description"), str) or not metadata["description"].strip():
            errors.append("description must be a non-empty string")
        forbidden = sorted(key for key in metadata if key in FORBIDDEN_RUNTIME_KEYS)
        if forbidden:
            errors.append(f"forbidden runtime keys: {', '.join(forbidden)}")

        writes: str | None = None
        if harness == "neutral":
            writes = "neutral"
        elif harness == "claude":
            denied = _role_string_list(metadata.get("disallowedTools", ""))
            if denied is None:
                errors.append("disallowedTools must be a string sequence")
            else:
                matches = [
                    mode
                    for mode, contract in WRITE_POSTURES.items()
                    if set(denied) == set(contract["claude"]["denied"])
                ]
                writes = matches[0] if len(matches) == 1 else None
        else:
            allowed = _role_string_list(metadata.get("tools"))
            if allowed is None:
                errors.append("tools must be a string sequence")
            else:
                effective_allowed = set(allowed) - {"subagent"}
                matches = [
                    mode
                    for mode, contract in WRITE_POSTURES.items()
                    if effective_allowed == set(contract["pi"]["allowed"])
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
            rows.append(
                {
                    "name": name,
                    **effective_posture(writes, harness),
                    "source": str(path),
                    "scope": "consumer" if is_consumer_role else "crew",
                    "role_valid": True,
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
) -> dict[str, Any]:
    """Compose all Doctor checks into one deterministic, non-persisted report."""
    report = deepcopy(installation_report)
    checks = report["checks"]

    for comparison in runtime_comparisons:
        capture = comparison.get("capture", {})
        capture_source = str(capture.get("source_command", "captured runtime catalogue"))
        for entry in comparison["entries"]:
            state = entry["state"]
            status = "OK" if state == "working" else "N/A" if state == "not tested" else "DEGRADED"
            fact = f"{entry['runtime_name']} runtime entry is {state}"
            sources = [capture_source]
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
            "evidence": [
                {
                    "claim": f"local-slot declaration is {read['state']}: {read['detail']}",
                    "source": read["source"],
                }
                for read in slot_reads
            ] or [{"claim": slot_fact, "source": ""}],
        }
    )

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
    for posture in role_postures:
        key = (str(posture.get("harness") or ""), str(posture.get("name") or ""))
        posture_index.setdefault(key, []).append(posture)
    for harness in ("claude", "pi"):
        for name in EXPECTED_ROLE_NAMES:
            matches = posture_index.get((harness, name), [])
            ready = len(matches) == 1 and _complete_role_posture(matches[0], harness, name)
            if ready:
                posture = matches[0]
                fact = f"{harness} role {name}: {posture['write_effect']}; {posture['caveat']}"
                inference = "effective tool posture matches the rendered role contract"
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
                    ] or [{"claim": fact, "source": ""}],
                }
            )

    fleet_keys = {
        (harness, name)
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
        ready = len(matches) == 1 and _complete_role_posture(matches[0], harness, name)
        if ready:
            posture = matches[0]
            fact = f"{harness} consumer role {name}: {posture['write_effect']}; {posture['caveat']}"
            inference = (
                "neutral role metadata is valid; effective tools remain harness-dependent"
                if harness == "neutral"
                else "effective tool posture matches the resolved consumer role contract"
            )
        else:
            fact = f"{harness} consumer role {name} posture evidence is incomplete or duplicated"
            inference = "consumer role readiness cannot be established"
        sources = [
            str(posture.get("source", ""))
            for posture in matches
            if posture.get("source")
        ]
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
                ] or [{"claim": fact, "source": ""}],
            }
        )

    working = [item["name"] for item in capability_checks if item["state"] == "working"]
    report["profile"] = profile_for(working, persona_evidence)
    profile_fact = f"operating profile is {report['profile']}"
    if persona_evidence:
        profile_sources = persona_evidence
    else:
        profile_sources = [
            evidence["source"]
            for item in capability_checks
            if item["state"] == "working"
            for evidence in item["evidence"]
        ]
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
            ] or [{"claim": profile_fact, "source": ""}],
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
                f"{item['claim']} (source: {item['source'] or 'not recorded'})"
                for item in row["evidence"]
            ),
        ]
        lines.append("| " + " | ".join(str(field).replace("|", "\\|") or "—" for field in fields) + " |")
    lines.append("")
    lines.append(f"Profile: {report['profile']}")
    lines.append("")
    lines.append(f"Top action: {top_actions[0]}")
    return "\n".join(lines) + "\n"
