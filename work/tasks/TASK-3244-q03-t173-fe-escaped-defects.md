---
id: TASK-3244
title: Q-03-T173 Front-end escaped-defect fix-forward 2027 Q4 (S26)
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: Q-03
plan_key: Q-03-T173
branch: s26b-q03-t173
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3244 · Q-03-T173 · Front-end escaped defects, S26

## Done
- `docs/quality/escaped-defects.md`: ED-322 (BND-03/TAX-13 screen-contract links, caught by `link-contract.test.ts`) and ED-323 (AUD-08's Edit adopting the model's text as a person's edit, caught by the ADR-065 lint rule), each with its fix and the layer that missed it.
- ED-323's recurrence test: `AUD-08.test.tsx` "f: Edit opens the host's editor and never adopts the model's text" (passes).
- ED-322's test is the existing link-contract rule 5 (passes since the fix).

## Progress log
- 2026-11-03: AUD-08 suite 10 passed.
