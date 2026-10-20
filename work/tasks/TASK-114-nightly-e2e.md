---
id: TASK-114
title: "F-01-T08 · Repair the nightly e2e journey for the Setup-first flow with an idempotent seed step and nightly-red issue automation"
spec: SPEC-045
acceptance_criteria: [AC-14, AC-15]
risk_zone: red
status: in-progress
epic: F-01
plan_key: F-01-T08
branch: task-114-nightly-e2e
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
e2e.yml is green three nights running with expectNoSeriousViolations intact, and a red night opens or updates a nightly-red issue.

## Scope
**In**
- `apps/web/e2e/journey.spec.ts` retitled "setup-first journey: create -> setup gates -> request -> retrieve -> screened"
- Idempotent fixture step replacing the mid-test `make seed` shell-out
- `nightly-red` issue open/update step in `e2e.yml`

**Out**
- J01 to J28 journeys (F-04 adds `e2e/journeys/Jnn-*.spec.ts`)
- Playwright fixture smoke (F-05)

## Context to load
- Spec: `docs/specs/SPEC-045-repo-ci-dev-environment.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process); `docs/plan/status/status-verified.csv` row for this key
- Epic: `docs/plan/epics/F-01.md` section 3 (F4, last story), section 9 (row F-01-T08), section 10 (E2E), section 11 (Q4)
- Epic tasks CSV: `docs/plan/epics/F-01.tasks.csv` row F-01-T08
- Code: `apps/web/e2e/journey.spec.ts`, `.github/workflows/e2e.yml`
- SPEC-025 (Setup-first flow)

## Plan
Steps:
1. [ ] Write the plan here (red zone): current failure points of the nightly.
2. [ ] Replace the mid-test `make seed` shell-out with an idempotent fixture step, or keep it with a comment.
3. [ ] Keep `expectNoSeriousViolations` after each step.
4. [ ] Add the `nightly-red` issue open/update step.
5. [ ] Confirm three consecutive green nights.

Files to create or change:
- apps/web/e2e/journey.spec.ts
- .github/workflows/e2e.yml

Tests to write (mapped to ACs):
- AC-14 -> three consecutive green nightly runs
- AC-15 -> a forced red night opens or updates the `nightly-red` issue

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
- 2026-10-20 (SU-17): journey rewritten as the setup-first journey: create, Setup checklist, acceptance and independence conclusion, independence confirmation, Requests tab, retrieve, screened; axe after every step; unique client names per run; the dev seed kept as one named idempotent step (no firm connections UI yet). Found and fixed an AA contrast failure on ink-3 (DEC-115). Passes twice in a row locally. e2e.yml: Playwright browser cache (actions/cache pinned to v6.1.0's SHA) and a nightly-red job (issues: write only) that opens or updates one issue. Waiting for three green nights.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | |

## Gotchas and discoveries
- Depends on TASK-110 (green main); a red nightly caused by a stale assertion is TASK-110's job, not this one's.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
