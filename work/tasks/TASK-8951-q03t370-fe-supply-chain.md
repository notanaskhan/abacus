---
id: TASK-8951
title: "Q-03-T370: Front-end supply-chain hygiene 2028 Q4"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-q03t370
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: Q-03-T370
---

## Objective
Front-end supply-chain hygiene 2028 Q4: pnpm audit --prod, dependency bumps through the protected package.json PR, pinned Playwright and axe container and font versions in the baseline manifest. Acceptance: No high or critical front-end advisory is open at the quarter's end and parity baselines match.

## Done
- pnpm audit --prod: no known vulnerabilities
- full audit had 3 high (js-yaml <4.3.2 via @hey-api/openapi-ts) and 1 moderate (minimatch <11.0.1 via typescript-eslint), both dev tooling: closed by pnpm-workspace overrides (js-yaml 4.3.2, minimatch 11.0.9); after: no known vulnerabilities
- lint, tsc and make generate unchanged with the overrides
- docs/design/parity-manifest.json tools pins (@playwright/test 1.64.1, axe 4.13.0, Geist 5.3.0) match the lockfile: no re-measure needed

## Progress log
- `2026-11-23` — 2026-11-23: done; the override is a protected-file change (pnpm-workspace.yaml) noted for the end-pass review.
