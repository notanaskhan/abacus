---
id: TASK-8733
title: "Q-05-T08: Agent monitoring nightly run, QM notices, dashboard signal readers"
spec: SPEC-711
acceptance_criteria: [AC-1, AC-2, AC-5]
risk_zone: amber
status: in-review
branch: s51p-q05-t08-monitoring
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T08
---

## Objective
Finish Q-05-T08 (TASK-8715): AgentMonitoringWorkflow nightly raises one open QM finding per cycle and agent above tolerance (system-raised, deduplicated by 0963's partial index), sends qm_finding.due and qm_evaluation.due, and ADM-11's independence-gap and open-consultations signals read from their owners, walls applied.

## Plan (amber)
1. practice/agent_monitoring.py (monitor per firm, sweep behind quality.management, activity practice.agent_monitoring_sweep, QmFindingDue/QmEvaluationDue events); practice/workflows.AgentMonitoringWorkflow; daily Schedule agent_monitoring:platform in practice/jobs.
2. identity annual_independence.annual_gaps → identity api annual_independence_gaps; assurance consultations_log.open_count(viewer) → assurance api consultations_open_count (counted through the walled log).
3. practice/quality_dashboard: signals take the viewer; dashboard(ctx, …); both signals registered; MODULE_DEPENDENCIES practice += assurance and the import-linter contract adds assurance to the modules that may not import practice.
4. Replay history agent-monitoring-v1-swept.json (record_s51_monitoring) and replay test; unit test test_q05t08_monitoring.py.

## Progress log
- `2026-11-19` — Built. Not built: the register and cycle import (dry run, publish with fresh MFA) and the risk-assessment review record (DV-7) — routes stay 501; firm content goes in through that import, not a seed. Gates and tests run once at the S51 end pass (build first, test last).
