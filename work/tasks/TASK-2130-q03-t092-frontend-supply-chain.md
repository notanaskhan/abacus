---
id: TASK-2130
title: Q-03-T092 Front-end supply-chain hygiene 2027 Q2
spec: Q-03 epic
acceptance_criteria: [backlog row]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T092
branch: s16-q03-t092
created: 2026-10-29
updated: 2026-10-29
---

## Objective
`pnpm audit --prod`, dependency bumps through the protected package.json PR, pinned Playwright,
axe container and font versions in the baseline manifest.

Acceptance (backlog row): "No high or critical front-end advisory is open at the quarter's end and
parity baselines are unchanged by the bumps."

## Plan (amber)
- `pnpm audit --prod` on main (2026-10-29): 2 moderate, 0 high, 0 critical — both in `seroval`
  1.6.8 (GHSA-f86p-h4j2-7qgj, GHSA-9wx9-5pv9-3349) through `@tanstack/router-core`.
- Fix: `pnpm update -r seroval seroval-plugins` within router-core's own `^1.6.7` range: 1.7.3.
  Lockfile only; no package.json, no allowlist change. `pnpm audit --prod`: no known
  vulnerabilities.
- Parity: seroval serialises router state for server rendering, which the SPA does not use; the
  visual suite runs at the end review to confirm baselines are unchanged.
- Rollback: revert the lockfile hunk.

## Progress log
- 2026-10-29: audit clean after the lockfile bump; web typecheck clean; routing tests pass. The
  Playwright, axe and font pins in the baseline manifest are unchanged (no bump needed).
- Seen, not caused: `src/app-core/auth/bff.csp.test.ts` fails on main (it reads vite.config.ts
  as text); recorded for the end review.
