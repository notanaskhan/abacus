---
id: TASK-122
title: "F-03-T01 · Contract register: docs/contracts/README.md for C1–C21 (provider epic, consumers, freeze sprint, version, status), _TEMPLATE.md, `contract: <name> vN` issue template, /docs/contracts/ in CODEOWNERS for both handles"
spec: SPEC-047
acceptance_criteria: [AC-1, AC-2]
risk_zone: red
status: todo
epic: F-03
plan_key: F-03-T01
branch: task-122-contract-register
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
The register lists C1–C21 with the chapter-01 provider and freeze sprint, and a PR touching docs/contracts/ needs the other founder's code-owner review.

Solo reading: the code-owner review clause, the issue template and CODEOWNERS are void; the register itself and `_TEMPLATE.md` are the deliverable.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-047-domain-migrations-contract-register.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-03.md` section 0 (summary), section 3.10 (Story 10.1), section 8 (contracts and dependencies), section 9 (row F-03-T01), section 10 (item 2)
- Epic tasks CSV: `docs/plan/epics/F-03.tasks.csv` row F-03-T01

## Plan
Steps:
1. [ ] Write the plan here (red zone): source the provider epic and freeze sprint of C1 to C21 from chapter 01.
2. [ ] Create `docs/contracts/README.md` and `_TEMPLATE.md`.
3. [ ] Document the frozen-contract rule (v2 with one sprint of overlap).
4. [ ] Run validate_docs.

Files to create or change:
- `docs/contracts/README.md`
- `docs/contracts/_TEMPLATE.md`

Checks (mapped to ACs):
- AC-1 -> 21 rows with all columns
- AC-2 -> rule text

## Definition of done
- [ ] Every listed AC is satisfied and the file or section that satisfies it is cited in the progress log
- [ ] `cd backend && uv run python -m abacus_tools.quality.validate_docs` passes
- [ ] No secrets or real client data committed
- [ ] Decisions recorded in `docs/product/decision-log.md` or an ADR

Commands:
```
cd backend && uv run python -m abacus_tools.quality.validate_docs
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
- `docs/contracts/` does not exist on 2026-10-20.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
