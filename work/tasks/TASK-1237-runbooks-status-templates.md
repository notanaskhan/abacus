---
id: TASK-1237
title: R0 and R1 runbooks with the validate_docs runbook rules; status-page content and incident templates (Q-01-T21, Q-01-T40, Q-01-T42)
spec: SPEC-050
acceptance_criteria: [AC-29]
risk_zone: amber
status: done
epic: Q-01
plan_key: Q-01-T21; Q-01-T40; Q-01-T42
branch: s8b-platform-ops
created: 2026-10-25
updated: 2026-10-25
---

## Objective
SPEC-050 AC-29: each runbook in `docs/runbooks/<slug>.md` with `id`, `owner`, `alarms`, `last_rehearsed`; R0: RB-01, RB-02, RB-24; "an alarm without a runbook link fails `validate_docs`". Q-01-T40: RB-03, RB-06 to RB-12, RB-15, RB-20, RB-22, RB-23, RB-26 and RB-29 drafted; stubs RB-04, RB-05 (A-02), RB-13, RB-14 (Q-02), RB-16 (Q-04). Q-01-T42: status-page components from SHL-05, SEV1, SEV2 and maintenance templates naming no firm or client, portal maintenance-banner wording with no firm, client or product name, `docs/ops/incident-templates.md`.

## Plan (amber zone)
- **validate_docs:** `check_runbooks` (frontmatter on every `RB-<nn>-<slug>.md`) and `check_alarm_runbooks` (every `aws_cloudwatch_metric_alarm` and `aws_cloudwatch_composite_alarm` in `infra/` names an `RB-<nn>` that exists). Paths resolve from `REPO` at call time, so the test pack stays isolated.
- **Runbooks:** frontmatter plus ADR-098's table and eight sections; the commands are the ones built in this wave (`rollback.yml`, `deploy-staging.yml`, `make deploy-lock`, `abacus_tools.schedules`, `abacus_tools.drill`, `drill.yml`); switches not built yet (platform AI pause, read-only mode: Q-01-T36, T37) are named as not built. RB-31 gains frontmatter. The README index and template gain the frontmatter and the new states.
- **Status page:** `docs/ops/incident-templates.md`.
- **Tests:** `tests/unit/quality/test_validate_docs.py` (+9), `tests/unit/quality/test_incident_templates.py` (4).
- **Rollback:** revert; nothing at runtime depends on these files.

## Progress log
- 2026-10-25: built as planned. No alarm resource exists in `infra/` yet (Q-01-T25, T33 add them); the rule holds them from the first one. Tests: `test_validate_docs.py` 70 passed, `test_incident_templates.py` 4 passed; `validate_docs` clean on the repository.
- Human to-dos: rehearse RB-01, RB-02 and RB-24 on staging once it exists and record the dates (R0 acceptance); rehearse RB-10 (with the first drill) and RB-22 before Fri Dec 11; review `docs/ops/incident-templates.md` and load the components and templates into Better Stack by hand (Q-01-T41); A-02, Q-02 and Q-04 write their stubs.
