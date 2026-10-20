---
id: TASK-111
title: "F-01-T06 · CI rebuild: stage 2 on push to main and merge_group, ready-for-review gating, caches, shard re-record, single Alembic head, vite build and check-generated in stage 1, ruleset phase 2"
spec: SPEC-045
acceptance_criteria: [AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11]
risk_zone: red
status: todo
epic: F-01
plan_key: F-01-T06
branch: task-111-ci-rebuild
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
Five consecutive main runs are green through stage 2 and the ruleset requires stage 1 (make check-fast) and stages 1 and 2 (make check).

Solo reading: rulesets are void; the objective is the five consecutive green `main` runs through stage 2 with stage 1 and stage 2 intact as `make check-fast` and `make check`.

## Scope
**In**
- Trigger, gating, cache and shard changes in `.github/workflows/ci.yml`
- `make check-heads` and `make check-generated` wired into stage 1
- Re-recorded `durations.json` via `abacus_tools.ci.shard --record`

**Out**
- Ruleset phase 2 and required-check configuration (void)
- Path filters (TASK-112)

## Already built (verify, fill gaps only)
Evidence from `docs/plan/status/status-verified.csv` (status `partial`): .github/workflows/ci.yml has merge_group, draft gating, changes job, frontend job; Makefile check-heads/check-generated; 5 green runs and ruleset not judgeable

Gap to close:
- Verify each AC against `ci.yml` and the Makefile (push-to-main jobs, ready-for-review types, caches, `check-heads` message, `vite build` loop over every HTML entry, `check-generated` for all five files).
- Re-record `backend/tests/durations.json` (156 files versus 86 listed) and check shard skew at 1.25x.
- Obtain five consecutive green `main` runs; skip the ruleset (void).

## Context to load
- Spec: `docs/specs/SPEC-045-repo-ci-dev-environment.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process); `docs/plan/status/status-verified.csv` row for this key
- Epic: `docs/plan/epics/F-01.md` section 3 (F4, stories from push-to-main to caches), section 4.1 (paths touched), section 9 (row F-01-T06), section 10, section 11 (R2)
- Epic tasks CSV: `docs/plan/epics/F-01.tasks.csv` row F-01-T06
- ADR-083 (CI pipeline)
- Depends on TASK-110 (green main)

## Plan
Steps:
1. [ ] Write the plan here (red zone): per AC, what exists in `ci.yml`/Makefile and what is missing.
2. [ ] Close the gaps in `ci.yml` and the Makefile.
3. [ ] Re-record `durations.json` and assert shard skew.
4. [ ] Measure a warm stage 1 (at most 5 minutes).
5. [ ] Land on `main`; record five consecutive green runs.

Files to create or change:
- .github/workflows/ci.yml
- Makefile
- backend/tests/durations.json (generated)
- abacus_tools/ci/shard.py (only if skew assertion needs it)

Tests to write (mapped to ACs):
- AC-4, AC-5 -> workflow trigger inspection plus a draft-PR and ready-for-review run
- AC-6 -> two migrations with one down_revision fail with the exact message
- AC-7 -> broken vite build fails stage 1
- AC-8 -> hand-edited generated file fails check-generated naming its codegen module
- AC-9 -> durations coverage and skew test
- AC-10 -> warm stage 1 time
- AC-11 -> five green main runs

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
- `merge_group` only takes effect if the plan offers a merge queue; keep it wired but optional.
- Do not run a local production build while a hosted build is running (shared pooled database).

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
