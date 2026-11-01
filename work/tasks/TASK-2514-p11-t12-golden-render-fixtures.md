---
id: TASK-2514
title: P-11-T12 Golden render fixtures (Brightwater Hale ENG-04 b/d/e/f, AUD-21 a, AUD-22 a, AUD-23 a, NOT-03 a, AR-C 70 package)
spec: SPEC-520  # AC-6, AC-11, AC-20
acceptance_criteria: [AC-6, AC-11, AC-20]
risk_zone: amber
status: done
epic: P-11
plan_key: P-11-T12
branch: s20b-p11-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Golden render fixtures written by the non-implementer: Brightwater Hale snapshots for ENG-04 b,
d, e and f, AUD-21 a, AUD-22 a, AUD-23 a, NOT-03 a and an AR-C 70 package, each with expected
SHA-256 for PDF and DOCX and extracted text equal to the DocBlock text.

Acceptance (backlog row): "Every fixture re-renders byte-identical, extracted text equals block
text, and the AR-C 70 legend is present on every package page."

## Plan (amber)
- `backend/tests/golden_render/p11t12_fixtures.py`: nine renderer inputs, wording from the handoff
  specs (ENG-04, AUD-21, AUD-22, AUD-23, NOT-03, CLS-08). Test data only: nothing in `abacus`.
- `render_fixtures.py` prints the hashes; `two_containers.sh` renders them in two fresh
  containers, compares, records `p11t12.sha256` with `RECORD_GOLDEN=1`, then runs the suite.
- `test_p11t12_golden_fixtures.py` (image-bound, as AC-30's): byte-identical rerender, recorded
  hashes, PDF and DOCX text equal to the block text, the legend on every package page.
- No migration, registry or flag edit. Rollback: delete the four files.

## Decisions
DEC-1562.

## Progress log
- `2026-10-31` — Built on `s20b-p11-t12` off main 7d4def8e5. Recorded in two fresh containers of
  the backend test image (same bytes); `tests/golden_render/test_p11t12_golden_fixtures.py`
  38 passed in the image.
