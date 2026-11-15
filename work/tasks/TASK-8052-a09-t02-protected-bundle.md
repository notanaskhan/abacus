---
id: TASK-8052
title: "A-09-T02: S45 group-audit protected bundle #1 (matrix rows, agent-never, protected paths)"
spec: SPEC-658
acceptance_criteria: [AC-0.1]
risk_zone: red
status: in-review
branch: a09-t02-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T02
---

## Objective
Per-module matrix rows for consolidation, eliminations, scoping, component auditors and the room,
with agent, support and portal deny on every firm write.

## Plan (red: written before the build)
1. **Protected** matrix files (new `ledger.yaml`; adjustments, assurance, portal, connections);
   regenerate `_matrix.py`, `actions.gen.ts`, security suites.
2. `abacus_tools/codegen/security_tests.py`: I-AGENT-NEVER entities and actions.
3. **Protected** `protected-paths.md`: consolidation compute and goldens.
Rollback: revert; no route uses the actions until A-09-T03.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029).
- `2026-11-15` — Built (DEC-5037). Codegen clean. Tests (regenerated suites) run at the end pass.
- **Needs:** Ayush's approval of the protected bundle (the plan's "AY's approval file").
