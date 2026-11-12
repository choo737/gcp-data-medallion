---
name: add-medallion-model
description: Step-by-step recipe for adding a new Bronze declaration, Silver table, and Gold mart.
---

# Add a Medallion Model Pipeline

Follow these steps when adding a new domain dataset to `gcp-data-medallion`.

## 1. Declare the Bronze Source

1. Create `definitions/01_bronze/<source_name>.sqlx`.
2. Set `type: "declaration"` with `database: dataform.projectConfig.vars.bronze_project` and `schema: dataform.projectConfig.vars.bronze_dataset`.
3. Document every source column inside `columns: { ... }`, including `_metadata_deleted` for CDC sources.

## 2. Build the Conformed Silver Table

1. Create `definitions/02_silver/<entity>.sqlx`.
2. Set `type: "incremental"` (for fact events) or `type: "table"` (for SCD Type 2 dimensions).
3. Configure `bigquery.partitionBy`, `bigquery.clusterBy`, and `requirePartitionFilter: true` on large fact tables.
4. Add `updatePartitionFilter` whenever `uniqueKey` and `requirePartitionFilter: true` appear together.
5. Attach `policy_tags.piiColumnConfig("...")` to every PII column.
6. Project columns explicitly without `SELECT *`.
7. Add `${audit_columns.ingestedAtSql()}`, `${audit_columns.recordHashSql([...])}`, and `${cdc_helpers.activeCdcFilter()}` for CDC sources.
8. Gate optional `_metadata_deleted` projections with `cdc_helpers.filterCdcDeletes()` for legacy Bronze compatibility.
9. If `requirePartitionFilter` is `true`, add a standalone `assert_<entity>_quality.sqlx` (`type: "assertion"`) with a `WHERE` partition filter.
10. If `requirePartitionFilter` is not set, define inline `assertions` (`nonNull` and `uniqueKey`).

## 3. Build the Gold Business Mart

1. Create `definitions/03_gold/<domain>/mart_<name>.sqlx`.
2. Set `database` and `schema` with optional domain vars falling back to `gold_project` and `gold_dataset`.
3. Add a `WHERE` filter on any upstream `partitionBy` column if `requirePartitionFilter: true` is enabled.
4. Define `assertions` (`nonNull`) on key dimensions and metrics.
5. Update `CODEOWNERS` if a new domain folder was added.

## 4. Validate

Run `make test` locally and use `.github/workflows/dataform-dryrun.yml` when WIF variables are configured.
