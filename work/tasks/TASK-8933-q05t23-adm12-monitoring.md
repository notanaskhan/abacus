---
id: TASK-8933
title: "Q-05-T23: ADM-12 Monitoring & inspections a-g"
spec: SPEC-711
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s53-q05t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: Q-05-T23
---

## Objective
ADM-12 Monitoring & inspections (T1 in the T12 frame), artboards a-g. Acceptance: ADM-12a to g match at Tier C, the inspection columns sum to 1,104, and Decide on Dec 14, 2026 shows Concluded Dec 14, 2026 · Margaret Okonkwo.

## Done
- Quality reads gain additive fields (inspection engagement_line, signer, selected_because, concluded_on, findings; finding root_cause, remediation, evaluated_by, evaluated_on; evaluation as_of and input counts); client regenerated
- Seed fixtures/seed/adm12.ts with footings; scenarios a-g in fixtures/scenarios/ADM-12.ts
- screens/ADM-12 inside SettingsLayout: filters, tiles, inspection plan (1,104 px), findings queue and detail with actions, annual evaluation card, Select engagements and Record finding sheets, SHL-11 decision card
- Route /settings/monitoring behind quality.management with sheet, cycle and finding in the URL; links to and from ADM-01, ADM-05, ADM-08; tax rows open TAX-02
- 14 vitest tests (a-g, 1,104, objectivity, decide, loading, error, links) + 3 seed footings; e2e/screens/ADM-12.spec.ts
- Manifest path set, status planned (FIL-01 to ADM-12 needs a files QM-finding link kind; DEC-5935)

## Progress log
- `2026-11-23` — 2026-11-23: built in the S53 sequential run; backend practice unit tests pass (84); web targeted tests pass. Integration and e2e left for the end pass.
