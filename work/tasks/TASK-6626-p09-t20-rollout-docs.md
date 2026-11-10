---
id: TASK-6626
title: "P-09-T20: agent dock and trace rollout and docs (folds in Q-04-T130)"
spec: SPEC-648
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s34-p09-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-09-T20
---

## Objective
The runbook is rehearsed, both flags expire outside the Jan 1 – Apr 20 window, and the canary flip
request is filed with both founders as approvers.

## Plan (amber)
1. `docs/runbooks/RB-69-agent-dock-and-trace-degraded.md`: detect, triage, contain (per-firm flags),
   recover, verify; the dashboard's panels.
2. The two signals as OTel metrics in `agents/runs_routes.py`: `abacus.agent_run.items_polls`
   (counter: state, empty) and `abacus.agent_run.trace_latency` (histogram).
3. Flag renewal (Q-04-T130): booked in `docs/plan/status/flag-renewals-2027.md`; no YAML change
   (DEC-3212).
4. Canary flip request: `docs/ops/windows/2028-03-14-agent-dock-canary.md` (both founders, written
   rollback).
5. `docs/architecture/reference/ai-agent.md` "Showing a run"; `.claude/skills/ai-agent` note.
Rollback: revert the commit; the metrics carry no data a person reads.

## Progress log
- 2026-11-10: built.
- Partial (by rule, S34.md): the staging rehearsal of RB-69 and the canary flip itself need staging
  and a live firm; the dashboard is a definition in RB-69 until `infra/modules/observability`
  (Q-01, a skeleton today) can carry it, so RB-69 lists no alarms yet.
- Both flags already expire outside the window (2027-05-07); the acceptance's flag clause holds
  without a change.
