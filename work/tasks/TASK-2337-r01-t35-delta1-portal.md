---
id: TASK-2337
title: R-01-T35 pen-test delta #1 readiness for client-facing portal flows
spec: SPEC-380
acceptance_criteria: [AC-22]  # the task row's acceptance, quoted under Objective (R-01 has no SPEC AC for it)
risk_zone: red
status: in-review
epic: R-01
plan_key: R-01-T35
branch: s18-r01-t35
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"Pen-test delta #1 readiness for client-facing portal flows: threat model for drops, the third-party
room, preview-as and templates (IDOR across scopes and tenants, hostile file names, drop-batch replay,
lint bypass, header injection in From and Reply-To); WAF size rule on the drop route; rate limits;
scope-letter rows." Acceptance: "The tester receives the threat model with the scope letter by Fri
Jun 18, 2027 and the four surfaces are live on the production-equivalent build."

## Plan
Stacked on N-01-T24 (#924: the WAF file-route rules). `infra/modules/waf/variables.tf` adds
`portal/binders/[^/]+/drops$` to the file routes (rule 21 exemption, rule 3 rate, rule 22 size cap);
`infra/tests/test_upload_edge.py` cases; `docs/ops/pentests/2027-06-delta-1-portal.md`. Rollback:
revert.

## Progress log
- `2026-10-31` — built. Found: the drop route (raw body) was blocked at the edge over 8 KB. Infra
  tests pass. Apply, build pin and letter are the builder's. `[skip ci]`.

## Handoff
- **Current state:** PR open (stacked on #924), held for the batch.
- **Exact next step:** P-04-T46.
