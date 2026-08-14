---
name: browser
description: Drive a real headless browser (navigate, read rendered pages, click, type, screenshot) via the federated `browser` MCP tools — a shared browserless/Chromium behind a Playwright-MCP server. Use when a task needs the *rendered* page (JS-executed content, an interactive site, a screenshot) rather than a raw HTTP fetch. Any client whose LiteLLM VK holds the `browser` access group gets these tools.
tier: subject
requires: [mcp:browser]
audience: [crew]
expects-local: [litellm-access-map]
---

## When to use this

Reach for `browser` when the task needs a **real, rendered** page — not just raw HTML:

- A site that renders its content with JavaScript (SPAs, dashboards, docs that hydrate client-side).
- You need to *see* the page: a screenshot, or the accessibility/structure snapshot to reason about layout.
- Light interaction: click a control, type into a field, wait for something to appear.

Don't use this for:

- Plain web search or fetching a static article — use `searxng-search` (cheaper, no browser).
- Reading our own vault/knowledge — use `vault_search`.
- Files in the current workspace — use `Grep`/`read`.

## The tools

All are prefixed `browser-` and take/return JSON. The core set (curated allowlist):

- `browser-browser_navigate(url)` — open a URL. **Returns the rendered page snapshot inline** in the result (URL, title, and an accessibility snapshot). This one call is usually all you need to *read* a page.
- `browser-browser_snapshot()` — the accessibility/structure snapshot of the current page (elements, roles, text) — the primary way to *read* a page for reasoning, cheaper than a screenshot.
- `browser-browser_take_screenshot(options?)` — a PNG of the current page, when the user needs to *see* it.
- `browser-browser_click(element)` / `browser-browser_type(element, text)` — interact with a control identified from the snapshot.
- `browser-browser_wait_for(condition)` — wait for text/an element before the next step.
- `browser-browser_console_messages()` — page console output (useful for debugging a broken page).
- `browser-browser_evaluate(fn)` — run JavaScript in the page. Powerful (arbitrary in-page JS) — use it for extraction only when a snapshot won't do.

## Pattern

- **Navigate-and-read (the common case):** call `browser-browser_navigate(url)` and read the snapshot it returns inline. Done — no separate snapshot call needed.
- **See it:** `navigate` → `browser-browser_take_screenshot`.
- **Interact:** `navigate` → read snapshot → `browser_click`/`browser_type` (referencing elements from the snapshot) → `browser_wait_for` → re-snapshot.

## Statefulness — important caveat

Browser state may **not persist across separate tool calls** when the browser is a shared service reached through MCP federation: each call can land on a fresh browser context (a clean `about:blank`). In practice:

- `browser_navigate` returns the loaded page's snapshot **in the same call** — rely on that, not a follow-up `browser_snapshot`.
- Don't assume a `navigate` in one call and a `click`/`snapshot` in a *later* call share the same page. For multi-step interaction, keep the steps tight and re-establish state (re-navigate) if a later call comes back blank.

## Delivering results

- A **screenshot** is media: deliver it the way your harness delivers any generated file (see the `comfyui` skill's *Delivering the result* — chat gateways send it as a real attachment via the message tool with `action=send`; dev harnesses surface a file path). Never paste an internal/browser URL as if the user can open it.
- Extracted **text** (from a snapshot) can go inline in your reply.

## Auth

Routes through LiteLLM MCP. The gateway requires a LiteLLM virtual key as a Bearer token; the MCP client config supplies it (`Authorization: Bearer ${LITELLM_API_KEY}`), so individual tool calls need no extra credentials. Whether a given surface *has* the browser at runtime depends on its VK holding the `browser` access group (see `litellm-routing-model`).

## Security

The browser is a **request-forgery primitive**: `browser_navigate` can reach any URL the cluster network can, and `browser_evaluate` runs arbitrary JS in the page. Treat the `browser` VK group as a real trust boundary — it belongs to dev-capable/operator surfaces, not to low-trust personas by default. The concrete allowlist and which surfaces hold the capability are deployment-specific and live in the consumer's local skill.
