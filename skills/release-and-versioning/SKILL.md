---
name: release-and-versioning
description: How to version and publish what a repository produces — one semver line per repo rather than per component, the version living in a file with the tag only selecting it, release notes sourced from a changelog, and checksums plus verified build provenance on every asset. Load before adding a release workflow, cutting a first release, changing a tag scheme, or reviewing anything that publishes an artifact consumers pin. Covers the failure modes that report green while publishing nothing, or the wrong bytes.
tier: concept
requires: [external:github, cli:gh]
expects-local: [platform-conventions]
---

# Release and versioning

A version is how a consumer says what they depend on, and how a maintainer says
what changed. A commit sha says neither. Everything below follows from that.

## The version lives in a file; the tag only selects it

Put the number in `VERSION` (or the language's manifest) and make CI **refuse a
tag that disagrees**:

```
tag v1.2.0 does not match VERSION (1.1.0)
```

Without that check, `v1.2.0` can ship `1.1.0` bytes and nothing downstream can
tell. This is the cheapest gate in this skill and the one most often missing.

**Every manifest that states the version must agree, and that is checked on
every push — not at release time.** Repos accumulate places that restate it: a
`pyproject.toml`, a `plugin.json`, a chart's `version`. Drift found on the tag
is drift found too late, when the fix is a new version rather than a commit.

## One release line per repository, not per component

The tempting design is a line per component — `v*` for the images,
`thing/v*` for the CLI — justified by "they move at different rates, so a
consumer pinning one shouldn't re-evaluate the other."

That reasoning is about the maintainer. What a consumer sees is a releases page
where **no entry describes the repository**, and where the forge labels
whichever shipped last as "Latest". Two independent lines produce colliding
numbers: a CLI's `0.2.0` appears to supersede the images' `0.1.0`.

Prefer one version covering everything the repo publishes. The cost is real and
worth stating in the changelog: a component's version stops meaning "what
changed in that component". The changelog means that. In exchange there is one
number to reason about and one page that describes the whole repo.

**A release should build everything from the one tagged commit** rather than
reusing artifacts from earlier builds. It is slower and it is rare; the
alternative is a release whose parts came from different commits, which nobody
can debug later.

## `version` is not `appVersion`

Two different facts, both worth publishing:

```
thing:cuda-v0.34.0    what is INSIDE          (moves)
thing:cuda-1.2.3      OUR packaging of it     (cut once)
```

Conflating them is a trap: change a Dockerfile without changing the upstream
release and `v0.34.0` is overwritten with different bytes.

**Pin what is inside; never resolve it at build time.** A workflow that asks the
upstream API for "latest" during the build makes releases non-reproducible — the
same tag rebuilt next month bakes something else, and a local build (using the
file's default) produces a third answer. Pin it in the repo, make bumping it a
reviewable commit, and let a scheduled job be the thing that tracks upstream.

## A repackaging repo's version describes *your* build

When a repo republishes someone else's artifact, its version is **not** theirs.
Rebuilding the same upstream release with a fixed build script is a patch bump
*here*. Upstream's version, and any compatibility tuple (ABI, runtime,
architecture), belongs in the artifact filename and a build-info file — not in
the tag. A tag cannot carry five axes and stay readable.

## Decide the prerelease policy, and enforce it

`v1.2.3-rc1` typically matches a trigger glob like `v*.*.*` but not the strict
`^v[0-9]+\.[0-9]+\.[0-9]+$` a publish path checks. The usual result is a version
that evaluates to empty, falls through to a fallback label, and **overwrites the
stable tags**. Either support prereleases explicitly or reject them loudly.

## Notes come from a changelog

Generate release notes from a `## <version>` section, and **fail the release if
that section is missing or still marked unreleased**. Publishing notes headed
"unreleased" is how a changelog stops being read.

## Assets: checksum, attest, and verify what you attested

Every downloadable asset ships a checksum beside it, so a URL pin is verifiable.
Mint build provenance — and then **verify it in the same job that produced it**.
An attestation nobody checks is decoration, and a step that silently produced
nothing is indistinguishable from one that worked.

Give the verification a selftest: confirm it *fails* on an artifact without
provenance. A gate is only proven by seeing it reject something.

## Never publish over an existing release

Refuse if the release already exists. A rebuild is a new version.

This matters most where a guard already appears to exist. A comparison-based
guard is only as good as what it compares: if the compared file is a
deterministic function of the inputs, a rebuild from *changed build code*
produces an identical file, passes, and replaces bytes under a URL consumers
pin. Removing the replace path entirely is stronger than teaching the guard to
compare more files.

If the forge offers immutable releases, that enforces this for free. If the
project deliberately keeps releases mutable, say so where consumers read it, and
keep the CI refusal so a replacement is at least deliberate.

## Publishing must never queue behind another publish

`cancel-in-progress: false` protects a run that is already executing. It does
**not** protect a *pending* one — forges commonly keep a single pending run per
concurrency group and cancel older ones. Two merges in quick succession can
therefore leave a commit with no published artifact at all. Give every
non-PR ref its own concurrency group, keyed by commit.

## Pin by digest; read the version to decide whether to move

A tag can move; a digest cannot. Semver exists to say whether a digest change
was a patch or a break — which a sha cannot express. Consumers should pin the
digest and read the version.

**The concrete pinning rules are deployment policy, not release policy** — how a
consumer records digests, and what needs verification before a pin changes,
belongs to the local `platform-conventions` skill. Publish the digest somewhere
findable (a job summary, a release asset) and stop there.

## Reviewing a release workflow

- Does a tag that disagrees with the file fail? Does a prerelease?
- Does every manifest restating the version get checked on ordinary pushes?
- Can one release line's tag trigger another's publish path? Trace the trigger,
  not the intent — a tag push is an ordinary push event.
- Does any label expression fall through to a literal like `latest`? That
  bypasses whatever guard protects the stable tags, because the label *is* the
  stable tag.
- Is provenance verified, or only produced?
- Is there a replace path, and what does its guard actually compare?
