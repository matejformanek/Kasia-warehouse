# 0068 restructure — discrepancy log

> Companion to [`decisions/0068`](../decisions/0068-code-architecture-restructure.md)
> + [`0069`](../decisions/0069-css-externalization.md). The restructure is
> **behavior-preserving**. Centralizing duplicated code and scattered CSS will
> surface pre-existing inconsistencies (a padding that differs between two
> screens, a guard applied on one číselník but not another, a copy-paste that
> drifted). This is the log where each is recorded and its resolution decided.

## How to use this log

For every inconsistency found while consolidating:

1. **Record it** below with: where, what differs, and the two (or more) variants.
2. **Classify the resolution:**
   - **Inert** — pure code/CSS consolidation with *no* rendered/behavioral change
     (e.g. identical rules deduped). Just note it; no approval needed.
   - **Behavior/pixel change** — the consolidation would change what a user sees
     or how the app behaves. **Do NOT fold it in silently.** Flag it, pick the
     intended variant, and get **explicit approval from Matej** before landing.
     If it's out of scope for the restructure, leave the behavior as-is and note
     it as a follow-up instead.
3. Reference the resolution in the commit that touches it.

The rule: a "no-behavior-change refactor" must actually change no behavior.
Anything that would is escalated here, not absorbed.

## Log

| # | Location | Discrepancy | Variants | Resolution | Approved? |
|---|----------|-------------|----------|------------|-----------|
| 1 | `inventory/tests.py` (6 tests) | White-box tests monkeypatched `services.<helper>`/`services.EmailMessage`; after the services split the call-sites look those names up in submodule namespaces. | patch `services.X` vs patch where used | **Inert** — re-pointed 6 monkeypatch targets to `services.dodaci_list.*` / `services.email.*` (patch where the name is looked up). Assertions unchanged; no app-behavior change. | n/a (inert) |

## Follow-ups deferred (not fixed in this restructure)

- _(none yet)_
