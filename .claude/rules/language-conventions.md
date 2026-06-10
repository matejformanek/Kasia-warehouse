**Czech for users, English for code, Czech-first for domain terms.**

## User-facing text

Locale `cs_CZ`. Czech with diacritics intact. Applies to:

- UI labels, buttons, form fields, validation messages
- Emails and notifications sent to Kasia staff or customers
- PDFs and printed documents (`dodací list`, faktura, etc.)
- Error messages a non-developer will see

Never strip diacritics for "safety." If a stack can't handle UTF-8 in 2026, that's a stack problem worth surfacing in `context/tech-options.md`.

## Code and developer-facing text

English. Applies to:

- Identifiers — function, class, variable, file, module, table, column names
- Code comments
- Log messages and structured-log fields
- Test names and test descriptions
- Internal API field names (until/unless a decision says otherwise)

## Repository text

English for commit messages, PR descriptions, and design documents in `context/`. Two exceptions:

- `context/owner-request.md` — verbatim Czech from the owner stays Czech.
- `context/domain-glossary.md` — Czech domain terms are the headword; English gloss follows.

## Domain terms in design docs

When discussing warehouse concepts in `context/` or rule files, lead with the Czech term, English in parens on first use within a document:

- *dodací list (delivery note)*
- *výdejka (issue slip)*
- *příjemka (receipt slip)*
- *mezisklad (intermediate warehouse)*

The spellings in `context/domain-glossary.md` are canonical. Cross-reference there; do not redefine.

**Never anglicise a Czech domain term as an identifier or product name.** No `DeliveryListGenerator`, no `delivery-list-er`. It is a *dodací list*; the generator is a `dodaci_list_generator` (or whatever the casing convention turns out to be once a language is chosen — see `no-premature-tech-choices.md`).

## Dates

- User-facing: Czech format `DD. MM. YYYY` (e.g. `02. 06. 2026`).
- Code, logs, filenames, API payloads: ISO `YYYY-MM-DD` (e.g. `2026-06-02`).
- Timestamps in logs: ISO 8601 with timezone.

## When in doubt

Defer to `context/domain-glossary.md` and `czech-first-domain.md`.
