---
id: TASK-1172
title: Client withdrawal - withdraw route, void and hide everywhere, status rollback, EvidenceWithdrawalPurge, evidence.withdrawal flag (P-06-T19)
spec: SPEC-319
acceptance_criteria: [AC-15]
risk_zone: red
status: done
epic: P-06
plan_key: P-06-T19
branch: s7c-client-uploads
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"An accepted version answers 409 evidence_accepted and a withdrawn version is unreadable after 30 days unless held." ADR-162 §1 to §4, §7; sprint demo item 5: a withdrawn upload is voided and hidden from firm reads, agents and exports, and only an unaccepted upload can be withdrawn.

## Plan (red zone)
- **Contract:** the C5 stub route goes live in `evidence/contract.py` behind `evidence.withdrawal` (new flag, `docs/architecture/feature-flags/evidence.yaml`, codegen), `Idempotency-Key`, authorise before replay; new error codes `evidence_accepted`, `evidence_not_withdrawable` (409) and `not_your_upload` (403); `make regenerate`. Matrix row unchanged (P-06-T01).
- **Code:** `evidence/withdrawals.py` (service, purge activity, subscriber); `workflows.py` `EvidenceWithdrawalPurge`; `workflow_types.WithdrawalPurgeInput`; `events.py`; `repository.not_withdrawn()` on every version read; guards in `processing.py`, `words.py`, `viewer.py`, `agents/service.py`, `agents/upload_review.py`; `requests` `fulfilment_withdrawals`, `live_fulfilment()` on every fulfilment read, `withdraw_upload`.
- **Migrations:** 0144 (T18: `evidence_withdrawals` and its guards, the accept trigger, `evidence_key_destroy`); **0145** (`fulfilment_withdrawals`, insert-only, person-bound guard; `down_revision` 0144). Rollback: `alembic downgrade 0143`.
- **Closed lists:** worker publisher handlers (`test_worker_screening.py`); C5 stub `IMPLEMENTED`; tenant isolation tables (regenerated).
- **Tests:** `tests/integration/backfill/test_p06t19_withdrawal.py` (13); `tests/workflows/test_withdrawal_purge_replay.py` with `histories/withdrawal-purge-v1-blocked-then-erased.json` (recorded by `abacus_tools.workflows.record_withdrawal_purge`).

## Progress log
- 2026-10-24: built. `fulfilments` is pinned insert-only by the schema-check suite, so voiding is a new insert-only table rather than a stamp column (DEC-298). The ORM `add` of the withdrawal sent its NULL stamp columns, which the app may not insert: core `insert().values()` instead. Not done (DEC-298): deleting the withdrawn version's derived database rows, the 30-day time-skipping test (Temporal's test server is a download), the erase record's "ciphertext persists until" date. Left for P-06-T23's independent suite: an accept racing a withdrawal at the database (the trigger is in 0144).

- 2026-10-24: security review fixes (DEC-299), tests first (each new test failed on e31f80ad, checked in a throwaway worktree): derived agent output, citations, regions and word layers of withdrawn versions hidden; the erase definer checks the window, holds and the version lock itself and erases derived content; a held version is refused 409 `legal_hold_active`; authorised on the upload's own item; concurrent withdrawals 404. `tests/integration/backfill/test_p06t19_security_review.py` (8). The T19 test firm is now synthetic so the frozen business clock reaches `abacus_now()`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-298 | Route, who, what, hide, purge as built | No (ADR-162) |
| DEC-299 | Security review of the withdrawal and the upload policy | No |
