# Security Policy

## Reporting a Vulnerability

Do not open public GitHub issues for suspected security vulnerabilities.

Report vulnerabilities privately through GitHub Security Advisories (`Security` -> `Report a vulnerability`).

Include reproduction steps, affected repository paths, and impact details in your report.

## Template Hygiene Rules

Never commit live Google Cloud project IDs, organization IDs, or billing account IDs.

Keep `platform-context.json`, `*.auto.tfvars`, `*.auto.tfvars.json`, and `*.tfstate*` files gitignored.

Use Workload Identity Federation instead of exported service account JSON keys.
