---
id: TASK-8541
title: "Q-03-T335: Supply-chain hygiene 2028 Q3 (laptop side)"
spec: SPEC-000
acceptance_criteria: []
risk_zone: red
status: in-review
branch: q03-t335-supply-chain
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: Q-03-T335
---

## Objective
Supply-chain hygiene 2028 Q3: pip-audit, bandit, Trivy, CodeQL and Inspector findings to SLA, uv.lock refresh and base-image digest bumps through the protected-manifest PR. AC: no high or critical dependency or image finding is older than its SLA at the quarter's end.

## Plan (red)
1. Run bandit (security.yml command), pnpm audit --prod, supply_chain check
2. Record in docs/quality/sweeps/2026-11-17-q03-t335-supply-chain.md
3. Open: base-image digest bump for the two zlib1g findings (due Dec 7), pip-audit and Trivy on CI, uv.lock refresh in the same protected-manifest PR, CodeQL and Inspector after the batch merge

## Progress log
- `2026-11-17` — Laptop side done: bandit clean, pnpm audit clean, register 2 open (zlib1g, trivy-image, first seen Nov 7, SLA Dec 7), none past SLA. The digest bump, lock refresh and CI scanners are open (registry, CI, AWS). Gates and tests run once at the S49 end pass (build first, test last).
