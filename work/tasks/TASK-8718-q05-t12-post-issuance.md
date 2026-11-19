---
id: TASK-8718
title: "Q-05-T12: Post-issuance cases: migration and code comparison and evaluation (dark)"
spec: SPEC-711
acceptance_criteria: [AC-15, AC-16, AC-17, AC-18]
risk_zone: red
status: in-review
branch: q05-t12-post-issuance
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T12
---

## Objective
Migration 0984: post_issuance_events (PI-nn cases, forward status by the service) with insert-only comparisons and evaluations. assurance/compute/post_issuance.py (pure): line comparison by code, evaluation against the materiality frozen at release (clearly trivial, share of overall to one place), and the decision's options (No action recommended only when below clearly trivial with no disclosure affected; all reserved to the EP).

## Plan (red)
1. migrations/versions/0984_assurance_post_issuance.py (on 0983).
2. assurance/registry.py: Q05T12 tables and columns.
3. assurance/compute/post_issuance.py.
4. tests/unit/assurance/test_q05t12_post_issuance.py.

## Progress log
- `2026-11-19` — Built (schema and compute); tests pass (2). Not built: assurance/post_issuance.py service under the post_issuance GUC kind (reads A-05's certified lines and the release's frozen materiality), the post_issuance_action decision kind and its side effect through A-07's ArchiveAdditionWorkflow, and the routes (stubs stay 501). Agent decide refusal holds at matrix (post_issuance.* deny agent) and decision-card layers. Gates and tests run once at the S51 end pass (build first, test last).
