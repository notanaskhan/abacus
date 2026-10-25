---
id: TASK-1248
title: Staff void of a wrong rule link (R-01-T09 remainder; portal-pbc contract, R-01 Story 2.2)
spec: SPEC-323
acceptance_criteria: [AC-3]
risk_zone: red
status: in-progress
epic: R-01
plan_key: R-01-T09
branch: s8b-core
created: 2026-10-25
updated: 2026-10-25
---

## Objective
R-01-T09 landed the portal drop and sort (TASK-1193) but left `POST /v1/engagements/{eid}/fulfilments/{id}/void` a 501 stub behind `portal.drop_sort`. R-01 Story 2.2: a person voids a wrong rule link with `{reason: wrong_request}`; the link is stamped void (`voided_at`, `voided_by`), audited `fulfilment.voided`, the request returns to `requested` if nothing else fulfils it, and the version waits in the engagement inbox again for a person to assign. A voided, human, agent or accepted link answers 409 `not_voidable`. The agent is denied (`fulfilment.confirm`, INV-1).

## Plan
- **Migration 0159** (requests, evidence):
  - `fulfilments` gains `voided_at timestamptz NULL`, `voided_by uuid NULL`, `void_reason text NULL CHECK (void_reason IN ('wrong_request'))`, all three set together.
  - `GRANT UPDATE (voided_at, voided_by, void_reason)` to the app.
  - Trigger `fulfilments_void_only` (BEFORE UPDATE): any other column changing, an un-void, a second void, a void of a non-`rule` link, a void not by the acting person (`app.actor_kind = 'human'`, `voided_by = app.actor_id`), or a void of a version with an `accept` review decision (undone or not) is refused.
  - Human-only register: 0156's 32 entries plus `fulfilment.voided` (verb decide); the downgrade restores 0156's list.
- **requests:**
  - `live_fulfilment()` also leaves out voided rows, so every read treats a voided link as never made.
  - `void_rule_fulfilment(tx, ...)` stamps the row, audits `fulfilment.voided`, reverts the item with `revert_to_requested`, and returns the item, version and status (`api.py`).
- **evidence** (`rule_voids.py`), because evidence already depends on requests and the void touches both:
  - Checks: live human, engagement ref, `authorise(fulfilment.confirm)`.
  - In one unit of work: refuses an accepted version (`ever_accepted`), voids through the requests API, returns the version's portal-drop inbox file to Waiting (status, assignment and decision cleared; `sort_outcome` stays `rule_linked`, the sort's own record), and emits `FulfilmentVoided`.
  - `NotVoidable` (409 `not_voidable`, fact `fulfilment_id`).
  - The route moves from requests' `pbc_contract.py` to `drops_contract.py`, with the same path, action, models and contract. It authorises before `idempotent(...)`. `portal.drop_sort` off answers 404.
- **Subscribers:**
  - The human-gate projector also hears `fulfilment.voided`, so the inbox-match gate reopens.
  - The screening aggregate recomposes the request's batch.
  - The worker's pinned subscriptions are extended.
- **Docs:** the portal-pbc contract (route home, as built), error catalogue, DEC-339.
- **Tests (written first):** `tests/integration/backfill/test_r01t09_rule_link_void.py`:
  - void of a rule link: request back to requested, file waiting, audit, event;
  - accepted, human, voided and other-firm links answer 409 or 404;
  - agent refused;
  - the database trigger refuses a forged update;
  - flag off answers 404;
  - an idempotent replay;
  - reads leave the voided link out.
- **Rollback:** revert and downgrade 0159. Rule links can no longer be voided (the stub's 501 returns).

## Progress log
- 2026-10-25: plan written; building in the core lane (main session).
- 2026-10-25: built. Void tests in `test_r01t09_portal_drops.py`: 6 passed (22 in the file). Wider targeted run: 9,311 passed, 8 xfailed; one real failure (the pinned update-column contract in `test_schema_check_db.py`, now extended with `fulfilments`); every other failure was Docker timing out under load. The Docker VM then stopped; the extended contract test and the schema-check, projector and portal-documents files are to re-run once Docker is back.
- 2026-10-25: security review fix round (one high, one medium, lows; DEC-339). High: the void now locks the request item before checking for an accept (`lock_rule_link`), matching the accept's lock order. Medium: the voided version is retired (`evidence_version_voids`, 0159) and left out by `not_withdrawn()` and `withdrawn_among`; gates hear `fulfilment.voided`. Lows: the poll reads `waiting` after a void, the idempotency key binds the engagement, the database stamps `voided_at`. Unit (no database): 5,928 + 3,250 passed after the pinned worker subscription list and a lint fix. Integration assertions added; to run once Docker is back (the Docker VM stopped mid-afternoon).
