---
id: TASK-081
title: Worktree isolation — own compose project and ports per worktree, and dev-fixtures (epic F-01-T09, part 2)
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: red
status: done
branch: task-081-worktree-isolation
worktree:
created: 2026-10-19
updated: 2026-10-19
---

## Objective
Two checkouts run `make dev` side by side with separate databases and ports, and the SPA can run alone without Docker (epic F-01-T09, part 2).

## Scope
**In**
- `make worktree-env` (`abacus_tools.local.worktree_env`): writes the git-ignored `.worktree.env` once — primary checkout `abacus`/0; a linked worktree `abacus-<slug>` and the next free offset of 10 (up to 90).
- `Makefile`: includes `.worktree.env`; exports `COMPOSE_PROJECT_NAME`, `ABACUS_PORT_OFFSET` and `ABACUS_{DB,S3,TEMPORAL,TEMPORAL_UI}_PORT`; `STACK_ENV` points the database, S3, Temporal and superuser settings at this checkout's ports for `dev`, `seed`, `migrate` and `db-guard`; the API serves on 8001 + offset. `make dev-fixtures` runs the SPA with `VITE_FIXTURES=1` only.
- `docker-compose.yml`: host ports from `ABACUS_*_PORT` (defaults unchanged).
- `vite.config.ts` (5173 + offset, proxy 8001 + offset, authority 9000 + offset), `playwright.config.ts` (baseURL), `oidc_server.py` (9000 + offset; redirect URIs of this worktree's SPA only).
- `.gitignore`: `.worktree.env`.

**Out**
- Fixture handlers behind `VITE_FIXTURES` (F-04, F-05).
- CI and testcontainers: unchanged (offset 0; random ports).

## Plan
Approved by founder (2026-10-19, auto mode): paths `docker-compose.yml`, `Makefile`, `.gitignore`, `backend/pyproject.toml` (S603 exemptions for the git calls); approval file `work/approvals/TASK-081.yaml`, expires 2026-10-26.

## Definition of done
- [x] `tests/unit/tools/test_worktree_env.py` (15) passes; `make check-fast` passes.
- [x] Live check: an offset-10 stack (`abacus-t081check`, db on 55442) beside the primary (55432); `make migrate` took the new database to 0056; a table created in one is absent from the other; the test stack was removed with `down -v`.
- [x] Vite at offset 10 serves 5183 and proxies to 8011; at 0, 5173 and 8001.
- [ ] CI green on the PR.

## Progress log
- 2026-10-19: built, tested, live-checked.

## Gotchas and discoveries
- Calling `docker compose` directly bypasses the Makefile's port exports; use `make dev` (or set `ABACUS_DB_PORT` etc.) in a worktree.
- `apps/web` has no Node types; the configs read the offset through `loadEnv` (Vite) and a local `process` declaration (Playwright).

## Questions for the human
- None.

## Handoff
Merge after CI; delete `work/approvals/TASK-081.yaml`. F-01-T09 is then complete except the staging deploy checks (Q-01).
