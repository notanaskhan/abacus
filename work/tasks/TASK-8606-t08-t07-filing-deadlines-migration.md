---
id: TASK-8606
title: "T-08-T07: Migration 0962 filing_deadlines and the platform.register_filing_deadline_source slot"
spec: SPEC-710
acceptance_criteria: [AC-35, AC-20, AC-15, AC-17]
risk_zone: amber
status: in-review
branch: t08-t07-filing-deadlines-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-08-T07
---

## Objective
Spec section: docs/plan/epics/T-08.md §4.2 NNNN_filing_deadlines, §4.1 platform. The filing_deadlines read model and filing_deadline_alerts in practice, plus the platform slot that fails closed on unknown kinds.

## Plan (amber)
1. migrations/versions/0962_filing_deadlines.py on 0961: filing_deadlines (metadata only; UNIQUE (tenant, source_kind, source_ref, filing_label); inputs_hash; no risk tier stored) and insert-only filing_deadline_alerts (UNIQUE (deadline, threshold, due_on)).
2. platform/filing_deadline_sources.py: SOURCE_KINDS (the CHECK), FilingDeadlineFact, FilingDeadlineWindow, register_filing_deadline_source raising UnknownFilingDeadlineSource on an unknown kind; exported from platform.api.
3. practice/registry.py and schema_check entries.
4. Rollback: downgrade drops both tables and the function; the slot is unused until T-08-T10.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5606). The read model keeps DELETE for the recompute (rows whose source disappeared); alerts are insert-only. Gates and tests run once at the S50 end pass (build first, test last).
