---
id: TASK-8344
title: "A-09-T18: AUD-32 bulk upload and pull-all (ConsolidationPullAll)"
spec: SPEC-658
acceptance_criteria: [AC-2]
risk_zone: amber
status: in-review
branch: a09-t18-bulk-pull
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-09-T18
---

## Objective
Spec section: SPEC-658 F2 (AC-2.1, AC-2.2); DV-1. AUD-32 bulk upload and pull-all (ConsolidationPullAll).

## Plan (amber)
1. Kernel slots beside connection coverage (`register_group_tb_sources`, `split_tb_by_subsidiary`, `pull_group_tbs`): connections registers its pure NetSuite splitter and the fake OneWorld pull, so assurance never imports connections (BOUND-002).
2. `assurance/group_pull.py`: bulk upload (the raw body; every subsidiary matched to an entity by its client entity's name first, else 422 `subsidiary_unknown` with its position, nothing stored; then one validated snapshot each attached to the current slot); `ConsolidationPullAll` (synthetic tenants only, DV-1; a refused token leaves the slot Needs reauth, never retried).
3. Ledger: `mark_slot_needs_reauth`; `ConsolidationFacts.missing()` counts a slot that cannot be read (Needs reauth) as missing, so finalize waits for it.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5329). Lint, pyright and the banned patterns clean; the app imports; client regenerated. Partial: A-02's reconnect request on Needs reauth; the live OneWorld connector (DV-1). Gates and
  tests run once at the S47 end pass (build first, test last).
