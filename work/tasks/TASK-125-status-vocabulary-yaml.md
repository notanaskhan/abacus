---
id: TASK-125
title: "F-03-T04 · Author docs/product/status-vocabulary.yaml from blueprint 3.3.1 + addendum 3.2 + gap 6.5 (code, context labels, variant, terminal, client_label, derived, RETIRED map) and list it in protected-paths.md"
spec: SPEC-047
acceptance_criteria: [AC-5, AC-6, AC-7, AC-8]
risk_zone: red
status: todo
epic: F-03
plan_key: F-03-T04
branch: task-125-status-vocabulary-yaml
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
Every 3.3.1 object has an entry (engagement 8 states, request 6 plus derived overdue, binder 5, every work-item subtype) and each of the 144 lib/status.js words is mapped or retired.

Solo reading: protected-paths listing is kept as a documentation list only; the builder authors and consumes the YAML.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-047-domain-migrations-contract-register.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-03.md` section 3.2 (Story 2.1), section 3.3 (Story 3.1), section 9 (row F-03-T04), section 11 (R5, R6)
- Epic tasks CSV: `docs/plan/epics/F-03.tasks.csv` row F-03-T04

## Plan
Steps:
1. [ ] Write the plan here (red zone): list the 3.3.1 objects and their states.
2. [ ] Author the YAML with all fields per entry.
3. [ ] Map each of the 144 `lib/status.js` words or retire it with its replacement.
4. [ ] Encode the request bridge (AC-7).
5. [ ] List the file in protected-paths.md; confirm it parses.

Files to create or change:
- `docs/product/status-vocabulary.yaml`
- `docs/architecture/protected-paths.md`

Checks (mapped to ACs):
- AC-5 -> object coverage count
- AC-6 -> 144-word mapping test
- AC-7 -> request code and label assertions
- AC-8 -> parses; path listed

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
- Depends on TASK-124 (P-34). Keep the screener vocabulary (`ready_for_review`, `needs_revision`) a separate type from request status (R6).
- Do not touch `docs/product/` from the planning step; this task writes it when run.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
