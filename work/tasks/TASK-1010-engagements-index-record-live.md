---
id: TASK-1010
title: Engagements index and record live — ENG-01 read model, ENG-02 projection, gates, interim recorded letter, migration 0124 (P-07-T15)
spec: SPEC-321
acceptance_criteria: [AC-16, AC-17]
risk_zone: amber
status: done
epic: P-07
plan_key: P-07-T15
branch: s6-clients-engagements
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"ENG-01 a to d and ENG-02 a to d resolve from the E0 seed, the tiles sum to the header, and a letter dated before acceptance answers 409." (P-07-T15; SPEC-321 AC-16, AC-17.)

## Plan (amber zone)
- **Code:** `engagements/index.py` *(new)*: one `visible(engagement.read_metadata)` base; rows sorted by the earliest open work-item due date (past due first) on a keyset cursor; `counts` per status over the base without the tile (`declined` dropped); `facets.service_line` over the base without the service line and tile; summary (prospect, Accepted without a recorded letter, past due); work-item sub-lines in their kind's object words; partner initials; letter summary. `engagements/record.py` *(new)*: the record projection (Details, Review and Delivery, Client Portal for content readers; designations for `client_contact.read`), gates G1–G9 from the registered providers with `met_at`/`met_by_user_id`, the interim recorded letter (G1 met, both dates on or after the decision, archived refused, Accepted → Contracted through the transition table, `letter.recorded`, `gate.met`). Routes in `contract.py` go live behind `engagements.v2`; a client principal answers 404.
- **Migration 0124** (down_revision 0123): `engagements.version` with a bump trigger, `engagements.period_label`, `engagement_letters` interim-letter columns. Rollback: `alembic downgrade 0123`. T16 appends the drafts table to the same file (branch-only).
- **Registry:** engagements `UPDATE_COLUMNS` (period_label; letter columns). Error code `letter_exceptions_off`; `letter_before_acceptance`, `gate_unmet`, `engagement_archived` raised from `record.py`.
- **Tests:** `tests/integration/test_engagements_v2_live.py` (AC-16, AC-17); the v2 stub contract test now knows the four live routes.
- **Deferred (DEC-224):** the plain-path move (`/v1/engagements` and `/{id}` stay v1 until their consumers move); retiring `engagements.work_items_api` (F-03's independent suite asserts the flag in `/v1/me`); `allow_letter_exceptions` (unregistered: the exception fails closed); the E0-seed figures of ENG-01 a–d (P-07-T14's independent suite over the seed).

## Progress log
- 2026-10-24: built as planned; 4 integration tests (`test_engagements_v2_live.py`), the 33 v2 contract tests and the related integration files (engagements, schema, work items, F-03 independent: 510 passed) pass; schema_check expectations updated for the new update columns. Frontend shapes unchanged (ENG-02, status and contract vitest suites pass). Mistake noted: banned patterns AUTHZ-001 (a role literal compared) and REQ-002 (the `accepted` literal) — use module constants and `EngagementStatus`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-224 | Index sort, period and letter filters, the interim letter's columns and exception, deferred path move and flag retirement | No |
- 2026-10-26 (S10 code gap, branch `s10-p07-t15-flag`): the EP exception. Migration 0182 registers
  the firm setting `allow_letter_exceptions` (`authz.matrix.POLICY_SETTING_KEYS`: no matrix cell
  may name it); `identity.firm_setting_on` reads it; `record_letter_v2` records "Not required this
  year" for the engagement partner with a reason while it is on (409 `letter_exceptions_off`
  otherwise, 422 `letter_exception_reason_required` without a reason), meets G3 and moves Accepted
  to Contracted. 0182's `down_revision` is 0180 on this branch; re-point to 0181 at the batch
  merge. **Still deferred:** retiring `engagements.work_items_api`, because F-03's independent
  suite asserts the flag in `/v1/me` (`test_f03_independent_acceptance.py:680`) and a test is
  never weakened without Ayush's word (DEC-224). Tests at the end of the run.
- 2026-10-27 (S10 gap build, branch `s10-p07t15-retire-work-items-flag`): `engagements.work_items_api` is retired, on Ayush's word ("Yes, retire the engagements.work_items_api flag (P-07-T15), including the F-03 independent test change").
  - `GET /v1/work-items` is live for every firm: `work_items_api_on` and its 404 are gone.
  - The registry entry is removed and `kernel/_flags.py` regenerated.
  - F-03's independent test (`test_f03_independent_acceptance.py`) no longer names the flag. It now asserts that every flag in `/v1/me` answers a boolean or a variant string, beside the existing check that the set equals the registry.
  - The wall suite's flag list drops it.
  - The engagements README and `docs/contracts/work-items.md` say the list is live.
