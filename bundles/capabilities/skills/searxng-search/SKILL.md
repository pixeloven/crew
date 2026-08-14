---
name: searxng-search
description: Privacy-respecting public web search via the platform's self-hosted SearXNG MCP. Use when you need current public-web information (upstream docs, vendor changelogs, GitHub issues outside your own org) that the vault doesn't have. Two tools available — `searxng-searxng_web_search` for queries and `searxng-web_url_read` for URL-to-markdown extraction.
tier: subject
requires: [mcp:search]
audience: [crew, persona]
expects-local: [litellm-access-map]
---

## When to use this

Reach for `searxng-search` when:

- The vault (`vault_search`) doesn't have the answer.
- You need current public-web information — upstream docs, vendor changelogs, GitHub issues outside `<your-org>/*`.
- You want privacy-respecting search that stays on the operator's own infrastructure.

Don't use this for:

- Looking up things in the vault — use `vault_search`.
- Searching your own GitHub org — use `gh search`, `gh issue list`, `gh pr list`.
- Code search inside the current workspace — use `Grep`.

## The two tools

### `searxng-searxng_web_search` — public web search

Query SearXNG and get a synthesised result list. Common parameters:

- `query` (required) — the search string.
- `pageno` (default 1) — page offset.
- `time_range` — `day` / `month` / `year`. Bias results to recent material when the topic changes fast.
- `language` (default `all`).
- `safesearch` (default `0` — off).

Returns: an array of results with `title`, `url`, `content` (snippet), `engine`, `score`. Pull the top N, decide which `url`(s) deserve a follow-up read.

### `searxng-web_url_read` — URL → markdown

Fetches a URL and returns the body as markdown. Cleaner than raw HTML. Parameters:

- `url` (required).
- `startChar` / `endChar` — character range for chunked reads of large pages.
- `section` — target a heading by name.
- `paragraphs` — return only paragraph-level text.

Use after `searxng-searxng_web_search` when a snippet isn't enough and you need the actual page body. Note that anti-bot pages, paywalls, and JS-heavy SPAs may still return noisy or empty content — if so, report the gap rather than retrying or attempting anti-bot workarounds; when the *rendered* page is genuinely needed, that's a headless-browser capability (see `browser`), not this tool.

## Discipline

- **Anchor with a quoted unique landmark.** SearXNG dispatches to engines that tokenise aggressively — `pi.dev` loses the dot, `@org/package` may lose the org prefix, and a query of all-common terms ends up matching everything. Wrap a unique term (`"pi-subagents"`, a version string, a known URL fragment) in quotes. A bare `pi.dev coding agent subagents api` returns generic noise; `"pi-subagents" npm package` returns the actual project pages on the first try.
- **Don't over-narrow with categories.** SearXNG accepts a `categories` param (e.g. `it`) that filters to developer-focused engines. Useful for generic technical queries — but on already-anchored queries, narrowing the engine pool can drop relevant general results. Try without the filter first; only narrow if the result set is too noisy.
- **Don't loop more than ~5 searches without a clear reason.** Bandwidth, bot detection on upstream engines, and your own context budget all push back.
- **Don't query for things obviously inside the platform itself.** LiteLLM endpoints, vault notes, internal docs — those have direct tools.
- **If a search or read tool returns an error, stop and report.** Don't auto-retry. SearXNG's limiter is conservative for a reason.

## Why this and not Exa / Perplexity / Gemini

The platform self-hosts SearXNG; queries stay on the operator's own infrastructure — no third-party API key, no third-party query logs. Bundled web-search packages (e.g. `pi-web-access` which uses Exa MCP, Perplexity, and Gemini) trade that privacy for zero-config convenience. See `litellm-routing-model` for the principle (LLM traffic through LiteLLM; search through SearXNG; everything stays inside the boundary).
