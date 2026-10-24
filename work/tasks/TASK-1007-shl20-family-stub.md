---
id: TASK-1007
title: SHL-20 family stub — screening card, rerun, feedback and the screening-return follow-up draft; screening.card flag; C5 §12 (P-06-T15)
spec: SPEC-319
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: red
status: done
epic: P-06
plan_key: P-06-T15
branch: s6-follow-ups
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The additive C5 change merges with consumer tests green for A-01 and R-01." P-06 §4.3 (SHL-20 rows), §4.4 (`screening.feedback`), §4.9 (`screening.card`).

## Plan (red zone)
- **Contract first:** `agents/screening_contract.py` — `ScreeningCardOut` (C2 `EvidenceScreeningStatus` verdict, named checks, flagged files with C4 region refs, provenance, the viewer's feedback, `allowed_actions`; no confidence), `ScreeningRerunOut`, `ScreeningFeedbackIn/Out` (a thumbs-down needs a reason), `ScreeningReturnDraftIn` → `FollowUpOut` (P-06-T14's). Routes: `GET …/request-items/{id}/screening` (`upload_review.read`), `POST …/screening/rerun` (`screening.request`, 202), `POST /v1/screenings/{id}/feedback` (`screening.feedback`, new), `POST …/request-items/{id}/follow-ups` (`follow_up.draft`). The follow-up edit and send shapes are P-06-T14's live routes.
- **Flag** `screening.card` (agents flags file; default off; 90 days): off 404, on 501.
- **Matrix:** `screening.feedback` partner, manager, senior, staff; independence required; agent deny.
- **Contract doc:** `docs/contracts/c5-requests-binders.md` §12 and v1.2 row.
- **Tests:** `tests/contracts/c5_requests_binders/test_c5_shl20_family.py`; gate lists in `test_app_gates.py`, `test_independence.py`.
- **Rollback:** remove the two routers from `agents.api.ROUTERS`, the flag and the matrix row; regenerate. No migration.

## Progress log
- 2026-10-24: built; 21 contract tests pass; C5 consumer tests: A-01, C-01, T-02 green; R-01's `test_r01_every_client_reach_of_the_request_filter_needs_client_visible` fails on origin/main too (DEC-211's client-wide grants, not this change).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-221 | Where the SHL-20 family lives, its flag, what the card carries | No |
