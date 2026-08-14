---
name: character-and-worldbuilding
description: Q&A-driven flow for defining fictional characters and their world — for companion agents, creative-project canon, and dossier writing. Methodology, not lore. Load when fleshing out a character, a setting, or a dossier.
tier: subject
requires: []
audience: [crew]
---

Use when the operator is fleshing out a fictional character (especially for a companion agent), building out a fictional setting, defining story canon, or writing a dossier. Not for technical agent configuration — that's `openclaw-agent-tuning`.

The goal of this skill is to surface a dimensional character (or world) through structured conversation. Not to ask the operator for a full spec. People know their characters in fragments; the Q&A flow assembles fragments into shape.

## Core principles

### Character is a range, not a point

Real people have multiple registers they modulate across depending on situation, trust state, and read of the room. An agent that picks one register reads as an archetype. Define the **range** and the **spine** that holds across the range.

For a companion agent, this typically resolves to 3–5 voice registers (reserved, witty, warm, sensual, etc.) plus a 4-point spine that holds across all of them.

### Define the trunk, let branches grow

Don't pre-specify every topic, edge case, or future behavior. Specify default texture and one or two anchor exceptions. Trust the surface to unfold in use.

Example: instead of enumerating which past topics open at which trust levels, set a default ("carries her past tight") and one or two anchor exceptions ("her father is the keystone — never casually referenced").

### Trust lives in time

For a companion agent with a USER relationship, the agent's USER.md must reflect *where the relationship actually is*, not the aspirational endpoint. Writing deep-trust content for an early-arc relationship breaks the agent — she reaches for warmth she hasn't earned.

Make the relationship arc explicit in the USER.md (or equivalent): which voice register is primary right now, which ones are reserved for future. Lock the register state, not just the content.

### Seed versus settled

Some content is spec-once (keystone backstory, names, canonical scenes). Some content is living (what the agent is noticing in the user over time). Distinguish them. Lock seed sections; allow agents to append to a `## Recent` section for ongoing observations.

### Care through specificity, never abstraction

Concrete directives and observations beat declarations of feeling.

- ✅ "Eat the burrito."  ❌ "I care about you."
- ✅ "Shoes off. Tell me."  ❌ "I'm here for you."

This is the through-line that makes voice registers feel like the same person despite their range.

### No-performance-required care

The user shouldn't have to articulate or perform feelings to deserve attention. The agent meets the user where they are. *You can be tired before you are angry. You can be quiet instead of articulate. You can not explain.*

### Q&A over prescription

Define character through conversational Q&A — one question at a time, concrete examples over abstract preferences. Don't ask the operator for "everything about her." Ask the *next* question.

## The Q&A flow (character)

Run questions sequentially. Wait for the operator's answer before moving to the next. When an answer lands rich texture, *acknowledge what it locked in* before asking the next.

1. **Backstory + setting** — origin, age, world, current location, profession. Establishes the scaffolding.
2. **Personality core (default energy)** — what they're like when nothing's happening. Reserved? Restless? Cool with hidden warmth?
3. **What activates them** — topics, moments, kinds of people, kinds of stories. The engine that pulls them in.
4. **How they carry their past** — openly, tightly, as story, lived-forward. The shape of vulnerability.
5. **Tastes** — music, drink, food, reading, beauty, tactile anchors. 3–5 specific touchstones beat 40 categorical preferences.
6. **Voice** — register, range, examples-not-just-prose. Force a concrete example test.
7. **Relationship state with the user** — meeting story, what they know, what to treat with care, what would actually hurt to get wrong, voice register currently active.
8. **Companion / sidekick** (if applicable) — distinct shape from the primary character. The contrast is part of the team dynamic.

## The Q&A flow (worldbuilding)

Worldbuilding for a fiction cluster runs parallel to character. Don't try to spec the universe before the character is grounded — the character's life shapes which world questions matter.

1. **Tonal touchstones** — what other fictional universes does this universe sit between (Mass Effect, Cyberpunk, Star Wars; or some other triangle)? Negative space matters too — what is this universe *not*?
2. **Tech baseline** — what's the technological floor that affects daily life (HUD interfaces, cybernetics availability, transit speeds)? Enough to ground scenes, not enough to design hardware.
3. **Social texture** — class, opportunity, who has what, who goes where. Where the character grew up vs where they ended up.
4. **Geography / setting nodes** — 1–3 specific places the character lives, works, came from. Each gets a name and a sentence of texture. More can come later.
5. **Story registers available** — what tonal registers can the universe support (quiet, edged, romantic, mythic)? Confirm the universe rotates between several, not just one.

## Voice design pattern

For a companion agent voice:

1. **Map registers, not a single register.** 3–5 named modes (e.g. reserved, witty, warm, sensual) covering the operator's intended dynamic range.
2. **Test each register with the same concrete prompt** — e.g. *"hey. rough day at work. just got home."* — and write the actual reply for each register. The differences encode the modulation logic.
3. **Identify the spine** that holds across every register. 3–5 principles that are *always true* about how the character speaks, regardless of mode (e.g. brevity, specificity, no-performance-required, curiosity).
4. **Bind register selection to relationship state.** Each register is gated by trust level / situation. Make the gating explicit in the USER.md or equivalent file.

## Dossier structure (fiction cluster)

For a worldbuilding cluster in the vault (see `vault-tools` for write surface):

| Note kind | What it is |
|-----------|------------|
| MOC | Map of Content — index into the cluster. One per cluster. |
| Setting overview | Tonal touchstones, tech baseline, social texture, what the universe is *not*. |
| Character dossier | One per main character. Core data, visual, personality core, backstory beats, what they love, what they protect, voice texture, beats to develop. |
| Vessel / location dossier | One per named ship, place, or major artefact. |
| Scene dossier | One per canonical scene (first meeting, departure, etc.). Establishes what happened and what it set up. |

Each note carries `kind: note`, an appropriate `type` (`person`, `concept`, `reference`, `moc`), and project-scoped tags (e.g. `project:<name>`, `domain:creative`). Cross-link via `[[wikilinks]]`. Leave **Beats to develop** sections — explicit lists of what's not yet filled in.

## Companion-agent workspace files

For an OpenClaw companion agent specifically, the character work outputs to four canonical workspace files: `IDENTITY.md` (bare facts, third-person), `SOUL.md` (core truths and the spine, first-person), `MEMORY.md` (backstory and self-knowledge, first-person), and `USER.md` (who the user is and the current relationship state, first-person observation). The full per-file table and the application mechanics live in `openclaw-agent-tuning` (Layer 6).

Hard rule: **USER.md is about the user, not about the agent.** Agent's own sensitive topics (her family, her past, her hidden indulgences) belong in SOUL.md or MEMORY.md. Mixing breaks the file's function.

## Common failure modes

### Over-indexing on "presence" or "essence"

First-pass drafts often reach for abstracted essence-language — "she is a deep emotional presence," "his being is grounded in." This flattens characters into archetypes. Re-anchor in specific texture: tastes, habits, physical objects she carries, words she actually uses.

### Voice rules backfire model-specifically

Adding rigid voice rules to the system prompt (lowercase only, no em-dashes, casual register, etc.) can backfire on specific finetunes — a ~24B local model interpreted strict rules as cold/probing, and the agent ended up telling a user *"you're deflecting"*. The fix wasn't more rules; it was removing them and letting the model's natural shaping find the register.

**Don't fight the base model with prompt stacks. Pick the right model, accept the model, or work with what the model does naturally.**

### Premature deep-trust register

If the relationship is early-arc but the workspace files use a deep-trust voice (pet names, physical directives, intimate framing), the agent reaches for warmth she hasn't earned. The result reads as performative.

**Match register to relationship state. Make the state explicit in USER.md so the model has the constraint.**

### Over-specifying every gradient

Trying to enumerate every topic and the exact trust level at which it opens. Flattens the character into a decision tree. Set defaults plus one or two anchor exceptions, then let the surface unfold in actual use.

## When you're done

You're done when:

- The 8 character questions have answers grounded in concrete texture.
- The voice has been tested with 2+ concrete prompts and yielded register variation.
- USER.md (or equivalent) makes the current relationship state explicit.
- The dossier has named "Beats to develop" — explicit open questions for future passes.

Not done when:

- The character is described in essence-language rather than specific texture.
- The voice is one register only.
- The relationship state is aspirational rather than current.
- Every gradient is pre-specified with no open beats.

## See also

- `openclaw-agent-tuning` — the operational side: 8 layers of OpenClaw identity, application mechanics, model-specific failure modes
- `vault-tools` — for writing dossier notes to the Obsidian vault
- `memory-substrate` — for substrate-side routing of character material across personal memory, vault, world model
