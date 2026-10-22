---
id: TASK-398
title: C16 v1 stub, notifications half (P-01-T01)
spec: SPEC-013
acceptance_criteria: [C16]
risk_zone: amber
status: done
epic: P-01
plan_key: P-01-T01
branch: p01-t01-c16-stub
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Stub merges in the batch with the E0 examples, flags and glossary rows." Under AMENDMENT-solo, the protected edits (flag file, kernel errors) are decided here rather than waiting for an approval.

## What changed
- `notifications/contract.py`: the v2 models, each field with a classification tag; `facts` is Restricted.
- The stub routes, `OWN`, behind `notifications.v2`. They answer 404 when the flag is off and 501 `not_implemented` when it is on:
  - `GET /v1/notifications/feed`;
  - `GET` and `PUT /v1/me/notification-preferences`.
- **Decision (contract §11):** the v2 list is served beside the v1 `GET /v1/notifications` for one sprint rather than replacing its shape. It moves to `GET /v1/notifications` once the v1 consumer is gone (P-01-T06 or T16).
- `kernel.errors.NotImplementedYet` gets a 501 handler in `api/app.py`. `AbacusRouter` accepts `errors=(501,)`, so the generated client types the 501.
- `docs/architecture/feature-flags/notifications.yaml`: `notifications.v2` and `notifications.email`, owner AY, expiring 2027-01-20. Regenerated.
- Glossary: a new "New terms: notifications" section (kind, category, inline action, preference, delivery).
- `docs/contracts/notifications.md` (C16 v1). It covers:
  - the slot and kind-code convention, with the legacy dotted codes listed;
  - categories, `pending` and the inline-action closed set;
  - preference defaults, facts classification, the email template keys and variables, the TRI rule;
  - the E0 examples.
- The register row moves from planned to stub. `make generate` was run.

## Progress log
- 2026-10-22: built per the S3 batch rules (static checks only). ruff and pyright are clean, and `make check-generated` passes.
