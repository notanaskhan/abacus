---
id: TASK-7323
title: "T-04-T37 rest: TAX-08's live drawer on the return-bound sessions; the workspace's real assistant availability"
spec: SPEC-649
acceptance_criteria: [AC-6, AC-11]  # §3.6 Assistant; §3.11 consent and agents-off
risk_zone: amber
status: in-review
branch: s37-tax08-live
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T37
---

## Objective
TASK-7317's flagged gap: "TAX-08's host wiring to these routes and the session stream (T-04-T34's
drawer) lands with the T-04-T29 swap." On a live build, `?ov=assistant` toggled but drew nothing,
and the workspace summary always answered `assistant: "agents_off"`, so the Assistant chip never
showed.

## Plan (amber)
- Backend `tax/review_tree.py`: `Summary.assistant` from `agents.api.capability_ready(ctx,
  engagement, "tax.assistant")`.
  - Ready reads `available`.
  - `consent_7216` reads `consent_required`: the chip shows and the drawer says why.
  - `paused` and `ai_policy_off` read `agents_off`: the chip is hidden.
  - Every other reason reads `ai_unavailable`.
  - The contract passes it through instead of the constant.
- Web `screens/TAX-08/live.tsx`, `AssistantLive`: the O2 drawer (420, peek).
  - Availability first. `consent_required` shows SPEC-649 AC-6.8's words and opens nothing.
  - A new thread offers the three prompts. The first ask creates the session
    (`subject_ref: tax_return`) and posts the message with an Idempotency-Key.
  - History lists the person's threads on the return.
  - The thread is the snapshot, polled at 1.5 s while a turn runs (the session stream answers 501
    until P-10-T26).
  - Items render through AgentBlocks and AgentText. An open question takes the next message as
    its answer (`answers_seq`).
  - A plan opens its child run in RunPane, where the person approves it. No control in the drawer
    approves.
- Route `routes/firm/tax-review.tsx`: the drawer on `?ov=assistant` in a live build only.
- Rollback: revert. The summary goes back to the constant and the route draws nothing again.

## Built
- Tests:
  - `tests/unit/tax/test_t04t29_unapprove_and_request.py`: seven reason-to-word cases on the
    summary.
  - `apps/web/src/screens/TAX-08/live.test.tsx`, six cases:
    - no consent: the words, and no session;
    - paused: the words, and no write;
    - a prompt creates the bound session and posts with an Idempotency-Key, and the thread
      renders;
    - a 409 on create names the reason and posts nothing;
    - History lists the threads with the subject query, and an open question takes the answer;
    - a plan opens the run pane, with no approve in the drawer.

## Partial
- No session stream: snapshots are polled until P-10-T26 builds `GET …/sessions/{id}/events`.
- AC-6.3 to AC-6.5's inline ApprovalCard (Approve adjustments, Edit…, Reject…, Undo) for the child
  run's proposal is not drawn in the drawer. The proposal reaches SHL-10 through the run's plan and
  the review's checkpoint path. Drawing it inline needs a read of a run's proposals by session.
- "Request consent…" (AC-6.8) needs T-01's consent-request flow from this surface. Not built.
- Copy: "Open plan", "Back to the thread" and "No threads on this return yet." are new words, not
  from the handoff (TAX-08 has no plan or history artboard). `agents_off` uses ADM-04's "Paused
  for the whole firm", and the other reasons use TAX-08's "This return isn't available."
- Real-model runs (T-04-T43) and Bedrock clearance are unchanged.

## Progress log
- `2026-11-12` — Built (S37 follow-ups).
