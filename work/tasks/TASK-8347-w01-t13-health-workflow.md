---
id: TASK-8347
title: "W-01-T13: IntegrationHealthWorkflow: the 15-minute probe and the firm admins' Needs reauth notification"
spec: SPEC-659
acceptance_criteria: [AC-27, AC-28]
risk_zone: red
status: in-review
branch: w01-t13-health-workflow
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T13
---

## Objective
Spec section: SPEC-659 AC-27, AC-28; W-01 §3 F4. IntegrationHealthWorkflow: the 15-minute probe and the firm admins' Needs reauth notification.

## Plan (red)
1. `integrations/health_workflow.py`: a platform Schedule every 15 minutes; every connected or needs-attention firm token install whose Connect port is registered here (or a fake on a synthetic firm) answers `check_health`; a transient answer retried in the tick up to three times, so three in a row needs no stored count; the outcome through `apply_probe`.
2. `apply_probe` opens a unit of work only when the probe changes something (it raised `MissingAuditEvent` on every healthy probe before).
3. C16: `integration.health_changed` to Needs reauth tells the firm's security and firm admins (`connection_needs_reauth`).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5333). Lint, pyright clean; the app imports. Partial: the optional SSE topic and a recorded replay history; the notification's wording needs a copy check. Gates and
  tests run once at the S47 end pass (build first, test last).
