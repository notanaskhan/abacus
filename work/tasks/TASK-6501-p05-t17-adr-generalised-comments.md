---
id: TASK-6501
title: "P-05-T17: ADR P-42 Generalised comments drafted (ADR-236; plan alias ADR-209)"
spec: SPEC-000  # ADR draft; P-05-T01 writes the SPEC
acceptance_criteria: [AC-1]  # ADR records append-only Resolve and Reopen, Correct and Redact, version-pinned anchors
risk_zone: red
status: in-review
branch: s33-p05-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-05-T17
---

## Objective
Draft ADR P-42 from chapter 09 P-42, DEC-29 and DF-18 so P-05-T01's gate check can read it.

## Plan
1. [x] Read P-05 §0.1, §3.3, §4.2 and §11.2 OQ-6, chapter 09 P-42, DEC-29, DF-18, ADR-109 and SPEC-032 Q7.
2. [x] Take the next free ADR number (`docs/adr/backlog.md`: plan numbers are aliases): ADR-236.
3. [x] Write `docs/adr/ADR-236-generalised-comments.md`, the README index row and the backlog row.

## Progress log
- `2026-11-09` — ADR-236 drafted, status `proposed` with ayushkbhatia as decider. The row's
  acceptance ("Accepted on origin/main") is not met: red ADRs never default on silence (DEC-3016's
  rule), so acceptance is Ayush's. OQ-6 is answered in the ADR (decision 3: `pin` vs `follow`).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3101 | P-42 takes ADR-236, drafted as proposed; S33's P-05 rows build only reversible dark work until acceptance | yes (this one) |
