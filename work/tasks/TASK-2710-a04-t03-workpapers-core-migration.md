---
id: TASK-2710
title: A-04-T03 Migration workpapers_core (expand-only)
spec: SPEC-620  # A-04 §4.2 M1 and docs/contracts/workpapers-core.md
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T03
branch: s22-a04-t03
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "up/down/up passes, every table has forced RLS and a work_item_id, the insert-only
  tables refuse UPDATE and DELETE as the app role" (the author/approver clause is DEC-1761's: one
  builder, AMENDMENT-solo).

## Scope
**In**: migration 0581 on SPEC-308's 0072 tables (columns added, cell keys widened, scope columns
back-filled and trigger-set), new `attention_flags`, `attention_flag_events` (insert-only) and
`audit_procedures`; workpapers registry and models; status-vocabulary comment; regenerated
tenant-isolation tests; migration test.
**Out**: the service, projection, export and registrations (A-04-T04); planning tables (A-04-T06).

## Plan (amber)
1. Reconcile decision (DEC-1761): land on 0072, keep every 0072 table insert-only, derive the
   current version and hash from `workpaper_versions`; `procedures` is taken by fieldwork (0057),
   so the A-04 table is `audit_procedures` (the status object is already `audit_procedure`).
2. Migration 0581 revises 0580 (re-chain at merge if another head lands first). Expand-only: added
   columns are nullable or defaulted; the two cell-key CHECKs are widened, never narrowed.
3. Scope: `workpaper_child_scope()` (invoker, search path pinned) sets `engagement_id` and
   `work_item_id` from the parent paper on every child insert; existing rows back-filled, then
   NOT NULL.
4. Grants: insert-only by REVOKE (ADR-004); `attention_flags` updates only `state`,
   `converted_to_kind`, `converted_to_id`; `audit_procedures` only `tailored`,
   `tailored_rationale`, `status`, `linked_work`; neither deletes. Actor kinds default from
   `app.actor_kind` and are not insertable.
5. Rollback: downgrade drops the three tables, the triggers, the function and the added columns,
   and restores the A1-only cell-key CHECKs.

## Progress log
- 2026-11-01: built; tests run in the S22 end pass.
