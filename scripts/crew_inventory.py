#!/usr/bin/env python3
"""Read-only inventory of what an environment has: one engine, three readers.

Onboarding writes its capability map into the `agent-runtime` slot, Doctor
checks that map, and `learn` reads the gaps. The engine reads configuration
and skill files and prints to stdout. It writes nothing. It starts no process
unless `--probe-versions` asks for `<cli> --version`, and it never runs
`claude mcp list` or `codex mcp list`: the first connects to every server.

MCP records carry only a server's name, transport, scope, command basename and
source path. Env, headers, args and URLs are never read into the output.
What a script cannot observe is listed in `not_observable`, and in the dated
table in docs/MAINTAINERS.md.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.parse
from typing import Any, Callable, Iterable, TextIO

try:
    from .check_skills import capability_vocabulary
    from .crew_doctor import (
        _manifest_version,
        _read_json,
        _read_toml,
        _string_list,
        declared_local_slots,
        inspect_packs,
        slot_fills,
    )
    from .frontmatter import read_frontmatter
except ImportError:  # Direct script execution.
    from check_skills import capability_vocabulary
    from crew_doctor import (
        _manifest_version,
        _read_json,
        _read_toml,
        _string_list,
        declared_local_slots,
        inspect_packs,
        slot_fills,
    )
    from frontmatter import read_frontmatter


SCHEMA = "crew-inventory/1"
CREW_ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESSES = ("claude", "codex", "pi")
CAPABILITY_KINDS = ("cli", "mcp", "external")
FILL = "▸ Fill"
MAP_BEGIN = re.compile(r"<!--\s*crew:capability-map begin(?P<attrs>[^>]*?)\s*-->")
MAP_END = re.compile(r"<!--\s*crew:capability-map end\s*-->")
MAP_HEADER = "| Capability | Provider | Kind | State | Fallback (operator command) |"
REMOVAL_LINE = "Pending removal (authorized removal only):"
CAPABILITIES_HEADING = re.compile(r"^##[ \t]+capabilities\b.*$", re.IGNORECASE | re.MULTILINE)
# A workflow `run:` line's first token is a candidate CLI unless it is shell
# syntax, a bash builtin, a function the same block defines, or a tool every
# runner has. Only bash/sh steps are read: another `shell:` (pwsh, python, cmd)
# is a language whose first tokens are not commands on PATH.
SHELL_WORDS = frozenset(
    "if then else elif fi for while until do done case esac in function select "
    "echo printf cd export set unset exit return true false test source eval exec "
    "read shift local declare trap wait sleep pushd popd mkdir rm cp mv cat ls touch "
    "chmod grep sed awk tee head tail sort uniq wc xargs find env sudo time "
    "break continue alias unalias bg fg jobs kill let ulimit umask typeset readonly "
    "getopts hash type command builtin enable caller compgen complete compopt disown "
    "dirs help history logout mapfile readarray shopt suspend times coproc".split()
)
POSIX_SHELLS = frozenset({"bash", "sh"})
# PowerShell's Verb-Noun cmdlets, for a pwsh step on a runner the file cannot name
# (`runs-on: ${{ matrix.os }}`).
CMDLET = re.compile(r"[A-Z][a-z]+-[A-Z][A-Za-z]+")
SHELL_FUNCTION = re.compile(r"^\s*(?:function\s+([A-Za-z_][\w.:-]*)|([A-Za-z_][\w.:-]*)\s*\(\s*\))")
# An external: service a CLI on PATH reaches directly, beside any MCP server or plugin.
EXTERNAL_CLIS = {"github": ("gh",)}
CLI_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=\S*")
BLOCK_INDICATOR = re.compile(r"^[|>][-+0-9]*$")
HEREDOC = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
STATE_RANK = {"present": 0, "disabled": 1, "absent": 2}
KIND_RANK = {"cli": 0, "mcp": 1, "plugin": 2}
NOT_OBSERVABLE = (
    {
        "what": "claude MCP tool lists",
        "why": "in-session only; `claude mcp list` connects to every server, so the engine never "
        "runs it. Pipe an in-session observation with --observations",
    },
    {
        "what": "codex MCP tool lists",
        "why": "in-session only; whether `codex mcp list` stays config-only is unverified, so the "
        "engine never runs it. Pipe an in-session observation with --observations",
    },
    {
        "what": "pi MCP servers",
        "why": "pi reaches MCP through extensions with no config surface the engine reads",
    },
    {
        "what": "session-only MCP servers",
        "why": "connectors granted by the host account or a managed policy are not in config files; "
        "only an in-session observation shows them",
    },
    {
        "what": "MCP reachability and authentication",
        "why": "configuration proves a server is configured, never that it connects or is authorized",
    },
    {
        "what": "external:* providers",
        "why": "matched to MCP servers and plugins by name, and to a known CLI on PATH (gh for "
        "external:github), never by a connection; a match or a miss is an inference",
    },
)


# --- reading helpers -------------------------------------------------------


def _note(reads: list[dict[str, str]], read: Any) -> Any:
    if read.state in {"malformed", "unreadable"}:
        reads.append({"state": read.state, "source": read.source, "detail": read.detail})
    return read.value


def _json_mapping(path: pathlib.Path, reads: list[dict[str, str]]) -> dict[str, Any]:
    value = _note(reads, _read_json(path, {}))
    return value if isinstance(value, dict) else {}


def _toml_mapping(path: pathlib.Path, reads: list[dict[str, str]]) -> dict[str, Any]:
    value = _note(reads, _read_toml(path))
    return value if isinstance(value, dict) else {}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _project_entry(projects: Any, project: pathlib.Path) -> dict[str, Any]:
    projects = _mapping(projects)
    for key in (str(project), str(project.resolve(strict=False))):
        if isinstance(projects.get(key), dict):
            return projects[key]
    return {}


def _same_path(value: Any, project: pathlib.Path) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return pathlib.Path(value).resolve(strict=False) == project.resolve(strict=False)


def _command_basename(value: Any) -> str | None:
    """The executable's basename only: never its arguments, path or inline flags."""
    if not isinstance(value, str) or not value.strip():
        return None
    name = pathlib.PurePath(value.strip().split()[0]).name
    return name if CLI_TOKEN.fullmatch(name) else None


def _transport(entry: dict[str, Any]) -> str:
    declared = entry.get("type", entry.get("transport"))
    if isinstance(declared, str) and re.fullmatch(r"[a-z][a-z-]*", declared):
        return declared
    if entry.get("command"):
        return "stdio"
    if entry.get("url"):
        return "http"
    return "unknown"


def _server(name: str, entry: Any, scope: str, source: pathlib.Path, *, disabled: bool = False) -> dict[str, Any]:
    entry = _mapping(entry)
    if entry.get("enabled") is False:
        disabled = True
    return {
        "name": name,
        "transport": _transport(entry),
        "scope": scope,
        "source": str(source),
        "state": "disabled" if disabled else "present",
        "command": _command_basename(entry.get("command")),
        "tools": None,
        "tools_source": None,
    }


def _servers_from(
    mapping: Any, scope: str, source: pathlib.Path, disabled: Iterable[str] = ()
) -> list[dict[str, Any]]:
    disabled = set(disabled)
    return [
        _server(name, entry, scope, source, disabled=name in disabled)
        for name, entry in sorted(_mapping(mapping).items())
        if isinstance(name, str) and name
    ]


def _mcp_json(path: pathlib.Path, reads: list[dict[str, str]]) -> dict[str, Any]:
    """A `.mcp.json` is `{"mcpServers": {...}}` or, in older plugins, the flat mapping."""
    data = _json_mapping(path, reads)
    return _mapping(data["mcpServers"]) if "mcpServers" in data else data


def _plugin_servers(
    root: pathlib.Path, manifest: pathlib.Path, scope: str, reads: list[dict[str, str]]
) -> list[dict[str, Any]]:
    declared = _json_mapping(manifest, reads).get("mcpServers")
    if isinstance(declared, dict):
        return _servers_from(declared, scope, manifest)
    path = root / declared if isinstance(declared, str) and declared else root / ".mcp.json"
    return _servers_from(_mcp_json(path, reads), scope, path)


def _skill_root(path: pathlib.Path, scope: str) -> list[dict[str, str]]:
    return [{"path": str(path), "scope": scope}] if path.is_dir() else []


# --- harnesses -------------------------------------------------------------


def _claude(project: pathlib.Path, home: pathlib.Path, reads: list[dict[str, str]]) -> dict[str, Any]:
    enabled: dict[str, bool] = {}
    for path in (  # later scopes win: local > project > user
        home / ".claude/settings.json",
        project / ".claude/settings.json",
        project / ".claude/settings.local.json",
    ):
        for plugin_id, value in _mapping(_json_mapping(path, reads).get("enabledPlugins")).items():
            if isinstance(value, bool):
                enabled[plugin_id] = value
    installed = _json_mapping(home / ".claude/plugins/installed_plugins.json", reads)
    plugins: list[dict[str, Any]] = []
    for plugin_id, entries in sorted(_mapping(installed.get("plugins")).items()):
        for entry in entries if isinstance(entries, list) else [entries]:
            entry = _mapping(entry)
            scope = entry.get("scope")
            if scope in {"project", "local"} and not _same_path(entry.get("projectPath"), project):
                continue
            root = entry.get("installPath")
            plugins.append(
                {
                    "id": plugin_id,
                    "version": entry.get("version") if isinstance(entry.get("version"), str) else None,
                    "root": root if isinstance(root, str) and root else None,
                    "scope": scope if isinstance(scope, str) else None,
                    "enabled": enabled.get(plugin_id),
                }
            )
    active = [plugin for plugin in plugins if plugin["enabled"] is True and plugin["root"]]
    skill_roots = [
        *_skill_root(project / ".claude/skills", "project"),
        *_skill_root(home / ".claude/skills", "user"),
    ]
    user_config_path = home / ".claude.json"
    user_config = _json_mapping(user_config_path, reads)
    project_entry = _project_entry(user_config.get("projects"), project)
    disabled = set(_string_list(project_entry.get("disabledMcpServers")))
    disabled_mcpjson = set(_string_list(project_entry.get("disabledMcpjsonServers")))
    project_mcp = project / ".mcp.json"
    servers = [
        *_servers_from(_mcp_json(project_mcp, reads), "project", project_mcp, disabled_mcpjson | disabled),
        *_servers_from(project_entry.get("mcpServers"), "local", user_config_path, disabled),
        *_servers_from(user_config.get("mcpServers"), "user", user_config_path, disabled),
    ]
    for plugin in active:
        root = pathlib.Path(plugin["root"])
        scope = f"plugin:{plugin['id']}"
        skill_roots.extend(_skill_root(root / "skills", scope))
        servers.extend(_plugin_servers(root, root / ".claude-plugin/plugin.json", scope, reads))
    return {"plugins": plugins, "skill_roots": skill_roots, "mcp_servers": servers}


def _codex(project: pathlib.Path, home: pathlib.Path, reads: list[dict[str, str]]) -> dict[str, Any]:
    config_path = home / ".codex/config.toml"
    config = _toml_mapping(config_path, reads)
    servers = _servers_from(config.get("mcp_servers"), "user", config_path)
    trusted = _project_entry(config.get("projects"), project).get("trust_level") == "trusted"
    if trusted:
        project_config = project / ".codex/config.toml"
        servers.extend(
            _servers_from(_toml_mapping(project_config, reads).get("mcp_servers"), "project", project_config)
        )
    plugins: list[dict[str, Any]] = []
    for plugin_id, entry in sorted(_mapping(config.get("plugins")).items()):
        if not isinstance(plugin_id, str) or "@" not in plugin_id:
            continue
        name, marketplace = plugin_id.split("@", 1)
        state = _mapping(entry).get("enabled")
        cache = home / ".codex/plugins/cache" / marketplace / name
        versions = sorted(path for path in cache.glob("*") if path.is_dir()) if cache.is_dir() else []
        for version in versions or [None]:
            plugins.append(
                {
                    "id": plugin_id,
                    "version": version.name if version else None,
                    "root": str(version) if version else None,
                    "scope": "user",
                    "enabled": state if isinstance(state, bool) else None,
                }
            )
    skill_roots = [
        *_skill_root(project / ".agents/skills", "project"),
        *_skill_root(home / ".agents/skills", "user"),
        *_skill_root(home / ".codex/skills", "user"),
    ]
    for plugin in plugins:
        if plugin["enabled"] is not True or not plugin["root"]:
            continue
        root = pathlib.Path(plugin["root"])
        scope = f"plugin:{plugin['id']}"
        skill_roots.extend(_skill_root(root / "skills", scope))
        servers.extend(_plugin_servers(root, root / ".codex-plugin/plugin.json", scope, reads))
    return {
        "plugins": plugins,
        "skill_roots": skill_roots,
        "mcp_servers": servers,
        "project_config_trusted": trusted,
    }


def _safe_package_ref(spec: str) -> str:
    """Drop URL userinfo, query and fragment from a pi package spec."""
    prefix = ""
    for candidate in ("git:", "npm:"):
        if spec.startswith(candidate):
            prefix, spec = candidate, spec[len(candidate):]
    if "://" in spec:
        parts = urllib.parse.urlsplit(spec)
        host = parts.hostname or ""
        if parts.port:
            host += f":{parts.port}"
        spec = urllib.parse.urlunsplit((parts.scheme, host, parts.path, "", ""))
    else:
        spec = re.split(r"[?#]", spec, maxsplit=1)[0]
        head, slash, tail = spec.partition("/")
        # npm scopes start with "@"; elsewhere an "@" before the first "/" is userinfo.
        if prefix != "npm:" and "@" in head:
            head = head.rsplit("@", 1)[1]
        spec = head + slash + tail
    return prefix + spec


def _pi_package_root(spec: str, base: pathlib.Path, settings_dir: pathlib.Path) -> tuple[pathlib.Path | None, str | None]:
    if spec.startswith("npm:"):
        name = spec[len("npm:"):]
        at = name.rfind("@")
        version = name[at + 1:] if at > 0 else None
        name = name[:at] if at > 0 else name
        return base / "npm/node_modules" / name, version
    if spec.startswith("git:") or "://" in spec:
        ref = _safe_package_ref(spec).removeprefix("git:")
        ref = ref.split("://", 1)[-1]
        at = ref.rfind("@")
        version = ref[at + 1:] if at > ref.find("/") > 0 else None
        ref = ref[:at] if version else ref
        return base / "git" / ref.removesuffix(".git"), version
    if spec.startswith((".", "/", "~")):
        return (settings_dir / pathlib.Path(spec).expanduser()).resolve(strict=False), None
    return None, None


def _pi(project: pathlib.Path, home: pathlib.Path, reads: list[dict[str, str]]) -> dict[str, Any]:
    plugins: list[dict[str, Any]] = []
    for scope, settings_path, base in (
        ("project", project / ".pi/settings.json", project / ".pi"),
        ("user", home / ".pi/agent/settings.json", home / ".pi/agent"),
    ):
        packages = _json_mapping(settings_path, reads).get("packages", [])
        for item in packages if isinstance(packages, list) else []:
            spec = item.get("source") if isinstance(item, dict) else item
            if not isinstance(spec, str) or not spec.strip():
                continue
            root, version = _pi_package_root(spec.strip(), base, settings_path.parent)
            plugins.append(
                {
                    "id": _safe_package_ref(spec.strip()),
                    "version": version,
                    "root": str(root) if root and root.is_dir() else None,
                    "scope": scope,
                    "enabled": True,
                }
            )
    skill_roots = [
        *_skill_root(project / ".pi/skills", "project"),
        *_skill_root(project / ".agents/skills", "project"),
        *_skill_root(home / ".pi/agent/skills", "user"),
        *_skill_root(home / ".agents/skills", "user"),
    ]
    for plugin in plugins:
        if plugin["root"]:
            skill_roots.extend(_skill_root(pathlib.Path(plugin["root"]) / "skills", f"package:{plugin['id']}"))
    return {"plugins": plugins, "skill_roots": skill_roots, "mcp_servers": []}


# --- skills, CLIs, observations --------------------------------------------


def _skills(roots: list[dict[str, str]], reads: list[dict[str, str]]) -> list[dict[str, Any]]:
    seen: set[pathlib.Path] = set()
    skills: list[dict[str, Any]] = []
    for root in roots:
        for path in sorted(pathlib.Path(root["path"]).glob("*/SKILL.md")):
            resolved = path.resolve(strict=False)
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                metadata, error = read_frontmatter(path)
            except (OSError, UnicodeDecodeError) as exception:
                reads.append({"state": "unreadable", "source": str(path), "detail": str(exception)})
                continue
            if error or not isinstance(metadata, dict):
                reads.append({"state": "malformed", "source": str(path), "detail": error or "frontmatter must be a mapping"})
                continue
            name = metadata.get("name")
            skills.append(
                {
                    "name": name if isinstance(name, str) and name else path.parent.name,
                    "root": root["path"],
                    "scope": root["scope"],
                    "path": str(path),
                    "requires": _string_list(metadata.get("requires")),
                    "expects-local": _string_list(metadata.get("expects-local")),
                    "provides": _string_list(metadata.get("provides")),
                }
            )
    return skills


def _command_token(line: str, functions: frozenset[str] = frozenset()) -> str | None:
    tokens = line.strip().split()
    while tokens and ASSIGNMENT.fullmatch(tokens[0]):
        if "$(" in tokens[0] or "`" in tokens[0]:
            return None  # `x=$(cmd …)`: a substitution, not a command position
        tokens.pop(0)
    if not tokens:
        return None
    token = tokens[0].strip("'\"")
    if token in SHELL_WORDS or token in functions or CMDLET.fullmatch(token) or not CLI_TOKEN.fullmatch(token):
        return None
    return token


def _key_column(line: str) -> int:
    """Column of a YAML key, past any `- ` sequence indicators."""
    match = re.match(r"^(\s*(?:-\s+)*)", line)
    return len(match.group(1)) if match else 0


def _step_shell(lines: list[str], start: int, end: int, column: int) -> str | None:
    """The `shell:` beside a `run:` key at `column`, within the step around lines[start:end]."""
    pattern = re.compile(r"^(?:\s*(?:-\s+)?)shell:\s*['\"]?([^\s'\"#]+)")
    for index in range(start - 1, -1, -1):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent < column and not line.lstrip().startswith("-"):
            break
        if _key_column(line) == column and (match := pattern.match(line)):
            return match.group(1)
        if line.lstrip().startswith("-") and _key_column(line) <= column:
            break
    for line in lines[end:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent < column or line.lstrip().startswith("-") and indent <= column:
            break
        if indent == column and (match := pattern.match(line)):
            return match.group(1)
    return None


def _block_end(lines: list[str], index: int, indent: int) -> int:
    """First line at or after `index` indented no deeper than `indent`."""
    while index < len(lines) and (
        not lines[index].strip() or len(lines[index]) - len(lines[index].lstrip()) > indent
    ):
        index += 1
    return index


def _default_shells(lines: list[str]) -> tuple[str | None, list[tuple[int, str | None, bool]]]:
    """Workflow `defaults.run.shell`, and per job: first line, `defaults.run.shell`, windows runner."""
    workflow: str | None = None
    jobs: list[tuple[int, str | None, bool]] = []
    stack: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        start = index
        index += 1
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        match = re.match(r"""([A-Za-z0-9_.-]+|'[^']*'|"[^"]*"):(?:\s+(.*))?$""", stripped)
        if stripped.startswith("-") or not match:
            index = _block_end(lines, index, indent)
            continue
        key, value = match.group(1).strip("'\""), re.sub(r"(^|\s+)#.*$", "", match.group(2) or "").strip()
        path = (*(name for _, name in stack), key)
        shell = re.match(r"""['"]?([^\s'"#]+)""", value)
        if path == ("defaults", "run", "shell") and shell:
            workflow = shell.group(1)
        elif len(path) == 2 and path[0] == "jobs":
            jobs.append((start, None, False))
        elif len(path) == 3 and path[0] == "jobs" and path[2] == "runs-on" and jobs:
            end = _block_end(lines, index, indent)
            labels = [value, *lines[index:end]]
            index = end
            jobs[-1] = (*jobs[-1][:2], "windows" in " ".join(labels).lower())
            continue
        elif len(path) == 5 and path[0] == "jobs" and path[2:] == ("defaults", "run", "shell") and shell and jobs:
            jobs[-1] = (jobs[-1][0], shell.group(1), jobs[-1][2])
        if BLOCK_INDICATOR.fullmatch(value):
            index = _block_end(lines, index, indent)
            continue
        stack.append((indent, key))
    return workflow, jobs


def workflow_clis(project: pathlib.Path) -> dict[str, list[str]]:
    """First tokens of `.github/workflows/*` `run:` lines, as cli -> workflow files."""
    found: dict[str, list[str]] = {}
    workflows = project / ".github/workflows"
    paths = sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")]) if workflows.is_dir() else []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        source = str(path.relative_to(project))
        workflow_shell, jobs = _default_shells(lines)
        index = 0
        while index < len(lines):
            match = re.match(r"^(\s*)(?:-\s+)?run:\s*(.*)$", lines[index])
            start = index
            index += 1
            if not match:
                continue
            value = match.group(2).strip()
            commands: list[str] = []
            if BLOCK_INDICATOR.fullmatch(value):
                end = _block_end(lines, index, _key_column(lines[start]))
                commands.extend(lines[index:end])
                index = end
            elif value and not value.startswith("#"):
                commands.append(value.strip("'\""))
            shell = _step_shell(lines, start, index, _key_column(lines[start]))
            job = [(default, windows) for first, default, windows in jobs if first < start]
            default, windows = job[-1] if job else (None, False)
            shell = shell or default or workflow_shell or ("pwsh" if windows else None)
            if shell is not None and shell not in POSIX_SHELLS:
                continue
            functions = frozenset(
                defined.group(1) or defined.group(2)
                for command in commands
                if (defined := SHELL_FUNCTION.match(command))
            )
            heredoc: str | None = None
            continued = False
            for command in commands:
                stripped = command.strip()
                if heredoc is not None:
                    heredoc = None if stripped == heredoc else heredoc
                    continue
                if continued or not stripped or stripped.startswith("#"):
                    continued = stripped.endswith("\\")
                    continue
                continued = stripped.endswith("\\")
                opened = HEREDOC.search(stripped)
                heredoc = opened.group(1) if opened else None
                token = _command_token(stripped, functions)
                if token and source not in found.setdefault(token, []):
                    found[token].append(source)
    return found


def _default_version_runner(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=5, check=False, stdin=subprocess.DEVNULL
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in (completed.stdout + "\n" + completed.stderr).splitlines():
        if line.strip():
            return line.strip()[:120]
    return None


def load_observations(source: str | pathlib.Path | TextIO) -> list[dict[str, Any]]:
    """Validate agent-supplied in-session captures (schema_version 1, Doctor's capture shape).

    Accepts one capture or a list. Only known fields are kept: name and tools
    for MCP servers, name and state for capabilities. Raises ValueError.
    """
    if hasattr(source, "read"):
        label, text = "stdin", source.read()
    else:
        path = pathlib.Path(source)
        label = str(path)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise ValueError(f"invalid observations {label}: {error}") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid observations {label}: {error}") from error
    captures = document if isinstance(document, list) else [document]
    observations: list[dict[str, Any]] = []
    for index, capture in enumerate(captures):
        where = f"invalid observations {label} entry {index}"
        if not isinstance(capture, dict):
            raise ValueError(f"{where}: must be a mapping")
        if type(capture.get("schema_version")) is not int or capture["schema_version"] != 1:
            raise ValueError(f"{where}: schema_version must be integer 1")
        if capture.get("harness") not in HARNESSES:
            raise ValueError(f"{where}: harness must be claude, codex, or pi")
        if not isinstance(capture.get("captured_at"), str) or not capture["captured_at"].strip():
            raise ValueError(f"{where}: captured_at must be a non-empty string")
        command = capture.get("source_command") or capture.get("source")
        if not isinstance(command, str) or not command.strip():
            raise ValueError(f"{where}: source_command is required")
        servers = []
        for server in capture.get("mcp_servers", []) or []:
            if not isinstance(server, dict) or not isinstance(server.get("name"), str) or not server["name"]:
                raise ValueError(f"{where}: mcp_servers entries need a name")
            tools = server.get("tools")
            if tools is not None and (not isinstance(tools, list) or not all(isinstance(t, str) for t in tools)):
                raise ValueError(f"{where}: mcp_servers tools must be a string sequence")
            servers.append({"name": server["name"], "tools": list(tools) if tools is not None else None})
        capabilities = []
        for capability in capture.get("capabilities", []) or []:
            if not isinstance(capability, dict) or not isinstance(capability.get("name"), str):
                raise ValueError(f"{where}: capabilities entries need a name")
            kind = capability["name"].split(":", 1)[0]
            if kind not in CAPABILITY_KINDS or ":" not in capability["name"]:
                raise ValueError(f"{where}: capability names are cli:, mcp:, or external:")
            if capability.get("state") not in {"present", "working", "unavailable", "not tested"}:
                raise ValueError(f"{where}: capability state is unsupported")
            capabilities.append({"name": capability["name"], "state": capability["state"]})
        observations.append(
            {
                "schema_version": 1,
                "harness": capture["harness"],
                "captured_at": capture["captured_at"],
                "source_command": command,
                "mcp_servers": servers,
                "capabilities": capabilities,
                "source": label,
            }
        )
    return observations


def _apply_observations(harnesses: dict[str, Any], observations: list[dict[str, Any]]) -> None:
    """Observations raise a server to `present` and attach in-session tools, never `working`."""
    for observation in observations:
        servers = harnesses[observation["harness"]]["mcp_servers"]
        for seen in observation["mcp_servers"]:
            matches = [server for server in servers if _norm(server["name"]) == _norm(seen["name"])]
            if not matches:
                matches = [
                    {
                        "name": seen["name"],
                        "transport": "unknown",
                        "scope": "session",
                        "source": observation["source"],
                        "state": "present",
                        "command": None,
                        "tools": None,
                        "tools_source": None,
                    }
                ]
                servers.append(matches[0])
            for server in matches:
                server["state"] = "present"
                if seen["tools"] is not None:
                    server["tools"] = sorted(seen["tools"])
                    server["tools_source"] = "session"


def _plugin_name(plugin_id: str) -> str:
    """`name@marketplace` or a pi spec's package/repo name; never its host."""
    spec = plugin_id.removeprefix("git:").removeprefix("npm:").split("://", 1)[-1]
    if "/" in spec:
        spec = spec.rsplit("/", 1)[1]
    return spec.split("@", 1)[0] if not spec.startswith("@") else spec


def _norm(name: str) -> str:
    return name.strip().lower().replace("_", "-")


# --- capabilities and gaps -------------------------------------------------


def _inside(path: str | None, root: pathlib.Path) -> bool:
    if not path:
        return False
    try:
        pathlib.Path(path).resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _probe_safe(path: str, project: pathlib.Path) -> bool:
    """A binary is probed only from an absolute PATH entry outside the project."""
    return pathlib.Path(path).is_absolute() and not _inside(path, project)


def _capabilities(
    harnesses: dict[str, Any],
    skills: list[dict[str, Any]],
    clis: Iterable[str],
    workflow: dict[str, list[str]],
    observations: list[dict[str, Any]],
    which: Callable[[str], str | None],
    version_runner: Callable[[list[str]], str | None] | None,
    project: pathlib.Path,
) -> dict[str, Any]:
    declared: dict[str, set[str]] = {}
    # `--version` executes a binary, so only names the operator passed or an installed
    # (non-project) skill requires may be probed. Workflow files, project skills and
    # observations are repo or session content: they are inventoried, never executed.
    probeable: set[str] = set(clis)
    for skill in skills:
        for requirement in skill["requires"]:
            if requirement.split(":", 1)[0] in CAPABILITY_KINDS and ":" in requirement:
                declared.setdefault(requirement, set()).add(skill["name"])
                if requirement.startswith("cli:") and not _inside(skill.get("path"), project):
                    probeable.add(requirement.split(":", 1)[1])
    for cli in clis:
        declared.setdefault(f"cli:{cli}", set()).add("--cli")
    for cli, sources in workflow.items():
        declared.setdefault(f"cli:{cli}", set()).update(f"workflow:{source}" for source in sources)
    observed: dict[str, list[dict[str, Any]]] = {}
    for observation in observations:
        for capability in observation["capabilities"]:
            if capability["state"] in {"present", "working"}:
                observed.setdefault(capability["name"], []).append(observation)
                declared.setdefault(capability["name"], set()).add(f"observation:{observation['harness']}")
    servers = [
        {**server, "harness": harness}
        for harness in HARNESSES
        for server in harnesses[harness]["mcp_servers"]
    ]
    plugins = [
        {**plugin, "harness": harness}
        for harness in HARNESSES
        for plugin in harnesses[harness]["plugins"]
        if plugin["enabled"] is True
    ]
    capabilities: dict[str, Any] = {}
    for capability in sorted(declared):
        kind, name = capability.split(":", 1)
        providers: list[dict[str, Any]] = []
        if kind == "cli":
            path = which(name)
            version = (
                version_runner([path, "--version"])
                if path and version_runner and name in probeable and _probe_safe(path, project)
                else None
            )
            providers.append(
                {"kind": "cli", "name": name, "state": "present" if path else "absent", "path": path, "version": version}
            )
        elif kind == "mcp":
            providers.extend(
                _mcp_provider(server) for server in servers if _norm(server["name"]) == _norm(name)
            )
        else:
            for cli in EXTERNAL_CLIS.get(name, ()):
                if path := which(cli):
                    providers.append(
                        {"kind": "cli", "name": cli, "state": "present", "path": path, "basis": "known-cli"}
                    )
            needle = _norm(name)
            providers.extend(
                {**_mcp_provider(server), "basis": "name-match"}
                for server in servers
                if needle in _norm(server["name"])
            )
            providers.extend(
                {
                    "kind": "plugin",
                    "name": plugin["id"],
                    "state": "present",
                    "harness": plugin["harness"],
                    "source": plugin["root"] or "",
                    "basis": "name-match",
                }
                for plugin in plugins
                if needle in _norm(_plugin_name(plugin["id"]))
            )
        for observation in observed.get(capability, []):
            providers.append(
                {
                    "kind": kind if kind != "external" else "observation",
                    "name": name,
                    "state": "present",
                    "harness": observation["harness"],
                    "source": observation["source"],
                    "basis": "observation",
                }
            )
        capabilities[capability] = {"declared_by": sorted(declared[capability]), "providers": providers}
    return capabilities


def _mcp_provider(server: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "mcp",
        "name": server["name"],
        "state": server["state"],
        "harness": server["harness"],
        "scope": server["scope"],
        "source": server["source"],
    }


def _best_provider(providers: list[dict[str, Any]]) -> dict[str, Any] | None:
    ranked = sorted(
        providers,
        key=lambda provider: (
            STATE_RANK.get(provider["state"], 3),
            KIND_RANK.get(provider["kind"], 3),
            provider["name"],
        ),
    )
    return ranked[0] if ranked else None


def capability_map_rows(inventory: dict[str, Any]) -> list[dict[str, str]]:
    """One row per capability: the best provider's name, kind and state. No paths."""
    rows = []
    for capability, entry in sorted(inventory["capabilities"].items()):
        best = _best_provider(entry["providers"])
        state = best["state"] if best else "absent"
        rows.append(
            {
                "capability": capability,
                "provider": best["name"] if best and state != "absent" else "—",
                "kind": best["kind"] if best else capability.split(":", 1)[0],
                "state": state,
            }
        )
    return rows


def inventory_digest(inventory: dict[str, Any]) -> str:
    """Hash only the sorted capability, provider name, kind and state."""
    rows = [
        [row["capability"], row["provider"], row["kind"], row["state"]]
        for row in capability_map_rows(inventory)
    ]
    payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def gaps(inventory: dict[str, Any]) -> list[dict[str, str]]:
    """What `learn` reads: unprovided capabilities, unfilled slots, unskilled tools."""
    found: list[dict[str, str]] = []
    known = capability_vocabulary()
    skill_requirements = {
        requirement for skill in inventory["skills"] for requirement in skill["requires"]
    }
    for capability, entry in sorted(inventory["capabilities"].items()):
        kind, name = capability.split(":", 1)
        present = [provider for provider in entry["providers"] if provider["state"] == "present"]
        declarers = ", ".join(entry["declared_by"])
        if not present:
            if kind == "cli" and all(source.startswith("workflow:") for source in entry["declared_by"]):
                # A workflow step runs on a CI runner, not this machine, so its absence
                # here says nothing about the step; and a run: line is read heuristically.
                evidence = (
                    f"shutil.which({name!r}) found nothing on PATH; declared only by {declarers}, "
                    "whose run: steps execute on CI runners, not this machine"
                )
                label = "inference"
            elif kind == "cli":
                evidence, label = f"shutil.which({name!r}) found nothing on PATH; declared by {declarers}", "fact"
            elif kind == "mcp":
                evidence = f"no enabled MCP server named {name} in the inspected configs; declared by {declarers}"
                label = "inference"
            else:
                evidence = f"no MCP server or plugin matched {name!r} by name"
                if EXTERNAL_CLIS.get(name):
                    evidence += f" and {', '.join(EXTERNAL_CLIS[name])} is not on PATH"
                evidence, label = f"{evidence}; declared by {declarers}", "inference"
            if kind != "cli" and capability not in known:
                # cli:<tool> is open; an mcp:/external: name outside the vocabulary
                # may be a typo or a source the vocabulary lacks (docs/CAPABILITIES.md).
                evidence += "; not in Crew's capability vocabulary (docs/CAPABILITIES.md)"
            found.append({"kind": "capability-unprovided", "name": capability, "evidence": evidence, "label": label})
        elif kind == "cli" and capability not in skill_requirements:
            path = next((provider.get("path") for provider in present if provider.get("path")), None)
            where = f"on PATH at {path}" if path else "observed in session"
            found.append(
                {
                    "kind": "tool-unskilled",
                    "name": capability,
                    "evidence": f"{where}; used by {declarers}; no installed skill declares {capability}",
                    "label": "inference",
                }
            )
    skilled_mcp = {_norm(req.split(":", 1)[1]) for req in skill_requirements if req.startswith("mcp:")}
    reported: set[str] = set()
    for harness in HARNESSES:
        for server in inventory["harnesses"][harness]["mcp_servers"]:
            key = _norm(server["name"])
            if server["state"] != "present" or key in skilled_mcp or key in reported:
                continue
            reported.add(key)
            found.append(
                {
                    "kind": "mcp-unskilled",
                    "name": server["name"],
                    "evidence": f"{harness} {server['scope']} server from {server['source']}; "
                    f"no installed skill declares mcp:{server['name']}",
                    "label": "inference",
                }
            )
    slots = inventory["slots"]
    for slot, entry in sorted(slots.get("slots", {}).items()):
        if entry.get("effective") is None:
            where = ", ".join(slots.get("inspection_sources", [])) or inventory["project_root"]
            owners = slots.get("pack_slots", {}).get(slot)
            owned = f" (pack {', '.join(f'`{name}`' for name in owners)}'s slot)" if owners else ""
            found.append(
                {
                    "kind": "slot-unfilled",
                    "name": slot,
                    "evidence": f"no local skill or pack provides {slot}{owned}; inspected {where}",
                    "label": "fact",
                }
            )
    order = {"capability-unprovided": 0, "slot-unfilled": 1, "tool-unskilled": 2, "mcp-unskilled": 3}
    return sorted(found, key=lambda gap: (order[gap["kind"]], gap["name"]))


# --- the capability map ----------------------------------------------------


def _cells(line: str) -> list[str]:
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", body)]


def parse_capability_map(text: str) -> dict[str, Any] | None:
    """Read the marker block: digest, date, crew version, rows and pending removals."""
    begin = MAP_BEGIN.search(text)
    if not begin:
        return None
    end = MAP_END.search(text, begin.end())
    stop = end.end() if end else len(text)
    attrs = dict(re.findall(r"([a-z]+)=(\S+)", begin.group("attrs")))
    rows: list[dict[str, str]] = []
    removals: list[str] = []
    for line in text[begin.end():end.start() if end else stop].splitlines():
        stripped = line.strip()
        if stripped.startswith(REMOVAL_LINE):
            removals = re.findall(r"`([^`]+)`", stripped)
            continue
        if not stripped.startswith("|") or stripped == MAP_HEADER or set(stripped) <= set("|-: "):
            continue
        cells = _cells(stripped)
        if len(cells) < 5:
            continue
        rows.append(
            {
                "capability": cells[0].strip("`"),
                "provider": cells[1],
                "kind": cells[2],
                "state": cells[3],
                "fallback": cells[4],
            }
        )
    return {
        "digest": attrs.get("digest"),
        "generated": attrs.get("generated"),
        "crew": attrs.get("crew"),
        "rows": rows,
        "removals": removals,
        "span": [begin.start(), stop],
        "closed": bool(end),
    }


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_capability_map(
    inventory: dict[str, Any],
    *,
    fallbacks: dict[str, str] | None = None,
    retained: list[dict[str, str]] | None = None,
    generated: str | None = None,
    crew: str | None = None,
) -> str:
    """The marker block onboarding writes; `retained` rows vanished and await removal."""
    fallbacks = fallbacks or {}
    retained = retained or []
    generated = generated or str(inventory["generated_at"])[:10]
    crew = crew or inventory.get("crew_version") or "unknown"
    lines = [
        f"<!-- crew:capability-map begin digest={inventory['map_digest']} generated={generated} crew={crew} -->",
        MAP_HEADER,
        "|---|---|---|---|---|",
    ]
    rows = [*capability_map_rows(inventory), *retained]
    for row in sorted(rows, key=lambda item: item["capability"]):
        fallback = fallbacks.get(row["capability"]) or FILL
        cells = [f"`{row['capability']}`", row["provider"], row["kind"], row["state"], fallback]
        lines.append("| " + " | ".join(_escape(cell) for cell in cells) + " |")
    if retained:
        names = ", ".join(f"`{row['capability']}`" for row in sorted(retained, key=lambda item: item["capability"]))
        lines.extend(["", f"{REMOVAL_LINE} {names}"])
    lines.append("<!-- crew:capability-map end -->")
    return "\n".join(lines)


def render_gaps(inventory: dict[str, Any]) -> str:
    if not inventory["gaps"]:
        return "no gaps\n"
    lines = ["| kind | name | label | evidence |", "|---|---|---|---|"]
    for gap in inventory["gaps"]:
        lines.append(
            "| " + " | ".join(_escape(gap[key]) for key in ("kind", "name", "label", "evidence")) + " |"
        )
    return "\n".join(lines) + "\n"


def _recorded_map(slots: dict[str, Any]) -> dict[str, Any]:
    entry = slots.get("slots", {}).get("agent-runtime")
    if not entry:
        return {"fill": None, "source": None, "recorded": None}
    if entry["local"]:
        source = entry["local"][0]["source"]
        fill = "local"
    elif entry["packs"]:
        source = entry["packs"][0]["source"]
        fill = "pack"
    else:
        return {"fill": None, "source": None, "recorded": None}
    try:
        text = pathlib.Path(source).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    recorded = parse_capability_map(text)
    if recorded:
        recorded.pop("span", None)
    return {"fill": fill, "source": source, "recorded": recorded}


# --- the inventory ---------------------------------------------------------


def build_inventory(
    project: pathlib.Path,
    home: pathlib.Path,
    *,
    observations: list[dict[str, Any]] | None = None,
    clis: Iterable[str] = (),
    probe_versions: bool = False,
    crew_root: pathlib.Path = CREW_ROOT,
    which: Callable[[str], str | None] = shutil.which,
    version_runner: Callable[[list[str]], str | None] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Assemble the `crew-inventory/1` document. Reads only; never writes."""
    project = pathlib.Path(project)
    home = pathlib.Path(home)
    crew_root = pathlib.Path(crew_root)
    observations = observations or []
    reads: list[dict[str, str]] = []
    harnesses = {
        "claude": _claude(project, home, reads),
        "codex": _codex(project, home, reads),
        "pi": _pi(project, home, reads),
    }
    _apply_observations(harnesses, observations)
    roots = [
        root
        for harness in HARNESSES
        for root in harnesses[harness]["skill_roots"]
    ]
    roots.extend(_skill_root(crew_root / "skills", "crew"))
    skills = _skills(roots, reads)
    package_roots = [
        pathlib.Path(plugin["root"])
        for harness in HARNESSES
        for plugin in harnesses[harness]["plugins"]
        if plugin["root"] and plugin["enabled"] is not False
    ]
    packs = inspect_packs(package_roots, crew_root)
    declared = declared_local_slots(crew_root, packs=packs)
    fills = slot_fills(
        declared["declared"],
        local_roots=[project / ".agents/skills", project / ".claude/skills"],
        packs=packs,
    )
    capabilities = _capabilities(
        harnesses,
        skills,
        clis,
        workflow_clis(project),
        observations,
        which,
        (version_runner or _default_version_runner) if probe_versions else None,
        project,
    )
    inventory: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": now or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "crew_version": _manifest_version(crew_root).value,
        "project_root": str(project),
        "harnesses": harnesses,
        "packs": packs,
        "skills": skills,
        "capabilities": capabilities,
        "slots": {
            "slots": fills["slots"],
            "inspection_sources": fills["inspection_sources"],
            # slot -> the pack(s) whose slots.txt declares it; Crew's slots are absent.
            "pack_slots": declared["pack_slots"],
            # slots two owners declare; Onboarding proposes no fill for them.
            "collisions": declared["collisions"],
        },
        "observations": observations,
        "not_observable": [dict(entry) for entry in NOT_OBSERVABLE]
        + (
            []
            if probe_versions
            else [{"what": "CLI versions", "why": "probed only with --probe-versions, which runs `<cli> --version`"}]
        ),
        "reads": reads + declared["reads"] + fills["reads"],
    }
    inventory["gaps"] = gaps(inventory)
    inventory["map_digest"] = inventory_digest(inventory)
    inventory["capability_map"] = {"rows": capability_map_rows(inventory), **_recorded_map(inventory["slots"])}
    return inventory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--project", required=True, type=pathlib.Path, help="absolute consumer repo root")
    parser.add_argument("--home", type=pathlib.Path, default=pathlib.Path.home())
    parser.add_argument("--observations", metavar="FILE|-", help="in-session capture (schema_version 1); - reads stdin")
    parser.add_argument("--cli", action="append", default=[], metavar="TOOL", help="also look this CLI up on PATH")
    parser.add_argument("--probe-versions", action="store_true", help="run `<cli> --version` for CLIs found on PATH")
    parser.add_argument("--format", choices=("json", "map", "gaps"), default="json")
    args = parser.parse_args(argv)
    if not args.project.is_absolute() or not args.project.is_dir():
        print(f"invalid input: --project must be an absolute directory: {args.project}", file=sys.stderr)
        return 2
    try:
        observations = (
            load_observations(sys.stdin if args.observations == "-" else args.observations)
            if args.observations
            else []
        )
    except ValueError as error:
        print(f"invalid input: {error}", file=sys.stderr)
        return 2
    for cli in args.cli:
        if not CLI_TOKEN.fullmatch(cli):
            print(f"invalid input: --cli {cli!r} is not a command name", file=sys.stderr)
            return 2
    inventory = build_inventory(
        args.project,
        args.home,
        observations=observations,
        clis=args.cli,
        probe_versions=args.probe_versions,
    )
    if args.format == "json":
        print(json.dumps(inventory, indent=2, ensure_ascii=False))
    elif args.format == "map":
        print(render_capability_map(inventory))
    else:
        print(render_gaps(inventory), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
