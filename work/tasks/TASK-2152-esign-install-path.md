---
id: TASK-2152
title: Firm DocuSeal install path - catalogue category, sealed install command, staging wiring (ADR-342)
spec: SPEC-381
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T18
branch: esign-install-path
created: 2026-10-30
updated: 2026-10-30
---

## Objective

N-02-T18's adapter only runs for a firm with a connected `docuseal` install whose sealed secret
holds the API key (`integrations.esign_install_secret`). Nothing creates that install: the
catalogue has no e-signature category, there is no `docuseal` catalogue row, and no command seals
a key. Build that path, end to end on a local stack and ready for staging, with W7 still closed
(ADR-150 v2 is proposed; opening W7 is a separate human decision). The key never passes through
git, an ops-request file, a command argument or a log.

## Plan

- **Migration 0407** (`0407_catalog_esignature_category.py`, on 0406): expand-only, the
  `integration_catalog` category CHECK gains `esignature`. Downgrade restores the old CHECK
  (refused by Postgres while an `esignature` row exists).
- **integrations/ports.py**: `CatalogCategory` = the read categories plus `esignature`; the
  catalogue load validates against it. `IntegrationCategory` (read adapters, client connections,
  the portal card) is unchanged: DocuSeal is never a registered read adapter, so its row never
  reaches a portal card.
- **integrations/esign_install.py** (exported through `integrations.api`): in one unit of work
  as the operator's context: `connect_esign_install` inserts the firm's `docuseal` install
  (`mode token`, `created_by` a member of the firm) and seals the secret (`store_secret`);
  refused while a live install exists. `rotate_esign_secret` erases and re-seals the secret on
  the live install. `disconnect_esign_install` erases the secret and marks the install
  `disconnected`. `esign_install_state` says connected or not (never the key). Each writes its
  audit event; targets by id only.
- **abacus_tools/esign_install.py**: `connect | rotate | disconnect | status --tenant <id>
--operator <handle> [--requested-by <member user id>] --reason <text>`. The key is read only
  from `ABACUS_ESIGN_INSTALL_API_KEY` (staging: mapped from Secrets Manager into the ops one-off
  task only). Before writing, `connect` and `rotate` check the key against DocuSeal (`GET /user`
  on `api.docuseal.com`; a refusal writes nothing) and ensure the hidden `docuseal` catalogue row
  through `integration_catalog_load` as `abacus_ops` (the platform's own provider declaration,
  DEC-1279). Added to `OPS_COMMANDS`.
- **Infra (staging; the builder applies)**: secret `abacus/staging/docuseal` (`api_key`, pasted
  by the builder); `docuseal_enabled` maps it into the ops one-off only; DNS firewall staging
  allowlist gains `api.docuseal.com` and `docuseal.com`; `infra/README.md` steps.
- **Sub-processor register**: the DocuSign row becomes DocuSeal (egress hosts above);
  `sub-processors.md` regenerated.
- **Tests**: unit (tool refusals: no key in env, bad handle, DocuSeal refusing the key writes
  nothing; the catalogue row validates); integration (connect seals a secret that opens to the
  account JSON; a second connect is refused; rotate replaces; disconnect erases; W7 closed still
  yields no secret); migration 0407 up/down.
- **Docs**: DEC-1279; RB-18 runbook connect/rotate/disconnect steps.
- Rollback: revert; downgrade 0407 after disconnecting and removing any `docuseal` row.

## Progress log

- 2026-10-30: plan written.
- 2026-10-30: built as planned. Also: `ops-task.yml` command options gain the four commands
  (the workflow is the allowlist's other copy, `test_ops_tasks_are_the_contracts_allowlist`);
  `error-codes.yaml` regenerated for `esign_install_exists`; RB-18 gains the install section.
  Tests: unit 7, integration 6 (local Postgres), migration 0407 up/down/refusal 1, all passing;
  related unit suites pass except failures already on main (TASK-5010's `mapping_set.*` actions,
  three status-vocabulary enums). Not run here: the staging apply and a staging connect (the
  builder applies; W7 stays closed).
