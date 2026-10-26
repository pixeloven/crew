#!/usr/bin/env python3
"""Render agents/ and pi-agents/ from the single-source roles/ tree.

Each roles/<role>/ contains exactly two files:
  role.yml            ONE harness-neutral definition (name, description, writes, dispatch)
  body.md             ONE shared body — the same prose reaches every harness

Text that every role carries verbatim (the reporting contract) lives once in
roles/_shared/<part>.md and a body pulls it in with a line of its own:
`<!-- include: <part> -->`. The renderer expands it, so the rendered agent is the
same as if the text were pasted there. `_shared` is not a role: directories whose
name starts with `_` are skipped by the role loop.

Both harnesses get the same name, description, body and capability posture. The
only thing that differs is dialect: Claude Code subtracts tools with
`disallowedTools`, pi with `excludeTools`, and every pi agent carries
`package: crew` so a host that loads it through pi-subagents registers it as `crew.<role>`. That translation lives HERE and
nowhere else, so the two trees cannot drift apart by editing. A consumer whose
runtime needs a role to behave differently shadows the rendered agent in its own
overlay — per-harness prose does not belong in this repo, because the differences
that actually matter are per-DEPLOYMENT, not per-harness.

Deliberately absent: model, reasoning/thinking level, and turn budget. Both
harnesses support all three (Claude: `model` / `effort` / `maxTurns`; pi: `model`
/ `thinking` / `turnBudget`) and both inherit sensible values from the session
when they are omitted. A role is a job description, not a procurement decision —
whoever dispatches it owns cost, depth, and blast radius. Shipping those values
from a foundation imposes one operator's choices on every consumer and goes stale
on every model release. `FORBIDDEN` below is the gate that keeps them out.

Usage:
  scripts/render_roles.py           # write rendered files
  scripts/render_roles.py --check   # exit 1 on drift or invalid frontmatter (CI)
"""

import pathlib
import re
import sys

try:
    from .role_contract import FORBIDDEN_RUNTIME_KEYS, PI_PACKAGE_NAME, WRITE_POSTURES
except ImportError:  # Direct script execution.
    from role_contract import FORBIDDEN_RUNTIME_KEYS, PI_PACKAGE_NAME, WRITE_POSTURES

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTICE = "<!-- GENERATED from roles/{role}/ — edit there and run scripts/render_roles.py -->"
SHARED = ROOT / "roles" / "_shared"
INCLUDE = re.compile(r"^<!-- include: (\S+) -->$", re.MULTILINE)
PART_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# What a role may declare. Anything else is a typo or a smuggled runtime knob.
ALLOWED = {"name", "description", "writes", "dispatch"}

# Runtime knobs that belong to whoever dispatches the role, not to the role.
FORBIDDEN = FORBIDDEN_RUNTIME_KEYS

# One capability posture per role, spoken in each harness's dialect.
#   none   — reads and reports; produces no files
#   drafts — may create and overwrite files; may not use surgical edit tools
#   full   — unrestricted write path
WRITES = {
    posture: {
        "claude": values["claude"]["denied"],
        "pi": values["pi"]["denied"],
    }
    for posture, values in WRITE_POSTURES.items()
}


def load_yaml(text, origin):
    try:
        import yaml
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
        import yaml
    try:
        data = yaml.safe_load(text)
    except Exception as e:
        sys.exit(f"{origin}: not valid YAML: {e}")
    if not isinstance(data, dict):
        sys.exit(f"{origin}: must be a YAML mapping")
    return data


def load_role(role_dir):
    origin = f"roles/{role_dir.name}/role.yml"
    path = role_dir / "role.yml"
    if not path.exists():
        sys.exit(f"{origin}: missing — every role needs one harness-neutral definition")
    data = load_yaml(path.read_text(), origin)

    for field in sorted(set(data) & set(FORBIDDEN)):
        sys.exit(
            f"{origin}: '{field}' is not a role property — {FORBIDDEN[field]}.\n"
            f"  A consumer that wants to pin it sets it in its own overlay or harness config."
        )
    for field in sorted(set(data) - ALLOWED):
        sys.exit(f"{origin}: unknown field '{field}' (allowed: {', '.join(sorted(ALLOWED))})")

    if data.get("name") != role_dir.name:
        sys.exit(f"{origin}: 'name' must equal the role directory name '{role_dir.name}'")
    if not data.get("description"):
        sys.exit(f"{origin}: missing 'description' — it is the whole discovery interface")
    extra = sorted(p.name for p in role_dir.iterdir() if p.name not in {"role.yml", "body.md"})
    if extra:
        sys.exit(
            f"roles/{role_dir.name}: unexpected file(s) {', '.join(extra)} — a role is role.yml + body.md.\n"
            f"  Per-harness or per-runtime prose belongs in the consumer's overlay, not here."
        )
    if data.get("writes") not in WRITES:
        sys.exit(f"{origin}: 'writes' must be one of {', '.join(WRITES)}")
    return data


def frontmatter(role, harness):
    """The same role, spoken in one harness's dialect."""
    desc = role["description"]
    if ":" in desc or desc.lstrip().startswith(("'", '"')):
        desc = '"' + desc.replace('"', '\\"') + '"'
    # `name` is REQUIRED on BOTH harnesses, and its absence is silent on pi.
    # pi-subagents resolves an agent's name strictly from this key — there is no
    # filename fallback anywhere in its load path — and `agents.ts` does
    # `if (!frontmatter.name || !frontmatter.description) continue;`, dropping the
    # file with no diagnostic. Every pi role this repo shipped omitted it, so the
    # whole pi fleet was invisible while the tree looked correct. Do not "simplify"
    # this back into the Claude branch.
    lines = [f"name: {role['name']}"]
    if harness == "claude":
        lines.append(f"description: {desc}")
        denied = WRITES[role["writes"]]["claude"]
        if denied:
            lines.append(f"disallowedTools: {', '.join(denied)}")
    else:
        # `package:` makes the runtime identity `crew.<name>` while `name:` stays
        # the bare local name. Without it a package agent named `reviewer` or
        # `researcher` silently replaces pi-subagents' built-in of that name in
        # its own acceptance review and profiles (package beats builtin).
        lines.append(f"package: {PI_PACKAGE_NAME}")
        lines.append(f"description: {desc}")
        # Subtract from pi's default tool set. Never emit `tools:` — it is a
        # strict allowlist that also shuts out ambient extensions (MCP).
        excluded = WRITES[role["writes"]]["pi"]
        if excluded:
            lines.append(f"excludeTools: {', '.join(excluded)}")
        if role.get("dispatch"):
            # The child-safe nested `subagent` tool, granted without turning an
            # omitted `tools:` into an allowlist.
            lines.append("allowNestedSubagents: true")
    return "\n".join(lines)


def expand_includes(body, origin, shared=SHARED):
    """Replace each `<!-- include: <part> -->` line with roles/_shared/<part>.md."""

    def part(match):
        name = match.group(1)
        path = shared / f"{name}.md"
        if not PART_NAME.fullmatch(name) or not path.is_file():
            sys.exit(f"{origin}: include '{name}' does not name a file in roles/_shared/")
        return path.read_text().strip("\n")

    return INCLUDE.sub(part, body)


def render(role_dir, role, harness):
    origin = f"roles/{role_dir.name}/body.md"
    body = expand_includes((role_dir / "body.md").read_text(), origin).strip("\n")
    notice = NOTICE.format(role=role_dir.name)
    return f"---\n{frontmatter(role, harness)}\n---\n\n{notice}\n\n{body}\n"


def main():
    check = "--check" in sys.argv
    roles = sorted(
        p for p in (ROOT / "roles").iterdir() if p.is_dir() and not p.name.startswith("_")
    )
    if not roles:
        sys.exit("no role directories under roles/")
    drift = []
    for role_dir in roles:
        role = load_role(role_dir)
        outputs = {
            ROOT / "agents" / f"{role_dir.name}.md": render(role_dir, role, "claude"),
            ROOT / "pi-agents" / f"{role_dir.name}.md": render(role_dir, role, "pi"),
        }
        for path, content in outputs.items():
            current = path.read_text() if path.exists() else None
            if current == content:
                continue
            if check:
                drift.append(str(path.relative_to(ROOT)))
            else:
                path.parent.mkdir(exist_ok=True)
                path.write_text(content)
                print(f"wrote {path.relative_to(ROOT)}")

    stale = sorted(
        str(p.relative_to(ROOT))
        for tree in ("agents", "pi-agents")
        for p in (ROOT / tree).glob("*.md")
        if p.stem not in {r.name for r in roles}
    )
    if stale:
        print("rendered files with no role source — delete them:")
        print("\n".join(f"  {s}" for s in stale))
        sys.exit(1)

    if check:
        if drift:
            print("rendered files out of date — run scripts/render_roles.py and commit:")
            print("\n".join(f"  {d}" for d in drift))
            sys.exit(1)
        print(f"{len(roles)} roles rendered clean for both harnesses")


if __name__ == "__main__":
    main()
