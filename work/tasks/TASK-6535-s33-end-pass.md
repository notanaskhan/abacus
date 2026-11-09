---
id: TASK-6535
title: "S33 end pass: generate, gates, tests, security review, one fix round"
spec: SPEC-000
acceptance_criteria: [AC-1]  # every S33 PR's gates and tests pass together; one CI run
risk_zone: red
status: in-review
branch: s33-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: S33
---

## Objective
The S33 rows (#1531–#1565) pass every gate and test together; the sprint's one CI runs on this
PR, merged last.

## What changed
- `make generate`: no OpenAPI schema or operationId removed or duplicated.
- Gates: A-07-T31's archive records moved from evidence to assurance (`archive_records.py`;
  OWN-001: assurance owns `archives`); internals reached through `agents.api` (BOUND-001); role
  reads replaced with identity's `engagement_partners` / `firm_admins` (AUTHZ-001/002); CAST-001
  and ANY-001 comments; the kernel's stream deadline reads `kernel.clock`; the plan check's
  reserved verbs exempted from REVIEW-001 as a named scope; a glossary-banned name renamed;
  docs ids normalised; two secrets-scan false positives allowed with reasons; pyright 0; web tsc,
  eslint (routes load screens lazily), prettier; build and 96 bundle budgets.
- Security review (DEC-3135): `events_stream` claims its slot before registering the stream (a
  refused seventh stream leaked a registry entry per attempt); `change_topics` holds the open's
  100-topic cap for the stream's life.
- Escaped defect (Q-03-T223, found by P-11-T37's independent suite): `form_extraction` put the
  form type (a string) in an audit `Ref`, so every live extraction write raised; fixed.
- Tests: new POST routes classified; the new audited actions reviewed; `report_release` and
  `archive` targets owned, `realtime` firm-level; catalogue and worker handler sets; the
  independence marks; R-02-T14's two emails are registrations, not POR-20's designed six;
  ReleaseWorkflow's recorded history and replay test; 0760/0761 down-and-up integration test;
  POR-09's `circle` icon in the portal registry; AUD-29 and SHL-18 Links tables.
- Results: backend unit + workflows 45,320 passed; web 3,424 run (isolated reruns of load flakes
  pass); 0760/0761 round trip and tenant isolation for the 17 new tables pass.

## Progress log
- `2026-11-09` — Done locally. The A-06 render test needs weasyprint's native libraries (CI has
  them; run locally with a stub). Two identity `visible()` tests are order-sensitive on main.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3135 | The S33 end pass's ownership move, review fixes and escaped-defect fix | no |
