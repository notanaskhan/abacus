---
id: TASK-1464
title: Independent AC tests (ADR-078) for review notes, bulk sign-off, decision cards, proposals, the adapters and the notification kinds (P-04-T28)
spec: SPEC-360
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T28
test_author: ayushkbhatia
test_session: 2026-10-27, branch s12-review (worktree abacus-s12-review), a clean session following .claude/skills/ac-test-author
branch: s12-review
created: 2026-10-27
updated: 2026-10-27
---

## Objective
P-04-T28's acceptance: "Tests written in ayushkbhatia's session pass and fail if an agent context
can decide a card or approve a proposal." Black-box at `create_app()` over HTTP (and the public
`agents.api` / `review.api` services where no route exists: raising a card, creating a proposal or
suggestion, the registration slots), written from SPEC-360, `docs/contracts/review-grammar.md`
(C3 v1, with the security-review paragraph of DEC-609), the matrix rows, SPEC-036 AC-5, ADR-005
and ADR-078. Covers P-04-T21, T22, T23 (#477) and T24, T25, T26 (this branch).

## Files
- `backend/tests/integration/backfill/p04t28_support.py`: the cast, the agent on a recorded run,
  C4 citations, outbox delivery, and a field owner, reviewable and decision kind registered
  through the public slots (codes `indep_*`).
- `backend/tests/integration/backfill/test_p04t28_proposals_independent.py` (AC-4, AC-5, INV-1).
- `backend/tests/integration/backfill/test_p04t28_decisions_notes_independent.py` (AC-1, AC-2,
  AC-3, AC-6, INV-1).
- No production code, migration, matrix or generated file. Rollback: delete the three files.

## Coverage per AC
- **AC-1 notes:** `test_ac1_two_open_notes_block_l2_and_clearing_both_lets_the_same_reviewer_sign`,
  `..._bodies_are_sealed_lists_carry_none_and_a_body_read_is_an_access_event`,
  `..._only_the_raiser_withdraws_...`, `..._raising_needs_a_registered_reviewable_...`,
  `..._review_note_raised_reaches_the_assignee_else_the_preparers_walls_rechecked`,
  `..._walls_and_other_firms_read_no_note`: pass.
- **AC-2 bulk:** `test_ac2_six_workpapers_three_ineligible_and_a_replay_returns_the_stored_result`
  (3 signed, `not_prepared`, `open_review_notes`, `content_changed`; replay identical, nothing
  signed again; another body 422 `idempotency_key_reused`), `test_ac2_reviewers_only_fresh_mfa_
  never_the_preparer_and_a_hidden_target_says_nothing` (staff 403, stale factor 403
  `mfa_required {max_age_s: 900}`, one target twice 422, the preparer gets `segregation`, a hidden
  and an unknown target both `level_not_permitted`, only hidden 403): pass.
- **AC-3 cards:** only Margaret decides (Hannah, Priya, Samuel, Kevin 403; no `decision.decide` in
  their `allowed_actions`), 422 `rationale_required`, 422 `decision_invalid`, stale factor 403,
  `recommendation_changed` after a reassessment, 409 `decision_card_state` on a second decide,
  reassessment v3 No change with `{benchmark 16861000, materiality 252900, difference 700}` by
  the reserved person only, the agent raises only in scope and on its own engagement, walls and
  other firms 404: pass.
- **AC-4 proposals:** the unsupported row (422 `uncited_change {count 1, row 5}`, then approve with
  edits), "Proposal approved by Samuel Ito" with one field version per row, citation re-check (a
  citation withdrawn after create; a citation on another engagement), uncited ids dropped from an
  edited row's field version, stale and replayed approval 409 `proposal_changed {version}`, reject
  reason codes, sealed follow-up with `Idempotency-Key` replay and reuse, 503 with no owner, the
  server's threshold (403 `{routed_to}`, also with edits; re-checked on edited values), routing
  to oneself, to a reviewer, to the run's preparer or around the named approver refused, the
  preparer never approves, `proposal_routed` once to the approver, suggestions adopt / edit /
  dismiss / `suggestion_changed` / a change set's row only with its proposal, roles the matrix
  denies, walls / non-member / offshore (DEC-319) / other firms, a target on another engagement
  never written: pass, except the two holds below.
- **AC-5 adapters:** reject maps `unsupported_value` to `does_not_agree`, a typed approve takes no
  edits, a shadow run's newer screening result never supersedes the live one and is 404, shadow
  stage and walls 404, an inbox-match rejection persists (reads `rejected`, second verdict 409,
  file keeps `waiting`): pass.
- **AC-6 kinds:** `review_note_raised`, `decision_assigned`, `proposal_routed` fan out once per
  recipient from the product's own outbox rows, delivered twice, walls re-checked: pass.
- **INV-1:** the matrix refuses agent and system every verdict even with the action in
  `task_scope`; `agents.api` and `review.api` export no verdict; the data layer refuses a state
  move written as the agent or the platform, and the human-only audit list refuses the verdicts'
  audit actions written as the agent: pass. These are the tests that fail if an agent context
  can decide a card or approve a proposal.

## Strict xfails (defects held, `open` in `docs/quality/escaped-defects.md`)
- **ED-170** `test_ac4_no_owner_answers_the_fixed_code_service_unavailable`: with no owner to
  write a row, approve answers 503 `{"detail": "service unavailable"}`; contract §6 part 2 fixes
  `{"detail": "service_unavailable"}` (status and "nothing written" pass in their own test).
- **ED-171** `test_ac4_a_shadow_runs_generic_proposal_is_invisible` and
  `test_ac4_a_shadow_stage_firm_sees_no_generic_proposal`: a generic proposal created by a shadow
  run, or in a firm whose stage for the agent is shadow, is served 200 with `proposal.approve` in
  `allowed_actions`. SPEC-036 AC-5 hides every firm-facing read of a shadow run, proposals named;
  DEC-608 implemented it for the typed adapters only.

## Spec drift and readings (DEC-550)
- 409 `recommendation_changed` carries `facts: {version_no}`; contract §6 shows no facts. Additive;
  the test asserts the detail.
- Follow-up now needs `Idempotency-Key` (DEC-609); §2's table row does not show the header yet.
- The raise response is the note detail (with its body), so the raiser's own read may be an
  access event; the suite asserts the list reads none and each other reader's detail read is one.
- A same-firm member with no role on the engagement: the contract fixes 404 only for walls and
  other firms, so the suite accepts 403 or 404 and asserts no content leaks and nothing is written.
- The 1.5% reassessment figure 252,900 is the contract's (SHL-11 d), from the provider; 1.5% of
  16,861,000 is 252,915 before the firm's rounding, so the test provider states the contract's
  figures rather than computing them.

## Progress log
- 2026-10-27: suites written from SPEC-360, C3 v1 and the matrix; adapted mid-session to the
  security-review fixes landing in the same worktree (server-side `ThresholdPolicy`,
  `engagement_of` on the suggestion slots, follow-up idempotency); DEC-609 was the builder's, so
  this task records DEC-550. Targeted pass and gates at the end; ED-170, ED-171 held as strict
  xfails.
