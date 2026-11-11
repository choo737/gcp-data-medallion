# gcp-data-medallion

This repository holds BigQuery Dataform SQLX models for a Bronze, Silver, and Gold medallion warehouse.

It pairs with [gcp-foundation](https://github.com/choo737/gcp-foundation) as the platform workload layer.

## Create Your Private Repository

GitHub forces normal forks of public repos to stay public.

Click **Use this template** on GitHub or run this command:

```bash
gh repo create acme-corp/gcp-data-medallion --private --template choo737/gcp-data-medallion --clone
```

## How This Pairs With gcp-foundation

Terraform in `gcp-foundation` provisions the underlying Google Cloud platform infrastructure.

- It creates the Bronze, Silver, and Gold GCP projects and BigQuery datasets.
- It creates BigQuery Policy Tags for PII governance.
- It provisions raw `google_bigquery_reservation` and `google_bigquery_reservation_assignment` resources in `modules/data/bigquery-reservations/`.
- It provisions these resources directly instead of Cloud Foundation Fabric, which lacks a reservation module.
- It creates a `google_dataform_repository` resource synced directly to this repository.
- It passes target projects, datasets, and Policy Tag IDs into Dataform release configs.

## Why Dataform Over dbt

Dataform runs natively inside BigQuery Studio with no separate runtime or license cost.

It integrates directly with BigQuery release configs, workflow configs, and Policy Tags.

## Root Configuration Layout

BigQuery Dataform v3 requires `workflow_settings.yaml` at the repository root (`/`).

Dataform reads this file first to set `dataformCoreVersion` (`3.1.5`), default dataset targets, and compilation `vars`.

## Compilation Variables Contract

The ten variables in `workflow_settings.yaml` connect Terraform outputs to SQLX definitions.

| Variable | Default Value | Purpose |
| :--- | :--- | :--- |
| `bronze_project` | `example-bronze-project` | GCP project holding raw Bronze tables |
| `bronze_dataset` | `bronze_raw` | BigQuery dataset for Bronze declarations |
| `silver_project` | `example-silver-project` | GCP project holding conformed Silver tables |
| `silver_dataset` | `silver_curated` | BigQuery dataset for Silver models |
| `gold_project` | `example-gold-project` | GCP project holding Gold business marts |
| `gold_dataset` | `gold_mart` | BigQuery dataset for Gold marts |
| `gold_retail_project` | `""` | Optional isolated GCP project for Retail Gold marts |
| `gold_retail_dataset` | `""` | Optional isolated BigQuery dataset for Retail Gold marts |
| `pii_policy_tag` | `""` | Optional BigQuery Policy Tag resource name |
| `allow_untagged_pii` | `"true"` | Set to `"false"` in production to require Policy Tags |

When `allow_untagged_pii` is `"true"` and `pii_policy_tag` is `""`, `includes/policy_tags.js` returns only the column `description`.

Set `allow_untagged_pii` to `"false"` in production so missing Policy Tags fail Dataform compilation.

## Medallion Architecture

```
definitions/
  01_bronze/      Raw CDC source declarations (no DDL)
  02_silver/      Conformed tables and partition-filtered assertions
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

Tables with `requirePartitionFilter: true` use standalone assertion `.sqlx` files (`assert_fct_orders_quality.sqlx`) with a partition predicate.

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
> Split into domain repositories (`medallion-finance`, `medallion-retail`) when `CODEOWNERS` review load or DAG compile time becomes a bottleneck.
>
> When splitting, Terraform in `gcp-foundation` provisions one `google_dataform_repository` per domain repository.
> Each domain repository reads upstream Silver tables through Dataform `declaration` blocks.

## Local Validation

Run the hermetic test suite before committing changes.

```bash
make test
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
