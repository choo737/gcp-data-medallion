# Architecture and Dataform SQLX Reference

This reference details how `gcp-data-medallion` compiles Dataform `3.1.5` SQLX models on BigQuery.

Return to [README.md](../README.md) for the high-level overview or follow [02-enterprise-operationalization-guide.md](02-enterprise-operationalization-guide.md) to deploy.

## Pairing With gcp-foundation

Terraform in [gcp-foundation](https://github.com/choo737/gcp-foundation) provisions the underlying Google Cloud platform infrastructure.

- It creates the Bronze, Silver, and Gold GCP projects and BigQuery datasets.
- It creates dual-tier BigQuery Policy Tags (formerly Data Catalog Policy Tags) (`restricted` and `masked`) for PII governance.
- It provisions `google_bigquery_reservation` and `google_bigquery_reservation_assignment` resources in `modules/data/bigquery-reservations/`.
- It provisions those reservations directly because Cloud Foundation Fabric lacks a reservation module.
- It creates a `google_dataform_repository` resource synced directly to this repository.
- It passes target projects, datasets, and Policy Tag IDs into Dataform release configs.

## Why Dataform Over dbt

Dataform runs natively inside BigQuery Studio with no separate runtime or license cost.

It integrates directly with BigQuery release configs, workflow configs, and Policy Tags.

## Root Configuration Layout

Dataform v3 requires `workflow_settings.yaml` at the repository root (`/`).

Dataform reads this file first to set `dataformCoreVersion` (`3.1.5`), default dataset targets, and compilation `vars`.

This repo omits `package.json` because Dataform v3 rejects setting `dataformCoreVersion` when `package.json` exists.

Never create `package.json` in this repository.

## Compilation Variables Contract

Contract variables in `workflow_settings.yaml` connect Terraform outputs and ingestion paths to SQLX definitions.

| Variable | Default Value | Purpose |
| :--- | :--- | :--- |
| `bronze_project` | `your-bronze-project-id` | GCP project holding raw Bronze tables |
| `bronze_dataset` | `bronze` | BigQuery dataset for Bronze declarations |
| `silver_project` | `example-silver-project` | GCP project holding conformed Silver tables |
| `silver_dataset` | `silver` | BigQuery dataset for Silver models |
| `gold_project` | `example-gold-project` | GCP project holding Gold business marts |
| `gold_dataset` | `gold` | BigQuery dataset for Gold marts |
| `gold_retail_project` | `""` | Optional isolated GCP project for Retail Gold marts |
| `gold_retail_dataset` | `""` | Optional isolated BigQuery dataset for Retail Gold marts |
| `pii_policy_tag` | `""` | Backwards-compatible fallback BigQuery Policy Tag resource name |
| `pii_restricted_policy_tag` | `""` | Restricted PII Policy Tag for national ID columns |
| `pii_masked_policy_tag` | `""` | Masked PII Policy Tag for email and name columns |
| `allow_untagged_pii` | `"true"` | Set to `"false"` in `uat`, `prod`, and strict CI dry runs |
| `filter_cdc_deletes` | `"true"` | Optional CDC tombstone filter toggle (`"false"` skips `_metadata_deleted`) |
| `cdc_lookback_days` | `"30"` | Rolling partition lookback window in days (`1..3650`) |
| `include_stream_orders` | `"false"` | Set to `"true"` to union `pos_orders_stream_cdc` into `fct_orders` |
| `include_batch_orders` | `"false"` | Set to `"true"` to union `pos_orders_batch_cdc` into `fct_orders` |
| `ml_audit_project` | `example-ml-ops` | GCP project hosting `ml_xai_audit_ledger` from `03-data-science` |
| `ml_audit_dataset` | `ml_xai_audit` | BigQuery dataset hosting `ml_xai_audit_ledger` |

Override customer values in gitignored `envs/{dev,uat,prod}.compilation.json` or GitHub Environment variables.

## Dual PII Policy Tags

`includes/policy_tags.js` exports `piiRestrictedPolicyTag`, `piiMaskedPolicyTag`, and backwards-compatible `piiPolicyTag`.

Both tier helpers validate full GCP Policy Tag resource paths when non-empty.

Empty tags fail Dataform compilation whenever `allow_untagged_pii` is `"false"`.

- `customer_ic_number` uses `piiRestrictedPolicyTag` in `fct_orders` and `dim_customers`.
- `customer_email` and `customer_name` use `piiMaskedPolicyTag`.
- When tier-specific variables are unset, both helpers fall back to `pii_policy_tag`.

## Unified Orders and Late-CDC Protection

Bronze declarations cover Datastream CDC (`pos_orders_cdc`), Pub/Sub streaming (`pos_orders_stream_cdc`), and GCS batch (`pos_orders_batch_cdc`).

When `include_stream_orders` or `include_batch_orders` is `"true"`, `fct_orders` unions normalized rows before calling `cdc_helpers.deduplicateCdc`.

`cdc_helpers.parseLookbackDays` validates `cdc_lookback_days` (`1..3650`) to block SQL injection.

Both `updatePartitionFilter` and the incremental `WHERE` filter use the same `cdc_lookback_days` window.

Keeping both windows equal prevents late CDC updates from creating duplicate `order_id` rows.

By default, `filter_cdc_deletes` is `"true"` and `includes/cdc_helpers.js` filters out deleted rows via `activeCdcFilter`.

Set `filter_cdc_deletes` to `"false"` for legacy Bronze tables lacking `_metadata_deleted`.

## SCD Type 2 Change Deduplication

`dim_customers` tracks `customer_ic_number`, `customer_email`, `customer_name`, `segment`, and `country_code` in `record_hash`.

`scd_type2.scd2PreviousHashSql` removes consecutive unchanged CDC heartbeats before computing `LEAD(_ingested_at)` for `valid_to`.

`scd_type2.scd2WindowColumnsSql` generates `valid_from`, `valid_to`, and `is_current` columns cleanly.

## Medallion Layer Structure

```
definitions/
  01_bronze/      Raw CDC, stream, and batch source declarations (no DDL)
  02_silver/      Conformed incremental and SCD2 tables with partition-pruned assertions
  03_gold/
    finance/      Incremental finance revenue marts
    retail/       Incremental retail store performance marts
    mlops/        Incremental XAI attribution and probability drift marts
```

1. **Bronze (`definitions/01_bronze/`)**: Holds Dataform `declaration` files only (`pos_orders_cdc`, `pos_orders_stream_cdc`, `pos_orders_batch_cdc`, `crm_customers_cdc`, `ml_xai_audit_ledger`).
2. **Silver (`definitions/02_silver/`)**: Conforms `fct_orders`, `dim_customers`, and `ml_customer_features` with dual Policy Tags and assertions (`assert_fct_orders_quality`, `assert_ml_customer_features_quality`, `assert_xai_shap_additivity`).
3. **Gold (`definitions/03_gold/`)**: Incrementally aggregates Silver into partitioned marts (`mart_daily_revenue`, `mart_store_performance`, `mart_xai_shap_drift`) with lookback pruning.

Tables with `requirePartitionFilter: true` use standalone assertion `.sqlx` files (`assert_fct_orders_quality.sqlx`) pruned by `cdc_lookback_days`.

## Who Creates Bronze Tables

Files in `definitions/01_bronze/` are Dataform `declaration` blocks only.

They never run DDL or create Bronze tables.

| Ingestion Path | Who Creates the Bronze Table | Terraform? |
| :--- | :--- | :--- |
| Datastream (CDC) | Datastream, automatically | No |
| Fivetran / Airbyte / SaaS ELT | The connector | No |
| Dataflow / Spark | The job (create-if-needed) | No |
| Batch loads from GCS | Load job or Dataform `operations` step | No |
| Pub/Sub -> BigQuery subscription | Must exist before the subscription; create it in the same Terraform as the subscription (platform/streaming owner) | Yes |

> [!NOTE]
> **Scaling via Data Mesh Split**
>
> Keep one `gcp-data-medallion` repository with `CODEOWNERS` on `definitions/03_gold/<domain>/` for unified DAG lineage.
> Split into domain repositories (`medallion-finance`, `medallion-retail`) when `CODEOWNERS` review load or DAG compile time slows teams down.
>
> When splitting, Terraform in `gcp-foundation` provisions one `google_dataform_repository` per domain repository.
> Each domain repository reads upstream Silver tables through Dataform `declaration` blocks.
