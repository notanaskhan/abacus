---
id: TASK-2343
title: N-01-T29 without the pen test (legacy inbox retired, flag calendar) and the pen-test deferral record
spec: SPEC-330
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T29
branch: s18-n01-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Ayush deferred every penetration test (2026-11-01). Record that so later sprint sessions find it,
then build the part of N-01-T29 that needs no pen test.

Row acceptance: "No critical or high finding from delta #1 is open on Jul 9 and the legacy screens
are gone." The first half is deferred (DEC-1389); the second is built here.

## Plan
1. Deferral record: `docs/plan/status/pen-test-deferral.md`, DEC-1389, backlog `status:
   deferred` on the 48 rows deferred in full, a pointer row in AGENTS.md "Where things are".
2. Map every assertion of `legacy/spec023`, `spec033matching` and `spec033matcher` to the test
   that carries it (SPEC-330 §8); add a server test where none does (`inbox_file_gone`).
3. Retire `legacy/InboxPanel.tsx`, `InboxAIMatch.tsx`, `matchingMessages.ts` and those tests.
4. Calendar the four N-01 flags in `docs/plan/status/flag-renewals-2027.md` (DEC-1390).
5. N-01-T29 backlog status `partial`.

Red zone: deletes UI code only; no backend route, migration, flag or permission changes. Rollback:
revert the PR.

## Progress log
- `2026-11-01` — built. 123 backlog rows mention a pen test: 48 deferred in full, 39 built
  without their pen-test clause, the rest incidental. Go-live gates that need a closed test stay
  open (rule 4). InboxPanel had no route; one assertion lacked a server test, now added.

## Handoff
- **Current state:** PR open.
- **Exact next step:** merge with CI. Left of N-01-T29: findings (deferred), per-firm flips and
  flag retirement (need live firms).
