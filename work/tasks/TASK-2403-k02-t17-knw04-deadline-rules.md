---
id: TASK-2403
title: K-02-T17 KNW-04 j Deadline rules section (DF-10, read-only)
spec: SPEC-000  # the backlog row; SPEC-500 and the KNW-04 contract
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: K-02
plan_key: K-02-T17
branch: s19-k02-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
KNW-04 j, Deadline rules (DF-10, composed from the T12 grammar, read-only): due-date rules,
holidays, postponements, 8879 form set and tolerances, information-return thresholds and retention
minimums, each with version, effective date and source.

Acceptance: "Each table shows its reference-set version, effective date and source, and no firm
role sees an edit control."

## Scope
**In**: `apps/web/src/screens/KNW-04/{deadline-rules.tsx,deadline-copy.ts}` and the section hook in
`index.tsx`; the route's section allowlist; reference-set fixtures (seed and handlers) and scenario
j (Grace Holloway); `knw04-deadline.test.tsx`; KNW-04 contract status; DEC-1453.
**Out**: DF-10 firm overrides (T-03); production sets (K-02-T20); parity, axe and journeys (K-02-T19).

## Plan
Separate files for the section and its copy, so K-02-T14's open KNW-04 work (#828) and this one
touch `index.tsx`, `scenarios.ts` and the fixtures scenario in a few lines only.
Migrations, registry, flags: none (`rules.reference_sets` exists). Tests: the six kinds in order;
version, effective date and source on each; resolved rows; no button or input for four roles.
Rollback: revert the PR.

1. [x] Fixtures. 2. [x] Section. 3. [x] Tests. 4. [ ] End review run.

## Progress log
- `2026-10-30` — Built on `s19-k02-t17` (build-only; tests run at the end review).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1453 | composed section j, read-only, fixtures cited "— verify" | no |

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** end review; merge after #828 or resolve its few-line overlap.
