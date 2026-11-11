# AGENTS.md

This file defines repository rules for OpenAI Codex, Antigravity, Cursor, and Amp.

## Medallion Layer Contract

- **`definitions/01_bronze/`**: Use `type: "declaration"` only. Never define tables or views in Bronze.
- **`definitions/02_silver/`**: Build conformed incremental or SCD Type 2 tables. Attach `policy_tags.piiColumnConfig(...)` to every PII column.
- **Partitioned Assertions**: Never use inline `assertions` when `requirePartitionFilter: true` is enabled. Create a standalone `type: "assertion"` file with a `WHERE` partition filter instead.
- **`definitions/03_gold/`**: Group marts by business domain (`finance/`, `retail/`). Always filter `fct_orders` on `order_date` to satisfy `requirePartitionFilter: true`. Define `assertions` on every mart.
- **SQLX Hygiene**: Never use `SELECT *`. Project every column explicitly. Keep `config { ... }` braces balanced.

## Reusable Helpers (`includes/`)

- Use `audit_columns.ingestedAtSql()` and `audit_columns.recordHashSql(columns)` for Silver audit columns.
- Use `policy_tags.piiColumnConfig(description)` for BigQuery Policy Tag attachment and `allow_untagged_pii` checks.
- Use `scd_type2.scd2WindowColumnsSql(...)` or `scd_type2.buildScd2Query(...)` for CDC history windows.

## Security and Prose Rules

- Never hardcode real GCP project IDs, org IDs, folder IDs, billing IDs, or developer LDAPs.
- Use neutral placeholder values (`example-silver-project`, `example-org`).
- Write short sentences (`<= 20` words) without decorative emojis, section symbols, or AI filler words.

## Required Verification

Run the hermetic test suite after every change.

```bash
make test
```
