# CLAUDE.md

Read [AGENTS.md](AGENTS.md) before modifying any file in this repository.

## Key Invariants

- Follow the Bronze (`declaration`), Silver (`incremental`/`table` + Policy Tags + assertions), and Gold (`table` + partition filter + assertions) layer rules.
- Never write `SELECT *` in `.sqlx` or `.js` files.
- Never hardcode real GCP identifiers or internal LDAPs.
- Keep `workflow_settings.yaml` at `/` with all ten contract `vars`.
- Run `make test` and confirm all checks pass before finishing.
