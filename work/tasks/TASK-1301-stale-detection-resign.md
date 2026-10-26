---
id: TASK-1301
title: Stale detection and re-sign (P-04-T19)
spec: ADR-160
acceptance_criteria: [R-SO-5, DEC-84]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T19
branch: s10-p04-signoffs
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Changing a cell on a signed workpaper shows later levels as Changed after sign-off without
updating any sign-off row, and an unconfirmed member is refused with `independence_pending`.

## Plan
- **Consumer** `review/stale.py` (`StaleSignOffDetector`): subscribed to the owners' change
  events (`trial_balance.version_created`, and the new `workpaper.content_changed` workpapers
  emits from `set_cells` and `cite`). For the changed target it reads the owner's current hash
  and `stale_of`, and emits one `sign_off.went_stale` per stale sign-off. Idempotent: the event
  id is derived from (sign-off, current hash), each in its own unit of work, and a replay's
  duplicate id is skipped. No sign-off row is touched (ADR-160 clause 3).
- **Notification** `sign_off_stale` (approval category): the signer, text "A sign-off of yours
  on {engagement} changed after sign-off." (glossary "Changed after sign-off").
- **G2** (R-SO-5): `sign` asks `engagements.api.independence_cleared` for the signer on every
  engagement, and on an attest client (unknown counts as attest) also needs the G2 gate met
  (`gate_fact(G2)`, the partner's conclusion): stricter on attest clients.
- **Re-sign**: a stale level is signable again by anyone the rules allow, as a new row; only the
  same person on the same content is `already_signed`. The ladder's `allowed_actions` names
  `sign_off.resign` for a stale level the caller may sign.
- **Tests first**: `tests/integration/test_p04t19_stale_resign.py`.
- **Rollback**: revert; no migration. Emitted events are informational.

## Progress log
- 2026-10-26: planned.
- 2026-10-26: built (tests written first, run in the end-of-batch targeted pass). Matrix and API client regenerated.
