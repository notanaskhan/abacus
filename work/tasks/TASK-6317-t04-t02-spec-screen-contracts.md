---
id: TASK-6317
title: T-04-T02 SPEC-649 and screen contracts for TAX-04 to TAX-08, TXI-01 to TXI-03
spec: SPEC-649
acceptance_criteria: [AC-1]  # 71 ACs adopted from T-04 §3; 52 artboards, 50 in scope
risk_zone: green
status: done
epic: T-04
plan_key: T-04-T02
branch: s32-t04-t02
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
The spec of record and eight screen contracts.

## Progress log
- `2026-11-09` — `docs/specs/SPEC-649-t04-return-review-workspace.md` (71 ACs across 13 stories,
  verbatim from T-04 §3) and `docs/screens/{TAX-04..08,TXI-01..03}.md` (52 artboards, TAX-08 g and h
  deferred to W-03). The validator (`validate_docs`) runs at the end pass. The handoff SHA in each
  contract is left for the screen rows that build them.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| — | The spec adopts the epic's ACs verbatim rather than restating them | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status done.
