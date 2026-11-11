---
name: split-domain-mesh
description: Recipe for splitting a Gold domain folder into an independent Data Mesh repository.
---

# Split a Gold Domain Into a Data Mesh Repository

Use this recipe when your engineering team exceeds 25 data engineers.

## 1. Provision the New Repository

1. Create a new repository such as `medallion-<domain>`.
2. Copy `workflow_settings.yaml`, `package.json`, `includes/`, `tests/`, and `AGENTS.md`.
3. Ask the platform team to add a `google_dataform_repository` in `gcp-foundation` pointing to the new repo.

## 2. Replace Upstream Silver Refs With Declarations

1. List every Silver table referenced by `definitions/03_gold/<domain>/`.
2. Create `definitions/01_upstream/<silver_table>.sqlx` with `type: "declaration"` pointing to `silver_project` and `silver_dataset`.
3. Keep Gold models in `definitions/03_gold/<domain>/` pointing to `${ref("<silver_table>")}`.

## 3. Enforce Partition Filters and Contracts

1. Preserve `WHERE` partition filters on upstream Silver tables that set `requirePartitionFilter: true`.
2. Keep Dataform `assertions` on every Gold mart.
3. Add Dataplex quality rules in `quality/` for critical domain outputs.

## 4. Retire the Old Domain Folder

1. Update `CODEOWNERS` in `gcp-data-medallion`.
2. Remove the migrated `definitions/03_gold/<domain>/` folder once the new repository passes release compilation.
3. Run `make test` in both repositories.
