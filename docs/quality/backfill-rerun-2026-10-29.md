# Back-fill re-run, 2026-10-29 (Q-03-T059)

The 44 back-filled suites (tranche 0 and S6 to S11) re-run on `main` against the final
MVP contracts. A red task needs a defect in `escaped-defects.md` with an owner.

| TASK | Spec | Suites | Result | Failing |
|---|---|---|---|---|
| 075 | SPEC-036 | 2 | green | — |
| 049 | SPEC-026 | 2 | green | — |
| 025 | SPEC-010 | 1 | green | — |
| 021 | SPEC-006 | 4 | green | — |
| 022 | SPEC-007 | 3 | green | — |
| 019 | SPEC-004 | 5 | green | — |
| 029 | SPEC-014 | 2 | green | — |
| 027 | SPEC-012 | 9 | green | — |
| 020 | SPEC-005 | 4 | green | — |
| 041 | SPEC-024 | 2 | green | — |
| 045 | SPEC-025 | 1 | green | — |
| 030 | SPEC-015 | 1 | green | — |
| 032 | SPEC-017 | 2 | green | — |
| 040 | SPEC-024 | 2 | green | — |
| 044 | SPEC-025 | 3 | green | — |
| 035 | SPEC-020 | 2 | green | — |
| 056 | SPEC-029 | 2 | green | — |
| 054 | SPEC-029 | 2 | green | — |
| 055 | SPEC-029 | 2 | green | — |
| 036 | SPEC-020 | 1 | green | — |
| 052 | SPEC-028 | 1 | green | — |
| 069 | SPEC-034 | 1 | green | — |
| 048 | SPEC-025 | 2 | green | — |
| 038 | SPEC-022 | 1 | green | — |
| 068 | SPEC-028 | 1 | green | — |
| 070 | SPEC-034 | 2 | green | — |
| 071 | SPEC-034 | 1 | green | — |
| 050 | SPEC-027 | 1 | green | — |
| 051 | SPEC-027 | 3 | green | — |
| 058 | SPEC-030 | 2 | green | — |
| 059 | SPEC-030 | 3 | green | — |
| 065 | SPEC-033 | 1 | green | — |
| 066 | SPEC-033 | 1 | green | — |
| 064 | SPEC-033 | 1 | green | — |
| 062 | SPEC-032 | 1 | green | — |
| 072 | SPEC-035 | 1 | green | — |
| 073 | SPEC-035 | 1 | green | — |
| 074 | SPEC-035 | 1 | green | — |
| 033 | SPEC-018 | 1 | green | — |
| 037 | SPEC-021 | 1 | green | — |
| 039 | SPEC-023 | 1 | green | — |
| 060 | SPEC-031 | 1 | green | — |
| 024 | SPEC-009 | 1 | green | — |
| 026 | SPEC-011 | 1 | green | — |

**44 of 44 green.**

## The run

On the S12 batch's combined tree (`main` 90a04405 with the seven S12r branches, #610, #613, #616,
#617, #618, #620, #621), 2026-10-29, `make backfill-rerun`, one pytest invocation per folder:

| Folder | Result |
|---|---|
| `tests/integration` | 68 passed |
| `tests/integration/backfill` | 452 passed |
| `tests/integration/backfill` (agent support suites) | 627 passed, 1 error |
| `tests/security` | 29 passed |
| `tests/unit` | 13,721 passed |
| web (vitest, the four `legacy/` suites) | 34 passed |

**Triage.**
- `backfill/test_q03t032_upload_reviewer.py::test_ac7_a_review_takes_no_action_on_the_evidence`
  errored at setup (500 `internal error`, a `DBAPIError`). Re-run alone: 36 of 36 passed. The
  builder switched the worktree's branch for a few seconds during this folder's run, which also
  removed the runner's JUnit folder; transient, not a defect.
- TASK-059 AC-10's suite, `legacy/spec030review.test.tsx`, was retired with the legacy AI review
  panel (#464, DEC-442); its assertions are carried by SHL-20 and AUD-03 (SPEC-330 §8). The tracker
  row now names them; they pass (56 of 56). Spec drift in the tracker, not a defect.
- The runner now reads each folder's JUnit file as that folder finishes, so a lost file can no
  longer stop the report (it did on this run, after every suite had finished).

No defect is open from the re-run: all 44 suites are green, so Q-03-T059's acceptance is met.
