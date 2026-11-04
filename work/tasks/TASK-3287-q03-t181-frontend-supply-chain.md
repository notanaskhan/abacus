---
id: TASK-3287
title: Q-03-T181 front-end supply-chain hygiene 2027 Q4
spec: SPEC-000  # row (docs/quality/supply-chain-quarterly.md supply-chain)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T181
branch: s27-q03-t181
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
pnpm audit --prod, dependency bumps through the protected package.json PR, pinned Playwright, axe
and font versions in the baseline manifest.

## Plan (amber, a report)
- `docs/quality/supply-chain-quarterly.md` § 2027 Q4 front end: audit results, the open dev-only
  highs inside SLA, the pinned versions and the parity-manifest drift (1.63.0 recorded, 1.64.1
  locked), re-measured in the end pass before the manifest moves.

## Progress log
- 2026-11-04: run and recorded. No manifest or lockfile edits (protected paths).
