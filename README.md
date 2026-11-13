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

## Onboarding and Standalone Brownfield Adoption

Use [QUESTIONNAIRE.md](QUESTIONNAIRE.md) and `.agents/skills/setup-data-medallion/SKILL.md` to configure Greenfield or standalone Brownfield deployments.

- **Greenfield Suite**: Pair with `gcp-foundation` and `gcp-data-ingestion`, or read gitignored `platform-context.json` from [choo737/gcp-launchpad](https://github.com/choo737/gcp-launchpad).
- **Brownfield Standalone**: Point `bronze_project` and `bronze_dataset` at existing BigQuery raw tables and adapt `definitions/01_bronze/*.sqlx`.
- **Environment Overrides**: Copy `envs/*.compilation.json.example` to gitignored `envs/{dev,staging,prod}.compilation.json` instead of committing customer IDs.

| Skill | File | Purpose |
| :--- | :--- | :--- |
| `setup-data-medallion` | `.agents/skills/setup-data-medallion/SKILL.md` | Interactive onboarding via `QUESTIONNAIRE.md` and optional `platform-context.json` |
| `add-medallion-model` | `.agents/skills/add-medallion-model/SKILL.md` | Add a new Bronze declaration, Silver table, and Gold mart |
| `split-domain-mesh` | `.agents/skills/split-domain-mesh/SKILL.md` | Split a Gold domain folder into a separate repository |

## How This Pairs With gcp-foundation

Terraform in `gcp-foundation` provisions the underlying Google Cloud platform infrastructure.

- It creates the Bronze, Silver, and Gold GCP projects and BigQuery datasets.
- It creates dual-tier BigQuery Policy Tags (`restricted` and `masked`) for PII governance.
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
| `allow_untagged_pii` | `"true"` | Set to `"false"` in staging, prod, and strict CI dry runs |
| `filter_cdc_deletes` | `"true"` | Optional CDC tombstone filter toggle (`"false"` skips `_metadata_deleted`) |
| `cdc_lookback_days` | `"30"` | Rolling partition lookback window in days (`1..3650`) |
| `include_stream_orders` | `"false"` | Set to `"true"` to union `pos_orders_stream_cdc` into `fct_orders` |
| `include_batch_orders` | `"false"` | Set to `"true"` to union `pos_orders_batch_cdc` into `fct_orders` |

## Dual PII Policy Tags

`includes/policy_tags.js` exports `piiRestrictedPolicyTag`, `piiMaskedPolicyTag`, and backwards-compatible `piiPolicyTag`.

Both tier helpers validate full GCP Policy Tag resource paths when non-empty.

Empty tags fail Dataform compilation whenever `allow_untagged_pii` is `"false"`.

- `customer_ic_number` uses `piiRestrictedPolicyTag` in `fct_orders` and `dim_customers`.
- `customer_email` and `customer_name` use `piiMaskedPolicyTag`.

## Unified Orders and Late-CDC Protection

Bronze declarations cover Datastream CDC (`pos_orders_cdc`), Pub/Sub streaming (`pos_orders_stream_cdc`), and GCS batch (`pos_orders_batch_cdc`).

When `include_stream_orders` or `include_batch_orders` is `"true"`, `fct_orders` unions normalized rows before calling `cdc_helpers.deduplicateCdc`.

`cdc_helpers.parseLookbackDays` validates `cdc_lookback_days` (`1..3650`) to block SQL injection.

Both `updatePartitionFilter` and the incremental `WHERE` filter use the same `cdc_lookback_days` window.

Keeping both windows equal prevents late CDC updates from creating duplicate `order_id` rows.

By default, `filter_cdc_deletes` is `"true"` and `includes/cdc_helpers.js` filters out deleted rows.

Set `filter_cdc_deletes` to `"false"` for legacy Bronze tables lacking `_metadata_deleted`.

## SCD Type 2 Change Deduplication

`dim_customers` tracks `customer_ic_number`, `customer_email`, `customer_name`, `segment`, and `country_code` in `record_hash`.

`scd_type2.scd2PreviousHashSql` removes consecutive unchanged CDC heartbeats before computing `LEAD(_ingested_at)` for `valid_to`.

## Medallion Architecture

```
definitions/
  01_bronze/      Raw CDC, stream, and batch source declarations (no DDL)
  02_silver/      Conformed incremental and SCD2 tables with partition-pruned assertions
  03_gold/
    finance/      Incremental finance revenue marts
    retail/       Incremental retail store performance marts
envs/             Per-environment Dataform compilation override examples
includes/         Reusable Dataform JS macros
quality/          Dataplex Auto Data Quality rule specs
tests/            Hermetic Python integrity test suite
```

1. **Bronze (`definitions/01_bronze/`)**: Holds Dataform `declaration` files only (`pos_orders_cdc`, `pos_orders_stream_cdc`, `pos_orders_batch_cdc`, `crm_customers_cdc`).
2. **Silver (`definitions/02_silver/`)**: Conforms `fct_orders` and `dim_customers` with deduplication, SCD2 windows, dual Policy Tags, and assertions.
3. **Gold (`definitions/03_gold/`)**: Incrementally aggregates Silver into partitioned marts (`mart_daily_revenue`, `mart_store_performance`) with lookback pruning.

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
> Split into domain repositories (`medallion-finance`, `medallion-retail`) when `CODEOWNERS` review load or DAG compile time becomes a bottleneck.
>
> When splitting, Terraform in `gcp-foundation` provisions one `google_dataform_repository` per domain repository.
> Each domain repository reads upstream Silver tables through Dataform `declaration` blocks.

## Multi-Environment Promotion (`dev` to `staging` to `prod`)

Per-environment Dataform overrides live under `envs/{dev,staging,prod}.compilation.json.example`.

Workflow `.github/workflows/dataform-promote.yml` promotes Dataform releases via GitHub Environments and keyless OIDC WIF.

- Pushes to `main` compile and update `dev-main`, then promote `staging-main` with strict PII checks.
- Pushes of `v*` tags or manual `prod` dispatches compile immutable tags with `allow_untagged_pii: "false"` and patch `prod-main`.

## Local Validation

Run the hermetic test suite before committing changes.

```bash
make test
```

## Keyless PR Compilation Check

Workflow `.github/workflows/dataform-dryrun.yml` runs offline hermetic checks unconditionally on every PR and push.

When WIF variables exist, it calls Dataform GA `v1` `compilationResults` over OIDC.

If `PII_MASKED_POLICY_TAG` and `PII_RESTRICTED_POLICY_TAG` are configured, it enforces `allow_untagged_pii: "false"`.

| Repository Variable | Example Value | Purpose |
| :--- | :--- | :--- |
| `GCP_WIF_PROVIDER` | `projects/123/locations/global/workloadIdentityPools/gh/providers/repo` | Workload Identity Pool provider resource path |
| `GCP_WIF_SERVICE_ACCOUNT` | `dataform-ci@example-silver-project.iam.gserviceaccount.com` | Service account granted Dataform viewer or runner roles |
| `DATAFORM_REPO_PATH` | `projects/example-silver-project/locations/asia-southeast1/repositories/medallion` | Target BigQuery Dataform repository resource name |

The check avoids service account JSON keys and fails if `compilationErrors` is non-empty.

## License

Apache License 2.0. See [LICENSE](LICENSE).
