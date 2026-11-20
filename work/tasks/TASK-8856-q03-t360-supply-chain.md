---
id: TASK-8856
title: "Q-03-T360: Supply-chain hygiene 2028 Q4"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-q03t360
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-03-T360
---

## Objective
pip-audit, bandit, Trivy, CodeQL and Inspector to SLA; lock refresh; base digest; dependabot PRs.

## Done
- pip-audit, bandit, pnpm audit clean locally
- Base digest already current (5e2bdb1b); zlib1g pair closes on the tip Trivy scan
- uv.lock refresh (55 packages, two majors) goes in its own protected-manifest PR
- #2136, #1518 ride the batch; #2314 held, dependabot groups minor+patch only

## Progress log
- `2026-11-20` — 2026-11-20: run; record in docs/quality/supply-chain-quarterly.md 2028 Q4. DEC-5853. Trivy, CodeQL, Inspector read on the tip CI.
