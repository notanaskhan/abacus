---
id: TASK-2033
title: Q-04-T018 Onboarding rehearsal, part AY (content through the firm's screens)
spec: SPEC-402
acceptance_criteria: [AC-3]
risk_zone: amber
status: blocked
epic: Q-04
plan_key: Q-04-T018
branch: s15c-q04-t018
created: 2026-10-30
updated: 2026-10-30
---

## Objective
200 synthetic clients through CLI-06 g, a PBC template through the KNW-01 importer, POR-20
templates published (l), ADM-10 pending DNS to published (d to f); every step timed through its
screen, each defect filed against its owning epic.

## Plan (amber: written before the code)
- `abacus_tools.synthetic.onboarding_files`: the run's inputs, deterministic, to a scratch folder
  (never committed): a CCH-headed 200-client CSV (synthetic names, `example.test` mail, no TIN
  column, `--near` rows for the review step) and a Workbook v2 PBC template; a manifest of hashes.
- `docs/ops/rehearsals/onboarding-content-part-ay.md`: the eight timed steps with their screen
  states, the run log, and where the timings go in `pilot-onboarding.md`.
- SPEC-402 AC-3; tests `backend/tests/unit/tools/test_onboarding_files.py` (run at the end review).
- Rollback: delete the generator and the record.

## Blocked on
- Q-04-T016 (part N): the rehearsal firm provisioned on staging and at `LEVEL=shadow`.
- ADM-10 steps 7 and 8: live sender domains (R-01-T27; the route answered 501 when the kit was
  written).
The run itself is a person walking staging's screens with a clock; it is recorded in the file
above when it happens.

## Progress log
- 2026-10-30: generator, rehearsal record, AC and tests built; the run waits on part N and R-01-T27.
