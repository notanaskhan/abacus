---
id: TASK-124
title: "F-03-T03 · Draft AY's F-03 ADRs: P-34 status registry and codegen; P-28 entitlements and agent-minutes"
spec: SPEC-047
acceptance_criteria: [AC-4]
risk_zone: amber
status: todo
epic: F-03
plan_key: F-03-T03
branch: task-124-status-adr-drafts
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
P-34 (pre-allocated ADR-122) is open by Thu Oct 22 and P-28 (minted from the ADR-200 block) by Fri Oct 30, each with N as approver.

Solo reading: numbers are the next free number from `backlog.md`; the approver clause is void.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-047-domain-migrations-contract-register.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-03.md` section 0.1, section 9 (row F-03-T03), section 3.2 and 3.7
- Epic tasks CSV: `docs/plan/epics/F-03.tasks.csv` row F-03-T03

## Plan
Steps:
1. [ ] Check whether the P-34 draft already exists (ADR-138 is on disk); fill gaps only.
2. [ ] Draft P-28 by Fri Oct 30.
3. [ ] Update backlog.md and the README; run validate_docs.

Files to create or change:
- `docs/adr/` files for P-34 and P-28
- `docs/adr/backlog.md`

Checks (mapped to ACs):
- AC-4 -> two ADR files, dates met

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
- ADR-138 (status registry) exists on disk on 2026-10-20.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
