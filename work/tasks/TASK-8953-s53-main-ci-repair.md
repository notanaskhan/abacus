---
id: TASK-8953
title: "S53-CI: S53 main CI repair (run 45357043811)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-ci-repair
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-24
updated: 2026-11-24
plan_key: S53-CI
---

## Objective
Bring main green after the S53 batch: the failures CI found in the suites the end pass did not run.

## Done
- field_manifest written as SQL NULL (JSONB none_as_null; ED-328)
- TbHandoffPreviewOut rebuilt so its fields classify (ED-329)
- xdist_group marker registered for mutation runs (ED-330)
- connect catalogue reader carries detail_copy (W-01 AC suite)
- T-08 and T-06 consumer tests list S53's live operations; C21 13 standard kinds; posting-status scan allows C-02-T41's read; TIN scans hold the W-9 entry and its masked route
- status codes shadow (capability_run_outcome), offered and read_only (ledger_write_grant)
- form-face watermark golden reads glyphs in drawing order (75 golden_render passed in the image)

## Progress log
- `2026-11-24` — 2026-11-24: fixed; contracts 10,824, P-11-T15 40, W-01 and offshore suites, vocabulary 1,398 and the render goldens green locally.
