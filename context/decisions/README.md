# Decision log

Append-only log of non-trivial design and technology decisions. The
intent is that, months from now, anyone can read the log in order and
understand both *what* was chosen and *why*.

As of this commit, **no decisions have been recorded.** This file
describes the format that future decision files will use.

## File naming

One file per decision, named:

```
NNNN-slug.md
```

- `NNNN` is a **zero-padded four-digit sequence number**, starting at
  `0001` and incrementing by one for each new decision. Gaps are not
  allowed; superseded decisions keep their number.
- `slug` is a short kebab-case description of the decision topic, e.g.
  `0001-language-and-runtime.md` or `0007-pack-size-model.md`.

## File contents

Each decision file uses the following sections, in this order. Keep
sections present even when short — empty sections are a signal that
the decision is not yet ready to land.

### Context

Why is this decision being made now? What surrounding facts about the
business, the system, or the previous decisions make this the moment
to choose? Link to relevant context files
(e.g. [`../product-ideology.md`](../product-ideology.md)) rather than
restating them.

### Options considered

The candidates that were on the table. Each option gets a short
paragraph: what it gives, what it costs. Reject candidates that were
seriously evaluated are listed here so the next reader knows they were
not overlooked.

### Choice

The chosen option, stated unambiguously in one or two sentences. No
hedging.

### Rationale

Why this option over the others. Strict, honest reasoning — not a
post-hoc justification. If the deciding factor was "the owner
preferred it", say so.

### Date & by-whom

The date the decision landed, and the person (or people) who made it.
Format: `YYYY-MM-DD — <name(s)>`.

### Consequences — things this now blocks or unblocks

What this decision enables (work that can now start), what it
forecloses (paths now closed off), and which open questions it
resolves. Link to the relevant entries in
[`../open-questions.md`](../open-questions.md).

## Append-only discipline

Decision files are **not edited in place** once landed. If a
decision is later changed or reversed:

1. Write a **new** decision file with the next sequence number.
2. Its **Context** section explicitly references the file being
   superseded (e.g. "Supersedes `0003-…`").
3. Its **Consequences** section notes that the older decision is now
   inactive.
4. Do **not** delete or rewrite the older file. Add a one-line note
   at the top of the older file pointing forward to the superseding
   decision, and only that.

This way the log is always a faithful timeline. Anyone reading the
files in numeric order sees the project's actual decision history,
including reversals, rather than a sanitised final state.

## When to record a decision

Record a decision when:

- A choice closes off other reasonable choices (language, framework,
  database, pack-size model, …).
- Multiple agents or humans would otherwise re-litigate the question.
- The choice constrains code that has not been written yet — record
  before writing.

Do **not** record a decision for: routine implementation details,
naming preferences inside a single screen, choices fully contained in
one commit that touches no public interface.
