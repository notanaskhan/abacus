---
id: TASK-8431
title: "W-01-T21: W-01 rollout and docs"
spec: SPEC-659
acceptance_criteria: [AC-34]
risk_zone: green
status: in-review
branch: w01-t21-rollout-docs
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: W-01-T21
---

## Objective
Spec section: docs/plan/epics/W-01.md §10 items 2 and 11. Rollout and docs: production catalogue import, flag renewal in the Aug 24 train, canary flip Tue Aug 29, RB-01/RB-04/RB-05 sections, connector skill update, Oct 24 real-firm flip plan.

## Plan (green)
1. RB-01: the W-01 flag-flip section (order, before, rollback, after).
2. RB-04: integration-provider outage (kill switch → Paused, silencing the health pass, status component).
3. RB-05: the Connect reauth wave (firm, personal, client-authorised, file bridge).
4. `.claude/skills/connector/SKILL.md`: "Integration adapters vs connectors".
5. `docs/plan/status/W-01-rollout.md`: renewal, production import, canary flip, last promotion and real-firm flips with owners and evidence.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5423). validate_docs clean. Partial (human steps): the production catalogue import with both approvals, the Tue Aug 29 canary flip, and the renewal and Oct 24 tickets; the skill edit is a protected path that needs both founders' approval in review. The W-01-T20 delta pen test is deferred (DEC-1389). Gates and tests run once at the S48 end pass (build first, test last).
