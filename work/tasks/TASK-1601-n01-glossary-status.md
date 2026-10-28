---
id: TASK-1601
title: N-01 glossary and status-vocabulary rows (N-01-T04)
spec: SPEC-380
acceptance_criteria: [AC-4, AC-18]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T04
branch: s13-ready
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Name the firm-intake and Files concepts once, so code and copy use one word each.

## Plan
- `docs/product/glossary.md` (protected): communications rows (inbox thread, inbound message, inbox attachment, triage decision, sender rule, intake scope, intake team, Log received documents); evidence rows (document classification, folder kind, permanent file, Filed).
- `docs/product/status-vocabulary.yaml` (C2): `inbox_item` gains `held` (shown as Waiting with a sub-line, DV-15) and `withdrawn`; new `inbox_thread`, `portal_intake_upload` (client words), `file_document` (FIL-01 projection).
- Don't-use cells hold only identifiers no existing class, function or table uses (lint L12 reads them).
- `make regenerate` (with T02) rebuilds `kernel/_statuses.py` and `packages/ui/src/status.gen.ts`.
- Rollback: revert.

## Progress log
- 2026-10-27: written; L12 and validate_docs run in the end-of-batch pass.
