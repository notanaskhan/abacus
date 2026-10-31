---
id: TASK-2433
title: "Q-03 catch-up lane: the ADR-078 suites DEC-1474 left owed (P-11-T09, T-02-T17, T-01-T18 approve path)"
spec: SPEC-000  # the backlog rows; ADR-078
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T121
branch: q03-owed-suites
worktree: /Users/ayushkbhatia/Accrued/abacus-s19-suites
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Write, in AY's session from the rows and contracts only, the independent AC suites DEC-1474 listed
as still owed for N's red and amber work of the period, and fix what they find.

Acceptance (Q-03-T121's): "No red or amber task of the period reaches its gate without an AC suite
by the other founder."

## Scope
**In**
- P-11-T09 (`record_generated`): `backend/tests/integration/test_p11t09_generated_independent.py`.
- T-02-T17 (duplicate-upload policy): `backend/tests/integration/backfill/test_t02t17_duplicates_independent.py`.
- T-01-T18 full approve path with a published BH-TAX-02: `backend/tests/integration/test_t01t18_approve_path_independent.py`.
- The fixes the suites found (DEC-1481): render retention, Keep newer, final approval's hash.

**Out**
- N-02-T18, T19, T20 and N-01-T17: DEC-1474 listed them as owed, but their independent suites
  are on main already: N-02-T22 (TASK-2232, DEC-1284; `test_n02t22_send_independent.py`,
  `test_n02t22_signatures_independent.py`) and N-01-T25 (TASK-2333, DEC-1379;
  `test_n01t25_flags_independent.py`). Nothing more is owed for them.
- The Sep 15 K-1 release snapshot in the Brightwater Hale slice (DEC-1477's "Not here").

## Plan (red)
- **Files:** the three suites above; `evidence/generated_copies.py` (`store_generated` takes the
  kind's record type and engagement), `reporting/render_job.py` (passes them),
  `evidence/retention.py` (`RECORD_TYPES` gains the two codes generated kinds register),
  `evidence/duplicates.py` (the resolution row records the voided and kept pair),
  `tax/approval.py` (the approve compares bare hashes).
- **Migrations / flags / registries:** none.
- **Rollback:** revert the PR; files rendered meanwhile keep their (longer) locks, which only
  ever extend.

## Definition of done
- [x] Each suite written from the row, with `# ac-test-author: ayushkbhatia`.
- [x] What a suite found is fixed and recorded (DEC-1481).
- [x] The suites and their neighbours pass; ruff, pyright, banned patterns.

## Progress log
- 2026-11-01: Checked DEC-1474's owed list against main; N-02-T18–T20 and N-01-T17 already have
  independent suites (N-02-T22, N-01-T25). Wrote the three suites still owed. The P-11-T09 suite
  found that the render job stored every file with the default lock and ignored the kind's
  `retention_record_type` (AC6.1); fixed (DEC-1481).
- 2026-11-01: End pass. The T-02-T17 suite found Keep newer always 500 (0468's two-version
  CHECK); the T-01-T18 suite found final approval impossible over HTTP (`sha256:` prefix against
  the checkpoint's bare hex). Both fixed (DEC-1481). Green: the three suites, the builders' suites
  for P-11-T09, P-11-T11, T-02-T17, T-02-T19 intake, T-01-T18, T-01-T25, Q-03-T121, and the
  retention suites.
