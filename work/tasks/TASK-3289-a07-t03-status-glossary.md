---
id: TASK-3289
title: A-07-T03 status vocabulary and glossary for completion, release and archive
spec: SPEC-644
acceptance_criteria: [AC-3]
risk_zone: amber
status: in-review
epic: A-07
plan_key: A-07-T03
branch: s27-a07-t03
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"make generate emits the new StrEnums and status.ts entries, and no A-07 screen string uses a
status word missing from the registry."

## Plan (amber)
- `status-vocabulary.yaml`: objects `eqr_review`, `eqr_checklist_item`, `completion_item`,
  `subsequent_event`, `legal_letter`, `representation_letter`, `governance_communication`,
  `audit_report`, `report_release`, `filing`, `archive_addition` with the A-07 §4.2 codes and the
  handoff words; `archive.locked` reads "Locked · sealed" (DF-20, DV-2); transient `locking` and
  `releasing` are derived (DV-7). The assurance phases `archiving` and `archived` already exist
  on `audit_engagement` (A-01).
- Glossary rows under "New terms: assurance" for every A-07 noun and the archived-write
  exception, with the words not to use.
- Regenerated: `kernel/_statuses.py`, `packages/ui/src/status.gen.ts` (OpenAPI unchanged).
- Tests: the existing status-registry and glossary lints at the end review.
- Rollback: revert and regenerate.

## Progress log
- 2026-11-04: built; `make regenerate` clean.

## Decisions made during this task
None new (DF-20 and DF-31 applied).
