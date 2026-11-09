---
id: TASK-6303
title: P-10-T23 independent AC tests for gateway v2 (T12, T13, T19, T21)
spec: SPEC-647  # AC-G1 to AC-G7; ADR-234
acceptance_criteria: [AC-G1, AC-G2, AC-G3, AC-G4, AC-G5, AC-G6, AC-G7]
risk_zone: red
status: done
epic: P-10
plan_key: P-10-T23
branch: s32-p10-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
ADR-078 suite that fails if `converse()` skips the boundary or `call()` output changes.

## Plan
`tests/integration/agent_tests/test_p10t23_gateway_v2_independent.py`, from SPEC-647 §3.1 and
ADR-234: every refusal reason before a provider call (malformed turn, `consent_7216` from a real
unconsented taxpayer, unresolved taxpayer, `pii_in_context`, budget, `ai_paused`); one row and one
`model.called` per attempt with the step; inputs by hash only; client content only inside
`<untrusted>` blocks through context v2; `call()`'s v1 signature, output and record (no v2
columns); no streaming on the seam or in the gateway source. No production code.

## Progress log
- `2026-11-09` — Written; not run (S32 end pass). The ADR-078 "other founder's session" clause
  drops under the solo rules: the suite is written from the spec, not the code.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3003 | What "call() output unchanged" and "no token streaming" assert | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status done.
