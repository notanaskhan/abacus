---
id: TASK-1255
title: Logged PII reveal (P-03-T16)
spec: SPEC-322
acceptance_criteria: [AC-26, AC-27, AC-28, AC-29]
risk_zone: red
status: in-review
epic: P-03
plan_key: P-03-T16
branch: s9a-pii-masking
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"An onshore engagement member gets the value with expires_in 30 and an audit row naming them,
while an offshore member, an agent or a client principal is refused and nothing is revealed."

## Plan (red zone)
- **Contract:** `POST /v1/evidence-versions/{v}/pii-reveals` already exists as a stub
  (`trust_contract.py`, `PiiRevealIn` and `PiiRevealOut`). The route now serves it and declares
  `errors=(429, 501)` (501 stays declared, as on the other served C4 routes). Then
  `make generate`, and `docs/contracts/c04-citations-viewer.md` §3.5 and §6 are updated.
- **Service (`evidence/reveals.py`):** the pattern of `organisations/tin.py reveal_tin`, in this
  order:
  - Refuse anything that is not a live person serving their own request: an agent, the system,
    a support session, a client, or a call outside an API request (`serving_request()`).
  - `visible_version` (403 for a client, 404 when invisible or walled).
  - `authorise(pii.reveal)` on the engagement. The matrix refuses an offshore member, a role
    without the action, a client role or a lack of independence. MFA that is stale or missing
    becomes 403 `forbidden` with `facts.reason = mfa_required`.
  - Then, in one unit of work: read the region (it must be on this version, none derived, else
    404); take a per-person advisory lock; count `pii_reveals` in the past hour (≥ 20 gives 429
    `reveal_rate_limited` with `retry_after`, plus an audited `pii.reveal_throttled`, a warning
    and a counter); insert the `pii_reveals` row (`source_review`, `mfa_at`, expiry 30 s on);
    write the `pii.revealed` audit event (actor is the person; target is the version; Ref
    `reveal_id` and `region_id`; never the value); open the sealed value with its region binding.
  - After commit, write an `access_events` row (`pii.revealed`, flagged `pii_tin`, `pii_bank` or
    `pii_dob`) before the value leaves. The response is `Cache-Control: no-store`.
- **Manifest:** `allowed_actions` carries `pii.reveal` when the version has masks, the flag is on
  and `allowed_actions()` allows it (it probes every layer but MFA). An offshore member, a client
  or a role without the action gets no chip.
- **Matrix:** unchanged. `mfa_recent: required` applies to every kind, which is stricter than
  "for TIN kinds" (DEC-370).
- **Tests first:** `tests/integration/trust_kit/test_pii_reveal.py` (AC-26 to AC-29 through the
  service with `serving_request` set, plus route-level no-store and status codes);
  `tests/integration/backfill/test_offshore_evidence_reads.py` review5 now expects the live
  refusal shape for Mia's unknown region (404) instead of the stub's 501.
- **Rollback:** revert, or turn off `evidence.pii_reveal` (the kill switch, ADR-097). No
  migration: 0109 has `pii_reveals`.

## Progress log
- 2026-10-26: plan written.
- 2026-10-26: built as planned. `test_pii_reveal.py` has 5 tests: AC-26 value, row, audit and
  access event, with no value in any table or log; AC-27 MFA missing or stale; AC-28 agent,
  client, support, outside-request and offshore refusals with no traces, and the chip omitted;
  a region from another version or firm; AC-29 the 21st reveal gets 429 and is audited. The
  route test (review5 in `test_offshore_evidence_reads.py`): Remy gets 403 with no row; Mia gets
  201 with the value, `no-store`, `expires_in` 30; an unknown region gets 404. `make generate`
  regenerated `packages/api-client` (the reveal's 429, and 409 on the three legacy page routes).
- 2026-10-26 (security review): the reveal itself passed review. L3: added a route test that
  the 429 carries `Retry-After` equal to `facts.retry_after` (the platform handler already set
  it). DEC-370 note added.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-370 | The reveal's MFA scope, refusal shapes and audit fields | No |
