---
id: TASK-6715
title: "R-02-T22: anchored portal threads: client routes for page comments, approval questions and Ask the auditor over P-05's collaboration API, pins linked to comments and the lit line, comment column and 390 bottom sheet"
spec: SPEC-646
acceptance_criteria: [AC-31, AC-32, AC-33, AC-34]
risk_zone: amber
status: in-review
branch: s35-r02-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: R-02-T22
---

## Objective
Dana's page-2 comment reaches the firm and Hannah's shared reply shows on pin 1, and Victoria's question to the auditor is invisible to every other committee member.

## Plan (amber)
1. `collaboration/client_threads.py` (new; P-05's additive hook): `register_client_policy`
   (`anchor_readers` default, `author_only`), `post_client_comment` (client person only; the
   anchor must be `client_visible`; the thread opens `shared` on the engagement; text plain, sealed,
   1–4,000), `client_comments` (shared threads only; under `author_only` only the reader's own
   thread, whose locator carries the author). Repository reads `shared_threads_on_anchor` and
   `comments_of_threads` in LIST_EXEMPT with the reason (the provider proved the client's grant).
2. `portal/thread_anchors.py` (new): `client_approval_item`, `deliverable_version` (anchor = the
   deliverable, locator `{version, page, line_ref | x, y}`, x and y in ten-thousandths) and
   `governance_communication` (author-only), registered from `portal/api.py`. Client facts come
   from the portal reads that prove the grant (`approvals.approval`, `reporting.portal_deliverable`,
   `assurance.governance_communication_scope`) and a system read of the engagement's client.
3. New reads: `reporting.api.deliverable_scope`, `assurance.api.governance_communication_scope`,
   `engagements.api.client_of` exported.
4. Portal routes implemented: approval questions (GET/POST), page comments (GET/POST), private
   questions (GET/POST); 501 stays declared.
5. POR-09: pins on the page in reading order (keyboard buttons), the selected comment lit with the
   match tokens in the column and on the pin, a working composer with a line chooser ("Add a
   comment on this page"), and the 390 bottom sheet.
6. Tests: `tests/unit/collaboration/test_r02t22_client_threads.py`.

## Partial
- `statement_approvals` "commented" row (AUD-20's client comments list, AC-32):
  `reporting.api.apply_management_decision` does not exist on main; not built.
- Notification kinds `client_question_asked` and `tcwg_question_asked` are not added (the firm sees
  the comment on the anchor's thread; the bell entry waits on the kinds).
- POR-08 and POR-15 front ends already post to these routes (S33/S34); unchanged.

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass).
