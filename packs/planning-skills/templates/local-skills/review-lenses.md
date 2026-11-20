---
name: <project>-review-lenses
description: <Project>'s cross-functional review lenses — the questions each partner function asks of a product concept, and the route to the role that answers them. Load when working out which partners a product concept needs.
---

<!-- planning-skills slot: review-lenses. Read by cross-functional-review.

     How this slot combines with the pack's defaults. The pack ships five default lenses:
     security, privacy-legal, data, accessibility, operations-support.
     - A section whose heading matches a default lens name OVERRIDES that default entirely.
     - A section with a new name ADDS an org-specific lens.
     - A section whose heading matches a default and whose body is only `n/a` (optionally
       followed by a reason) SWITCHES THAT LENS OFF for this project.
     - A default lens with no section here runs as shipped.
     Every review says which lenses came from this slot and which are defaults.
     cross-functional-review can draft a lens for you from the partner's own checklist
     or past review comments. -->

## Lens: <lens-name>

> **▸ Fill:** copy this section once per lens you override or add. Use a default's exact name (`security`, `privacy-legal`, `data`, `accessibility`, `operations-support`) to override it, or a new kebab-case name to add one. To switch a default off, the body is just `n/a — <reason>`.

### Questions this partner asks

> **▸ Fill:** the questions this partner puts to any concept, in their words where you can — what data it touches, who it affects, what it promises customers, what it hands them to check. A concept that raises none of them leaves the lens quiet.

### Route

> **▸ Fill:** the role that answers for this partner and how to reach it (a queue, a channel, a recurring review). A role, never a named person.
