---
name: setup-data-medallion
description: Interactive customer onboarding workflow covering private repo creation, platform-context.json lookup, QUESTIONNAIRE.md intake, compilation config generation, and local validation.
---

# Setup Data Medallion

Run these steps in order when onboarding `gcp-data-medallion` for a customer or test run.

## Step 0: Create a Private Customer Repository

GitHub keeps standard `gh repo fork` clones public.

Never store customer project IDs or Policy Tag paths inside a public fork.

```bash
gh repo create <owner>/<customer-repo> --private --template choo737/gcp-data-medallion --clone
cd <customer-repo>
gh repo view --json isPrivate --jq '.isPrivate'
```

Confirm the final command prints `true`.

## Step 1: Check for Optional Platform Context

Check whether `platform-context.json` exists from [choo737/gcp-launchpad](https://github.com/choo737/gcp-launchpad) in the repository root.

1. Read `platform-context.json` if present to prefill project IDs, region, dataset names, and Policy Tags.
2. Confirm `platform-context.json` and `envs/*.compilation.json` are gitignored before writing customer values.
3. Proceed directly to `QUESTIONNAIRE.md` when running standalone without `gcp-launchpad`.

## Step 2: Walk Through QUESTIONNAIRE.md

Never guess GCP project IDs, BigQuery Policy Tag paths, or GitHub WIF identifiers.

Ask the customer each question in [QUESTIONNAIRE.md](../../../QUESTIONNAIRE.md) and record their answers:

1. **Upstream Bronze source mode**: Confirm Greenfield Suite or Brownfield standalone BigQuery (`bronze_project`, `bronze_dataset`, `defaultLocation`).
2. **Brownfield schema mapping**: Adapt `definitions/01_bronze/*.sqlx` declarations if existing raw table or column names differ.
3. **Active order and CDC streams**: Confirm `include_stream_orders`, `include_batch_orders`, and `filter_cdc_deletes`.
4. **PII compliance tier**: Collect `pii_restricted_policy_tag`, `pii_masked_policy_tag`, and `pii_policy_tag`, setting `allow_untagged_pii` to `"false"` in `staging` and `prod`.
5. **CDC lookback and Gold topology**: Confirm `cdc_lookback_days` (`1..3650`) and single Gold project versus `gold_retail_project` domain isolation.
6. **Data quality expectations**: Review `quality/silver_orders_quality.yaml` thresholds for `order_id`, `order_date`, and `net_amount`.
7. **GitOps WIF variables**: Collect `GCP_WIF_PROVIDER`, `GCP_WIF_SERVICE_ACCOUNT`, and `DATAFORM_REPO_PATH` for `dev`, `staging`, and `prod` GitHub Environments.

Run `.agents/skills/split-domain-mesh/SKILL.md` later if additional isolated Gold domain repositories are needed.

## Step 3: Populate Compilation Configurations

Never create `package.json` because Dataform `3.1.5` uses `dataformCoreVersion: 3.1.5` in `workflow_settings.yaml`.

1. Update `workflow_settings.yaml` non-sensitive defaults (`defaultLocation`, `defaultDataset`, `cdc_lookback_days`, `include_stream_orders`, `include_batch_orders`, `filter_cdc_deletes`).
2. Copy `envs/dev.compilation.json.example`, `envs/staging.compilation.json.example`, and `envs/prod.compilation.json.example` to gitignored `envs/{dev,staging,prod}.compilation.json`.
3. Populate customer project IDs and Policy Tag paths only inside gitignored `envs/{dev,staging,prod}.compilation.json`.
4. Enforce `"allow_untagged_pii": "false"` in `envs/staging.compilation.json` and `envs/prod.compilation.json`.
5. Configure repository and environment variables in GitHub for `.github/workflows/dataform-dryrun.yml` and `.github/workflows/dataform-promote.yml`.

```bash
cp envs/dev.compilation.json.example envs/dev.compilation.json
cp envs/staging.compilation.json.example envs/staging.compilation.json
cp envs/prod.compilation.json.example envs/prod.compilation.json
```

## Step 4: Validate Locally Before Committing

Confirm no customer secrets or untracked override files are staged for commit:

```bash
git status
make test
```

Commit changes to the private customer repository only after `make test` passes cleanly.
