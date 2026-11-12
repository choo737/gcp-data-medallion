# gcp-data-medallion

This repository holds BigQuery Dataform SQLX models for a Bronze, Silver, and Gold medallion warehouse.

It pairs with [gcp-foundation](https://github.com/choo737/gcp-foundation) and [gcp-data-ingestion](https://github.com/choo737/gcp-data-ingestion) in one three-repository stack.

## 3-Repository Accelerator Suite

Three linked repositories separate cloud infrastructure, ingestion pipelines, and SQLX transformations.

| Repository | Layer | Scope |
| :--- | :--- | :--- |
| [choo737/gcp-foundation](https://github.com/choo737/gcp-foundation) | Platform | Terraform landing zone, BigQuery datasets, Policy Tags, and Dataform repositories |
| [choo737/gcp-data-ingestion](https://github.com/choo737/gcp-data-ingestion) | Ingestion | Batch GCS, streaming Pub/Sub, and Datastream CDC into Bronze |
| [choo737/gcp-data-medallion](https://github.com/choo737/gcp-data-medallion) | Medallion | BigQuery Dataform Bronze, Silver, and Gold SQLX models |

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

This repo omits `package.json` because Dataform v3 rejects setting `dataformCoreVersion` when `package.json` exists.

## Compilation Variables Contract

Ten contract variables in `workflow_settings.yaml` connect Terraform outputs to SQLX definitions.

An optional `filter_cdc_deletes` variable toggles `_metadata_deleted` tombstone filtering in Silver.

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
| `filter_cdc_deletes` | `"true"` | Optional CDC tombstone filter toggle (`"false"` skips `_metadata_deleted`) |

When `allow_untagged_pii` is `"true"` and `pii_policy_tag` is `""`, `includes/policy_tags.js` returns only the column `description`.

Set `allow_untagged_pii` to `"false"` in production so missing Policy Tags fail Dataform compilation.

By default, `filter_cdc_deletes` is `"true"` and `includes/cdc_helpers.js` filters out deleted rows.

Set `filter_cdc_deletes` to `"false"` for legacy Bronze tables lacking `_metadata_deleted`.

## CDC Tombstone Filtering

Bronze declarations document nullable `_metadata_deleted` flags emitted by Datastream `APPEND_ONLY` and Pub/Sub CDC streams.

Silver models `fct_orders` and `dim_customers` use `includes/cdc_helpers.js` to exclude delete tombstones.

`cdc_helpers.activeCdcFilter(alias)` validates optional table aliases against a strict identifier pattern before generating SQL.

It compiles to `COALESCE(_metadata_deleted, FALSE) = FALSE` by default, or `TRUE` when `filter_cdc_deletes` is `"false"`.

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

## Keyless PR Compilation Check

Workflow `.github/workflows/dataform-dryrun.yml` runs BigQuery Dataform compilation checks via GitHub OIDC Workload Identity Federation.

It triggers on `workflow_dispatch` and `pull_request` events targeting `main`.

The workflow skips automatically when optional repository variables are unset in template clones.

| Repository Variable | Example Value | Purpose |
| :--- | :--- | :--- |
| `GCP_WIF_PROVIDER` | `projects/123/locations/global/workloadIdentityPools/gh/providers/repo` | Workload Identity Pool provider resource path |
| `GCP_WIF_SERVICE_ACCOUNT` | `dataform-ci@example-silver-project.iam.gserviceaccount.com` | Service account granted Dataform viewer or runner roles |
| `DATAFORM_REPO_PATH` | `projects/example-silver-project/locations/asia-southeast1/repositories/medallion` | Target BigQuery Dataform repository resource name |

The check avoids service account JSON keys and fails if `compilationErrors` is non-empty.

## License

Apache License 2.0. See [LICENSE](LICENSE).
