---
id: TASK-7309
title: "T-04-T36: K-1 activities and treatments service: activities from the TXP-12 hand-off (DEC-88) and third-party uploads; SALY; changed_vs_prior; override with a required reason; multi-change approval; k1_package.released consumer diffing draft and final (DEC-84)"
spec: SPEC-649
acceptance_criteria: [AC-7]  # the spec's section ids (validate_docs reads AC-<n>)
risk_zone: amber
status: in-review
branch: s37-t04-t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T36
---

## Objective
Ridgeline shows 8 treatments with 7 proposed and treatment 8 approved, only PTET is Changed vs
2024, an override without a reason answers 422, and a release that moves basis to 4,676,125 raises
a re-proposal instead of editing the approved treatment.

## Plan (amber)
- `backend/src/abacus/modules/tax/k1_treatments.py`: read model (activities, treatments, lines
  per kind, SALY, `changed_vs_prior`, pending proposal, DEC-88 source package only with both
  engagements readable), `override_treatment` (reason required 422, sealed, `seen_version` 409,
  `overridden` event), `apply_approved_treatments` (the approver must hold
  `k1_treatment.approve`, else `level_not_permitted`; one `approved` event per row),
  `refresh_saly`, `activity_from_handoff`, `activity_from_upload`, `on_package_released`
  (release, diff draft box lines against the hand-off's final values, `went_stale` and
  `reproposed` for each approved treatment whose boxes moved).
- `worksheet_review.apply_k1_proposal` now approves through the service; `agents.api` gains
  `proposal_approver` (the newest approving decision's person).
- Routes (the T-04-T09 stubs): `GET …/k1-activities`, `GET /v1/tax/k1-activities/{id}`,
  `POST /v1/tax/k1-treatments/{id}/override`. `K1ActivityOut.source_package_id` is additive.
- `tax.api.SUBSCRIPTIONS["k1_package.released"]` runs T-04-T23's issue resolution, then this.
- Tests: `backend/tests/unit/tax/test_t04t36_k1_treatments.py`,
  `backend/tests/integration/agent_tests/test_t04t36_k1_treatments.py`.
- No migration (0761's tables and grants), no flag (`tax.review_workspace`).

## Partial
- The approval's checkpoint "K-1 treatments" needs a review-side way to record a checkpoint for
  the approving person from a system applier (no `member_context` caller added); the rows carry
  the decision and their events, `checkpoint_id` stays null.
- The re-proposal raises its events and returns the row to Proposed; the TAX-06 issue for it
  needs a system issue path (review's `create_issue` from a system context), left with the
  checkpoint.
- Treatment facts and rationale come from the agent's `k1_treatments` mode (T-04-T38, S38).
- `POST …/treatment-runs` stays 501 until T-04-T38.

## Progress log
- `2026-11-12` — Built (S37). App import smoke and ruff clean; tests written, run at the end pass.
