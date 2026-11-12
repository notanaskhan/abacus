---
id: TASK-7507
title: F-07-T25 additive C2 status rows for tier 4
plan_key: F-07-T25
spec: SPEC-652  # F-07 tier-4 templates, AC-6
acceptance_criteria: [AC-6]  # one additive status-vocabulary PR, make generate green, no kit-local draft status type
risk_zone: red
status: in-review
branch: f07-t25-c2-status-rows
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Add the tier-4 status rows C2 still lacks and remove the kit-local draft type.

## Plan
- Inventory (F-07-T01, `docs/design/tier4-inventory.md`): `workbench_session` and the K-1 package
  words ("Draft K-1 · pre-release", "Released {date}") were already in C2 (P-10, T-02); only
  `filing_deadline` was missing.
- `docs/product/status-vocabulary.yaml` (PROTECTED, additive): `filing_deadline` with overdue
  "Past due" (red), due_7 "Due this week" (red-tint), due_30 "Due this month" (amber), later
  "Upcoming" (neutral), done "Done" (green-tint, check), postponed "Postponed → {date}", extended
  "Extended to {date}"; every code derived, never stored.
- Regenerated `kernel/_statuses.py` and `packages/ui/src/status.gen.ts`
  (`abacus_tools.codegen.status_vocabulary`).
- Removed `packages/ui/src/tier4/draft-status.ts` (nothing imported it); SPEC-652 AC-6 types T13's
  chip tier as `RegistryCode<"filing_deadline">`; inventory and `tokens/DECISIONS.md` updated.
- Test: `packages/ui/src/status.f07t25.test.ts` (`satisfies` exhaustiveness, derived, no draft type).

## Partial
- The protected YAML carries the founders' approval (notanaskhan's codegen review in the plan);
  Ayush records it at the batch merge. The full `make generate` runs at the end pass.

## Progress log
- `2026-11-12` — Rows added and draft type removed (DEC-4507).
