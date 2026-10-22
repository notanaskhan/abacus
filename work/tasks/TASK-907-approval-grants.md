---
id: TASK-907
title: Approval grants - issue, consume and void, single use and bound to their payload (P-04-T10)
spec: SPEC-319
acceptance_criteria: [AC-6]
risk_zone: red
status: done
epic: P-04
plan_key: P-04-T10
branch: p04-t10-approval-grants
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"A grant cannot be consumed before not_before, twice, after a void, or by an approver who has lost the action, each proven by a test" (P-04-T10; ADR-126, ADR-161, DEC-24).

## Plan
- Migration `0102_approval_grants` (identity): the table under tenant RLS, a settle-once trigger, insert and column-update grants, and the grant half of 0095's Undo trigger on `proposal_decisions`.
- `identity/grants.py`: `issue_grant` and `void_grant`, which run in the caller's unit of work, and `consume_grant`, the single gate.
- Register `consume_grant` as the relay's grant consumer. The consumer now receives the event id and the payload's SHA-256.
- Tests: `tests/integration/test_approval_grants.py`.
- Rollback: downgrade 0102 restores 0095's Undo function and drops the table. No caller issues grants yet.

## What changed
- **`approval_grants`** stores the subject (type and id), the action, the approver, the engagement and work item for the re-check, the payload SHA-256, `not_before`, `expires_at`, `used_at` with `consumer_ref`, and `voided_at`.
  - The app may update only the three settle columns, and only once (trigger).
  - Business time (`abacus_now()`) throughout.
- **`issue_grant`** re-runs `authorise` for the approver, so fresh MFA and walls apply.
- **`consume_grant(tenant, grant, consumer_ref, payload_sha256)`:**
  - before `not_before` it raises `GrantNotYetDue`, so the relay retries and never drops the effect;
  - it returns False when the grant is void, expired, bound to another payload, or already spent by another consumer, or when the approver lost the action (re-checked with `member_context` and `allowed_actions`, which skips fresh MFA);
  - a retry by the same consumer stays True;
  - it is audited as `approval_grant.consumed`, on behalf of the approver.
- **`void_grant`** returns False once the grant is used, so the caller answers `effect_started`. It is audited as `approval_grant.voided`.
- **Kernel:** `payload_sha256` (canonical JSON) and `uow.event_sha256(event)`. The relay passes `(tenant, grant, event_id, digest)` to the consumer.
- **Undo trigger:** an undo is refused once the undone decision's grant has been consumed.
- **Fixed on main (other S4 merges):**
  - `identity_token_url` (P-01-T09) broke the "secret-looking setting is a SecretStr" test, so it is renamed `identity_exchange_url`;
  - `portal_home.read` (P-08-T01) is the first conditioned read. The `visible()` parametrizations now leave conditioned reads out, and a new test asserts that `visible()` refuses them.

## Decisions
- `consumer_ref` makes the relay's at-least-once delivery safe: a crash after consume and before publish retries as the same event and still delivers.
- No outbox events (`approval_grant.issued/voided/effective`) yet. `effective` belongs to the effect-hold dispatcher (P-04-T29), and nothing subscribes to the others.

## Progress log
- 2026-10-23: `test_approval_grants.py` (11), the relay, the Undo window, and the kernel and identity units pass.
