---
id: TASK-8075
title: "lo45 end pass: gates, suites, review and fix round over the S43/S44 partials batch"
spec: SPEC-655
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: lo45-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: LO45-END
---

## Suites (2026-11-15, under the test lock)
- `make check-fast`: green.
- `tests/unit`: 54,462 passed. Its 6 failures came from this batch (expectations and catalogue
  lists) and are fixed. 12 tests need WeasyPrint's native library, which this machine lacks; CI
  runs them.
- Web vitest: 4,156 passed. UI vitest: 1,440 passed.
- Contracts, acceptance, workflows, golden and security: 26,476 passed.
- Integration (J08 and the 316 tests touching the changed modules): 29 failures, now all fixed.

## Found (DEC-5061)
- **Main has been broken since S45:** C-01-T15's close plan gate named `close_plan.publish` as its
  read action. C13 filters with `visible()`, which takes reads only, so every HOME-02 list answered
  500 (28 of the 29). It now reads `close_plan.read`. `register_gate_source` refuses a non-read
  read action at startup, with a unit test.
- J08 part 2's K-1 expectation was wrong: none exist at 9:52, because Run 3 writes them.

## Security review
All of this batch's red changes are reviewed:
- C-01-T02's condition (`staff_function_in`) and the `has_conditions` fail-open fix.
- W-02-T23's edit validator: it runs before any write, and the name guard refuses paths.
- T-07-T03's gate and kinds: identifiers and the form only, and walls apply at fan-out.
Nothing open.
