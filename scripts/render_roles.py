#!/usr/bin/env python3
"""Render agents/ and pi-agents/ from the single-source roles/ tree.

Each roles/<role>/ contains exactly two files:
  role.yml            ONE harness-neutral definition (name, description, writes, dispatch)
  body.md             ONE shared body — the same prose reaches every harness

Both harnesses get the same name, description, body and capability posture. The
only thing that differs is dialect: Claude Code expresses capability as a denylist
(`disallowedTools`), pi as an allowlist (`tools`). That translation lives HERE and
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
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTICE = "<!-- GENERATED from roles/{role}/ — edit there and run scripts/render_roles.py -->"

# What a role may declare. Anything else is a typo or a smuggled runtime knob.
ALLOWED = {"name", "description", "writes", "dispatch"}

# Runtime knobs that belong to whoever dispatches the role, not to the role.
FORBIDDEN = {
    "model": "the dispatcher's choice — both harnesses inherit the session model",
    "thinking": "reasoning depth is the dispatcher's choice",
    "effort": "reasoning depth is the dispatcher's choice",
    "model_reasoning_effort": "reasoning depth is the dispatcher's choice",
    "turnBudget": "blast radius is the dispatcher's choice",
    "maxTurns": "blast radius is the dispatcher's choice",
}

# One capability posture per role, spoken in each harness's dialect.
#   none   — reads and reports; produces no files
#   drafts — may create files (plans, drafts); may not edit existing ones
#   full   — unrestricted write path
WRITES = {
    "none": {"claude": ["Write", "Edit", "NotebookEdit"], "pi": ["read", "bash", "grep", "find"]},
    "drafts": {"claude": ["Edit", "NotebookEdit"], "pi": ["read", "write", "bash", "grep", "find"]},
    "full": {"claude": [], "pi": ["read", "write", "edit", "bash", "grep", "find"]},
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
    lines = []
    if harness == "claude":
        lines.append(f"name: {role['name']}")
        lines.append(f"description: {desc}")
        denied = WRITES[role["writes"]]["claude"]
        if denied:
            lines.append(f"disallowedTools: {', '.join(denied)}")
    else:
        lines.append(f"description: {desc}")
        tools = list(WRITES[role["writes"]]["pi"])
        if role.get("dispatch"):
            tools.append("subagent")
        lines.append(f"tools: {', '.join(tools)}")
    return "\n".join(lines)


def render(role_dir, role, harness):
    body = (role_dir / "body.md").read_text().strip("\n")
    notice = NOTICE.format(role=role_dir.name)
    return f"---\n{frontmatter(role, harness)}\n---\n\n{notice}\n\n{body}\n"


def main():
    check = "--check" in sys.argv
    roles = sorted(p for p in (ROOT / "roles").iterdir() if p.is_dir())
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
