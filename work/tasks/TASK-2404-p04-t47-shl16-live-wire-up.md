---
id: TASK-2404
title: P-04-T47 SHL-16 live wire-up for the tax pilot (import checkpoints, Out of sync, j06 coordination)
spec: SPEC-000  # the backlog row; SPEC-360 and the SHL-16 handoff
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: P-04
plan_key: P-04-T47
branch: s19-p04-t47
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
SHL-16 live wire-up for the tax pilot: import checkpoints from the T-01 file bridge, the Out of
sync chip, and the j06 coordination step (CCH import diff approved by Samuel Ito).

Acceptance: "j06 coordination passes on staging with the import checkpoint pending until Samuel Ito
approves it, ready for the Jul 27 shadow."

## Scope
**In (built from main)**: the import-author variant (ia, ib, ie); the record refetch on a decision
so the sync chip reads "Out of sync"; `TAX-02:j06` and the J06 coordination step in the fixture
project; tests.
**Out (waits)**: the staging walk, which needs T-01-T19/T22 (held #837, #835) to create the import
checkpoint; the Jul 27 shadow.

## Plan
Files: `screens/SHL-16/{index.tsx,shl16-import.test.tsx,SHL-16.test.tsx}`,
`domain/review/checkpoints.ts`, `fixtures/seed/review.ts`, `fixtures/scenarios/{SHL-16,TAX-02}.ts`,
`fixtures/screen-scenarios.ts`, `e2e/journeys/J06-individual-1040.spec.ts`, DEC-1454.
Migrations, registry, flags: none. Rollback: revert the PR.

1. [x] Import fixtures and author line. 2. [x] Refetch on decision. 3. [x] j06 scenario and step.
4. [x] Tests. 5. [ ] End review run. 6. [ ] Staging walk after the T-01 bridge merges.

## Progress log
- `2026-10-30` — Built on `s19-p04-t47` (build-only; tests run at the end review).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1454 | import author line, record refetch by id, fixture-half j06 | no |

## Handoff
- **Current state:** fixture half built, PR open, held for the batch.
- **Exact next step:** end review; the staging walk once #837/#835 are live.
