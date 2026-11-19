---
id: TASK-8715
title: "Q-05-T08: Quality dashboard with component health from signals"
spec: SPEC-711
acceptance_criteria: [AC-1, AC-2]
risk_zone: amber
status: in-review
branch: q05-t08-dashboard
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T08
---

## Objective
GET /v1/quality/dashboard: tiles (objectives at risk of all, open findings, the override rate from Q-05-T07's projection with its tolerance, open consultations, days to the evaluation date) and the six components' health from an owner flag or registered signals (independence gaps → ethical requirements, agents over tolerance → engagement performance, overdue remediation → the finding's component); an office narrows the rate only.

## Plan (amber)
1. practice/compute/quality_dashboard.py (pure) and practice/quality_dashboard.py (read; register_quality_signal for independence gaps and open consultations).
2. quality_contract: the dashboard route calls it.
3. Tests: tests/unit/practice/test_q05t08_dashboard.py (92 days to Dec 15 on Sep 14, 2026).

## Progress log
- `2026-11-19` — Built; tests pass (3). Not built: register and cycle import (dry run, publish), the risk-assessment review record, AgentMonitoringWorkflow (nightly deduplicated QM-F findings; the 0963 partial unique index dedupes), finding-due and evaluation-due notifications; accuracy reads null until Q-05-T07's accuracy projection; the independence-gap and consultations signal readers register with their owners (G-02, Q-05-T09). Gates and tests run once at the S51 end pass (build first, test last).
