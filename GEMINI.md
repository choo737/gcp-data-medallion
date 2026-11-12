# GEMINI.md

Read [AGENTS.md](AGENTS.md) before modifying any file in this repository.

## Key Invariants

- Follow the Bronze (`declaration`), Silver (`incremental`/`table` + Policy Tags + assertions), and Gold (`table` + partition filter + assertions) layer rules.
- Exclude CDC delete tombstones in Silver using `includes/cdc_helpers.js` (`cdc_helpers.activeCdcFilter()`).
- Never write `SELECT *` in `.sqlx` or `.js` files.
- Never hardcode real GCP identifiers or internal LDAPs.
- Keep `workflow_settings.yaml` at `/` with all ten contract `vars` plus optional `filter_cdc_deletes`.
- Run `make test` and confirm all checks pass before finishing.
