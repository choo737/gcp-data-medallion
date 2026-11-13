# AGENTS.md

This file defines repository rules for OpenAI Codex, Antigravity, Cursor, and Amp.

## Medallion Layer Contract

- **`definitions/01_bronze/`**: Use `type: "declaration"` only. Never define tables or views in Bronze. Document `_metadata_deleted` on CDC declarations.
- **`definitions/02_silver/`**: Build conformed incremental or SCD Type 2 tables. Attach `policy_tags.piiRestrictedPolicyTag()` or `policy_tags.piiMaskedPolicyTag()` to PII columns. Filter CDC tombstones with `cdc_helpers.activeCdcFilter()`.
- **Partitioned Assertions**: Never use inline `assertions` when `requirePartitionFilter: true` is enabled. Create a standalone `type: "assertion"` file pruned by `cdc_helpers.lookbackDays()`.
- **`definitions/03_gold/`**: Group marts by business domain (`finance/`, `retail/`). Use incremental merges with `updatePartitionFilter` and `order_date` filters driven by `cdc_helpers.lookbackDays()`. Define `assertions` on every mart.
- **SQLX Hygiene**: Never use `SELECT *`. Project every column explicitly. Keep `config { ... }` braces balanced.

## Reusable Helpers (`includes/`)

- Use `audit_columns.ingestedAtSql()` and `audit_columns.recordHashSql(columns)` for Silver audit columns.
- Use `cdc_helpers.parseLookbackDays(val)`, `cdc_helpers.lookbackDays()`, `cdc_helpers.deduplicateCdc(...)`, and `cdc_helpers.activeCdcFilter(alias)` for Bronze CDC processing.
- Use `policy_tags.piiRestrictedPolicyTag(vars)` and `policy_tags.piiMaskedPolicyTag(vars)` for BigQuery Policy Tag attachment.
- Use `scd_type2.scd2PreviousHashSql(...)`, `scd_type2.scd2WindowColumnsSql(...)`, or `scd_type2.buildScd2Query(...)` for CDC history windows.

## Onboarding and Skills

- **Skills**: Register and follow `.agents/skills/setup-data-medallion/SKILL.md`, `.agents/skills/add-medallion-model/SKILL.md`, and `.agents/skills/split-domain-mesh/SKILL.md`.
- **Questionnaire**: Walk customers through `QUESTIONNAIRE.md` before editing `workflow_settings.yaml` or gitignored `envs/{dev,staging,prod}.compilation.json`.
- **Standalone Brownfield**: Support existing BigQuery Bronze datasets directly by adapting `definitions/01_bronze/*.sqlx` declarations.
- **Launchpad Handoff**: Read optional gitignored `platform-context.json` from `https://github.com/choo737/gcp-launchpad` to prefill project and Policy Tag settings.

## Security and Prose Rules

- Never hardcode real GCP project IDs, org IDs, folder IDs, billing IDs, or developer LDAPs.
- Use neutral placeholder values (`example-silver-project`, `example-org`).
- Write short sentences (`<= 20` words) without decorative emojis, section symbols, or AI filler words.

## Required Verification

Run the hermetic test suite after every change.

```bash
make test
```

Workflows `dataform-dryrun.yml` and `dataform-promote.yml` use Dataform GA `v1` endpoints over OIDC WIF.
