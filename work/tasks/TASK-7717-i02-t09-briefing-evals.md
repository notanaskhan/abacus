---
id: TASK-7717
title: I-02-T09 evals/briefing_today (cases, graders, frozen thresholds, calibration set)
plan_key: I-02-T09
spec: SPEC-654
acceptance_criteria: [AC-6.1]
risk_zone: amber
status: in-review
branch: i02-t09-briefing-evals
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
The frozen suite `briefing.today` must pass before its prompt, with graders, adversarial and
seeded cases and the judge's calibration set; ten Today turns in the workbench suite.

## Built
- `abacus_tools/evals/briefing_today.py`, CLI hook, `evals/briefing_today/suite.yaml` (46 pass,
  8 seeded, 30 calibration); `evals/workbench_assistant/suite.yaml` + 10 cases.
- Authoring check: the fake-model run passes (all graders covered by a seeded case).
- Tests: `backend/tests/unit/briefing/test_i02t09_briefing_suite.py`.

## Partial
- Calibration labels are AY's on this run (26 of 30 agree); the prioritisation judge's model
  runs with I-02-T08 and real routes after clearance.
- The ten workbench Today turns mirror the read-only shape; Today-specific tool calls land with
  the ask binding (W-02-T15).
- Found while authoring: the frozen workbench suite records `assurance.read_materiality(
  engagement_id, version)`, `workpapers.read_section(workpaper_id, section)`, `binders.read(
  tax_year, binder_ids, cursor)` and `tax.season_counts(tax_year, group_by, status_in)`; W-02-T11's
  tools take other inputs. Aligned in the end-pass fix round.

## Progress log
- 2026-11-13: built; suite authoring run green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4720 | graders, thresholds and the case set | no |
