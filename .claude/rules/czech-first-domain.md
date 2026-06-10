**The business runs in Czech. When uncertain about a domain term, defer to the Czech meaning — not the English approximation.**

The English glosses in `context/domain-glossary.md` are a convenience for non-Czech readers. They are not the source of truth. The Czech term governs the semantics.

## Specific terms that are routinely mis-mapped

- **`dodací list`** is *not* "delivery note" in the generic British/American sense. It is the Czech document that accompanies goods on issue, listing items, quantities, and batches. It is the basis the *účetní* (accountant) uses to issue a *faktura* (invoice). An English-speaking developer who treats it as a generic packing slip will model it wrong.
- **`výdejka`** and **`příjemka`** are internal warehouse documents (issue slip / receipt slip respectively). They are distinct from `dodací list`. Do not conflate them in schema, UI, or prose.
- **`mezisklad`** is a real warehouse concept — an intermediate storage location, often used between branches or between receiving and main storage. It is *not* a synonym for "branch" or "location." Modelling `mezisklad` as just another warehouse row will miss the workflow semantics.
- **`faktura`** is the tax invoice and has its own legal requirements (VAT, due date, ID numbers). Do not conflate with `dodací list`.

When new terms come up: add them to `context/domain-glossary.md` first, with the Czech headword and an English gloss. Then use them.

## How this rule applies to design work

- **Schema** — column and table names should reflect Czech semantics. If a column models *dodací list* line items, that's what it models; do not flatten it into a generic `delivery_lines`.
- **UI labels** — Czech only, per `language-conventions.md`.
- **Workflows** — when documenting a workflow in `context/workflows.md`, use the Czech term and link to the glossary.
- **Conversations with the user** — when the user uses a Czech term, use the same Czech term back. Do not silently translate.

## The test

If a Czech reader of `context/domain-glossary.md` would find your wording odd, ambiguous, or wrong: **fix the wording, not the glossary.** The glossary reflects how the business actually talks.

## Cross-references

- `context/domain-glossary.md` — canonical Czech-first glossary
- `context/workflows.md` — uses these terms in context
- `language-conventions.md` — when to use Czech vs English
