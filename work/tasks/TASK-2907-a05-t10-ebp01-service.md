---
id: TASK-2907
title: A-05-T10 EBP-01 service (plan profile, plan status, providers and checks)
spec: SPEC-640
acceptance_criteria: [AC-8]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T10
branch: s24-a05-t10 (stacked on s24-a05-t09)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

EBP-01's backend: plan facts through the field history, the plan-status engine, the plan number on the plan entity, providers and code checks.

## Acceptance (backlog)

Northwind reads large filer, due Oct 15, 2026, one SOC gap on Keystone and one EIN mismatch routed to Summit; PN 58217 or 000 is refused with the Form 5500 helper, and a staff member's PATCH answers 403.

## Plan

- `assurance/compute/ebp/plan_status.py` (pure): filer status (100 at BOY; the 80-120 rule), the due date (last day of month 7; with a 5558 the 15th of month 10; weekend and holiday roll), plan-number problems (format, zero, the recordkeeper's ID).
- `assurance/ebp_plan.py`: plan view; `edit_plan` (first save records the plan; later saves at their version; every field through `record_value` with the citation note; PN via `organisations.api.set_entity_plan_number` after the checks, `pn_format` check recorded); providers list and add with the `soc_gap` and `ein_mismatch` checks (the mismatch names the TPA it is routed to), provider status `correction_requested` when flagged; check notes as code sentences; audit owners.
- `organisations/plan_numbers.py`: `entity_plan_number`, `set_entity_plan_number`, `entity_name`.
- Contract: `GET`/`PATCH /ebp/plan`, `GET`/`POST /ebp/providers` live; `ProviderIn` gains SOC fields and last-four EINs; `PlanOut.sponsor_ein` optional.
- Deferred (DEC-1955): Invite provider (C5 third-party delegation) stays 501 for A-05-T11's screen task; Raise exception through C3 issues needs an `ebp_provider` issue record type (A-05-T11); full EINs and fingerprints wait for A-05-T18; K-02's holiday set joins when its read API exists.
- Tests: `tests/unit/assurance/test_a05t10_plan_status.py`, `tests/integration/backfill/test_a05t10_ebp01_service.py`.

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-05-T09. Pyright clean on the new files; tests written, not run.
