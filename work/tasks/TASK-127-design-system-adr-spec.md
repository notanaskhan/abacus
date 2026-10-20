---
id: TASK-127
title: "F-05-T01 · ADR P-03 and SPEC-1NN Accrued design system; seed tokens/DECISIONS.md conflict log"
spec: SPEC-048
acceptance_criteria: [AC-12]
risk_zone: amber
status: done
epic: F-05
plan_key: F-05-T01
branch: task-127-design-system-adr-spec
created: 2026-10-20
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan into this file before code (solo amendment: no approval step).
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
ADR P-03 is accepted with N as approver (never the author) and the new SPEC supersedes SPEC-016 section 4 before any token PR merges.

## Scope
**In**
- ADR P-03 (next free ADR number on main) accepting the Accrued design system, superseding only ADR-011's shadcn-as-base clause
- Mark SPEC-048 as superseding SPEC-016 section 4 (note in both files)
- Seed `packages/ui/src/tokens/DECISIONS.md` with the conflict log, including the 2026-10-20 decisions (pill controls, /components, codemod as check)

**Out**
- Any token, CSS or lint code (T03 onward)
- Editing docs/adr/ files owned by other sessions beyond adding this one ADR and its index row

## Context to load
- Spec: `docs/specs/SPEC-048-design-system-core.md` (sections 5 and Task map; ACs AC-12)
- Epic: `docs/plan/epics/F-05.md`: F-05 §0 (decisions row: DEC-04, DEC-11, DEC-15, ADR P-03); F-05 §3 A (stories A1 to A4) and J (Atelier retirement); F-05 §10 item 9 (docs and DECISIONS.md); F-05 §11 R1, Q5
- Task row: `docs/plan/epics/F-05.tasks.csv`, `F-05-T01`
- Process: `docs/plan/AMENDMENT-solo.md`
- Prior work: TASK-091..101 (Anas: tokens, Geist, components)

## Plan
- [ ] Plan written in this file (required for amber and red)

Steps:
1. [ ] Read SPEC-016 section 4 and ADR-011; list what SPEC-048 replaces
2. [ ] Write the ADR and add its row to docs/adr/README.md
3. [ ] Add the supersession notes; seed DECISIONS.md
4. [ ] Run validate_docs

Files to create or change:
- docs/adr/ADR-<next>-accrued-design-system.md
- docs/adr/README.md (index row)
- docs/specs/SPEC-016-ui-foundation-and-first-screens.md (supersession note)
- packages/ui/src/tokens/DECISIONS.md

Tests to write (mapped to ACs):
- AC-12 -> validate_docs passes; ADR and SPEC-048 cross-reference; SPEC-016 section 4 marked superseded

## Definition of done
- [ ] All listed ACs have passing tests or checks that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] No secrets or real client data committed (public repo)
- [ ] No new dependencies, or each one listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation (N/A for this task unless it adds either)
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals (N/A unless it adds any)
- [ ] Module README and relevant docs updated
- [ ] Decisions below recorded; ADR raised where needed

Commands:
```
make check
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — task file written from the epic (SU-14); nothing built yet.
- 2026-10-20 (SU-24): ADR-155 (P-03) accepted; SPEC-048 records that it supersedes SPEC-016 §4 (SPEC-016 not edited); packages/ui/src/tokens/DECISIONS.md seeded with DEC-11, DEC-15, DEC-109 and the open line-height item.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- 

## Questions for the human
- [ ] 

## Handoff
- **Current state:** not started
- **Exact next step:** step 1 of the plan
- **Uncommitted or partial work:** none
- **Known failing checks:** none
- **Open issues:** none
