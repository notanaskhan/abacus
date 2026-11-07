---
id: TASK-6011
title: "I-01-T23 the tax export gate: a final-approved return waiting for its engine export"
spec: SPEC-000  # row (I-01-T23)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: I-01
plan_key: I-01-T23
branch: s29l-i01-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
Every subkind registered by Fri Dec 10, 2027 renders on HOME-01 and HOME-02, and no I-01 flag stays live into the Jan 1, 2028 window.

## Plan
tax/gate_sources.py: subject `tax_return_export`, kind `send`, read `tax_return.read`, events `tax_return.approved` and `engine_sync.exported`; open while a return is `final_approved` and no engine export was generated since its last final approval; presenter titles "Export the <form> · TY<year> to the tax engine" and opens TAX-02. Registered from tax/api.py; both events join C13_EVENTS (and the pinned C13 list); HOME's GATE_SUBKIND_TITLE gains the words; test_home_gate_subkinds covers it. Rollback: revert.

## Progress log
- 2026-11-07: built. tests/unit/test_home_gate_subkinds.py and tests/contracts/review_grammar/test_c13_human_gates.py pass (23); both queries EXPLAINed on a freshly migrated database (one wrong column caught: engine_exports.generated_at). Web tsc clean.

## Decisions made during this task
DEC-2609
