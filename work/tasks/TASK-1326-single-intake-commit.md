---
id: TASK-1326
title: Single intake commit, live (P-07-T42; CLI-06 a-f, h, i)
spec: SPEC-332
acceptance_criteria: [AC-23]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T42
branch: s10b-client-intake
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The Thornbury estate is added under Walter Thornbury with three return work items in one
transaction and a replayed key returns the same result." Turns P-07-T37's dedupe, intake-draft
and commit stubs live (the import routes stay 501 until P-07-T52).

## Plan
- **Migration 0177** `client_intake_drafts` (P-07 §4.2 M8, same shape and purge rule as M2):
  id, tenant_id, created_by, step (CHECK the six steps), payload jsonb (object, bounded), version,
  saved_at, discarded_at, committed_at, committed_client_id (FK clients), result jsonb
  (identifiers only). RLS via `tenant_table`; UPDATE/DELETE revoked, column grants for insert
  and the autosave/discard/commit columns; registered in `engagements/registry.py`.
- **organisations** (`intake.py`, new; through `api.py`): `dedupe_candidates` (normalised name,
  fiduciary designators, `pg_trgm` similarity; walled clients never candidates; no TIN input),
  `add_intake_relationship` and `add_intake_contact` (inside the caller's unit of work),
  `conflict_check_outcome` (the check's subject and outcome for this reader).
- **engagements** (`intake.py`, new): drafts (own scope, autosave `seen_version` 409
  `stale_version`, discard), per-step validation (`date_of_death_required` for Form 706,
  the SSN/ITIN guard on a non-synthetic firm, 422 `tin_kind_not_allowed`), and the commit as one
  unit of work: client or a new entity under an existing client (404 when walled), entity
  attributes, relationships, contacts with roles, one Prospect engagement per engagement type
  and period with the engagement partner and its work items by service (Form 56 a line item
  only), the conflict check linked (409 `gate_unmet` unless cleared), with `start_acceptance` an
  acceptance record per engagement; `client_intake.committed`. A committed draft answers its
  stored result; the route also stores the answer by `Idempotency-Key`.
- **Contract**: routes live in `intake_contract.py` (import routes still the stub);
  `IntakeServiceIn.forms` (additive: the type's forms to create, default all);
  `docs/contracts/intake-import.md` v1 notes; `make generate`.
- **Conflict subject**: `client_intake_draft` registered (owner-only drafts).
- **Decisions**: DEC-430 (intake commit choices), DEC-441 (dedupe scoring).
- **Tests**: TASK-1324's suite (marker dropped), the stub suite's live routes, a unit suite for
  validation and scoring.
- **Rollback**: revert the commits and downgrade 0177; the routes answer 501 again.

## Progress log
- 2026-10-26: planned.
- 2026-10-26: built (DEC-430, DEC-441). Deviation found by TASK-1324's suite: a manager could not
  clear a hit on the firm admin's intake, because the conflict subject was owner-only; the
  `client_intake_draft` subject is now visible to its owner and to anyone holding
  `conflict.clear` who is not walled from the draft's client (DEC-430). `open_record` takes the
  record kind; `drafts._work_items` is now `work_items_for`. Tests: TASK-1324's suite (12),
  `tests/unit/engagements/test_intake_rules.py`, the stub suite (live routes no longer 501),
  `test_schema_check_db.py` (the new update columns), regenerated tenant-isolation suite. Gates
  green; `make generate`; web tsc.
