---
id: TASK-7637
title: S40 CI repair — main's ci on f2a76b4aa
plan_key: S40-end-pass
spec: SPEC-000  # S40 CI repair
acceptance_criteria: [AC-20]  # main ci green on the S40 causes
risk_zone: green
status: in-review
branch: s40-ci-repair
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Fix the S40 causes of `ci` run 43321315133 on f2a76b4aa (DEC-4632).

## Plan
- The search workflows' work class: fixed on main by #1839 (DEC-4809), not here.
- Pinned tests gain S40 entries: `test_tenant_provisioning.py` (workflows),
  `test_tri_and_offshore.py` (`run_artifact.download`), `test_schema_check_db.py` (0850, 0851).
- `test_t05t24_handshake.py`: the strict xfail on T-05-T32 lifted (it landed in S40).
- `test_q01t43_platform_controls_independent.py`: `POST /v1/search` exempt, as the server is.
- Fixture exports: 24 JSON files restored to their writers' bytes; `handoff-links.json`
  re-rendered by `seed-manifest.mjs`; `make fixtures SNAPSHOT=2026-09-24T10:20` regenerated.
- `packages/ui/src/templates/workbench-layout.tsx`: tabsbar `flex-none`; panes' padding is the
  shell's. `e2e/visual/tier-d-workbench.spec.ts` passes 11 of 11 locally.

## Partial
- Red before S40 and left to their owners: `components.spec.ts` E4 virtualisation (200 ms on
  the CI runner) and `run-stream.spec.ts` j23 (fixture server on 8001).

## Progress log
- `2026-11-13` — Root causes found in the CI log. Lesson: run prettier only as
  `pnpm -C apps/web exec prettier` (it reads `apps/web/.prettierignore`); a run from another
  directory rewrote the byte-held fixture exports.
