---
id: TASK-3003
title: N-04-T04 notices compute library
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T04
branch: s25-n04-t04 (stacked on s25-n04-t03)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
- **[AC-1]** "Goldens for Whitley (3,120; 686.40; 753.01), Collins and Santos pass, and the library
  imports nothing beyond the kernel numeric and calendar packages."

## Plan (amber)
- `notices/compute/`: `stamp`, `notice_types` (+ `notice_types.yaml`), `risk`, `plausibility`,
  `underreporter`, `bracket` (+ `rate_schedules/ty2023..2025.yaml`), `balance_due`, `payments`,
  `clocks`.
- `pyproject.toml` import-linter: `notices.compute` joins the compute-only contract.
- CPA memo `docs/quality/golden-reviews/notices@1.md` (requested).
- Rollback: revert; nothing reads it until N-04-T11.

## Acceptance
| Check | Test |
|---|---|
| Whitley, Collins, Santos goldens | `tests/unit/notices/test_n04t04_compute_goldens.py::test_ac_*` |
| Imports only kernel numeric and calendar | import-linter contract; `test_the_library_imports_only_*` |
| Purity and idempotence | `test_property_*`, `test_same_inputs_same_stamp_*` |

## Progress log
- 2026-11-02: built; goldens checked by hand (22,798.00 / 23,484.40 / 686.40 / 753.01 / Nov 16). Tests at the S25 end review.

## Decisions made during this task
DEC-2053.
