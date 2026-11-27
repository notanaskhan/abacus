---
id: TASK-9039
title: "T-06-T57: Security cases for the entity-depth surfaces"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s54-t06-t57-security
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: T-06-T57
---

## Objective
Portal isolation, TRI and classification scrubbing for the new tables and models, wall 404s, offshore masking on form faces.

## Done
- Each case runs in the security stage
- the TRI check fails on a deliberately leaked field
- REST: a portal-room Postgres case for the §754 request's single recipient

## Progress log
- `2026-11-27` — 2026-11-27: built per DEC-6043, 13 cases green.
