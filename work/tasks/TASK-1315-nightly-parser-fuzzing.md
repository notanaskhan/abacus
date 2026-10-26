---
id: TASK-1315
title: Nightly Hypothesis fuzzing of the import parsers (Q-03-T030)
spec: SPEC-045
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T030
branch: s10-q03-t030-fuzz
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Fuzz the TB and GL import parsers (five ledger formats), the XLSX request-list importer and PDF
extraction in its child process nightly within a 15-minute budget; a crash becomes a SEV3 ticket
with the minimised synthetic input committed as a regression case.

## Plan
- `backend/tests/property/fuzz/test_parsers.py`: one Hypothesis property per target (`TARGETS`):
  structure-aware rows from each format's own header labels (CSV, or XLSX via openpyxl), raw
  bytes, mutated seed PDF. Only `NormaliseError` / `RequestListInvalid` may escape; extraction
  never raises; the isolated child never returns `crashed`. `test_regressions` replays
  `regressions/<target>/*.bin` (seeded with empty and header-only cases).
- `conftest.py`: `ci` (default, derandomised, 40 examples) and `nightly` profiles, picked by
  `ABACUS_FUZZ_PROFILE`.
- `.github/workflows/fuzz-nightly.yml`: nightly cron, `timeout --signal=INT 15m`, verdict from the
  junit report, artifact with the log and Hypothesis database, `gh issue create` SEV3 on a crash
  (`issues: write` only; no secrets).
- `docs/ops/fuzzing.md`: the runbook.
- No production code, no migration, no flag. Rollback: revert.
- Unverifiable from the repo: 14 green nights before M6 (counted from the job summaries).

## Progress log
- 2026-10-26: built (build-first; the targeted test pass and gates at the end of the run).
