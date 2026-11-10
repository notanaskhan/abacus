---
id: TASK-6229
title: R-02-T09 close, POR-09's "In Sign" rows from C7's envelopes
spec: SPEC-646
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: R-02
plan_key: R-02-T09
branch: s31c-r02-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (amber)
- `signatures/signer_facts.portal_envelopes`: the person's own envelopes on a work item.
- `signatures/api.py` registers it with `reporting.api.register_envelope_rows`.
- No migration.
- Test: `tests/unit/signatures/test_r02t09_portal_envelopes.py`.

## Left
- "Coming next" waits for engagement milestones (no provider exists).

## Progress log
- 2026-11-08: built; runs at the close end pass.
