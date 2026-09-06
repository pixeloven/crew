#!/usr/bin/env python3
"""Render agents/ and pi-agents/ from the single-source roles/ tree.

Each roles/<role>/ contains:
  claude.yml          frontmatter for agents/<role>.md
  pi.yml              frontmatter for pi-agents/role-<role>.md
  body.md             shared body; may contain one '{{RUNTIME_CONTEXT}}' marker line
  claude-context.md   optional per-runtime replacement for the marker
  pi-context.md       optional per-runtime replacement for the marker

Usage:
  scripts/render_roles.py           # write rendered files
  scripts/render_roles.py --check   # exit 1 on drift or invalid frontmatter (CI)
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKER = "{{RUNTIME_CONTEXT}}"
NOTICE = "<!-- GENERATED from roles/{role}/ — edit there and run scripts/render_roles.py -->"


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
        sys.exit(f"{origin}: frontmatter not valid YAML: {e}")
    if not isinstance(data, dict):
        sys.exit(f"{origin}: frontmatter must be a YAML mapping")
    return data


def validate_frontmatter(role, fm_file, data):
    origin = f"roles/{role}/{fm_file}"
    if not data.get("description"):
        sys.exit(f"{origin}: missing 'description'")
    if fm_file == "claude.yml":
        name = data.get("name")
        if not name:
            sys.exit(f"{origin}: missing 'name'")
        if name != role:
            sys.exit(f"{origin}: name '{name}' must equal the role dir name '{role}' (lowercase)")
    else:
        for field in ("tools", "thinking", "turnBudget"):
            if field not in data:
                sys.exit(f"{origin}: missing '{field}'")


def render(role_dir, fm_file, ctx_file):
    fm_text = (role_dir / fm_file).read_text().strip("\n")
    validate_frontmatter(role_dir.name, fm_file, load_yaml(fm_text, f"roles/{role_dir.name}/{fm_file}"))
    body = (role_dir / "body.md").read_text().strip("\n")
    ctx_path = role_dir / ctx_file
    if MARKER in body:
        if ctx_path.exists():
            body = body.replace(MARKER, ctx_path.read_text().strip("\n"))
        else:
            body = re.sub(r"\n*" + re.escape(MARKER) + r"\n*", "\n\n", body).strip("\n")
    elif ctx_path.exists():
        sys.exit(f"roles/{role_dir.name}: {ctx_file} exists but body.md has no {MARKER} marker")
    notice = NOTICE.format(role=role_dir.name)
    return f"---\n{fm_text}\n---\n\n{notice}\n\n{body}\n"


def main():
    check = "--check" in sys.argv
    roles = sorted(p for p in (ROOT / "roles").iterdir() if p.is_dir())
    if not roles:
        sys.exit("no role directories under roles/")
    drift = []
    for role_dir in roles:
        outputs = {
            ROOT / "agents" / f"{role_dir.name}.md": render(role_dir, "claude.yml", "claude-context.md"),
            ROOT / "pi-agents" / f"role-{role_dir.name}.md": render(role_dir, "pi.yml", "pi-context.md"),
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
    if check:
        if drift:
            print("rendered files out of date — run scripts/render_roles.py and commit:")
            print("\n".join(f"  {d}" for d in drift))
            sys.exit(1)
        print(f"{len(roles)} roles rendered clean")


if __name__ == "__main__":
    main()
