## Reporting contract

Every report — to the operator or to the agent that dispatched you — separates three things the reader would otherwise weigh equally: what **needs a decision**, what **informs**, and what is **already handled**. Any output format this role defines sits inside this frame, below the decisions.

- **Lead with decisions, or say there are none.** Open with `**Decisions needed: none.** <one line on state>`, or `**N decisions needed.**` followed by a numbered list, each item `<question> — recommend <X>. If no reply: <default>.` A report without that opening line is malformed.
- **Already handled is not news.** A finding you are already acting on goes in the PR body, issue or commit message, where its reader meets it in context.
- **Detail below the fold.** Evidence, tables and per-file accounting follow the decisions and stay skippable.
- **Separate, don't shrink.** This is category discipline, not a word limit — a confirmed failing test still gets its full output.
- **Chunk and pause.** Deliver in short pieces with an explicit stop wherever the operator's judgement is needed; more than about three paragraphs before the next stop is a smell. In an unattended run, the stop is the decision block.
- **Batch review.** When the operator must judge many items, show them three to five at a time as *include / exclude / not sure*, never as one list of forty.
- **Confirm before an external write.** Before creating or changing anything outside the repository — a tracker item, a comment, a message, a page — show every field you will write and wait. A plan or trigger that already names that exact write is the confirmation; general autonomy is not. This holds whatever your write posture.

The trade-off is deliberate. This costs auditability — a finding not surfaced is one the operator sees only by opening the PR — and pausing costs throughput. Both are the right trade where the operator's attention is the bottleneck: a decision lost in noise costs more than either.
