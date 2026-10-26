---
id: RB-32
title: "Client withdrawal: erase failures and legal-hold conflicts"
owner: builder
owning_epic: P-06
alarms: []
last_rehearsed: never
rehearse_by: 2027-04-16
---
# RB-32 · Client withdrawal: erase failures and legal-hold conflicts

| Field | Value |
|---|---|
| Owner | builder (written by P-06-T27) |
| Severity range | SEV4 to SEV3; SEV1 only if a withdrawn upload was read after its withdrawal (go to RB-08) |
| Linked from | none yet (no alarm on the purge exists; RB-14 covers the hold workflows) |
| SLO affected | none |
| Kill switches that apply | `evidence.withdrawal` per firm (stops new withdrawals only; a purge already started keeps running) |
| Rehearse by | R2 (Fri Apr 16, 2027) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

**The flow this covers** (ADR-162; P-06-T18, T19; DEC-298, DEC-299). A client withdraws an upload the firm never accepted: `POST /v1/engagements/{eid}/evidence-versions/{vid}/withdraw` (`evidence/withdrawals.py: withdraw`). One unit of work writes the `evidence_withdrawals` row (`erase_after` = business clock + 30 days), voids the fulfilments (`requests.withdraw_upload`), audits `evidence_version.withdrawn` and emits it. The outbox handler `on_withdrawn` starts `EvidenceWithdrawalPurge` (`withdrawal:<tenant>:<version>`, reuse rejected, work class `batch`). The workflow sleeps on a durable timer, then runs the activity `evidence_withdrawal.erase` (`erase_withdrawn`) until it answers 0. Each attempt can end four ways:

| Outcome | Where | Row and audit | Next |
|---|---|---|---|
| Not due on the business clock | `erase_withdrawn` (`at < erase_after`) | none | sleep the seconds left |
| No hold check registered | `kernel.holds.held_versions` raises `HoldCheckMissing` | `erase_blocked_at`, `block_reason = no_hold_check`; `evidence_withdrawal.erase_blocked` (`held=0`) | sleep 1 day |
| Held | the hold check, or `evidence_key_destroy` answering `held` under the version's lock | `erase_blocked_at`, `block_reason = legal_hold`; `evidence_withdrawal.erase_blocked` (`held=1`) | sleep 1 day |
| Clocks disagree | `evidence_key_destroy` answers `not_due` (`abacus_now()` is before `erase_after`) | none | sleep 1 day |
| Erased | `evidence_key_destroy` answers `destroyed` or `gone` | `erased_at`; `evidence_withdrawal.erased`; outbox `evidence_withdrawal.erased` | done |

Anything else (database, KMS or storage unavailable; a raised exception in the activity) is retried by Temporal without limit, 5 s doubling to 10 minutes (`_PURGE_RETRY`). After 30 attempts the workflow continues as new with the same id.

## 1. Recognise it
- **Erase blocked:** `evidence_withdrawals` rows with `erased_at IS NULL AND erase_blocked_at IS NOT NULL`, and `evidence_withdrawal.erase_blocked` audit events repeating daily for the same version. Read `block_reason`:
  - `legal_hold`: a hold covers the version (a `hold_objects` row not released, or an `applying`/`active` hold over its engagement or, for a client-level scope, its client). **Expected, not a failure.**
  - `no_hold_check`: nothing registered `kernel.holds.register_hold_check`. `evidence/holds.py` registers `holds_covering` when it is imported, which `evidence.api` does; this means the process that ran the activity never imported it. **A deploy fault.**
- **Erase failing:** an `evidence_withdrawal_purge` workflow whose current activity attempt count keeps rising (Temporal UI or `temporal workflow describe -w withdrawal:<tenant>:<version>`), with no `erase_blocked` audit. The activity is raising. Typical: `insufficient_privilege` from `evidence_key_destroy` (the session is not the system actor `evidence.withdrawal_purge`), `check_violation` (no withdrawal row for that version), a database or KMS outage.
- **Purge never started:** a withdrawal row with `erased_at IS NULL`, past `erase_after`, and no workflow `withdrawal:<tenant>:<version>`. The outbox delivery of `evidence_version.withdrawn` failed or is stuck: see RB-06 (queue backlog) and RB-23 (workflow engine).
- **Hold conflict at withdraw time:** the client gets 409 `legal_hold_active` and the audit shows `evidence_version.withdrawal_refused` (`held=1`); nothing else was written. **Expected** (DEC-299): a held version is not withdrawn.
- Not this runbook: a hold that fails to apply or release (RB-14); a fingerprint or seal mismatch (RB-29); firm offboarding and crypto-shred (RB-13).

## 2. Contain
- Nothing to contain for `legal_hold` or `legal_hold_active`: the hold wins by design and the withdrawn version stays hidden from every firm read and agent from the withdrawal's commit (`repository.not_withdrawn`).
- For `no_hold_check`: do not register a stub check or edit the row to force the erase. Fix the worker (§6). Until then nothing is erased, which is the safe state.
- If a withdrawn version was read after its withdrawal (an evidence read, an agent run, an export naming it), that is a hiding failure, not an erase failure: treat it as SEV1 and go to RB-08.
- Turning `evidence.withdrawal` off for a firm stops new withdrawals (the route answers 404). It does not stop or roll back a purge already started, and it must not: the client was told the file would be erased.

## 3. Preserve
- The `evidence_withdrawals` row (ids, `withdrawn_at`, `erase_after`, `erase_blocked_at`, `block_reason`, `erased_at`), the `evidence_object_keys` row's `retained_at` and `destroyed_at` (never the wrapped key), and the audit events for the version (`evidence_version.withdrawn`, `.withdrawal_refused`, `evidence_withdrawal.erase_blocked`, `.erased`).
- The workflow's history: `temporal workflow show -w withdrawal:<tenant>:<version> --output json` into the incident folder. Payloads are identifiers only.
- For a hold conflict: the hold's id, scope and status from `legal_holds` and `hold_objects`.
- Never copy the file name, the file or any derived text into a ticket. The audit trail deliberately carries no file name.

## 4. Assess
- **How many** versions are blocked and for how long past `erase_after`? A `legal_hold` block can last as long as the hold; ADR-162 erases after 30 days unless held, so a held version is the design, not a late erase. The client's withdraw copy (DF-15, R-01) promises 30 days without naming holds: if a client asks, the firm explains the hold.
- **`no_hold_check`:** since when? Every purge in every firm on that worker is blocked; the backlog drains on its own once fixed (each blocked purge retries daily).
- **Activity failures:** one version or all? One version points at its data (a missing key row: `evidence_key_destroy` raises; a key already retained by an accept that raced the withdrawal: the 0144 guard should have refused the withdrawal, see `test_p06t23_withdrawal_race_and_screening_rows.py`). All versions point at the platform (database, KMS, Temporal).
- **Data classes:** the withdrawn file was a client upload, possibly tax return information (ADR-031). The erase destroys the wrapped data key; the ciphertext stays in S3 under Object Lock governance retention, unreadable, until it lapses.

## 5. Notify
- `legal_hold`: no notice. The hold owner already knows the version is held.
- A purge that is late for any reason other than a hold, by more than a day past `erase_after`: tell the firm's admin which withdrawal is late (by its request, never the file name) and the expected date, using the incident notice template (vault reference per RB-27). If the delay comes from an Accrued fault and touches firm data, RB-27 sets the 72-hour clock.
- A hiding failure: RB-08.

## 6. Recover
1. **`no_hold_check`:** check that the worker imports the evidence module: `abacus/worker/__main__.py` imports every `abacus.modules.<name>.api` in `abacus.modules.MODULES`, and `evidence.api` imports `evidence/holds.py`, which registers `holds_covering`. A worker built without evidence, or a change that stops `evidence.api` importing `holds.py`, shows as this. Redeploy the fixed worker (RB-01). Verify: the next daily attempt for a blocked version writes no new `erase_blocked` with `no_hold_check`.
2. **Activity raising `insufficient_privilege`:** the purge must run as `TenantContext(tenant, "system", "evidence.withdrawal_purge")` (`withdrawals.PURGE_ACTOR`, bound in migration 0144). A changed actor id in code without a migration breaks every erase: revert the change (RB-01). Never call `evidence_key_destroy` by hand from another session.
3. **Platform outage (database, KMS, Temporal):** follow RB-10, RB-23 or RB-09 as fits. The activity's unlimited retries resume on their own; nothing to restart.
4. **Purge never started:** once the outbox and workers are healthy, the relay redelivers `evidence_version.withdrawn`; `on_withdrawn` is idempotent (`WorkflowAlreadyStartedError` suppressed, conflict policy use-existing). If the event is gone, start it with the same id and input through `kernel.dispatch` (`WithdrawalPurgeInput(tenant, version, wait_seconds)`), never by `start_workflow`: the erase activity reads the business clock and does nothing early.
5. **`legal_hold`:** nothing to do. When the hold is released (RB-14), the next daily attempt erases.
6. **Rollback:** none. An erase cannot be undone, and no step here erases anything early.

## 7. Verify
- The row has `erased_at` set, `evidence_object_keys.destroyed_at` is set and `wrapped_key` is null, and `evidence_withdrawal.erased` is in the audit.
- Reading the version's content answers as erased (`storage.get` raises `KeyDestroyed`); its previews, checks and extractions are gone.
- The workflow `withdrawal:<tenant>:<version>` is completed.
- Tests that pin the behaviour: `backend/tests/integration/backfill/test_p06t19_withdrawal.py` (`test_ac15_nothing_is_erased_before_30_days`, `test_ac15_a_legal_hold_blocks_the_erase_and_it_is_retried_daily`, `test_ac15_without_a_registered_hold_check_nothing_is_erased`, `test_ac15_only_the_purge_stamps_a_withdrawal`) and `backend/tests/workflows/test_withdrawal_purge_replay.py` (history `withdrawal-purge-v1-blocked-then-erased.json`).

## 8. Review
Open the blameless review (ADR-097). Each action becomes a test, a lint rule, an alert or an ADR. The first likely action: an alarm on `evidence_withdrawals` rows with `block_reason = 'no_hold_check'`, or with `erased_at` null more than a day past `erase_after` and no hold, linked here. Update this runbook and set "Last reviewed against an incident".

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
