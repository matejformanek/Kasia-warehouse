**`context/state.md` is the cold-start anchor for the next agent. Treat it as load-bearing.**

The next agent — possibly you in two weeks — opens `context/state.md` first. If it's stale, the agent rebuilds context wrong. Keep it honest.

## Update cadence

At the end of every working session, and whenever you're about to hand off:

1. **Done** — append what was completed, with the ISO date (`YYYY-MM-DD`). Link to the relevant `context/decisions/NNNN-*.md` entry if a decision was made.
2. **In progress** — update what's actively underway. If nothing is in progress, leave the section header with an empty list rather than deleting the section.
3. **Next** — reorder if priorities shifted. Smallest-grain first; the top item should be picked-up-able in one session.

## Style

- Bullets, dates, links. No narrative paragraphs.
- One line per bullet where possible.
- Reference files by relative path (`context/decisions/0003-db-choice.md`), not by description.
- Keep the whole file scannable in under 30 seconds.

## Honesty

Never let `state.md` lie:

- If you got blocked, write that. Name the blocker.
- If you abandoned a path, write that. Reference the decision (or open question) that closed it.
- If you discovered the plan was wrong, write that — and update `context/open-questions.md` or draft a new decision.

A wrong `state.md` is worse than no `state.md`. The whole point is cold-resumability — by the next agent, or by you after a long break.

## What goes elsewhere

- Long-form reasoning → `context/decisions/NNNN-*.md`
- Open questions and unknowns → `context/open-questions.md`
- Workflow descriptions → `context/workflows.md`
- Anything ephemeral (session notes, scratchpads) → not in the repo

## Cross-references

- `context/state.md` — the file itself
- `decision-log-discipline.md` — `state.md` links new decisions, doesn't replace them
