---
id: TASK-6507
title: "A-07-T30: the in-app release transaction (G8) — POST /v1/audits/{id}/release, ReleaseWorkflow, report_releases"
spec: SPEC-644
acceptance_criteria: [F6]
risk_zone: red
status: in-review
branch: s33-a07-t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: A-07-T30
---

## Objective
Margaret Okonkwo's 10:07 AM release records G8 once under replay, a render failure records
nothing, and agent, system and stale-MFA calls are refused.

## Plan (red)
1. `assurance/release.py` (PROTECTED; finishes TASK-332's interim G8 file): `snapshot` (G5–G7 from
   their providers, the also-required list, the report version and its L4 approval; SHA-256 is
   the gate hash), `request_release` (live EP, fresh MFA, in-app mode, replay by
   Idempotency-Key, `gates_not_met`, `content_changed`, a fresh approval grant per decision bound
   to work item, version, draft hash and gate hash), `consume_and_render` (single gate, re-check,
   C11 `render_final` under the consumed grant through a ContextVar approval provider),
   `record_in_app_release` (one UoW: `report_releases`, report `released`, C11 lock, C10
   deliverable, phase to Released by G8, `report.released`), `fail_release` (void, reason only).
2. `release_workflow.py`: ReleaseWorkflow (`time_sensitive`) and four activities; a failed render
   is non-retryable and records nothing.
3. `release_facts.py`: also-required providers (FS approved, independence, final materiality,
   AU-C 260 sent); `bring_down` stays unmet until A-07-T32 registers its provider.
4. `reporting/api.py`: `render_outcome`, `document_of_owner`, `fs_approved_by_management_at`.
5. `release_contract.py`: GET and POST `/release` live behind `audits.report_release`.
6. `a07_registrations.py`: `audit_report`'s approval provider; the `report_released` index tag.
7. Matrix `report.release` takes `mfa_recent` (DEC-2261), fresh-MFA register, RELEASE-001.
Rollback: revert; no migration (0668 has the tables).

## Progress log
- `2026-11-09` — Built; unit acceptance tests written (`tests/unit/assurance/test_a07t30_release.py`),
  not run (end pass). Partial: `bring_down` has no provider until A-07-T32 (this sprint); filings
  stay `[]` until A-07-T36 (S34); the deliverable's audience is the engagement's client.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3107 | The release's grant, gate hash, approval provider and the one unit of work | no |
