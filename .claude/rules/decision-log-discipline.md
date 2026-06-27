**Every non-trivial decision is recorded in `context/decisions/NNNN-slug.md` before it lands anywhere else.**

## Format

See `context/decisions/README.md` for the canonical template. Each entry has:

- **Context** — what's the situation, what triggered the choice
- **Options considered** — what we looked at, briefly (one line each is fine)
- **Choice** — what we picked
- **Rationale** — why this over the others
- **Date & by-whom** — ISO date, decider
- **Consequences** — what this now blocks, unblocks, or commits us to

Numbering is monotonic: `0001-`, `0002-`, etc. Slug is short-kebab-case.

## What counts as non-trivial

- Any tech choice — language, framework, ORM, DB engine, deployment target, frontend approach, auth model, PDF library, etc.
- Schema shape decisions — e.g. mass-only vs pack-as-SKU, multi-tenant vs single, soft-delete vs hard
- New models that persist user-submitted data (e.g. `Feedback` per 0046, `ContactInquiry` per 0051) — the durability/retention story is a decision, not an implementation detail
- Workflow shape that contradicts something in `context/workflows.md` (update `workflows.md` in the same change)
- Anything you're about to do that you can't easily undo

When in doubt, write the entry. A cheap entry is better than a missing one.

## Append-only

Decisions are never edited in place once merged. To change a prior decision:

1. Write a new entry `NNNN-<new-slug>.md` that references the superseded one by number.
2. Add a one-line `> **Superseded by NNNN**` note at the **top of the old file**, immediately under the title — that is the only permitted edit to a prior entry. (Matches step 4 of the append-only protocol in `context/decisions/README.md`.)

This preserves the reasoning trail. Future agents need to know why the old choice was made, not just that it changed.

## Process

If a decision is forming in the conversation:

1. Pause coding or editing.
2. Draft the entry in `context/decisions/`.
3. Ask the user to confirm wording, especially **Choice** and **Consequences**.
4. Once confirmed, proceed with the work the decision unblocks.

Do not write code that depends on an unmerged decision. See `no-premature-tech-choices.md` — these rules reinforce each other.

## Cross-references

- `context/decisions/README.md` — canonical template and index
- `no-premature-tech-choices.md` — why decisions gate code
- `state-file-discipline.md` — `state.md` should link new decisions in the **Done** section
