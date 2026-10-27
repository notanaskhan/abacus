---
id: TASK-1444
title: Scenario content wave 3 (P-07-T50)
spec: SPEC-307
acceptance_criteria: [AC-2, AC-3]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T50
branch: s11-assurance
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"The J19 and J02 fixtures load on staging and the import file reproduces 204 matched, 8 to review
and 0 new." Wave 3 of the Brightwater Hale content, through the services the loader already
calls (as P-07-T40 did), synthetic only.

## Plan
- **Holdout `thornbury_estate`** (`holdouts.py`, `scenario.build`): the Thornbury client in its
  earlier form, Walter Thornbury with his own entity only, so CLI-06 b's intake can add the
  estate under him (96% match). Events about the estate client are left out; an event can name
  the holdout it needs (`data["holdout"]`). The default scenario's hash is unchanged.
- **Slice `intake`** (`intake.py`; needs `people`, `acceptance`): Granite Peak's ENG-03 d draft and
  Fairhaven's ENG-03 a draft at step 1 (Margaret Okonkwo's, DEC-593), Samuel Ito's Harborline
  check over Walter Thornbury left open (CLI-06 h; only with the holdout), Meridian's CLI-07 f
  answers, Low rating, one Low flag and send to the partner. Loader: drafts may name their step,
  a check may leave its hits open, prepared answers and flags are per draft.
- **CCH client list** (`client_list.py`, `files/cch-axcess-client-list.csv`): 212 rows, no
  identifiers; 204 score at or above 90%, 8 between 60% and 90% (rows 7 and 8 among them), 0 below.
- **Tests**: `tests/unit/scenarios/test_intake_slice.py` (holdout, slice gating, the file equals
  its generator, the 204/8/0 count under a model of pg_trgm), `tests/integration/
  test_scenario_intake.py` (load with the holdout through the services, read back, the file
  scored in Postgres by `dedupe_candidates` as Grace, reload writes nothing).
- **Not here**: the staging load (no hosted database from a builder session); the CLI-06 g
  import itself (P-07-T52, S14: the parser, the review table and `ClientImportWorkflow`).
- **Rollback**: revert the commit; the slice and holdout are opt-in.

## Progress log
- 2026-10-27: planned and built; DEC-593.
