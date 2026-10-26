---
id: TASK-1300
title: The sign-off service, POST /v1/sign-offs with the ladder and eligibility reads (P-04-T18)
spec: SPEC-308
acceptance_criteria: [AC-5]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T18
branch: s10-p04-signoffs
created: 2026-10-26
updated: 2026-10-26
---

## Objective
The C3 stub-1 sign-off routes (`GET /v1/sign-offs`, `GET /v1/sign-offs/eligibility`,
`POST /v1/sign-offs`) answer 501. Make them live on the one sign-off engine: a person signs what
they saw (`seen_hash`) at a level the matrix allows them, and every R-SO rule answers its fixed
code. Acceptance (P-04.tasks.csv): in an API test Hannah Leclerc signs Trial Balance v1 at L2
after Marcus Delaney's L1 adoption, and every R-SO rule returns its fixed error code.

## Plan
- **Service** `review/sign_offs.py` (new): `ladder`, `eligibility`, `sign`.
  - Facts from the owner (`reviewable_facts`, fail closed), the engagement resource from
    `engagements.api.engagement_resource_of` (walls answer 404).
  - `sign`: R-SO-1 live human first (`ctx.client`, non-human actor or support refused), then
    `authorise(sign_off.create)`, then the level row with the target's preparers
    (`TargetFacts`, P-04-T15). Denials map to fixed codes: the level row's role layer (and a
    non-preparer condition) 403 `level_not_permitted`; a known preparer on L2/L3 409
    `segregation`; the independence layer or an uncleared signer 409 `independence_pending`
    (R-SO-5, `engagements.api.independence_cleared`, the one answer ADR-164 names for P-04).
  - Then, in order: `seen_hash` against the owner's current hash (409 `content_changed`,
    nothing written); the statement version must be the level's current one (422
    `sign_off_invalid`); R-SO-6 empty required fields 409 `incomplete`, uncited values 422
    `uncited_change`; R-SO-4 open notes block L2+ (409 `open_review_notes`, `facts.count`);
    L2+ need a current L1 (409 `not_prepared`); the same level already signed by the caller on
    this content 409 `already_signed`; the L1 signer can't sign L2/L3 (409 `segregation`,
    R-SO-3, also in the matrix).
  - Insert one row with what was true at signing: `kind`, `work_item_id`, `initials` (from the
    display name), `engagement_role_at_sign`, `version_no`, `statement_version`,
    `adopted_run_id` (R-SO-8: an L1 on agent work, from the owner's facts),
    `independence_checked_at`. Audit `sign_off.recorded`; outbox `sign_off.recorded`
    (identifiers only).
- **Facts** (`slots.ReviewableFacts`): optional `label`, `context_label`, `work_item_id`,
  `cell_count`, `citation_count`, `cited_count`, `incomplete_count`, `uncited_count`,
  `adopted_run_id`, `adopted_run_number`, defaulted so existing owners keep working. Workpapers
  fill label, counts and uncited agent cells; trial balances their label.
- **Statements**: per level, versioned in code (`STATEMENTS`), copy verbatim from the SHL-12
  handoff spec (reviewer and EQR texts).
- **Matrix**: unchanged. ADR-160 wants `eqr_reviewer` on `sign_off.eqr`, but SPEC-308's
  shipped test pins `{reviewer}`; left open for Ayush (DEC-401).
- **Static rule** `SIGNOFF-001`: only review's service files, its `api.py` and the two existing
  owner call sites (`workpapers/service.py`, `assurance/mapping.py`,
  `assurance/trial_balance.py`) name `record_sign_off` / `sign_target`.
- **Errors**: `content_changed`, `segregation`, `open_review_notes`, `independence_pending`,
  `incomplete`, `uncited_change`, `level_not_permitted` in `error-codes.yaml`
  (`error_codes --write`).
- **Contract**: `docs/contracts/review-grammar.md` behaviour notes; consumer test `LIVE` set;
  `make generate`. Bulk (`:bulk`, R-SO-7) stays 501 for P-04-T22.
- **Not here**: `sign_off_requested` to the next level is a P-04-T26 notification kind;
  adopting the run's pending suggestions on L1 waits for the suggestions service (P-04-T24).
- **Tests first**: `tests/integration/test_p04t18_sign_off_service.py` (service and HTTP).
- **Rollback**: revert the branch; the routes answer 501 again. Rows written are valid
  `sign_offs` rows (no migration).

## Progress log
- 2026-10-26: planned.
- 2026-10-26: built (tests written first, run in the end-of-batch targeted pass). Matrix and API client regenerated.
