---
id: TASK-8013
title: "W-02-T24 part 1: independent AC and security tests for W-02-T03, T12 and T15"
spec: SPEC-653
acceptance_criteria: []
risk_zone: red
status: in-review
branch: w02-t24-independent-part1
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: W-02-T24
---

## Objective
The ADR-078 tests of notanaskhan's red W-02 work that is on main, written in ayushkbhatia's
session from SPEC-653 and the rows' acceptance: fail on any agent-actor approval, unverified
citation shown as fact, walled read or wrong attribution.

## Plan (red: written before the build)
1. [x] T03: no agent, system, support or portal principal holds a session or artifact-download action; the artifact routes answer 404 while `workbench.enabled` is off.
2. [x] T12: the assistant proposes only `files.propose_save`, holds no final verb, `client_data: none`, no `tri`; code refuses a turn claiming a human act and a plan naming the agent as approver.
3. [x] INV-2 through AgentBlocks: an unverified citation, a free number and an unregistered fact are refused before display.
4. [x] T15: a tool call on a walled client, by engagement or by client id, is `out_of_scope`; the read-only line is code's.
5. [ ] Part 2 (waits): T19 session plans and the per-item failure ledger, T20 run artifacts and drill (S43, #1953, #1956), T23 Save to Files (W-02-T23, waits on those), and `backend/tests/integration/agent_tests/test_workbench_journey.py` (J11 b1–b3, WB-02e, locked Copperleaf, wall on Northwind for Ana Cruz) with the F-04 invariant checker.

## Progress log
- `2026-11-14` — Part 1 built: `backend/tests/unit/workbench/test_w02t24_independent.py`. Not run (S44 end pass). The 404-while-off tests avoid asserting 501 so they stay true once W-02-T20 serves the routes.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
