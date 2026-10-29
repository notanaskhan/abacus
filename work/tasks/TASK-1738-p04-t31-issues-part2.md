---
id: TASK-1738
title: P-04-T31 Issues service part 2
spec: SPEC-360
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T31
branch: s14-p04-t31
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Resolutions, fix instructions and send-to-client live. Acceptance (backlog row): "Ana Cruz's
Northwind issue creates one client-visible request item that carries only the client wording, and
no agent context can resolve any issue."

## Plan (red)
- `review/issue_resolutions.py`; routes in `review/contract.py`; `review.slots` fix runner
  returns the run id; `agents/issue_client_requests.py` registers the sender. C3 stub test marks
  the seven routes live. Error codes; audit actions reviewed. DEC-828.
- Rollback: flag `review.grammar_api` off; revert.

## Acceptance
| Check | Test |
|---|---|
| One item with only the client wording (replay safe) | `backend/tests/integration/backfill/test_p04t31_issues_part2.py::test_ac_one_request_item_with_only_the_client_wording` |
| No agent context can resolve any issue | `…::test_ac_no_agent_context_can_resolve_any_issue` |
| One step at a time; not applicable; fix runner fail-closed; G3 | four tests |

## Progress log
- `2026-10-28` — Built. ruff, pyright, lint-imports, banned patterns clean; `make regenerate`;
  error codes. Tests written, not run (end-of-batch review).

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** A-02-T30.
