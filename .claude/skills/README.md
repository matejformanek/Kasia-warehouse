# Skills

This directory is intentionally empty for now.

Skills will be authored once the stack is chosen and we know which recurring operations actually need automating. Likely candidates, once they're real:

- "Generate a migration" — once a DB and migration tool exist
- "Render a *dodací list* PDF locally for QA" — once the PDF pipeline exists
- "Run the test suite scoped to one screen flow" — once tests exist
- "Bootstrap a new screen" — once the frontend approach is settled

Until then:

- **Do not fabricate skills speculatively.** A skill that references a non-existent build command, test runner, or migration tool is worse than no skill — the next agent will follow it and break things.
- **Do not add skills that just wrap shell commands** without first checking whether the surrounding rules (`.claude/rules/`) already make the command obvious.

## Note on `.claude/settings.json`

There is deliberately no `.claude/settings.json` in this repo yet. Permission allowlists will be configured once we know which commands actually get run — premature permissions cause either prompt fatigue (too narrow) or quiet bypasses (too broad). Revisit after the first stack decisions land in `context/decisions/`.
