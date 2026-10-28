---
id: TASK-1807
title: Source-assisted security review of the binder export (A-01-T32)
spec: docs/contracts/engagement-export-v1.md
acceptance_criteria: [A-01-T32]
risk_zone: red
status: in-review
epic: A-01
plan_key: A-01-T32
branch: s13r-a01-t32
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Review the export routes, `EngagementExportWorkflow` and the package builder by a non-author session: authz and walls, not_offshore, fresh MFA, Range, path and zip-slip, formula injection, expiry and voiding; file findings; ask Q-03 to add the routes to delta #1.

## Plan
- `docs/ops/pentests/2027-04-binder-export-review.md` (results only), linked from the pentests README.
- No code change: two findings, low and info, proposed accepted-risk.

## Progress log
- 2026-10-28: review written. Open human steps: both founders sign the findings off before Tue Jun 1, 2027; Q-03 adds the routes to the delta #1 scope letter.
