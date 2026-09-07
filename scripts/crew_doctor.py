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
from typing import Any

try:
    from .frontmatter import parse_inline_list, parse_simple_mapping, read_frontmatter
except ImportError:  # Direct script execution.
    from frontmatter import parse_inline_list, parse_simple_mapping, read_frontmatter


CREW_REPO = "pixeloven/crew"
FIRST_PI_ROLE_DISCOVERY_VERSION = (0, 35, 0)
RECOMMENDED_LOCAL_VOCABULARY = ("litellm-access-map", "vault-ops")
PROFILE_TAXONOMY = ("portable", "platform", "personas")


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
        "capabilities": {"state": "not tested", "source": ""},
        "findings": [],
    }


def _record_runtime(result: dict[str, Any], runtime: dict[str, Any] | None) -> None:
    """Record only evidence supplied by this harness's capture."""
    if runtime is None or runtime.get("tested") is False:
        return
    state = runtime.get("state", "working")
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
    if not registrations:
        return result

    primary = next(
        (item for item in registrations if item["settings"] == str(project / ".pi/settings.json")),
        registrations[0],
    )
    result["installation"] = {"state": "present", "source": str(primary["settings"])}
    result["enablement"] = {"state": "present", "source": str(primary["settings"])}
    result["configured_version"] = primary["version"]

    checkouts = sorted((home / ".pi").glob("*/git/github.com/pixeloven/crew"))
    resolved = [
        {"root": str(checkout), "version": _manifest_version(checkout)}
        for checkout in checkouts
        if _manifest_version(checkout)
    ]
    result["resolved_installations"] = resolved
    result["resolved_version"] = resolved[0]["version"] if resolved else None
    if resolved:
        result["installation"]["source"] = str(resolved[0]["root"])

    stale_pins = [
        item for item in registrations
        if _version_tuple(item["version"]) and _version_tuple(item["version"]) < FIRST_PI_ROLE_DISCOVERY_VERSION
    ]
    if stale_pins:
        result["status"] = "DEGRADED"
        result["findings"].append(
            f"configured pin v{stale_pins[0]['version']} predates v0.35.0; "
            "the Pi role fleet is silently invisible below v0.35.0"
        )
    elif result["resolved_version"]:
        result["status"] = "OK"
    else:
        result["status"] = "DEGRADED"
        result["findings"].append("package is configured but its resolved checkout manifest was unavailable")
    if len(registrations) > 1:
        result["status"] = "DEGRADED"
        result["findings"].append(f"Crew is registered in {len(registrations)} Pi settings scopes")
    if (
        result.get("configured_version")
        and result.get("resolved_version")
        and result["configured_version"] != result["resolved_version"]
    ):
        result["status"] = "DEGRADED"
        result["findings"].append(
            f"configured Pi version {result['configured_version']} differs from resolved {result['resolved_version']}"
        )
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
            result["installation"] = {"state": "present", "source": str(settings_path)}
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

    installed_path = home / ".claude/plugins/installed_plugins.json"
    installed = _read_json(installed_path, {})
    plugins = installed.get("plugins", {}) if isinstance(installed, dict) else {}
    registrations = plugins.get("crew@crew", []) if isinstance(plugins, dict) else []
    result["registrations"] = registrations if isinstance(registrations, list) else []
    if result["registrations"]:
        result["installation"] = {"state": "present", "source": str(installed_path)}
    if runtime is not None and runtime.get("tested") is not False:
        result["loaded_version"] = runtime.get("version")
    else:
        result["loaded_version"] = None

    if result["installation"]["state"] != "present":
        return result
    result["status"] = "OK" if result["enablement"]["state"] == "present" else "DEGRADED"
    if result["enablement"]["state"] != "present":
        result["findings"].append("Crew is installed for Claude but not enabled in an inspected scope")
    if len(result["registrations"]) > 1:
        result["status"] = "DEGRADED"
        result["findings"].append(
            f"installed_plugins.json contains {len(result['registrations'])} Crew scope registrations"
        )
    installed_versions = {
        str(record.get("version"))
        for record in result["registrations"]
        if isinstance(record, dict) and record.get("version")
    }
    compared_versions = installed_versions | {
        value for value in (result.get("served_version"), result.get("loaded_version")) if value
    }
    if len(compared_versions) > 1:
        result["status"] = "DEGRADED"
        result["findings"].append(
            f"Claude served/installed/loaded versions disagree: {', '.join(sorted(compared_versions))}"
        )
    return result


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
    resolved_root = cache_roots[-1] if cache_roots else None
    result["cache_roots"] = [str(path) for path in cache_roots]
    if resolved_root and (resolved_root / "skills").is_dir():
        result["installation"] = {"state": "present", "source": str(resolved_root / "skills")}
        result["resolved_version"] = _manifest_version(resolved_root) or _clean_version(resolved_root.name)
    else:
        result["resolved_version"] = None
        for catalogue in (project / ".agents/skills", home / ".agents/skills"):
            if all((catalogue / name / "SKILL.md").is_file() for name in ("doctor", "onboarding")):
                result["installation"] = {"state": "present", "source": str(catalogue)}
                break
    result["configured_version"] = _clean_version(crew_market.get("ref")) if isinstance(crew_market, dict) else None
    if isinstance(crew_plugin, dict) and crew_plugin.get("enabled") is True:
        result["enablement"] = {"state": "present", "source": str(config_path)}
    if runtime is not None and runtime.get("tested") is not False:
        result["loaded_version"] = runtime.get("version")
        result["runtime_skill_roots"] = list(runtime.get("skill_roots", []))

    mcp = config.get("mcp_servers", {}) if isinstance(config, dict) else {}
    litellm = mcp.get("litellm", {}) if isinstance(mcp, dict) else {}
    if isinstance(litellm, dict) and litellm.get("url") and litellm.get("bearer_token_env_var"):
        result["capabilities"] = {"state": "present", "source": str(config_path)}
    else:
        result["capabilities"] = {"state": "unavailable", "source": str(config_path)}

    if result["installation"]["state"] == "present":
        if result["enablement"]["state"] == "present":
            result["status"] = "OK"
        else:
            result["status"] = "DEGRADED"
            result["findings"].append("Crew is installed for Codex but not enabled in inspected config")
    if len(cache_roots) > 1:
        result["status"] = "DEGRADED"
        result["findings"].append(f"Codex has {len(cache_roots)} Crew plugin-cache versions")
    if (
        result.get("configured_version")
        and result.get("resolved_version")
        and result["configured_version"] != result["resolved_version"]
    ):
        result["status"] = "DEGRADED"
        result["findings"].append(
            f"configured Codex version {result['configured_version']} differs "
            f"from resolved {result['resolved_version']}"
        )
    return result


def inspect_installations(
    project_root: pathlib.Path,
    home: pathlib.Path,
    runtime_fixtures: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reconcile configured, installed, enabled, runtime, and grant state."""
    project_root = pathlib.Path(project_root)
    home = pathlib.Path(home)
    runtime_fixtures = runtime_fixtures or {}
    harnesses = {
        "pi": _inspect_pi(project_root, home, runtime_fixtures.get("pi")),
        "claude": _inspect_claude(project_root, home, runtime_fixtures.get("claude")),
        "codex": _inspect_codex(project_root, home, runtime_fixtures.get("codex")),
    }
    evidence: list[dict[str, str]] = []
    for harness, result in harnesses.items():
        evidence.append(
            _evidence(
                "observed",
                f"{harness} installation is {result['installation']['state']}",
                result["installation"].get("source", ""),
            )
        )
        if result["runtime"]["state"] == "not tested":
            evidence.append(_evidence("untested", f"{harness} runtime was not tested"))
    versions = {
        name: result.get("loaded_version")
        or result.get("resolved_version")
        or result.get("served_version")
        for name, result in harnesses.items()
    }
    observed_versions = {value for value in versions.values() if value}
    if len(observed_versions) > 1:
        evidence.append(
            _evidence(
                "observed",
                "cross-harness Crew version skew: "
                + ", ".join(f"{name}={value or 'unknown'}" for name, value in versions.items()),
            )
        )
    missing = [name for name, result in harnesses.items() if result["installation"]["state"] != "present"]
    degraded = [name for name, result in harnesses.items() if result["status"] == "DEGRADED"]
    if missing:
        top = f"Install or locate Crew for {missing[0]}, then rerun the free checks"
    elif degraded:
        top = f"Resolve the {degraded[0]} installation finding, then rerun the free checks"
    else:
        top = "Healthy installation evidence; run only authorized runtime probes still marked untested"
    evidence.append(_evidence("recommendation", top))
    return {"harnesses": harnesses, "evidence": evidence, "top_actions": [top]}


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


def _expected_catalog(disk_entries: list[dict[str, Any]], harness: str) -> dict[str, dict[str, Any]]:
    expected: dict[str, dict[str, Any]] = {}
    ordered = disk_entries
    if harness == "pi":
        # Pi is flat; the project overlay wins over the package on collision.
        ordered = sorted(disk_entries, key=lambda item: item.get("source") == "project")
    for entry in ordered:
        expected[_runtime_name(entry, harness)] = entry
    return expected


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
                for name, entry in expected.items()
            ],
        }

    visible = {
        str(entry["name"]): entry
        for entry in runtime_fixture.get("skills", [])
        if isinstance(entry, dict) and entry.get("name")
    }
    rows: list[dict[str, Any]] = []
    for name, disk in expected.items():
        runtime = visible.get(name)
        if runtime is None:
            state = "omitted"
        elif not runtime.get("description"):
            state = "loaded-but-undiscoverable"
        elif runtime.get("description") == disk.get("description"):
            state = "working"
        elif str(disk.get("description", "")).startswith(str(runtime.get("description", ""))):
            state = "truncated"
        else:
            state = "unavailable"
        rows.append({"runtime_name": name, "state": state, "disk": disk, "runtime": runtime})
    for name, runtime in visible.items():
        if name not in expected:
            rows.append({"runtime_name": name, "state": "present", "disk": None, "runtime": runtime})

    degraded = {"omitted", "truncated", "loaded-but-undiscoverable", "unavailable"}
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
    for path in pathlib.Path(package_root).glob("skills/*/SKILL.md"):
        frontmatter, error = read_frontmatter(path)
        if error or not frontmatter:
            continue
        declared.update(parse_inline_list(frontmatter.get("expects-local", "")))
    return {
        "declared": sorted(declared),
        "recommended_vocabulary": list(RECOMMENDED_LOCAL_VOCABULARY),
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
    lines = [
        "| harness | installation | enablement | resolved runtime | capability grants | "
        "status | repeatable evidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, item in report["harnesses"].items():
        lines.append(
            f"| {name} | {item['installation']['state']} | {item['enablement']['state']} | "
            f"{item['runtime']['state']} | {item['capabilities']['state']} | {item['status']} | "
            f"{item['installation'].get('source') or '—'} |"
        )
    lines.extend(
        [
            "",
            "| fact | inference | recommendation | untested |",
            "|---|---|---|---|",
        ]
    )
    by_kind = {kind: [] for kind in ("observed", "inference", "recommendation", "untested")}
    for item in report["evidence"]:
        by_kind[item["kind"]].append(item["claim"])
    lines.append(
        "| "
        + " | ".join(
            "; ".join(by_kind[kind]) or "—"
            for kind in ("observed", "inference", "recommendation", "untested")
        )
        + " |"
    )
    lines.append("")
    lines.append(f"Top action: {report['top_actions'][0]}")
    return "\n".join(lines) + "\n"
