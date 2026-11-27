---
id: TASK-9005
title: "T-08-T30: Amendments service"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-t08-t30-amendments
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: T-08-T30
---

## Objective
Okafor's 1040-X foots to (2,708), refund 2,708 and IL (495), the original is never written, and it reads Superseded only after the amendment's ack.

## Done
- tax/compute/amendment.py: 1040-X and IL-1040-X lines, total change, refund or balance (pure)
- tax/amendments.py: create from an accepted return with its approved checkpoint as the baseline, read, Part II versions, route for approval (C16 to the signer), supersession on the amendment's accepted federal ack
- routes: create, read (federal, il), explanation (If-Match), routing (additive)
- engagements.create_work_item gains authorised_under (amendment.create)
- tax return insert carries amends_return_id (migration 1033 grants INSERT; ED-348)
- tests: 4 unit (Okafor numbers), 2 integration (row acceptance end to end; only an accepted return; walls)
- DEC-6011

## Progress log
- `2026-11-26` — Built; tests green. T-08-T33 adds the amended-return eligibility in tax/approval.py; T34 the agent's draft.
