---
id: TASK-3315
title: P-11-T28 synthetic scanned corpus generator and goldens
spec: SPEC-000  # row (P-11-T28)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T28
branch: s28-p11-t28
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"The generator is deterministic from a seed, every golden value foots to the Brightwater Hale figures, and test-only faces never ship in a production layout (DEC-78)."

## Plan
- `abacus_tools/synthetic/scanned_corpus.py`: eight faces, skew, noise, JPEG, phone perspective; `FakeOcr` recordings.
- `tests/golden/scanned_corpus.yaml`.
- Rollback: delete the module; nothing in `abacus` reads it.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2314
