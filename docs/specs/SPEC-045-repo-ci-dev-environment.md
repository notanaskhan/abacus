---
id: SPEC-045
title: "Repo, CI and dev environment: green main, cheap staged CI, a trustworthy nightly e2e, and local safety rails"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-083, ADR-088]
related_specs: []
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition: `docs/plan/AMENDMENT-solo.md` overrides any two-founder process in the epic. No owner, approver, test author, ruleset, reservation issue or merge window applies. Acceptance tests are written first from this spec; a test is never edited to make it pass.

## 1. Summary
This is epic F-01 (plan: `docs/plan/epics/F-01.md`) cut to its solo-mode slice: make `main` green on the full suite with an honest coverage floor, rebuild CI so stage 2 runs on push and on ready-for-review, make frontend-only changes fast, repair the nightly Setup-first e2e journey, and keep local runs safe (worktree isolation, a no-Docker fixture target, a session-context hook, a database and deploy guard, and a block on hand-editing generated files). Nothing user-facing changes.

## 2. Problem and context
Today stale assertions and a coverage shortfall keep stage 2 from being trustworthy, CI runs backend shards for frontend-only diffs, the nightly e2e is not proven green, and a local run can point at a hosted database. Several pieces already exist (see each task's "Already built" section); this spec closes the gaps. The two-founder governance rows (F-01-T01 to T04, T11 to T16) are dropped by `docs/plan/AMENDMENT-solo.md`, and F-01-T10 (number blocks and reservation forms) is cut: SU-06 removed number blocks.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Builder | Writes the tooling and runs the gates. |
| Claude Code session | Subject of the SessionStart, protect-generated and guard-bash hooks. |
| CI (GitHub Actions) | Runs stage 1, stage 2, the frontend job and the nightly e2e. |

## 4. Goals and non-goals
**Goals**
- `main` green on stage 2 with `fail_under = 95` intact or a dated, ratcheted exception.
- Stage 1 and stage 2 enforce single head, `vite build` and generated-file drift.
- Frontend- or docs-only diffs finish in 6 minutes or less.
- Nightly e2e green three nights running, with automated red-night reporting.
- No local command can touch a hosted database or fight an in-flight deploy.

**Non-goals**
- Governance, rulesets, CODEOWNERS, approvals, number blocks, reservation forms, the release train and merge windows (void under the solo amendment).
- F-01-T10 (cut), F-01-T01 to T04, T11 to T16.
- Fixture handlers for `make dev-fixtures` (F-04 and F-05).

## 5. User stories and acceptance criteria
### Story 1: main is green and the coverage floor is honest (F-01-T05)
- **AC-1** Given the three stale assertions (`test_engagements.py:897`, `agent_tests/test_board_reads_api.py:230`, `test_schema_check_db.py:1083`) and whatever else a full run exposes, when they are fixed, then every changed assertion cites the SPEC AC it now matches (SPEC-025 Setup-first flow; AC-20 update-column contract), and no test is skipped, deleted or loosened.
- **AC-2** Given the fixes, when one full stage-2 run executes on `main`, then it is green.
- **AC-3** Given measured combined coverage below `fail_under = 95` (73% is recorded), when the gap is assessed, then it is closed with tests if that takes at most 2 builder-days; otherwise a dated exception that ratchets back to 95 by 2026-12-01 is recorded in `docs/product/decision-log.md` or an ADR (DEC-10). The floor in `backend/pyproject.toml` is never lowered.

### Story 2: CI that is green and cheap (F-01-T06)
- **AC-4** Given a push to `main`, then the `unit`, `integration`, `contracts`, `coverage` and `stage-2` aggregate jobs run (today they are `pull_request`-only). The workflow also triggers on `merge_group`, which takes effect only if the plan offers a merge queue.
- **AC-5** Given a draft PR, then only stage 1 runs; on `ready_for_review`, stage 2 runs (`pull_request` types: opened, synchronize, reopened, ready_for_review).
- **AC-6** Given two migrations that share a `down_revision`, when stage 1 runs `alembic heads`, then it fails with "multiple heads: rebase onto origin/main and renumber (P-38)".
- **AC-7** Given a change that breaks `vite build`, then stage 1 fails. The build step loops over every HTML entry in `apps/web/` (`index.html` today, `portal.html` when F-05 or P-01 adds it).
- **AC-8** Given a hand-edited `backend/src/abacus/modules/identity/authz/_matrix.py`, when `make check-generated` runs in stage 1, then it fails and names `python -m abacus_tools.codegen.permission_matrix`. It runs the same `--check` for `kernel/_flags.py`, `kernel/_provider_terms.py`, `modules/agents/specs/_specs.py` and `ai_gateway/_eval_suites.py`; api-client drift stays in `ci-contracts`.
- **AC-9** Given a re-recorded `backend/tests/durations.json`, then it lists every test file (156 today, against 86 listed now), and the slowest shard of each suite is at most 1.25 times that suite's mean.
- **AC-10** Given caches for `setup-uv`, the pnpm store and Playwright browsers, then a warm stage 1 finishes in at most 5 minutes (ADR-083).
- **AC-11** Given the rebuilt workflow, then five consecutive `main` runs are green through stage 2.

### Story 3: frontend-only PRs are fast (F-01-T07)
- **AC-12** Given a PR whose diff touches only `apps/web/**`, `packages/ui/**` or `docs/**`, when CI runs, then the backend `unit`, `integration` and `coverage` jobs report success without running tests; a `frontend` job runs Vitest and `vite build`, with the Playwright fixture smoke and axe slot wired once F-05 provides fixture mode; the required checks finish in at most 6 minutes. A backend PR finishes in at most 12 minutes.
- **AC-13** Given a diff under `backend/src/abacus/ai_gateway/`, `backend/src/abacus/modules/agents/`, `evals/` or `backend/src/abacus_tools/evals/`, then `evals-fast` still runs. The path classifier in `abacus_tools/ci/paths.py` is the single source for both filters.

### Story 4: the nightly e2e journey is trustworthy (F-01-T08)
- **AC-14** Given the Setup-first flow (create, setup gates, requests, retrieve, screened), when the nightly `e2e.yml` runs `apps/web/e2e/journey.spec.ts`, then it passes three consecutive nights, `expectNoSeriousViolations` still runs after each step, and the mid-test `make seed` shell-out is replaced by an idempotent fixture step (or kept with a comment if it cannot be).
- **AC-15** Given a red night, then an issue labelled `nightly-red` is opened or updated. Two red nights in a row make the fix the first work of the next session.

### Story 5: parallel-work and database safety (F-01-T09)
- **AC-16** Given two checkouts, the primary and a second worktree, when each runs `make dev`, then `make worktree-env` writes a git-ignored `.worktree.env` with `COMPOSE_PROJECT_NAME=abacus-<slug>` and `ABACUS_PORT_OFFSET` (0 for the primary, otherwise the next free slot of 10); the two stacks use separate volumes and ports (5173/8001/9000/55432/7070/7233/8233 plus offset); a migration in one does not change the other's schema.
- **AC-17** Given `ABACUS_PORT_OFFSET=10`, then `vite.config.ts` serves on 5183 and proxies `/v1` to 8011; the fake OIDC server listens on 9010 and accepts only the offset redirect URIs; Playwright's `baseURL` follows the offset; `ABACUS_LOCAL_SUPERUSER_DSN` and the `ABACUS_*_DATABASE_URL` values exported by the Makefile point at 55442; `Settings()` still loads because `ABACUS_PORT_OFFSET` is not a settings field and is ignored like `ABACUS_LOCAL_SUPERUSER_DSN`. CI keeps offset 0 and testcontainers keep random ports (`abacus_tools/stack.py`).
- **AC-18** Given Docker is stopped, when `make dev-fixtures` runs, then the SPA starts with `VITE_FIXTURES=1` and no compose, Python or Temporal process. F-04 and F-05 supply the fixture handlers.
- **AC-19** Given a new Claude Code session, when the SessionStart hook `session_context.py` runs, then it prints the branch and the linked TASK file and status; how many commits the branch is behind `origin/main`; the worktree's port offset; and the handoff version (or "HANDOFF_VERSION not set" until F-05 adds `docs/design/HANDOFF_VERSION`). It never blocks; a failure prints a warning.
- **AC-20** Given `ABACUS_MIGRATIONS_DATABASE_URL` or `ABACUS_DATABASE_URL` resolving to a host outside {127.0.0.1, localhost, ::1, `db`}, when `make migrate`, `make seed`, `make seed-staging`, `make loadtest` or any future `build-prod` target runs, then `db_guard` refuses it with "never point a local run at a hosted database".
- **AC-21** Given a sanctioned operator flow against staging, when `gh run list --workflow deploy-staging.yml --status in_progress` returns a run, or the SSM `/abacus/staging/deploy-lock` is held (once Q-01 publishes it), then the guard refuses; when `gh` is unavailable for a non-local target, it refuses (fail closed). Local targets are unaffected.
- **AC-22** Given a session tries to Edit or Write `packages/api-client/openapi.json`, `packages/api-client/src/**`, any `_matrix.py`, `_flags.py`, `_provider_terms.py`, `_specs.py` or `_eval_suites.py`, `backend/tests/durations.json` or `backend/tests/workflows/histories/*.json`, then `protect_generated.py` blocks it and names the regenerating command (`make generate`, the codegen module, `abacus_tools.ci.shard --record`, the replay recorder).
- **AC-23** Given `git checkout --ours` or `git checkout --theirs` on those paths, then `guard_bash.py` blocks it; the builder resolves conflicts with `make regenerate`, and `.gitattributes` marks the paths `linguist-generated=true` so PR diffs collapse them.

## Task map
Plan key to the acceptance criteria it must satisfy. F-01-T10 is cut and has no task file.

| Plan key | Acceptance criteria |
|---|---|
| F-01-T05 | AC-1, AC-2, AC-3 |
| F-01-T06 | AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11 |
| F-01-T07 | AC-12, AC-13 |
| F-01-T08 | AC-14, AC-15 |
| F-01-T09 | AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23 |

## 6. Behaviour and flows
Tooling-only. Each story is verified by the CI run or hook test named in section 18. Order: T05 (green main), then T06, T07 (CI), T09 (local safety), T08 (nightly e2e, needs a green stage 2).

## 7. Domain and data changes
N/A beyond what the criteria name; this slice changes no product tables unless an AC says so.

## 8. Interfaces
N/A beyond what the criteria name.

## 9. Authorisation and tenancy
N/A: repository, documentation and contract tooling; no tenant data is read or written by the slice. Where an AC names a matrix action, the standard `authorise()` and agent-deny rules apply.

## 10. AI behaviour
N/A: no model calls.

## 11. Integrations
N/A except where an AC names GitHub Actions, `gh` or a hosted database.

## 12. Edge cases and failure modes
- A coverage gap larger than 2 builder-days: record the dated exception; never lower the floor.
- `merge_group` is wired but only effective if the plan offers a merge queue; it is optional.
- `gh` unavailable for a non-local target: the guard fails closed.
- Docs-only diff that also touches an agent path: `evals-fast` still runs (AC-13).

## 13. Security and privacy
- **Data classification:** internal tooling; no client data.
- **Secrets:** CI uses none; local passwords are local-only. Never commit a secret.
- **Threats considered:** pointing a local run at a hosted database; hand-merged generated files.
- **Mitigations:** `db_guard` (AC-20, AC-21), `protect_generated.py` and `guard_bash.py` (AC-22, AC-23).

## 14. Audit trail and evidence integrity
Every decision is recorded in `docs/product/decision-log.md` or an ADR. Generated files are never hand-edited.

## 15. Observability
N/A.

## 16. Performance and scale
Only the CI time budgets named in the criteria.

## 17. UX
N/A: no screens.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 | unit | Each changed assertion carries a SPEC AC comment; diff shows no skip, delete or loosening. |
| AC-2 | e2e | Full stage-2 run on main is green. |
| AC-3 | review | Recorded coverage and, if below 95, the dated exception; pyproject keeps fail_under=95. |
| AC-4 | e2e | Workflow triggers inspected, then a push to main runs the named jobs. |
| AC-5 | e2e | Draft PR runs stage 1 only; ready_for_review starts stage 2. |
| AC-6 | unit | Two migrations with one down_revision fail check-heads with the exact message. |
| AC-7 | e2e | A deliberately broken vite build fails stage 1; the loop covers every HTML entry. |
| AC-8 | unit | Hand-edited _matrix.py fails check-generated naming the codegen module; same for the four other files. |
| AC-9 | unit | durations.json covers all test files; shard skew assertion at 1.25x. |
| AC-10 | e2e | Warm stage 1 duration read from a CI run. |
| AC-11 | e2e | Five consecutive main runs green. |
| AC-12 | e2e | Docs/frontend-only PR: backend jobs succeed without tests, checks within 6 minutes. |
| AC-13 | unit | test_paths.py cases for agent paths; evals-fast triggers on a diff in each listed directory. |
| AC-14 | e2e | Three consecutive nightly runs green; no make seed shell-out or a comment. |
| AC-15 | integration | A forced red night opens or updates the nightly-red issue. |
| AC-16 | integration | worktree_env test: slug, offset, separate volumes and ports. |
| AC-17 | unit | Offset 10 maps every port; Settings() loads with ABACUS_PORT_OFFSET set. |
| AC-18 | integration | make dev-fixtures with Docker stopped; VITE_FIXTURES read in apps/web/src. |
| AC-19 | unit | session_context.py output cases, including HANDOFF_VERSION unset and failure to warning. |
| AC-20 | unit | db_guard refuses each non-local host for each guarded target. |
| AC-21 | unit | db_guard with gh in-flight run, held lock, gh missing (fail closed), local target unaffected. |
| AC-22 | unit | test_hooks: protect_generated blocks each listed path and names the command. |
| AC-23 | unit | guard_bash blocks checkout --ours/--theirs on generated paths; .gitattributes marks them. |

## 19. Rollout
No feature flag unless an AC names one. Changes land on `main` once `make check` is green; staging is deployed once at sprint close (AMENDMENT-solo section 9).

## 20. Open questions
All answered with the plan's proposed option.
- [x] Coverage (R3): close with tests if at most 2 builder-days, else a dated exception ratcheting to 95 by 2026-12-01 in the decision log or an ADR; the floor is never lowered.
- [x] merge_group (R2): wired but optional; no merge queue is assumed.
- [x] Who repairs the nightly e2e (Q4): the builder.
- [x] Reviewer-model rule (Q2) and number blocks (Q1): void under the solo amendment.
- [x] Several Docker stacks (R6): cap full-stack worktrees at two per machine; otherwise use `make dev-fixtures`.

## 21. Future / explicitly deferred
- F-01-T10 number blocks and reservation forms: cut.
- Release-train merge side and merge-window checks: void.
- Nightly Playwright fixture smoke and axe slot until F-05 provides fixture mode.
