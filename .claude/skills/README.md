# Skills

The stack and frontend are now settled and live, so the first real skill exists.

## Present skills

- **`kasia-sklad-frontend/`** — loads on-demand when an agent is about to edit a
  template (`kasia/templates/**`) or CSS (`kasia/static/css/**`). It routes to the
  two source-of-truth rules (`frontend-and-templates.md`, `design-system.md`) and
  front-loads the mistakes that render *silently wrong* (multi-line `{# #}`
  comments, `floatformat` in number `value=`, inline `<style>`/`@import`, renamed
  locked hooks, un-scoped branch data). Paired with the mechanical guard
  `inventory/tests/test_template_hygiene.py`, which fails CI/`make test` if the
  two enforceable traps recur.

## Rules of the road for adding skills

The bar stays high — a bad skill is worse than none:

- **Do not fabricate skills speculatively.** A skill that references a
  non-existent command, test runner, or file layout is worse than no skill — the
  next agent will follow it and break things.
- **Do not add skills that just wrap shell commands** without first checking
  whether the surrounding rules (`.claude/rules/`) already make the command
  obvious. A good skill either automates a real multi-step operation or surfaces
  load-bearing context *on-demand at the moment it's needed* (like
  `kasia-sklad-frontend`), rather than duplicating a rule.
- **Point at the rules, don't fork them.** Rules in `.claude/rules/` are the
  source of truth; a skill routes to them and adds the trigger + checklist.

Still-open candidates, once genuinely useful:

- "Render a *dodací list* PDF locally for QA"
- "Run the test suite scoped to one screen flow"

## Note on `.claude/settings.json`

There is deliberately no `.claude/settings.json` in this repo yet. Permission allowlists will be configured once we know which commands actually get run — premature permissions cause either prompt fatigue (too narrow) or quiet bypasses (too broad). Revisit after the first stack decisions land in `context/decisions/`.
