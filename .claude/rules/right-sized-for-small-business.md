**Kasia has ~30 employees and ~6 active users on this tool. Build for that, not for a hypothetical Series B.**

## Defaults

- **Boring beats clever.** Prefer the most-trodden path in whatever stack we end up on. The framework's documented happy path is almost always right.
- **Two-tier architecture is the goal.** One Django *project*, one DB. (Multiple Django *apps* inside that one project — `inventory`, `accounts`, `web` — are fine and expected; "one app" here means one deployable, one database, not a single Python package. Per [`../../context/decisions/0049-public-site-and-sklad-split.md`](../../context/decisions/0049-public-site-and-sklad-split.md).) No microservices, no message queues, no event-sourcing, no CQRS, no separate read/write models — unless a *specific* feature requirement justifies it and that justification is written into `context/decisions/`.
- **No SSO, no SAML, no OAuth provider integration.** Password + optional magic-link is plenty for ~6 users. Revisit only if Kasia grows or onboards external parties.
- **No Kubernetes, no service mesh, no autoscaling, no multi-region.** A single VPS or simple PaaS deploy is enough. One box can serve this workload with room to spare.
- **No real-time anything** (websockets, SSE, live cursors) unless a screen actually demands it. The owner's request in `context/owner-request.md` is well-served by plain request/response.
- **No mobile app unless a workflow demands phone-in-hand use.** A responsive web view covers most cases.
- **No analytics warehouse, no event pipeline, no data lake.** Reports run off the operational DB until that genuinely hurts.

## The first-instinct check

**Reject the first enterprise-shaped suggestion.** If you find yourself reaching for a tool because "that's what real systems use" or "we'll want this eventually," stop. Write the simpler version. The added complexity is only justified once a concrete user-visible requirement makes the simple version inadequate.

If a suggestion sounds like a conference-talk architecture, it probably is. Write down what the simplest two-tier version looks like first, then ask whether the enterprise version is actually necessary.

## Backups matter more than uptime

Two branches losing access for an hour is annoying. Losing six months of *dodací listy* is catastrophic. Optimise for durability, not 99.99%.

- Backups are non-optional from day one of any deployed system.
- Restore drills are part of "done" — an untested backup does not exist.
- Uptime targets above ~99% are not worth the complexity at this scale.

## When this rule conflicts with another

If another rule or a fresh requirement seems to demand enterprise-grade infrastructure, that's a signal to (a) re-examine the requirement, and (b) if the requirement holds, write the trade-off into `context/decisions/`. See `decision-log-discipline.md`.

## Cross-references

- `context/company-profile.md` — why ~6 users is the right scale
- `context/product-ideology.md` — the deliberate simplicity stance
- `no-premature-tech-choices.md` — defer the stack until the shape is clear
