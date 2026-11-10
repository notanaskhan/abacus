---
id: TASK-6606
title: "P-10-T31: Independent AC tests for the spec v2, tool registry, first tools and harness (T20, T22, T25, T28)"
spec: SPEC-647
acceptance_criteria: [AC-R1, AC-R2, AC-R3, AC-R4, AC-R5, AC-R6, AC-R8]
risk_zone: red
status: in-review
branch: s34-p10-t31
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T31
---

## Objective
Tests pass and fail if a tool can read outside client_scope or a never-tool verb can be
registered.

## Plan (red)
1. `backend/tests/unit/agents/test_p10t31_tools_independent.py`: every first tool (T28) called with
   Granite Peak's ids answers `out_of_scope` before authorisation; a walled client answers
   `not_visible`; every never verb is refused as a name and as an action for read, compute and
   propose, by `validate_tool` and `register_tool`; no registered tool holds a human-only action
   or an `agent: deny` action; consent before a TRI read; `<untrusted>` wrapping a client's text
   that tries to close the block; a loop spec without tool-call limits does not load.
2. No production code. Rollback: delete the file.

## Progress log
- `2026-11-10` — Written from SPEC-647, C17 and the T28 row (solo independence, DEC-3201's
  reading). Not run (end pass). The harness half (T25: repair once, then escalate, AC-G4) has
  its own suite in `test_p10t25_harness.py`; this suite covers the tool calls it makes.
