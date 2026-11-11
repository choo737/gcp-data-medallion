---
name: add-medallion-model
description: Step-by-step recipe for adding a new Bronze declaration, Silver table, and Gold mart.
---

# Add a Medallion Model Pipeline

Follow these steps when adding a new domain dataset to `gcp-data-medallion`.

## 1. Declare the Bronze Source

1. Create `definitions/01_bronze/<source_name>.sqlx`.
2. Set `type: "declaration"` with `database: dataform.projectConfig.vars.bronze_project` and `schema: dataform.projectConfig.vars.bronze_dataset`.
3. Document every source column inside `columns: { ... }`.

## 2. Build the Conformed Silver Table

1. Create `definitions/02_silver/<entity>.sqlx`.
2. Set `type: "incremental"` (for fact events) or `type: "table"` (for SCD Type 2 dimensions).
3. Configure `bigquery.partitionBy`, `bigquery.clusterBy`, and `requirePartitionFilter: true` on large fact tables.
4. Add `updatePartitionFilter` whenever `uniqueKey` and `requirePartitionFilter: true` appear together.
5. Attach `policy_tags.piiColumnConfig("...")` to every PII column.
6. Project columns explicitly without `SELECT *`.
7. Add `${audit_columns.ingestedAtSql()}` and `${audit_columns.recordHashSql([...])}`.
8. Define `assertions` (`nonNull` and `uniqueKey`).

## 3. Build the Gold Business Mart

1. Create `definitions/03_gold/<domain>/mart_<name>.sqlx`.
2. Set `database: dataform.projectConfig.vars.gold_project` and `schema: dataform.projectConfig.vars.gold_dataset`.
3. Add a `WHERE` filter on any upstream `partitionBy` column if `requirePartitionFilter: true` is enabled.
4. Define `assertions` (`nonNull`) on key dimensions and metrics.
5. Update `CODEOWNERS` if a new domain folder was added.

## 4. Validate

Run `make test` and confirm all unit tests pass.
