# CLAUDE.md

Read [AGENTS.md](AGENTS.md) before modifying any file in this repository.

## Quick Rules

- Follow Bronze (`declaration`), Silver (BigQuery Policy Tags, formerly Data Catalog, and assertions), and Gold (incremental lookback) rules.
- Exclude CDC delete tombstones in Silver using `includes/cdc_helpers.js` (`cdc_helpers.activeCdcFilter()`).
- Keep `fct_orders` `updatePartitionFilter` and incremental `WHERE` aligned via `cdc_helpers.lookbackDays()`.
- Never write `SELECT *` in `.sqlx` or `.js` files.
- Never hardcode real GCP identifiers or internal LDAPs.
- Onboard via `QUESTIONNAIRE.md` and `.agents/skills/setup-data-medallion/SKILL.md` for standalone Brownfield tables.
- Optionally load `platform-context.json` from `https://github.com/choo737/gcp-launchpad` to prefill projects and Policy Tags.
- Keep `workflow_settings.yaml` at `/` with all contract `vars` and never create `package.json`.
- Store customer overrides only in gitignored `envs/{dev,uat,prod}.compilation.json` or `platform-context.json`.
- Keep `ml_customer_features` free of restricted national ID columns and verify SHAP additivity via `assert_xai_shap_additivity`.
- Consult [docs/01-architecture-and-sqlx-reference.md](docs/01-architecture-and-sqlx-reference.md) and [docs/02-enterprise-operationalization-guide.md](docs/02-enterprise-operationalization-guide.md) for SQLX contracts.
- Keep `tests/suite_doc_contract.py` synced with `gcp-launchpad` and never create `GEMINI.md` or `catalog.yaml`.
- Run `make test` and confirm all checks pass before finishing.
