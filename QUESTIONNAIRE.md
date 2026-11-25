# Medallion Onboarding Questionnaire

Use this questionnaire to configure `gcp-data-medallion` before running Dataform compilation or GitOps promotion.

This repository works standalone on existing BigQuery tables or paired with [choo737/gcp-launchpad](https://github.com/choo737/gcp-launchpad).

Keep `platform-context.json` and `envs/*.compilation.json` untracked in git.

## Handoff From Launchpad

If `platform-context.json` exists from [choo737/gcp-launchpad](https://github.com/choo737/gcp-launchpad), prefill `workflow_settings.yaml` and `envs/{dev,uat,prod}.compilation.json` first.

| `platform-context.json` Field | Target Medallion Setting | Purpose |
| --- | --- | --- |
| `primary_region` | `defaultLocation` | Dataform dataset and compilation region |
| `existing_landing_zone.core_project_id` | `bronze_project` and `bronze_dataset` | Source BigQuery Bronze dataset inputs |
| `existing_landing_zone.core_storage_project_id` (`data-core`) | `silver_project` | Conformed Silver BigQuery target project |
| `existing_landing_zone.analytics_project_id` | `gold_project` | Gold domain mart target project |
| `pii_*_policy_tag_id` | `pii_restricted_policy_tag` / `pii_masked_policy_tag` | BigQuery Policy Tags (formerly Data Catalog) |

## Section 1: Upstream Bronze Source Mode

Choose how Bronze tables are provisioned and populated before Silver models run.

| Option | Mode | Upstream Provisioning | Required Files & Variables |
| :--- | :--- | :--- | :--- |
| **A (Default)** | Greenfield Suite | `gcp-foundation` creates datasets; `gcp-data-ingestion` populates Bronze | Set `bronze_project`, `bronze_dataset`, and `defaultLocation` |
| **B** | Brownfield Standalone BigQuery | Existing Datastream, Fivetran, Airbyte, Debezium, or custom ELT tables | Set `bronze_project`, `bronze_dataset`, and adapt `definitions/01_bronze/*.sqlx` |

In Brownfield mode, update `name` and `columns` inside `definitions/01_bronze/*.sqlx` to match your source tables.

Keep `type: "declaration"` in every Bronze file and never run DDL in `definitions/01_bronze/`.

## Section 2: Active Order and CDC Streams

Select which Bronze order and customer streams feed `definitions/02_silver/fct_orders.sqlx` and `definitions/02_silver/dim_customers.sqlx`.

| Stream | Source Declaration | Config Variable | Default | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Relational Order CDC | `pos_orders_cdc.sqlx` | Always enabled | Active | Primary POS order stream; uses `_metadata_deleted` when `filter_cdc_deletes` is `"true"` |
| Relational Customer CDC | `crm_customers_cdc.sqlx` | Always enabled | Active | Feeds `dim_customers` SCD Type 2 history |
| CDC Delete Tombstones | `_metadata_deleted` column | `filter_cdc_deletes` | `"true"` | Set `"false"` only for legacy Bronze tables lacking `_metadata_deleted` |
| Pub/Sub Streaming Orders | `pos_orders_stream_cdc.sqlx` | `include_stream_orders` | `"false"` | Set `"true"` to union real-time Pub/Sub BigQuery subscription orders |
| GCS Batch Orders | `pos_orders_batch_cdc.sqlx` | `include_batch_orders` | `"false"` | Set `"true"` to union daily or hourly GCS batch order loads |

## Section 3: PII Classification and Regulatory Governance

Select a compliance tier for BNM RMiT, PDPA, or GDPR controls.

| Tier | Profile | `allow_untagged_pii` | Policy Tag Variables | Quality Rules (`quality/silver_orders_quality.yaml`) |
| :--- | :--- | :--- | :--- | :--- |
| **1** | `sandbox_poc` | `"true"` in `dev` | Empty strings allowed locally | Keep default completeness and `net_amount >= 0` rules |
| **2** | `enterprise_standard` | `"false"` in `uat` and `prod` | Set `pii_restricted_policy_tag` and `pii_masked_policy_tag` | Enforce threshold `1.0` on primary keys and amounts |
| **3** | `regulated_fsi_rmit` | `"false"` in all shared environments | Separate restricted IC tag, masked email/name tag, and `pii_policy_tag` fallback | Add store, currency, and reconciliation rules in `quality/silver_orders_quality.yaml` |

Restricted columns (`customer_ic_number`) read `pii_restricted_policy_tag` via `policy_tags.piiRestrictedPolicyTag()`.

Masked columns (`customer_email`, `customer_name`) read `pii_masked_policy_tag` via `policy_tags.piiMaskedPolicyTag()`.

Both helpers fall back to `pii_policy_tag` when tier-specific tags are empty.

Builds fail closed when `allow_untagged_pii` is `"false"` and no valid Policy Tag is set.

Example tag format: `projects/<gov-project>/locations/<region>/taxonomies/<taxonomy-id>/policyTags/<tag-id>`.

## Section 4: Incremental CDC Lookback and Gold Domain Topology

Choose your late-arriving CDC replay window and Gold project layout.

| Decision | Option | Variable Setting | Trade-off |
| :--- | :--- | :--- | :--- |
| Lookback window | High-volume low-cost | `cdc_lookback_days: "7"` | Lowest BigQuery merge scan cost; 7-day late replay tolerance |
| Lookback window | Standard default | `cdc_lookback_days: "30"` | Balanced cost; 30-day late CDC replay tolerance |
| Lookback window | Quarterly backfill | `cdc_lookback_days: "90"` | Higher merge scan bytes; 90-day late CDC replay tolerance |
| Gold layout | Single Gold project | `gold_project`, `gold_dataset`; `gold_retail_project: ""` | Simplest IAM and single Dataform repository |
| Gold layout | Multi-project domain mesh | Set `gold_retail_project` and `gold_retail_dataset` | Isolates Retail marts; see `.agents/skills/split-domain-mesh/SKILL.md` for more domains |
| XAI audit ledger | Regulated ML telemetry | Set `ml_audit_project` and `ml_audit_dataset` | Links `ml_xai_audit_ledger` from `choo737/gcp-data-science` and `03-data-science` |

Keep `cdc_lookback_days` between `1` and `3650` so `includes/cdc_helpers.js` validation passes.

## Section 5: GitOps Dry-Run and Tag-Gated Release Promotion

Configure GitHub Environments (`dev`, `uat`, `prod`) with keyless Workload Identity Federation (WIF).

Workflow `.github/workflows/dataform-dryrun.yml` runs offline checks and compiles PRs against Dataform GA `v1`.

Workflow `.github/workflows/dataform-promote.yml` updates `dev-main` and `uat-main` on `main` pushes, and promotes `prod-main` on `v*` tags.

| GitHub Variable | Scope | Example / Format | Purpose |
| :--- | :--- | :--- | :--- |
| `GCP_WIF_PROVIDER` | Repo / Environment | `projects/<num>/locations/global/workloadIdentityPools/gh/providers/repo` | Keyless OIDC provider for Google Cloud auth |
| `GCP_WIF_SERVICE_ACCOUNT` | Repo / Environment | `dataform-ci@example-silver-project.iam.gserviceaccount.com` | Service account compiling Dataform releases |
| `DATAFORM_REPO_PATH` | Repo / Environment | `projects/<project>/locations/<location>/repositories/<repo>` | Target Dataform repository resource path |
| `DATAFORM_RELEASE_CONFIG` | Optional Environment | `dev-main`, `uat-main`, or `prod-main` | Overrides default release config ID per environment |
| `BRONZE_PROJECT` | Environment | `example-prod-bronze-project` | Overrides `vars.bronze_project` during CI compilation |
| `SILVER_PROJECT` | Environment | `example-prod-silver-project` | Overrides `defaultDatabase` and `vars.silver_project` |
| `GOLD_PROJECT` | Environment | `example-prod-gold-project` | Overrides `vars.gold_project` during CI compilation |
| `PII_MASKED_POLICY_TAG` | Environment (`uat`/`prod`) | `projects/<gov>/locations/<loc>/taxonomies/111/policyTags/222` | Sets `pii_masked_policy_tag` and `pii_policy_tag` |
| `PII_RESTRICTED_POLICY_TAG` | Environment (`uat`/`prod`) | `projects/<gov>/locations/<loc>/taxonomies/111/policyTags/333` | Sets `pii_restricted_policy_tag` and forces `allow_untagged_pii: "false"` |

## Section 6: Target File Mapping Summary

Map collected questionnaire answers to these repository files before running `make test`.

| Answer Group | Target File | Git Status |
| :--- | :--- | :--- |
| Default project, location, and baseline `vars` | `workflow_settings.yaml` | Tracked (placeholders or non-sensitive defaults only) |
| Per-environment compilation overrides | `envs/{dev,uat,prod}.compilation.json` | Gitignored (copied from `envs/*.compilation.json.example`) |
| Knowledge Catalog (formerly Dataplex) Auto data quality expectations | `quality/silver_orders_quality.yaml` | Tracked |
| Custom Brownfield raw source schemas | `definitions/01_bronze/*.sqlx` | Tracked |
| WIF and Dataform CI/CD settings | GitHub Environments (`dev`, `uat`, `prod`) | GitHub UI / `gh variable set` |
