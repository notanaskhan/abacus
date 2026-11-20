---
id: TASK-8854
title: "K-03-T10: TV-1 and SH-1 consumer contract tests"
spec: SPEC-720
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s52-k03t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: K-03-T10
---

## Objective
Pin the C22 TV-1 and C23 SH-1 contracts from both sides before T11/T12 implement them.

## Done
- Every TV-1 and SH-1 operation carries its matrix action and a 501
- Every write is denied to agent and system; publish and import need fresh MFA
- Models carry the fields KNW-06, KNW-07, SHL-22, SHT-01..04 read
- Fixture half: all 41 artboards served; 3,698,700.00, 31+8+1+0=40, Added 3 · Changed 5 · Removed 0 foot

## Progress log
- `2026-11-20` — 2026-11-20: built; 74 pytest + 7 vitest pass (focused). DEC-5851.
