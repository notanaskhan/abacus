---
id: TASK-2020
title: N-01-T14 Portal intake
spec: SPEC-380
acceptance_criteria: [AC-25]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T14
branch: s15n-n01-t14
created: 2026-10-29
updated: 2026-10-29
---

## Objective
POR-03 "Upload something else": a portal principal sends a batch to the firm Inbox, lists its
own uploads in client words and withdraws while unfiled; withdrawn files are hidden at once and
crypto-erased after 30 days unless held (DEC-1060).

Acceptance (backlog row): "Claire Feld's upload reaches the firm Inbox and a withdrawn upload is
hidden at once and unreadable after 30 days unless held."

## Built
- Migration 0371: `evidence_intake_object_keys`; `inbox_attachments.withdrawn_at`;
  `inbound_messages.portal_scope_kind/id`.
- evidence: `intake_keys.py` (detached staging, key record/destroy, live keys); `key_for` falls
  back to intake keys; registry.
- communications: `portal_intake.py` (create, add file, list own, withdraw, erase activity),
  `intake_purge_workflow.py` (`IntakeWithdrawalPurge`), detached ingest for `portal_upload`,
  event `portal_intake.withdrawn`; registry.
- portal: the four routes live. Stacked on N-01-T13.

## Tests
Build-only (Ayush, 2026-10-29): no tests written or run; at the end review (with the purge's
replay history).

## Progress log
- 2026-10-29: built (S15 group B, build-only). ruff, pyright, lint-imports, banned_patterns clean.
