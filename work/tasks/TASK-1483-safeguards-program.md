---
id: TASK-1483
title: Safeguards program in platform (G-02-T20; ADM-06 h fieldset D)
spec: SPEC-349
acceptance_criteria: [AC-27, AC-30, AC-45, AC-46, AC-47]
risk_zone: amber
status: in-review
epic: G-02
plan_key: G-02-T20
branch: s12-gov
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The firm's safeguards record (QI, WISP and its approval, annual report dates, training, PTIN,
access review), Pub 4557 control status rows over imported platform content, and Export WISP pack.

## Plan
- **Migration 0242**: `safeguards_control_definitions` (global platform content, imported by
  staff as a numbered set and published by a second staff member; no app write), 
  `safeguards_programs` (tenant PK), `safeguards_control_statuses` (tenant, control_key),
  `wisp_packs` (the pack jobs). Status words `evidenced` and `open` become real
  (`docs/product/status-vocabulary.yaml`; the `NO_YAML_ENTRY` findings removed).
- **Service** `platform/safeguards.py`: read (counts over the published definitions), save
  (`safeguards.updated`, 409 `stale_version`), control status (`safeguards_control.updated`;
  404 for an unknown key), WISP pack (202, `wisp_pack.prepared`).
- **WISP pack**: `WispPackWorkflow` (batch) zips the WISP and the evidence items the controls
  link, read through `evidence.api` as the requester, into the exports bucket.
- **Posture**: registers `pub4557_open`.
- **Rollback**: revert; downgrade 0242.

## Progress log
- 2026-10-27: plan written; built.
