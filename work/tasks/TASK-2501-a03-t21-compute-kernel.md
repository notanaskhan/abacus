---
id: TASK-2501
title: A-03-T21 compute kernel (kernel.numeric, kernel.calendar) and the compute import contract
spec: SPEC-580
acceptance_criteria: [AC-4, AC-5, AC-6]
risk_zone: red
status: done
epic: A-03
plan_key: A-03-T21
branch: s20-a03-t21
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The two kernel modules the import-linter compute contract names, which no epic created, and the
contract switched on (A-03 §4.1, §4.7; chapter 03 §10.1).

Acceptance (backlog row): "kernel.numeric and kernel.calendar exist on main before any compute
package imports them, allocate's properties pass, K-02's calendar goldens pass without edits, and
import-linter rejects any other import from sampling/compute or ledger/compute."

## Plan (red)
- `backend/src/abacus/kernel/numeric.py`: `PRECISION`, `CONTEXT` (28, ROUND_HALF_UP), `unit`,
  `quantize_half_up`, `allocate(total, weights, places, *, half_up_shares)` (largest remainder;
  the half-up override puts the residual on the largest weight).
- `backend/src/abacus/kernel/calendar.py`: `is_business_day`, `roll`, `add_business_days` moved
  verbatim from `practice/compute/calendar.py`, which re-exports them (`as` imports), so
  `practice.api.add_business_days` and the I-CLOCKS goldens are unchanged.
- `sampling/compute/__init__.py`, `ledger/compute/__init__.py`: the packages the contract names
  (import-linter needs them to exist; T04 and T08 fill them).
- `backend/pyproject.toml`: forbidden contract from both compute packages to every `abacus`
  package and `abacus_tools`, ignoring only the two kernel helpers and the package's own modules
  (`unmatched_ignore_imports_alerting = "none"` until the packages import them). A probe import of
  `kernel.clock` from `sampling/compute` broke the contract; `kernel.numeric` stayed allowed.
- Kernel README rows and section; protected-paths entry.
- Rollback: revert; `practice/compute/calendar.py` regains its three functions.

## Acceptance
| Check | Test |
|---|---|
| Context, quantize, allocate examples and refusals | `tests/unit/kernel/test_a03t21_numeric.py` |
| Every split foots (Hypothesis) | `tests/property/kernel/test_a03t21_allocate_properties.py` |
| Business days over a passed holiday set; practice re-imports | `tests/unit/kernel/test_a03t21_calendar.py`; K-02 `tests/unit/practice/test_k02t07_calendar.py` and the I-CLOCKS goldens unchanged |
| Contract configured; imports scanned | `tests/unit/kernel/test_a03t21_compute_contract.py`; `lint-imports` |

## Progress log
- 2026-10-30: built (S20 block; tests first, run at the end review). K-02's I-CLOCKS goldens are
  S18 #830 (open): the end review runs them on the merged branch. DEC-1551.
