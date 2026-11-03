---
id: TASK-3240
title: Q-03-T170 Supply-chain hygiene 2027 Q4
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T170
branch: s26b-q03-t170
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3240 · Q-03-T170 · Supply-chain hygiene, 2027 Q4

## Done
- pip-audit (locked export) and bandit (high, `backend/src`): clean.
- pnpm audit: three high js-yaml advisories under the API-client generator, open inside their SLA (due 2026-12-03). An override fixes them (tried, client byte-identical) but the dependency gate refuses `overrides` and the lockfile is a protected manifest: the fix goes in the protected-manifest PR.
- `docs/quality/supply-chain-quarterly.md` gains the 2027 Q4 section; the register has nothing open.

## Not done
- Trivy, CodeQL and Inspector: CI only, and GitHub Actions created no runs on 2026-11-03.
- uv.lock refresh and base-image digest bumps (protected-manifest PR with replay histories).

## Progress log
- 2026-11-03: scans run locally; override applied.
