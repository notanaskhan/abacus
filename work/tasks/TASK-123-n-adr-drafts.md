---
id: TASK-123
title: "F-03-T02 · Draft N's F-03 ADRs from chapter 03 text: P-38, P-04, P-05, P-39, P-36 for Decision Day, then P-44, P-06, P-09, P-10"
spec: SPEC-047
acceptance_criteria: [AC-3]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T02
branch: task-123-n-adr-drafts
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
Nine draft ADR PRs exist, numbered as docs/adr/backlog.md lists them (pre-allocated ADR-117 P-38, 120 P-04, 121 P-05, 123 P-36, 124 P-39, 128 P-44; P-06, P-09 and P-10 minted from ADR-131 when drafted), each naming both deciders: P-38, P-04, P-05, P-39 and P-36 open by Thu Oct 22, and P-44, P-09, P-10 and P-06 open by Fri Oct 30 (M1).

Solo reading: numbers are the next free number, taken from `backlog.md`; the deciders clause (both handles) and PRs are void; files land on `main` as `proposed` ADRs.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-047-domain-migrations-contract-register.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-03.md` section 0.1 (decisions and ADRs gating this epic), section 9 (row F-03-T02), section 11 (R2)
- Epic tasks CSV: `docs/plan/epics/F-03.tasks.csv` row F-03-T02

## Plan
Steps:
1. [ ] Write the plan here (red zone): for each of the nine P-IDs, check `docs/adr/` and `backlog.md` for an existing draft (P-38, P-04, P-34 and P-36 may already exist) and fill gaps only.
2. [ ] Draft the first five by Thu Oct 22, the other four by Fri Oct 30.
3. [ ] Add README index rows; run validate_docs.

Files to create or change:
- Nine files in `docs/adr/`
- `docs/adr/backlog.md`
- `docs/adr/README.md`

Checks (mapped to ACs):
- AC-3 -> nine files, dates met, backlog numbers match

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
- 2026-10-20: done in setup step SU-13: ADR-135 (P-38), ADR-136 (P-04), ADR-137 (P-05), ADR-140 (P-39), ADR-139 (P-36), ADR-144 (P-44), ADR-145 (P-06), ADR-146 (P-09) accepted and indexed in docs/adr/README.md and docs/adr/backlog.md.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | |

## Gotchas and discoveries
- On 2026-10-20 `docs/adr/` already holds ADR-135 (migration policy), ADR-136 (work items and gates), ADR-138 (status registry) and ADR-139 (API conventions); verify against `backlog.md` before drafting.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
