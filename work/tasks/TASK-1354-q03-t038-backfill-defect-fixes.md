---
id: TASK-1354
title: S9-S10 back-fill defect fixes for the agent, comments and guidance suites (Q-03-T038)
spec: SPEC-319
acceptance_criteria: [AC-16, AC-19, AC-20]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T038
branch: s10c-red
created: 2026-10-27
updated: 2026-10-27
---

## Objective
No agent back-fill failure is open at the S11 Contract Monday.

## What is open
- The S9 and S10 back-fill suites for the agent (`test_q03t031_engagement_agent.py`), the upload
  reviewer (`test_q03t032_upload_reviewer.py`), the matcher (`test_q03t033_matcher.py`), comments
  and the drafter (`test_q03t039_comments_and_drafter.py`) and drafted guidance
  (`test_q03t040_drafted_guidance.py`) hold no strict xfail and recorded no escaped defect
  (TASK-1282, 1283, 1284, 1308, 1309: "no defect").
- The agent-side failures still held are the follow-up drafter's, recorded by P-06-T23's
  independent suite (TASK-1280) against `agents/follow_up_drafts.py` and the human-only guard:
  **ED-081** (a `system` actor may write `follow_up.sent`) and **ED-082** (an empty selection
  answers 500 `authz.unchecked_route`), five strict xfails in
  `backfill/test_p06t23_follow_ups_v2_independent.py`.

## Plan
- **ED-082**: `requests.api.selection_engagements(ctx, binder_ids, item_ids)` returns the
  engagements of the selected binders and requests the caller may read (`visible()`) and whether
  every selected binder was readable. The route runs `check_draft_selection` first (404 for an
  unreadable binder or a request selection none of which is readable, else `follow_up.draft` on
  each engagement); `draft_for` authorises on the readable engagements before reading what is
  open, so a direct call over an unreadable binder still drafts nothing (P-06-T14's
  `test_ac16_a_walled_or_unreadable_binder_drafts_nothing`, which the first cut broke).
- **ED-081**: migration **0197** `follow_up_sent_person_only` redefines
  `audit_events_human_only()`: `follow_up.sent` is refused from any actor but a person; every
  other human-only action keeps 0097's agent-or-policy rule (DEC-452).
- Remove each xfail only when its test passes unchanged; record both fixes against their ED rows.
- **Rollback**: revert; 0197's downgrade restores 0097's function body.

## Progress log
- 2026-10-27: planned and built (S10 wave C).
- 2026-10-27: targeted pass: the first cut raised 404 inside `draft_for`, which broke P-06-T14's
  service-level test; the 404 moved to the route's check. Both suites pass.
