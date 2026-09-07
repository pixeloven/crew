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
from typing import Any

try:
    from .frontmatter import parse_inline_list, parse_simple_mapping, read_frontmatter
except ImportError:  # Direct script execution.
    from frontmatter import parse_inline_list, parse_simple_mapping, read_frontmatter


CREW_REPO = "pixeloven/crew"
FIRST_PI_ROLE_DISCOVERY_VERSION = (0, 35, 0)
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


def _read_json(path: pathlib.Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _read_toml(path: pathlib.Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, tomllib.TOMLDecodeError, OSError):
        return {}


def _manifest_version(root: pathlib.Path) -> str | None:
    value = _read_json(root / ".claude-plugin/plugin.json", {})
    version = value.get("version") if isinstance(value, dict) else None
    return str(version) if version is not None else None


def _clean_version(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(?:^|@)v?(\d+\.\d+\.\d+)(?:$|[^0-9])", value)
    return match.group(1) if match else None


def _version_tuple(value: str | None) -> tuple[int, int, int] | None:
    clean = _clean_version(value)
    return tuple(map(int, clean.split("."))) if clean else None


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


def _record_runtime(result: dict[str, Any], runtime: dict[str, Any] | None) -> None:
    """Record only evidence supplied by this harness's capture."""
    if runtime is None or runtime.get("tested") is False:
        return
    state = runtime.get("state")
    if state in {"not-tested", "not tested"}:
        result["runtime"] = {
            "state": "not tested",
            "source": runtime.get("source", "captured runtime"),
        }
        return
    if state is None:
        skills = runtime.get("skills")
        if not isinstance(skills, list):
            state = "unavailable"
        else:
            crew_entries = [
                entry
                for entry in skills
                if isinstance(entry, dict)
                and (
                    str(entry.get("name", "")).startswith("crew:")
                    or entry.get("namespace") == "crew"
                    or entry.get("source") == "foundation"
                    or re.search(r"(?:pixeloven/crew|/crew/crew/)", str(entry.get("path", "")))
                )
            ]
            if not crew_entries:
                state = "omitted"
            elif any(not entry.get("description") for entry in crew_entries):
                state = "loaded-but-undiscoverable"
            else:
                state = "working"
    if state not in {
        "present",
        "working",
        "unavailable",
        "loaded-but-undiscoverable",
        "truncated",
        "omitted",
    }:
        raise ValueError(f"unsupported runtime state: {state}")
    result["runtime"] = {"state": state, "source": runtime.get("source", "captured runtime")}
    if state in LOADED_RUNTIME_STATES and runtime.get("version"):
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


def _declared_capabilities(roots: list[pathlib.Path]) -> dict[str, list[str]]:
    declared: dict[str, list[str]] = {}
    for root in dict.fromkeys(roots):
        catalogue = root if root.name == "skills" else root / "skills"
        for skill in sorted(catalogue.glob("*/SKILL.md")):
            metadata, error = read_frontmatter(skill)
            if error or not metadata:
                continue
            requirements = metadata.get("requires", [])
            if isinstance(requirements, str):
                requirements = parse_inline_list(requirements)
            if not isinstance(requirements, list):
                continue
            for requirement in requirements:
                if isinstance(requirement, str) and requirement:
                    declared.setdefault(requirement, []).append(str(skill))
    return declared


def _record_capabilities(
    result: dict[str, Any],
    harness: str,
    supplied: list[dict[str, str]],
) -> None:
    declared = _declared_capabilities([pathlib.Path(root) for root in result["package_roots"]])
    observations: dict[str, dict[str, str]] = {}
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
        if name in observations:
            raise ValueError(f"duplicate {harness} capability evidence: {name}")
        observations[name] = observation

    checks: list[dict[str, Any]] = []
    for name, declaration_sources in sorted(declared.items()):
        observation = observations.get(name)
        state = observation["state"] if observation else "not tested"
        sources = [observation["source"]] if observation else declaration_sources
        checks.append(
            {
                "harness": harness,
                "name": name,
                "state": state,
                "evidence": [
                    {
                        "claim": f"{harness} capability {name} is {state}",
                        "source": source,
                    }
                    for source in dict.fromkeys(sources)
                ],
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


def _inspect_pi(project: pathlib.Path, home: pathlib.Path, runtime: dict[str, Any] | None) -> dict[str, Any]:
    result = _base_harness()
    _record_runtime(result, runtime)
    settings_paths = [project / ".pi/settings.json", home / ".pi/settings.json"]
    settings_paths.extend(sorted((home / ".pi").glob("*/settings.json")))
    registrations: list[dict[str, str | None]] = []
    for settings_path in dict.fromkeys(settings_paths):
        settings = _read_json(settings_path, {})
        packages = settings.get("packages", []) if isinstance(settings, dict) else []
        for item in packages:
            if isinstance(item, str) and re.search(r"(?:github\.com/|github:)?pixeloven/crew(?:@|$)", item):
                registrations.append(
                    {"settings": str(settings_path), "package": item, "version": _clean_version(item)}
                )
    result["registrations"] = registrations
    checkouts = sorted((home / ".pi").glob("*/git/github.com/pixeloven/crew"))
    resolved = [
        {"root": str(checkout), "version": _manifest_version(checkout)}
        for checkout in checkouts
        if _manifest_version(checkout)
    ]
    result["resolved_installations"] = resolved
    primary = next(
        (item for item in registrations if item["settings"] == str(project / ".pi/settings.json")),
        registrations[0] if registrations else None,
    )
    runtime_paths = _runtime_paths(runtime)
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
    _record_runtime(result, runtime)
    settings_records: list[dict[str, str]] = []
    for scope, settings_path in (
        ("project", project / ".claude/settings.json"),
        ("user", home / ".claude/settings.json"),
    ):
        settings = _read_json(settings_path, {})
        enabled = settings.get("enabledPlugins", {}) if isinstance(settings, dict) else {}
        marketplaces = settings.get("extraKnownMarketplaces", {}) if isinstance(settings, dict) else {}
        if "crew" in marketplaces or "crew@crew" in enabled:
            settings_records.append({"scope": scope, "path": str(settings_path)})
        if enabled.get("crew@crew") is True:
            result["enablement"] = {"state": "present", "source": str(settings_path)}
            result["enabled_scope"] = scope
    result["settings_records"] = settings_records

    registry_path = home / ".claude/plugins/known_marketplaces.json"
    registry = _read_json(registry_path, {})
    record = registry.get("crew", {}) if isinstance(registry, dict) else {}
    # This registry is location metadata. Never synthesize a version from it.
    result["marketplace_registry_records"] = [
        {key: record[key] for key in ("source", "installLocation", "lastUpdated") if key in record}
    ] if record else []
    location = pathlib.Path(record.get("installLocation", "")) if isinstance(record, dict) else pathlib.Path()
    result["served_version"] = _manifest_version(location) if str(location) not in {"", "."} else None
    result["served_version_source"] = (
        str(location / ".claude-plugin/plugin.json") if result["served_version"] else ""
    )
    if result["served_version"]:
        result["installation"] = {"state": "present", "source": str(location)}

    installed_path = home / ".claude/plugins/installed_plugins.json"
    installed = _read_json(installed_path, {})
    plugins = installed.get("plugins", {}) if isinstance(installed, dict) else {}
    registrations = plugins.get("crew@crew", []) if isinstance(plugins, dict) else []
    result["registrations"] = registrations if isinstance(registrations, list) else []
    installed_records: list[dict[str, Any]] = []
    by_root: dict[pathlib.Path, dict[str, Any]] = {}
    for registration in result["registrations"]:
        if not isinstance(registration, dict) or not isinstance(registration.get("installPath"), str):
            continue
        root = pathlib.Path(registration["installPath"])
        manifest_version = _manifest_version(root)
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
        raw_registration_version = registration.get("version")
        if raw_registration_version:
            registration_version = (
                _clean_version(str(raw_registration_version)) or str(raw_registration_version)
            )
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
    installed_records.extend(by_root.values())
    result["installed_versions"] = installed_records
    runtime_paths = _runtime_paths(runtime)
    selected_installed = next(
        (
            record
            for record in installed_records
            if any(_path_within(path, pathlib.Path(record["root"])) for path in runtime_paths)
        ),
        None,
    )
    if selected_installed is None and result["served_version"]:
        selected_installed = next(
            (record for record in installed_records if pathlib.Path(record["root"]) == location),
            None,
        )
    if selected_installed is None and installed_records:
        selected_installed = installed_records[0]
    result["installed_version"] = selected_installed["version"] if selected_installed else None
    result["installed_version_source"] = selected_installed["source"] if selected_installed else ""
    if selected_installed:
        result["installation"] = {"state": "present", "source": selected_installed["root"]}
    result["package_roots"] = [record["root"] for record in installed_records]
    if result.get("served_version") and location not in by_root:
        result["package_roots"].append(str(location))

    if result["installation"]["state"] != "present":
        return result
    result["status"] = "OK" if result["enablement"]["state"] == "present" else "DEGRADED"
    if result["enablement"]["state"] != "present":
        _add_finding(
            result,
            "Crew is installed for Claude but not enabled in an inspected scope",
            result["installation"].get("source", ""),
            *(record["path"] for record in settings_records),
        )
    if len(result["registrations"]) > 1:
        result["status"] = "DEGRADED"
        _add_finding(
            result,
            f"installed_plugins.json contains {len(result['registrations'])} Crew scope registrations",
            str(installed_path),
        )
    registration_versions = {
        _clean_version(str(registration.get("version"))) or str(registration.get("version"))
        for registration in result["registrations"]
        if isinstance(registration, dict) and registration.get("version")
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


def _catalogue_skill_names(catalogue: pathlib.Path) -> set[str]:
    names: set[str] = set()
    if not catalogue.is_dir():
        return names
    for skill in catalogue.glob("*/SKILL.md"):
        metadata, error = read_frontmatter(skill)
        if not error and metadata and metadata.get("name") == skill.parent.name:
            names.add(skill.parent.name)
    return names


def _is_complete_crew_catalogue(catalogue: pathlib.Path) -> bool:
    distributed = pathlib.Path(__file__).resolve().parents[1] / "skills"
    expected = _catalogue_skill_names(distributed)
    return len(expected) >= 10 and expected <= _catalogue_skill_names(catalogue)


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
    _record_runtime(result, runtime)
    config_path = home / ".codex/config.toml"
    config = _read_toml(config_path)
    marketplaces = config.get("marketplaces", {}) if isinstance(config, dict) else {}
    plugins = config.get("plugins", {}) if isinstance(config, dict) else {}
    crew_market = marketplaces.get("crew", {}) if isinstance(marketplaces, dict) else {}
    crew_plugin = plugins.get("crew@crew", {}) if isinstance(plugins, dict) else {}
    cache_base = home / ".codex/plugins/cache/crew/crew"
    cache_roots = sorted(
        (path for path in cache_base.glob("*") if path.is_dir()),
        key=lambda path: _version_tuple(path.name) or (0, 0, 0),
    )
    result["configured_version"] = _clean_version(crew_market.get("ref")) if isinstance(crew_market, dict) else None
    valid_cache_roots = [root for root in cache_roots if _manifest_version(root) and (root / "skills").is_dir()]
    runtime_paths = _runtime_paths(runtime)
    resolved_root = next(
        (root for root in valid_cache_roots if any(_path_within(path, root) for path in runtime_paths)),
        None,
    )
    if resolved_root is None and result["configured_version"]:
        resolved_root = next(
            (
                root
                for root in valid_cache_roots
                if (_manifest_version(root) or _clean_version(root.name)) == result["configured_version"]
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
        result["resolved_version"] = _manifest_version(resolved_root) or _clean_version(resolved_root.name)
        result["resolved_version_source"] = str(resolved_root / ".claude-plugin/plugin.json")
    else:
        result["resolved_version"] = None
        result["resolved_version_source"] = ""
        if valid_cache_roots:
            result["installation"] = {
                "state": "present",
                "source": "; ".join(str(root / "skills") for root in valid_cache_roots),
            }
        for catalogue in (project / ".agents/skills", home / ".agents/skills"):
            if _is_complete_crew_catalogue(catalogue):
                result["installation"] = {"state": "present", "source": str(catalogue)}
                result["package_roots"].append(str(catalogue))
                break
    if isinstance(crew_plugin, dict) and crew_plugin.get("enabled") is True:
        result["enablement"] = {"state": "present", "source": str(config_path)}
    if runtime is not None and runtime.get("tested") is not False:
        result["runtime_skill_roots"] = list(runtime.get("skill_roots", []))

    if result["installation"]["state"] == "present":
        if result["enablement"]["state"] == "present":
            result["status"] = "OK"
        else:
            result["status"] = "DEGRADED"
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
        _record_capabilities(result, harness, capability_evidence.get(harness, []))
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
    fixture = _read_json(pathlib.Path(path), {})
    if fixture.get("schema_version") != 1 or fixture.get("harness") not in {"claude", "codex", "pi"}:
        raise ValueError(f"unsupported runtime fixture: {path}")
    return fixture


def parse_codex_prompt_capture(path: pathlib.Path) -> dict[str, Any]:
    """Parse the free `codex debug prompt-input` JSON protocol into a fixture."""
    payload = _read_json(pathlib.Path(path), None)
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
    unused = set(range(len(visible)))
    rows: list[dict[str, Any]] = []
    absent_state = runtime_fixture.get("state", "omitted")
    if absent_state not in {"omitted", "unavailable", "truncated", "loaded-but-undiscoverable"}:
        absent_state = "omitted"
    for name, disk in expected:
        candidates = [
            index for index in unused if str(visible[index].get("name")) == name
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
                "runtime_name": str(runtime["name"]),
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


def declared_local_slots(package_root: pathlib.Path) -> dict[str, list[str]]:
    declared: set[str] = set()
    sources: list[str] = []
    for path in pathlib.Path(package_root).glob("skills/*/SKILL.md"):
        frontmatter, error = read_frontmatter(path)
        if error or not frontmatter:
            continue
        raw_slots = frontmatter.get("expects-local", "")
        if isinstance(raw_slots, list):
            slots = [slot for slot in raw_slots if isinstance(slot, str)]
        else:
            slots = parse_inline_list(raw_slots) if isinstance(raw_slots, str) else []
        if slots:
            declared.update(slots)
            sources.append(str(path))
    return {
        "declared": sorted(declared),
        "recommended_vocabulary": list(RECOMMENDED_LOCAL_VOCABULARY),
        "sources": sources,
    }


def profile_for(working_capabilities: list[str], persona_evidence: list[str]) -> str:
    """One taxonomy: personas takes deterministic precedence over platform."""
    if persona_evidence:
        return "personas"
    if working_capabilities:
        return "platform"
    return "portable"


def inspect_role_postures(package_root: pathlib.Path) -> list[dict[str, Any]]:
    """Return rendered posture evidence for every neutral Crew role."""
    try:
        from .role_contract import effective_posture
    except ImportError:  # Direct script execution.
        from role_contract import effective_posture

    rows: list[dict[str, Any]] = []
    for path in sorted(pathlib.Path(package_root).glob("roles/*/role.yml")):
        role = parse_simple_mapping(path.read_text(encoding="utf-8"))
        for harness in ("claude", "pi"):
            posture = effective_posture(str(role.get("writes")), harness)
            rows.append({"name": role.get("name"), **posture, "source": str(path)})
    return rows


def _complete_role_posture(posture: dict[str, Any], harness: str, name: str) -> bool:
    try:
        from .role_contract import effective_posture
    except ImportError:
        from role_contract import effective_posture

    writes = posture.get("writes")
    if not isinstance(writes, str):
        return False
    try:
        expected = effective_posture(writes, harness)
    except ValueError:
        return False
    return (
        posture.get("name") == name
        and posture.get("harness") == harness
        and all(posture.get(key) == value for key, value in expected.items())
        and isinstance(posture.get("source"), str)
        and bool(posture["source"])
    )


def compose_doctor_report(
    installation_report: dict[str, Any],
    *,
    runtime_comparisons: list[dict[str, Any]],
    local_slots: dict[str, list[str]],
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
    checks.append(
        {
            "check": "local-slots.declarations",
            "status": "OK",
            "fact": slot_fact,
            "inference": "declared slots remain separate from recommended vocabulary",
            "recommendation": "",
            "untested": "",
            "evidence": [
                {"claim": slot_fact, "source": source}
                for source in local_slots.get("sources", [])
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
