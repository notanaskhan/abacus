---
id: TASK-8348
title: "W-01-T14: Agent dependency wired: requires_integrations on spec v2, run admission and the dependents provider"
spec: SPEC-659
acceptance_criteria: [AC-29, AC-30]
risk_zone: red
status: in-review
branch: w01-t14-admission-wiring
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T14
---

## Objective
Spec section: SPEC-659 AC-29, AC-30; W-01 §3 F5. Agent dependency wired: requires_integrations on spec v2, run admission and the dependents provider.

## Plan (red)
1. `AgentSpecV2.requires_integrations` (catalogue keys, at most 8).
2. `agents.run_start.open_capability_run` admits a run only when each required integration is connected for the firm (`integrations.api.admit`): 409 `integration_reauth_required`, `integration_unhealthy` or `integration_not_connected`, naming the key.
3. The agents module registers the dependents provider (`dependents_of`): the capabilities whose spec requires a key, WB-11's Agents using it.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5334). Lint, pyright clean; the app imports; regenerated. Partial: no capability spec declares an integration yet (the Season Progress Reporter's spec lands with its row); `record_run_failed` waits on a scheduled-run start path; a dependent shows its spec id until specs carry display names. Gates and
  tests run once at the S47 end pass (build first, test last).
