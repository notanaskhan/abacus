---
id: TASK-1296
title: AUD-03 Remind and third-party wiring to P-06 follow-ups and delegation; legacy redirect (A-01-T16)
spec: SPEC-330
acceptance_criteria: [AC-24]
risk_zone: green
status: in-review
epic: A-01
plan_key: A-01-T16
branch: s9c-aud03-pbc
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Wire AUD-03's "Remind…" (header and the requested row's "Remind") to P-06's follow-ups v2
(`POST /v1/follow-ups/drafts {request_item_ids}`, FollowUpSheet, a person sends after the 10-s
Undo), the card's "Draft follow-up" to the screening return (DEC-368, through
ScreeningCardHost), and "Request from third party…" to P-06's delegate endpoint
(`POST …/request-items/{id}/delegate {contact_id}`, the #418 third-party room). Redirect the
legacy `/engagements/$id/requests` to `/audits/$auditId/source-documents` when `audits.cockpit`
is on and the engagement has an assurance work item.

## Plan
- Header "Remind…": every open request; the row "Remind": the open requests owed by the same
  person (Dana's 5). Both through `useFollowUps` / `FollowUpSheet` (no new code path).
- "Request from third party…": a Dialog over `GET …/client-contacts` (third-party roles), the
  delegate mutation, gated on `request_item.delegate` (senior and above, C5).
- Legacy redirect in `routes/firm/engagements.tsx` (`/requests`): reads `…/work-items`.
- **Out of scope locally:** the staging fixture-to-live swap and the M6 journey step on staging
  (Fri Mar 5): no hosted environment is touched from this worktree.

## Tests
In `screens/AUD-03/AUD-03.test.tsx` ("A-01 Story 4.1", "third party") and the redirect test.

## Rollback
Revert the commit; the board route renders the legacy board again.

## Progress log
- 2026-10-26: Remind (header and row), screening return (via ScreeningCardHost), third-party
  delegation and the legacy redirect built and tested in AUD-03.test.tsx (Story 4.1, delegate,
  redirect). The staging swap and the M6 journey step remain (hosted). DEC-422.
