---
id: TASK-8086
title: "A-08-T12: JE test service (je_testing migration, scoring workflow, selection)"
spec: SPEC-657
acceptance_criteria: [F1, F3, AC-1.1, AC-1.2, AC-1.4]
risk_zone: amber
status: in-review
branch: a08-t12-je-test-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T12
---

## Objective
Journal entry testing over a GL population proved complete by code: the firm's criteria, code's
scores with reason codes, and a selection drawn as a sample-set version (AUD-12, JE variant).

## Plan (amber)
- Migration `0895_je_testing` (expand only): `je_tests`, insert-only `je_test_criteria`,
  `je_posting_user_roles` (sealed name + SHA-256), `je_score_runs`, `je_scores`; constraint swaps:
  `sample_set_versions.method` + `je_score_selection`, `monetary_unit`; `sample_items.selection_reason`
  + `risk_score`, `unpredictable`; `threshold_policies.kind` + `je_risk_criteria`,
  `mus_confidence_factors`. Down swaps back and drops the five tables.
- Methodology: `JeRiskCriteriaPayload`, `MusConfidenceFactorsPayload`, `je_risk_criteria_version`.
- Sampling: `je_repository`, `je_tests` (service), `JeScoringWorkflow` (batch queue) and its
  activities, `compute/je_selection.py` (frozen `je_select/1.0`), `je_draw` (the
  `SampleDrawWorkflow` branch for `je_score_selection`); routes served in `fieldwork_contract`.
- Rollback: revert the PR; `alembic downgrade 0894`.

## Built
- The tie re-reads from the snapshot's balances (a snapshot exists only after `validate_gl`
  proved it); scoring refuses `population_not_tied`, `criteria_required`, `je_test_busy`.
- Criteria copy the policy version with overrides into a new configured version; `post_close`
  without `through` takes the test's post-close date; the engine validates the parameters.
- Posting users match by SHA-256 of the case-folded name; names are sealed (`seal`, AAD
  `sampling.je_posting_user`), never logged.
- Scoring stores the run (engine version, inputs hash, entries, unique flagged, hits) and every
  entry's score, reason codes, criteria mask, date, amount, account last 4 and description.
- Entries page by score then reference (keyset cursor), filter by criterion and by selected.
- Selection: `je_select/1.0` takes the by-score part (floor and/or count; a zero score never) and
  the seeded unpredictable picks (the one random primitive) from the rest; it writes a population
  of the scored entries with the JE tie, a sample set (first time), a `drawing` version with the
  seed and sampler version, and dispatches `SampleDrawWorkflow`, whose `run_draw` re-runs the
  selection and refuses on any hash difference.
- Tests: `tests/unit/sampling/test_a08t12_je_tests.py`, `tests/golden/scenario/test_a08t12_je_selection.py`
  (Granite Peak 34 + 6 = 40, 18 pass with the unit file); `tests/integration/test_a08t12_je_testing.py`
  (Postgres; runs in the end pass).

## Partial
- AC-1.2's timing (412,903 lines within 10 minutes) is a staging run: not measurable here.
- Workflow history recording for `je_scoring` (recorder) joins the end pass.
- Protected path: `sampling/compute/je_selection.py` is under the protected sampler library
  (ADR-340) and needs the human approval recorded for protected changes.

## Progress log
- `2026-11-15` — Built (DEC-5068).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5068 | JE selection is a frozen sampler version over the scored run, drawn by `SampleDrawWorkflow`; zero scores never by score; unpredictable from the rest by reference order | no (ADR P-57 covers it) |
