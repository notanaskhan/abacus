---
id: TASK-126
title: "F-03-T06 · C1 stub PR: work-item and lifecycle Pydantic models with classification tags, 501 route stubs, matrix actions, flag engagements.work_items_api, MeOut v2 fields, make generate, docs/contracts/work-items.md with Brightwater Hale E0 examples"
spec: SPEC-047
acceptance_criteria: [AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15]
risk_zone: amber
status: todo
epic: F-03
plan_key: F-03-T06
branch: task-126-c1-stub
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
The generated client exposes every C1 operation returning 501 behind the flag, and the contract doc carries Copperleaf, Northwind, Bluestem and Meridian E0 example payloads.

Solo reading: land on `main` after `make check` is green; no PR review or approvals.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-047-domain-migrations-contract-register.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-03.md` section 3.1 (Stories 1.1 to 1.3), section 3.6 (Story 6.2), section 3.10, section 4.3 to 4.10 (endpoints, matrix, events, flags), section 8.1 (contracts provided), section 9 (row F-03-T06)
- Epic tasks CSV: `docs/plan/epics/F-03.tasks.csv` row F-03-T06

## Plan
Steps:
1. [ ] Write the plan here (amber): list the C1 operations and models.
2. [ ] Write the acceptance tests first: generated-client 501 check, example-payload contract tests, matrix agent-deny test.
3. [ ] Implement models, 501 routes, matrix actions, flag and MeOut v2.
4. [ ] Run `make generate`; author `docs/contracts/work-items.md`.
5. [ ] Run `make check`.

Files to create or change:
- `backend/src/abacus/modules/engagements/` (models, routes)
- `identity/authz` matrix registration and `kernel` flag
- `docs/contracts/work-items.md`
- generated files via `make generate` (never hand-edited)

Tests to write (mapped to ACs):
- AC-9 -> generated client lists every operation, each 501 behind the flag
- AC-10, AC-11, AC-12, AC-13 -> contract tests over the example payloads
- AC-14 -> MeOut v2 field test
- AC-15 -> agent/system deny test and audit/outbox shape

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
- Depends on TASK-122, TASK-123 and F-02-T04 (TASK-118). Single Alembic head; this task adds no migration.
- The accept/decline/hold paths are human-only (INV-1).

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
- 2026-10-26 (S10 code gap, branch `s10-f03-t06-examples`): docs/contracts/work-items.md §9 carries the Copperleaf, Northwind, Bluestem and Meridian E0 examples, captured through the API from a throwaway E0 + binders load. The 501-stub half of the row is superseded by F-03-T31 (live).
