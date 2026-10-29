---
id: TASK-2030
title: Q-03-T084 Pilot 0 top-10 usability defects fixed before M9 (PW0 exit)
spec: SPEC-341
acceptance_criteria: [AC-50]
risk_zone: green
status: blocked
epic: Q-03
plan_key: Q-03-T084
branch: s15c-q03-t084
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The ten issues in F-09's Pilot 0 log closed (defects fixed) or re-filed against an owning epic
(capabilities, to its cut list) before Tue Jun 1, 2027.

## State on 2026-10-30
**Blocked on Pilot 0 itself.** No Pilot 0 session has run (the PW0 window is Jan 11 – May 28, 2027
on the plan's calendar); there is no usability log, no issue and no `pilot-0` label in the
repository, so there are no defects to fix. Nothing is invented.

## Built so far (so the acceptance can be checked the day the findings exist)
- `docs/ops/pilot/pilot-0-usability-log.md`: the top-10 table (issue, pilot code, screen, state,
  severity, owning epic, kind, status, resolution) and its rules: pilot codes only, defects fixed
  with a test, capabilities re-filed to the epic's cut list, all resolved before M9.
- `.github/ISSUE_TEMPLATE/pilot-usability.yml`: the finding form F-09 files from (G3's fields, a
  no-names warning, defect versus capability).
- `abacus_tools.quality.pilot_log`: the shape check in `make check-fast`; `--exit` is the
  acceptance (ten rows, none open; an empty log fails it).
- SPEC-341 AC-50; tests in `backend/tests/unit/quality/test_pilot_log.py` (run at the end review).

## To finish (after the Pilot 0 sessions)
1. F-09 files findings with the form; the human creates the `pilot-0` label (the form applies it).
2. F-09 fills the ten rows by the exit review (Fri May 14, T121).
3. Each defect: a fix PR with the screen-state or journey test that would have caught it; the row
   becomes `closed` with that PR. Each capability: `re-filed` with the cut-list issue.
4. `python -m abacus_tools.quality.pilot_log --exit` passes before Tue Jun 1, 2027.

## Progress log
- 2026-10-30: log, form, checker and AC built; the defect work waits for Pilot 0.
