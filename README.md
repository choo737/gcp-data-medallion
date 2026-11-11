# gcp-data-medallion

This repository holds BigQuery Dataform SQLX models for a Bronze, Silver, and Gold medallion warehouse.

It pairs with [gcp-foundation](https://github.com/choo737/gcp-foundation) as the platform workload layer.

## How This Pairs With gcp-foundation

Terraform in `gcp-foundation` provisions the underlying Google Cloud platform infrastructure.

- It creates the Bronze, Silver, and Gold GCP projects and BigQuery datasets.
- It creates BigQuery Policy Tags for PII governance and slot reservations for compute.
- It creates a `google_dataform_repository` resource synced directly to this repository.
- It passes target projects, datasets, and Policy Tag IDs into Dataform release configs.

## Root Configuration Layout

BigQuery Dataform v3 requires `workflow_settings.yaml` at the repository root (`/`).

Dataform reads this file first to set `dataformCoreVersion` (`3.0.43`), default dataset targets, and compilation `vars`.

## Compilation Variables Contract

The seven variables in `workflow_settings.yaml` connect Terraform outputs to SQLX definitions.

| Variable | Default Value | Purpose |
| :--- | :--- | :--- |
| `bronze_project` | `example-bronze-project` | GCP project holding raw Bronze tables |
| `bronze_dataset` | `bronze_raw` | BigQuery dataset for Bronze declarations |
| `silver_project` | `example-silver-project` | GCP project holding conformed Silver tables |
| `silver_dataset` | `silver_curated` | BigQuery dataset for Silver models |
| `gold_project` | `example-gold-project` | GCP project holding Gold business marts |
| `gold_dataset` | `gold_mart` | BigQuery dataset for Gold marts |
| `pii_policy_tag` | `""` | Optional BigQuery Policy Tag resource name |

When `pii_policy_tag` is `""`, `includes/policy_tags.js` returns only the column `description`.

This keeps local development compilation working without Cloud IAM Policy Tag bindings.

## Medallion Architecture

```
definitions/
  01_bronze/      Raw CDC source declarations (no DDL)
  02_silver/      Conformed incremental and SCD Type 2 tables
  03_gold/
    finance/      Finance domain aggregation marts
    retail/       Retail store domain marts
includes/         Reusable Dataform JS macros
quality/          Dataplex Auto Data Quality rule specs
tests/            Hermetic Python integrity test suite
```

1. **Bronze (`definitions/01_bronze/`)**: Holds Dataform `declaration` files only (`pos_orders_cdc`, `crm_customers_cdc`).
2. **Silver (`definitions/02_silver/`)**: Conforms records (`fct_orders`, `dim_customers`) with deduplication, SCD Type 2 windows, Policy Tags, and assertions.
3. **Gold (`definitions/03_gold/`)**: Aggregates Silver tables into partitioned marts (`mart_daily_revenue`, `mart_store_performance`) with partition filters.

> [!NOTE]
> **Scaling Beyond 25 Data Engineers (Data Mesh Split)**
>
> Teams with fewer than 25 data engineers should keep one `gcp-data-medallion` repository.
> Use `CODEOWNERS` on `definitions/03_gold/<domain>/` so teams keep unified DAG lineage.
>
> Teams with more than 25 data engineers should split into domain repositories (`medallion-finance`, `medallion-retail`).
> Terraform in `gcp-foundation` provisions one `google_dataform_repository` per domain repository.
> Domain repositories consume upstream Silver tables through Dataform `declaration` blocks.

## Local Validation

Run the hermetic test suite before committing changes.

```bash
make test
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
