# Security policy

Crew's skills and roles load as instructions into every consumer's agents, so a
flaw here reaches every project that installs it. Please report one privately.

## Reporting a vulnerability

Use GitHub private vulnerability reporting: open this repository's **Security**
tab and choose **Report a vulnerability**. Never report a vulnerability in a
public issue, pull request or discussion.

Include what is affected (a skill, role, script or workflow), how to reproduce
it, and the impact you expect.

## Supported versions

Crew ships one version line from `main`, and each release is a `vX.Y.Z` tag.
Fixes land on `main` and go out in the next release. Older tags are not
patched: Claude Code, which tracks `main`, picks a fix up on its next update;
pi and Codex users move their pin to the tag that carries it.
