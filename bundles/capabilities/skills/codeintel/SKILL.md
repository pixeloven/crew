---
name: codeintel
description: Code intelligence — SAST (static analysis) and AST/structural queries over source. The federated `semgrep` MCP tools (any VK with the `codeintel` access group) plus the `ast-grep` and Serena LSP CLIs baked into dev images. Use to security-scan a diff, find a structural code pattern, or navigate/refactor by symbol — beyond plain text grep.
tier: subject
requires: [mcp:codeintel]
audience: [crew]
expects-local: [litellm-access-map]
---

## When to use this

Reach for `codeintel` when a task needs to *understand code structure*, not just match text:

- **Security-scan** a file or diff for vulnerabilities (SAST) before merge.
- **Structural search/refactor** — find/rewrite by syntax shape ("every `except:` with a bare pass", "all calls to `foo(` with a literal first arg"), which regex can't express reliably.
- **Symbol navigation** — go-to-definition, find-references, rename across a codebase (LSP).

Don't use this for:

- Plain text search in the current workspace — use `Grep`.
- Running/booting the app — use `coder-workspace-dispatch`.

## Federated tools — `semgrep` MCP (via the `codeintel` access group)

- `security_check(code_or_path)` — quick security-focused SAST pass.
- `semgrep_scan(...)` — run Semgrep's registry rulesets.
- `semgrep_scan_with_custom_rule(code, rule)` — scan with an **inline** YAML rule you supply.
- `get_abstract_syntax_tree(code, language)` — the AST for structural reasoning.

**Tokenless limitation (important).** Without a Semgrep cloud token, the MCP is crippled: registry configs (`p/*`, `auto`) are login-gated and return **0 findings**, and `semgrep_scan` rejects local `config` *paths* (path-traversal guard). In practice **only `semgrep_scan_with_custom_rule` (inline rule) works reliably** through the MCP. So treat the MCP as a *supplement* for ad-hoc inline checks — the real, comprehensive SAST gate is the CLI running in CI against the vendored ruleset baseline, not this MCP. (`semgrep_findings` is deliberately excluded from the allowlist — it needs a cloud token we don't set and would only surface auth errors.)

## CLI tools (dev images: pi.dev / Claude Code)

- **`ast-grep`** — structural code search & rewrite by AST pattern. `ast-grep run -p '<pattern>' -l <lang>` to find; `-r '<rewrite>'` to refactor. The right tool for "change this syntactic shape everywhere," where a regex would be fragile.
- **Serena (LSP)** — language-server-backed navigation (definitions, references, rename) for precise, symbol-aware edits. Spike-gated; watch memory on huge `node_modules` trees.

These are CLIs, not MCP tools — available where they're baked into the image, independent of the `codeintel` VK group.

## Pattern

1. **Scan a diff before merge:** `security_check` (or an inline `semgrep_scan_with_custom_rule`) over the changed files; triage findings.
2. **Structural refactor:** `ast-grep run -p …` to preview matches, then `-r …` to rewrite; review the diff.
3. **Understand unfamiliar code:** Serena for go-to-def / find-refs; `get_abstract_syntax_tree` when you need the raw shape.

## Auth

The `semgrep` MCP routes through LiteLLM MCP — the client config supplies the LiteLLM virtual key as a Bearer token; availability depends on the VK holding the `codeintel` access group (see `litellm-routing-model`). The `ast-grep`/Serena CLIs need no credentials.

## Security

SAST results are advisory signal, not proof — a clean scan is not a guarantee, and findings need triage (false positives are common). The comprehensive gate is CI, not an interactive scan. Structural rewrites (`ast-grep -r`, Serena rename) mutate code — review the diff before committing, same as any edit.
