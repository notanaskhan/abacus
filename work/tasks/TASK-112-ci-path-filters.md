---
id: TASK-112
title: "F-01-T07 · Path filters that report success for backend shards on frontend- or docs-only diffs, plus a frontend job"
spec: SPEC-045
acceptance_criteria: [AC-12, AC-13]
risk_zone: red
status: todo
epic: F-01
plan_key: F-01-T07
branch: task-112-ci-path-filters
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
A frontend-only PR completes required checks in 6 minutes or less without running backend shards, while agent-path diffs still trigger evals-fast.

## Scope
**In**
- Frontend job timing and caching
- Path classifier cases for docs/frontend-only and agent-path diffs

**Out**
- Playwright fixture smoke and axe slot (wired once F-05 provides fixture mode)
- Backend sharding changes (TASK-111)

## Already built (verify, fill gaps only)
Evidence from `docs/plan/status/status-verified.csv` (status `partial`): abacus_tools/ci/paths.py + tests/unit/tools/test_paths.py; ci.yml frontend and evals-fast gates; 6-minute clause unmeasured (frontend job timeout 10)

Gap to close:
- Measure a frontend-only PR end to end against the 6-minute budget; tighten the frontend job (timeout is 10) until it holds.
- Confirm a backend PR finishes in 12 minutes or less and that agent-path diffs still run `evals-fast`.

## Context to load
- Spec: `docs/specs/SPEC-045-repo-ci-dev-environment.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process); `docs/plan/status/status-verified.csv` row for this key
- Epic: `docs/plan/epics/F-01.md` section 3 (F4, path-filter and evals-fast stories), section 9 (row F-01-T07), section 10
- Epic tasks CSV: `docs/plan/epics/F-01.tasks.csv` row F-01-T07
- Code: `backend/src/abacus_tools/ci/paths.py`, `backend/tests/unit/tools/test_paths.py`, `.github/workflows/ci.yml`
- Depends on TASK-111

## Plan
Steps:
1. [ ] Write the plan here (red zone): current job timings from recent runs.
2. [ ] Open a frontend-only and a docs-only PR (or push a branch) and read the check durations.
3. [ ] Tighten caches/steps until the required checks are 6 minutes or less; lower the frontend timeout.
4. [ ] Add path cases for each agent directory so `evals-fast` triggering is proven.

Files to create or change:
- .github/workflows/ci.yml
- backend/src/abacus_tools/ci/paths.py
- backend/tests/unit/tools/test_paths.py

Tests to write (mapped to ACs):
- AC-12 -> a docs/frontend-only run shows backend jobs successful without tests and required checks within 6 minutes
- AC-13 -> `test_paths.py` cases for each listed agent directory

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
- None yet.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
