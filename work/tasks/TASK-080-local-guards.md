---
id: TASK-080
title: Local safety guards — generated files never hand-edited, local DB guard, session context hook (epic F-01-T09, part 1)
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: red
status: done
branch: task-080-local-guards
worktree:
created: 2026-10-19
updated: 2026-10-19
---

## Objective
Agents can't hand-edit or hand-merge generated files, local database targets refuse hosted databases, and every session starts knowing its branch, task, staleness and port offset (epic F-01-T09, part 1).

## Scope
**In**
- `.claude/hooks/_protected.py`: `GENERATED` (api client, `_matrix.py`, `_flags.py`, `_provider_terms.py`, `_specs.py`, `_eval_suites.py`, `durations.json`, replay histories); an Edit or Write is blocked even with an approval, naming the regenerating command.
- `.claude/hooks/guard_bash.py`: `git checkout --ours/--theirs` on a generated path is blocked. The "never push directly to main" rule is removed: the founder pushes straight to `main` (2026-10-19); force pushes stay blocked.
- `.claude/hooks/session_context.py` (SessionStart, registered in `.claude/settings.json`): branch, linked task file and status, commits behind `origin/main`, port offset, design handoff version. Never blocks.
- `abacus_tools/local/db_guard.py` and `make db-guard`, run before `migrate`, `seed`, `seed-staging`, `loadtest`.
- `make regenerate`; `.gitattributes` marks generated paths `linguist-generated`.

**Out (part 2, TASK-081)**
- Worktree isolation (`make worktree-env`, compose project, port offsets in vite, OIDC fake, Playwright, Makefile URLs) and `make dev-fixtures`.
- The staging deploy-in-flight and deploy-lock checks (no deploy workflow or SSM lock until Q-01).

## Plan
Approved by founder (2026-10-19, auto mode): paths `.claude/hooks/**`, `.claude/settings.json`, `Makefile`, `backend/tests/unit/quality/test_hooks.py`, `backend/pyproject.toml`; approval file `work/approvals/TASK-080.yaml`, expires 2026-10-26.

Tests written in this session (founder waived ADR-078's separate author, 2026-10-19): `test_hooks.py` (generated edits, side-picking, session context; push to `main` moved to allowed), `tests/unit/tools/test_db_guard.py`.

## Definition of done
- [x] Hook and guard tests pass under the venv and system `python3` (288 tests in `tests/unit/tools` and `test_hooks.py`).
- [x] `make regenerate` runs and leaves no diff; `make check-fast` passes.
- [ ] CI green on the PR.

## Progress log
- 2026-10-19: guards, hook, Makefile targets, gitattributes and tests.

## Gotchas and discoveries
- Sessions started in `~/Downloads/abacus` (the parent folder) don't load this repo's `.claude/` hooks at all, so nothing in this file is enforced for them. Start sessions in the repo root.
- `make regenerate` needs Node 24 first on `PATH` (as `make setup` does).

## Questions for the human
- None.

## Handoff
Merge after CI, delete `work/approvals/TASK-080.yaml`, then TASK-081 (worktree isolation, part 2).
