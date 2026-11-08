---
id: TASK-6218
title: R-02-T10 independent AC tests for R-02-T07's serving
spec: SPEC-R02
acceptance_criteria: [AC-38, AC-39, AC-40, AC-41]
risk_zone: red
status: in-review
epic: R-02
plan_key: R-02-T10
branch: s31-r02-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (red: written before building)
- One file, tests only, headed `ac-test-author: ayushkbhatia` (ADR-078):
  `tests/unit/evidence/test_r02t10_serving_independent.py`. It covers:
  - the link's 60-second life is the database's, bound to its tenant and person;
  - the URL is the API's own route, never an object key;
  - the audience refusals, including roles that never read and governance rooms;
  - no unwatermarked draft is served, page or file;
  - a page view writes exactly one access row;
  - anyone but a client person reads 404.
- Rollback: delete the file. T07's own DB suite (`test_r02t07_download_links.py`) stays.

## Progress log
- 2026-11-08: written; runs at the S31 end pass.
