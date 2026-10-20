---
id: TASK-113
title: "F-01-T09 · Worktree isolation (compose project and port offset), no-Docker fixture dev target, SessionStart context hook, local DB and deploy guard, regenerate-never-hand-merge hook"
spec: SPEC-045
acceptance_criteria: [AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23]
risk_zone: red
status: todo
epic: F-01
plan_key: F-01-T09
branch: task-113-local-safety-tooling
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
Two worktrees run make dev side by side with separate databases, make dev-fixtures runs without Docker, DB targets refuse non-local or in-flight hosted databases, and hand edits to generated files are blocked.

## Scope
**In**
- Port-offset and compose-project isolation
- No-Docker `make dev-fixtures`
- SessionStart `session_context.py`
- `db_guard` local-host and in-flight-deploy checks
- `protect_generated.py`, `guard_bash.py`, `.gitattributes`, `make regenerate`

**Out**
- Number blocks and reservation forms (F-01-T10, cut)
- Fixture handlers (F-04, F-05)
- Two-founder hook, CODEOWNERS, protected-path approvals (void)

## Already built (verify, fill gaps only)
Evidence from `docs/plan/status/status-verified.csv` (status `partial`): tools/local/db_guard+worktree_env tests, .claude/hooks (test_hooks generated-file test), Makefile dev-fixtures; VITE_FIXTURES read nowhere in apps/web/src

Gap to close:
- Wire `VITE_FIXTURES=1` into `apps/web/src` so `make dev-fixtures` actually starts the SPA in fixture mode (read nowhere today).
- Verify each remaining AC against the existing `db_guard`, `worktree_env`, `session_context.py`, `protect_generated.py` and `guard_bash.py`; add missing cases (deploy-in-flight, fail-closed `gh`, offset 10 port map, `.gitattributes`).

## Context to load
- Spec: `docs/specs/SPEC-045-repo-ci-dev-environment.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process); `docs/plan/status/status-verified.csv` row for this key
- Epic: `docs/plan/epics/F-01.md` section 3 (F5, all stories except number blocks and issue forms), section 4.1, section 9 (row F-01-T09), section 10, section 11 (R6)
- Epic tasks CSV: `docs/plan/epics/F-01.tasks.csv` row F-01-T09
- Code: `tools/local/db_guard`, `tools/local/worktree_env`, `.claude/hooks`, `Makefile`, `apps/web/vite.config.ts`
- Working agreement: do not run a local build while a hosted build is running (CLAUDE.md)

## Plan
Steps:
1. [ ] Write the plan here (red zone): a table of AC, existing evidence, missing piece.
2. [ ] Wire `VITE_FIXTURES` in `apps/web/src` and prove `make dev-fixtures` runs with Docker stopped.
3. [ ] Add the missing hook, guard and offset-map test cases.
4. [ ] Add the `.gitattributes` `linguist-generated=true` entries and the `make regenerate` target if absent.
5. [ ] Run `make check`.

Files to create or change:
- Makefile
- apps/web/src (VITE_FIXTURES read)
- apps/web/vite.config.ts
- tools/local/db_guard*, tools/local/worktree_env*
- .claude/hooks/session_context.py, protect_generated.py, guard_bash.py
- .gitattributes

Tests to write (mapped to ACs):
- AC-16, AC-17 -> worktree_env and offset-10 port map tests
- AC-18 -> make dev-fixtures with Docker stopped
- AC-19 -> session_context output cases
- AC-20, AC-21 -> db_guard refusal, in-flight and fail-closed cases
- AC-22, AC-23 -> test_hooks cases for protect_generated and guard_bash

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one listed below
- [ ] Module README and relevant docs updated
- [ ] Decisions below recorded; ADR raised where needed

Commands:
```
make check-fast
make check
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| | | | |

## Progress log
Append-only. Newest at the bottom.

- (none yet)

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | |

## Gotchas and discoveries
- `ABACUS_PORT_OFFSET` must not become a `Settings()` field.
- Worktree isolation as a process is void; this task keeps the tooling only.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
