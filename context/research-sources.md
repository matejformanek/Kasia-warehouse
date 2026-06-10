# Research sources

Public sources used to compile the company profile and the surrounding
domain context. Each entry: the link, what we used it for, and what to
re-check on refresh.

This file exists so that any future agent revisiting the profile knows
exactly which facts are sourced from where, and where to look again if
the world has moved on.

## Kasia vera s.r.o. — company facts

### https://www.kasia.cz/

The company's own website. Used for: brand name (VERA GURMET), product
range scope (raw spices vs branded mixtures), market positioning (B2B,
no e-shop), location of Říčany HQ, and tone of voice. Re-check on
refresh: any new branches announced, any change in the product range,
any new sales channel (the absence of an e-shop is a load-bearing
assumption).

### https://ares.gov.cz/

Official Czech business register (ARES). Used for: legal name "Kasia
vera s.r.o.", IČO 25756729, registered seat in Říčany u Prahy,
founding year (1993), legal form. Re-check on refresh: registered
seat change, change of statutory body, any annotation about
liquidation or restructuring.

### https://www.firmy.cz/

Seznam.cz business directory entry. Used as a secondary corroboration
of seat, contact data, and category classification (spices /
foodstuffs distribution). Re-check: phone, email, opening hours
displayed for branches.

### https://www.b2bhint.com/

Aggregator that scrapes public corporate filings to produce
business directory snapshots. Used as a third corroboration of
IČO, founding year, and headcount band (25–49 employees). Re-check:
headcount band can shift between snapshots; verify against ARES or
a newer source before quoting.

## Domain / market context

(Add to this section as research continues.)

- Generic Czech industry context for spice distribution, food-safety
  legislation, and dodací list / faktura conventions is sourced from
  general knowledge of Czech accounting practice and Czech commercial
  law; specific citations to be added as they are consulted.

## Technology comparison sources

References for the candidates in [`tech-options.md`](./tech-options.md)
are listed inline in that file (each candidate links to its project
homepage). Re-check those before any tech decision is recorded in
[`decisions/`](./decisions/), because open-source project health and
maintenance status change month to month.

## Refresh discipline

When refreshing this file:

1. Re-fetch each linked source.
2. Diff against the facts quoted in [`company-profile.md`](./company-profile.md).
3. If any fact has changed materially (seat, brand, scale band,
   product count), update the profile **and** note the refresh date
   here next to the source.
4. Do **not** silently update the profile without leaving a trace —
   the provenance trail is the point of this file.
