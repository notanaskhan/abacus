---
id: TASK-1461
title: Typed proposal adapters for the live specialists (P-04-T25)
spec: SPEC-360
acceptance_criteria: [AC-5]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T25
branch: s12-review
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Project the screener's results, the upload reviewer's findings and the matcher's proposals as C3
proposals (`GET /v1/proposals/screening_result:<id>`, `upload_review:<id>`, `inbox_match:<id>`)
with verified citations, and map approve and reject onto the existing REVIEW-001 and inbox
decide paths. Hidden while the firm's agent stage is shadow. Acceptance: "Accepting a Granite
Peak screening flag through the proposal route writes the same review_decisions row AUD-03 writes
today, and a shadow-stage firm sees no proposal."

## Plan
- `agents/proposal_adapters.py`: parse the ref; read the typed row; 404 for a shadow run or a
  firm whose stage for that agent is shadow (synthetic firms have no stages); `proposal.read` on
  the engagement; rows and citations from C4 (`verified_citation_ids` on the row's anchor).
- Approve: screening result and upload review call `evidence.api.decide(..., "accept",
  seen_proposal=<the screener's latest result>)`, exactly the AUD-03 call (the evidence route's
  own matrix action and checks run inside); inbox match calls the inbox assign with the
  matcher's first shown proposal (`followed_suggestion`, source `matcher`, rank 1).
- Reject: evidence adapters send the file back with the reason mapped to a platform reason code
  (DEC-603); an inbox match rejection is recorded (audit only) and the file keeps waiting.
- The approve and reject routes take the same `ref` path parameter as the read (DEC-600).
- REVIEW-001 names `evidence/api.py` and `agents/proposal_adapters.py` beside the evidence
  routes (DEC-604).
- **Tests first**: `tests/integration/test_p04t25_proposal_adapters.py`.
- **Rollback**: revert.

## Progress log
- 2026-10-27: planned.
- 2026-10-27: built (acceptance tests first; run in the end-of-batch targeted pass). Claude Code restarted mid-build; the worktree was saved as WIP commit 743d43fa and the build resumed from it. Decisions DEC-600 to DEC-608; migrations 0230, 0231; SPEC-360 gains AC-4 to AC-7.
