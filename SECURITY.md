# Security policy

Crew's skills and roles load as instructions into every consumer's agents, so a
flaw here reaches every project that installs it. Please report one privately.

## Reporting a vulnerability

Use GitHub private vulnerability reporting: open this repository's **Security**
tab and choose **Report a vulnerability**. Never report a vulnerability in a
public issue, pull request or discussion.

Include what is affected (a skill, role, script or workflow, or a pack under
`packs/`), how to reproduce it, and the impact you expect. This policy covers
the packs folded into this repo too.

## Supported versions

Crew and its packs ship one version line from `main`, and each release is a
`vX.Y.Z` tag. Fixes land on `main` and go out in the next release. Older tags
are not patched: consumers move their marketplace `ref` (Claude Code, Codex) or
package pin (pi) to the tag that carries the fix.
