---
id: TASK-8824
title: "Q-05-T08: S52 Q-05 sweep: the SQMS register, imports and risk review (Q-05-T08 remainder)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-q05-sweep
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-05-T08
---

## Objective
Every Q-05 quality route answers from the service (no 501 left on the register, objectives, imports and the risk-assessment review).

## Done
- practice/quality_register.py: register read (objectives with risk and response counts), objective patch (owner, at-risk flag, sealed note; version-checked), register import dry run and publish from an evidence CSV (code-checked components, refs, parents; existing refs kept), risk-assessment review record
- five quality routes wired (quality_contract has no 501 left)
- assurance registry: post_issuance_sources insert-only
- reviewed audit actions; tests

## Progress log
- `2026-11-20` — Carried from S51 (Q-05-T08 remainder) so Q-05 has no partial left (DEC-5802).
