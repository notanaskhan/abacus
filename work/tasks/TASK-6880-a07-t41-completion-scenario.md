---
id: TASK-6880
title: "A-07-T41 follow-up: no audit reference carries text (completion projector, subsequent events) and a static scan"
spec: SPEC-000  # row (A-07-T41)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-07
plan_key: A-07-T41
branch: s36p-a07-t41
worktree: /Users/ayushkbhatia/Accrued/abacus-s34-merge
created: 2026-11-11
updated: 2026-11-11
---

## Objective
"make seed-demo and fixture mode show identical AUD-18 to AUD-25 data and the scenario writes only
through service APIs."

## What this is
The slice is S35's `archive` slice (#1669, TASK-6735, DEC-3302); its end pass (#1678) fixed the
EQR checklist provider and the text in the EQR, rep-letter and release audit references. Found by
the same walk and not on main: four more records put text in a `Ref`, which the kernel refuses at
runtime (a 500): `subsequent_events` (a procedure's status and date, a not-applicable item, a
request) and `completion_projector`'s not-applicable item. Now integers (0/1 for a state,
yyyymmdd for a date). It is the second time text reached a `Ref` (S34's S2 was the first), so
`tests/unit/kernel/test_ref_values_static.py` scans `src/abacus` for the two shapes that are
always text: a non-fingerprint string literal and a date's `.isoformat()` (the AGENTS "mistake
twice" rule).

## Progress log
- 2026-11-11: built; rebased onto S35 round 2 (ed2995a11), keeping only what main lacks.
