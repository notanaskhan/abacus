---
id: TASK-8081
title: "T-07-T20: ADR-078 independent AC tests for T-07-T12, T14 and T16"
spec: SPEC-656
acceptance_criteria: [AC-0]
risk_zone: amber
status: in-review
branch: t07-t20-fiduciary-ac
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T20
---

## Objective
Independent AC tests from the spec and contracts, each with a seeded fault it must catch.

## Built
`tests/unit/tax/test_t07t20_fiduciary_ac_independent.py` (15 pass locally): I-AGENT-NEVER on the
reader tools and the fiduciary routes, uncited governed determinations refused, recompute
idempotent by `inputs_hash`, an edit moving the content hash (the L2 goes stale), walls 404, the
§7216 refusal before any model call, and the interpretation reviewable's L1/L3 split.

## Progress log
- `2026-11-15` — Built. Locked-determination immutability and end-to-end R-SO-3 (a preparer
  refused at L3) need the Postgres stack: they join the S46 integration pass with the T-07-T16
  version rows (`tests/integration`, end pass).
