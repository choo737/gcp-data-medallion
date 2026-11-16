# CLAUDE.md

Read [AGENTS.md](AGENTS.md) before modifying any file in this repository.

## Key Invariants

- Follow Bronze (`declaration`), Silver (dual Policy Tags and assertions), and Gold (incremental lookback and assertions) rules.
- Exclude CDC delete tombstones in Silver using `includes/cdc_helpers.js` (`cdc_helpers.activeCdcFilter()`).
- Keep `fct_orders` `updatePartitionFilter` and incremental `WHERE` aligned via `cdc_helpers.lookbackDays()`.
- Never write `SELECT *` in `.sqlx` or `.js` files.
- Never hardcode real GCP identifiers or internal LDAPs.
- Onboard via `QUESTIONNAIRE.md` and `.agents/skills/setup-data-medallion/SKILL.md` for standalone Brownfield tables or `platform-context.json` from `https://github.com/choo737/gcp-launchpad`.
- Keep `workflow_settings.yaml` at `/` with all contract `vars` and never create `package.json`.
- Store customer project overrides only in gitignored `envs/{dev,staging,prod}.compilation.json` or `platform-context.json`.
- Consult [docs/01-architecture-and-sqlx-reference.md](docs/01-architecture-and-sqlx-reference.md) and [docs/02-enterprise-operationalization-guide.md](docs/02-enterprise-operationalization-guide.md) for SQLX contracts and rollout steps.
- Run `make test` and confirm all checks pass before finishing.
