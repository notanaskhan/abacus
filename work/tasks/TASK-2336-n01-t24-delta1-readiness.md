---
id: TASK-2336
title: N-01-T24 pen-test delta #1 readiness for the inbox and portal intake
spec: SPEC-380
acceptance_criteria: [AC-22]  # SPEC-380 AC-22 (walls 404) and the task row, quoted under Objective
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T24
branch: s18-n01-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"Pen-test delta #1 readiness for the inbox and portal intake (Jun 21 – Jul 2): threat model
(hostile files, zip bombs, polyglots, file-name injection, IDOR across clients and tenants, cursor
tampering, intake-scope escalation), WAF size rule on upload routes, rate limits, security dashboard
signals, scope letter rows." Acceptance: "The inbox and portal intake are on the production-equivalent
build by Fri Jun 18 with the threat model attached to the tester's scope."

## Plan
Red zone (edge rules). Files: `infra/modules/waf/{main,variables}.tf` (rule 3 upload rate, rule 22
upload size cap by Content-Length, `upload_path_regex` widened to every file route),
`infra/tests/test_upload_edge.py` (offline), `docs/ops/pentests/2027-06-delta-1-inbox-intake.md`
(scope-letter rows, threat model, dashboard signals, human steps). No migration, registry or flag
change. Rollback: revert; the WAF reverts on the next apply.

## Progress log
- `2026-10-31` — built. Found: rule 21 blocked every raw-body file route not named `…upload`
  (staff-logged intake files, engine, standards, questionnaire, report-template and envelope
  imports) over 8 KB; fixed with the widened exemption. Infra tests 199 pass. Apply, build pin and
  scope letter are the builder's. `[skip ci]`.

## Handoff
- **Current state:** PR open, held for the batch.
- **Exact next step:** R-01-T35.
