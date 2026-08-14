---
name: comfyui
description: Media generation via the federated ComfyUI MCP tools — generate an image, picture, illustration, avatar, or audio from a text prompt; run ComfyUI workflows; browse, convert, and deliver generated assets. Covers job polling, the two delivery paths (/view URL on allowlisted gateways vs inline bytes to a local file), and allowed_tools scoping so image surfaces never see the server's privileged host-path tools. Use when asked to make, draw, or generate a picture, image, or song.
tier: subject
requires: [mcp:imagegen]
audience: [crew, persona]
expects-local: [litellm-access-map]
---

## When to Use

Use for creative/media generation tasks: generating images, music, or running custom ComfyUI workflows. Not for infrastructure or knowledge tasks.

## Available Tools

Generation:
- `comfyui-generate_image(prompt, workflow?, options?)` → `{job_id, status}`
- `comfyui-generate_audio(prompt, options?)` → `{job_id, status}`
- `comfyui-run_workflow_url(url, inputs?)` → `{job_id, status}`
- `comfyui-regenerate(job_id, options?)` → re-run a previous job with same or modified params

Job management:
- `comfyui-get_job_status(job_id)` → job status, output asset IDs when complete
- `comfyui-cancel_job(job_id)` → cancel an in-progress job
- `comfyui-get_queue()` → current queue depth and active jobs

Assets — **two kinds of tool, and which one you need depends on the surface (see *Delivering the result*):**

*Metadata tools (return the asset's `/view` URL + provenance — the URL is the delivery handle on an allowlisted gateway):*
- `comfyui-list_assets(type?, limit?)` → browse generated assets (each with its `/view?…` URL)
- `comfyui-get_asset_metadata(asset_id)` → full provenance + the workflow snapshot + `/view` URL
- `comfyui-list_output_images(...)` → filesystem listing of output files

*Content tools (return the image BYTES inline — the fallback delivery path):*
- `comfyui-convert_image(asset_id, format, quality?)` → re-encodes to png/jpeg/webp and returns the bytes inline; **prefer this for the bytes path** — it lets you shrink to jpeg/webp to fit channel size caps, and it completes faster than `view_image` (which can hit an MCP call timeout on large PNGs)
- `comfyui-view_image(asset_id)` → the image as an inline image content block (PNG/JPEG/WebP only)
- `comfyui-get_image(filename, …)` → fetches by filename and returns bytes inline (use `get_history` first to get the filename)

The `/view?filename=…` URL points at the **ComfyUI server on the cluster's internal network**. Whether you deliver it *as a URL* (the gateway fetches it server-side) or fall back to *inline bytes* depends entirely on how the surface is configured — see *Delivering the result*.

Workflows:
- `comfyui-list_workflows()` → available ComfyUI workflows

## Pattern

1. Submit job → get `job_id`
2. Poll `comfyui-get_job_status(job_id)` until status is `complete`
3. Get the asset's `/view` URL from the job output (or `get_asset_metadata` / `list_assets`).
4. **Deliver it to the user** (see below) — the job completing is not the same as the user receiving the asset.

## Delivering the result

Generating an asset is only half the task — the user has to actually *receive* it as a native attachment. A raw `asset_id` or a `MEDIA:<asset_id>` token is never something the user can see. There are two delivery paths; which one applies depends on the surface.

**Primary — send the `/view` URL directly (chat gateways whose outbound-media fetch allowlists the ComfyUI host).** Deliver by passing the asset's `/view` URL as the attachment: `message(action=send, media="<comfyui /view URL>")`. The gateway fetches the URL server-side and uploads the bytes as a real photo — no local file, no byte-wrangling. Pass the URL as the **`media` argument**, never as message *text* (as text it shows as an unreachable link).

> The `/view` URL points at the ComfyUI server on the cluster's internal (private) network, so the gateway's outbound-media fetch must be allowed to reach that host. OpenClaw gates this with a host allowlist — the ComfyUI host must be listed in `messages.media.allowedHostnames`. If a URL send is refused with a private-IP / SSRF error, the host simply isn't allowlisted: that's a one-line deployment-config fix (add the host), **not** a reason to fall back to pasting the URL as text. The concrete host and allowlist live in the consumer's local skill.

**Fallback — inline bytes to a local file (surfaces with a filesystem/exec tool, or when the URL genuinely can't be fetched).** A *content* tool returns the image as an **MCP image content block** — `{ "type": "image", "data": "<base64>", "mimeType": "image/png" }`. The host passes that through inline: it does **not** offload it to a media store, mint a `media://` reference, or auto-attach it (auto-attach and `media://inbound/<id>` refs are for *user→agent* channel attachments and the host's *native* image-generation tool — not a federated-MCP tool result). So it's only deliverable if you can land the bytes on a local file the send tool can read:
  1. `comfyui-convert_image(asset_id, format="jpeg", quality=80)` → inline bytes (preferred — fits size caps, faster than `view_image`).
  2. Write the bytes to a **local file** under an allowed media root — for OpenClaw `/tmp/openclaw/<name>.jpg` or the workspace dir; for dev harnesses any session path.
  3. Send the **path**: `message(action=send, media="/tmp/openclaw/<name>.jpg")` (a local path, not a URL); on a dev harness, surface the path for the operator to pick up.
  - `media=` does **not** accept `data:` URIs or inline base64. `comfyui-get_image(save_dir=…)` and `comfyui-convert_image(out_path=…)` write on the **ComfyUI/MCP server's** filesystem, not yours — use the **inline bytes** and write them locally yourself.

A surface with neither a host allowlist nor a filesystem tool cannot deliver — say so plainly rather than pasting an internal reference.

Confirm the asset reached the user, not merely that the job reported `complete`.

## Auth

Routes through LiteLLM MCP. The gateway requires a LiteLLM virtual key as a Bearer token; the MCP client config supplies it (`Authorization: Bearer ${LITELLM_API_KEY}` in the MCP client config), so individual tool calls need no extra credentials.

## Security — this server is more than image generation

The full server exposes **~35 tools**, and the catalog is **not** limited to generation. Alongside `generate_image` / `generate_audio` / `run_workflow_url` it carries **privileged operational tools** — host-path and manifest operations and node-control actions (e.g. `add_extra_path`, `apply_manifest`, `bisect_start`). Those can read/write host paths, mutate ComfyUI's deployed configuration, and drive node lifecycle. They are not something an image-generating surface (a chat UI, a companion agent, a web app) should be able to call.

**Scope with a per-server `allowed_tools` allowlist** to the generation subset — the `generate_*`, `run_workflow_url`, `regenerate`, job-management, and asset/read tools above — and exclude the host-path/manifest/node-control tools. This is the only reliable per-server tool restriction (`disallowed_tools` is broken in v1.86.2; see `litellm-routing-model`). A surface granted the image-generation capability should see only the generation subset, never the full 35.

The concrete allowlist and which surfaces hold the image-generation capability are deployment-specific — they live in the consumer's local skill.
