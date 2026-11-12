# GEMINI.md

Read [AGENTS.md](AGENTS.md) before modifying any file in this repository.

## Key Invariants

- Follow the Bronze (`declaration`), Silver (`incremental`/`table` + dual Policy Tags + assertions), and Gold (`incremental` + lookback filter + assertions) rules.
- Exclude CDC delete tombstones in Silver using `includes/cdc_helpers.js` (`cdc_helpers.activeCdcFilter()`).
- Keep `fct_orders` `updatePartitionFilter` and incremental `WHERE` aligned via `cdc_helpers.lookbackDays()`.
- Never write `SELECT *` in `.sqlx` or `.js` files.
- Never hardcode real GCP identifiers or internal LDAPs.
- Keep `workflow_settings.yaml` at `/` with all contract `vars`.
- Run `make test` and confirm all checks pass before finishing.
