---
id: TASK-7729
title: Q-03-T277 and T278 S41 generator-coverage gaps
plan_key: Q-03-T277
spec: SPEC-000  # ADR-080; Q-03 §E
acceptance_criteria: [AC-1]  # every new table and condition kind has generated tests; every gap closed by a test
risk_zone: red
status: in-review
branch: q03-t277-generated-gaps
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Run the generator-coverage audit over S41's code and close every gap (T277's audit part, T278).

## Plan (red)
- Regenerate `backend/tests/security/{test_tenant_isolation,test_route_introspection,
  test_fresh_mfa_generated}.py` (`python -m abacus_tools.codegen.security_tests`).
- Rollback: revert; the generated files go back to the pre-S41 sets.

## Partial
- The compliance invariant catalogue run and the ADR-093 reliability follow-ups: the S41 end pass.
- DAST, Inspector and GuardDuty triage: staging and AWS (human; DEC-1389).

## Progress log
- 2026-11-13: audit 2 isolation gaps → 0 after regeneration; quarantine 0. Tests not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4732 | gaps closed by regeneration; runs and scans placed | no |
