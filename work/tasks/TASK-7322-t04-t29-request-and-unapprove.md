---
id: TASK-7322
title: "T-04-T29 rest: Request final approval to BH-TAX-02's signer; Unapprove any live approval at the viewer's level"
spec: SPEC-649
acceptance_criteria: [AC-2]  # §3.2 detail and manager review: Unapprove and the final-approval request
risk_zone: amber
status: in-review
branch: s37-t04t29-approvals
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T29
---

## Objective
Two of TASK-6828's flagged gaps, as code: the live "Request final approval…" (it "waits on SHL-12
h's assignee picker"), and Unapprove limited to approvals made in the same session ("the tree
carries no approval id").

## Plan (amber)
- Backend `tax/review_tree.py`: `_LIVE_IDS` (each version's latest unreversed approval at a level,
  `DISTINCT ON`), `Doc.approval_id`, and `Summary.final_approver_user_id`. The last calls
  `approval.signer_for` on the engagement's client, and only when the viewer holds
  `tax_return.request_approval`.
- Contract `tax/workspace_contract.py`: `ReviewDocumentOut.approval_id` and
  `WorkspaceSummaryOut.final_approver_user_id` (both optional, Internal). The generated client is
  regenerated. No migration, no flag, no new route.
- Web `TAX-04/live.tsx`: Unapprove on the tree's `approval_id`. Request final approval… appears
  when nothing is left to review and the viewer may request it. It is disabled while the K-1 is a
  draft or no signer is named, and a ConfirmDialog names the level and the assignee before posting.
- Rollback: revert the PR. The fields are optional, so older clients ignore them.

## Built (DEC-4320)
- No assignee picker: BH-TAX-02 names the partner, and `approval.approve` accepts only that person.
  The handoff (TAX-05 e: "→ SHL-12 with level Partner, assignee Daniel Reyes") shows that same
  person, preset.
- Tests:
  - `tests/unit/tax/test_t04t29_unapprove_and_request.py`: the tree's approval id at the shown
    level, and the signer named only to a requester.
  - `tests/integration/test_t04t29_live_approval_ids.py`: the query on Postgres (the latest
    unreversed approval; a reversed one or another level names nothing).
  - `apps/web/src/screens/TAX-04/live.test.tsx`, seven new cases: Unapprove reaches another
    session's approval and is hidden without the action; the request names the signer and posts
    on confirm; it is disabled for a draft K-1 or no signer; a 409 renders in words; it is hidden
    without the action or while a document needs review.

## Partial
- The staging walk-through (no staging).
- TAX-04's leadsheet, links and K-1 matrix routes still answer 501. They belong to T-04-T22 and
  later rows.
- Artboard parity belongs to T-04-T47.

## Progress log
- `2026-11-12` — Built (S37 follow-ups).
