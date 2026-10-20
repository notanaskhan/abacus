---
id: TASK-143
title: "Q-01-T02 · TASK-014 plan rewritten as 'Staging and production on AWS through Terraform' plus ADR drafts P-55 AWS topology (ADR-130) and P-54 authentication and sessions (ADR-129) for Decision Day"
spec: SPEC-050
acceptance_criteria: [AC-7]
risk_zone: red
status: todo
epic: Q-01
plan_key: Q-01-T02
branch: task-143-task-014-plan-adrs
created: 2026-10-20
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Solo edition: one builder, no approvals, no reviewers to wait for (`docs/plan/AMENDMENT-solo.md`).
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan below into this file first, then build.
> - If scope must change, add it to *Questions for the human* and carry on with the plan's proposed option.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.
> - Region is us-east-2 (DEC-03). Terraform apply is run by the builder by hand, never from a session; a session runs `fmt`, `validate`, `tflint`, `trivy config` and read-only `plan` only.
> - Never write an amount; refer to "the DEC-03 envelope".

## Objective
The TASK-014 plan is rewritten in its task file and both ADR drafts are open by Thu Oct 22 with the builder as decider.

## Scope
**In**
- Rewrite the plan in `work/tasks/TASK-014-staging-deploy.md` as 'Staging and production on AWS through Terraform'
- Draft ADR P-55 AWS topology (ADR-130) and P-54 authentication and sessions (ADR-129) with the builder as decider
- Record DEC-03 and DEC-22 in `docs/product/decision-log.md` on Fri Oct 23 using the plan's proposed options

**Out**
- Any infrastructure change
- ADR text beyond what the plan specifies

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-7; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §0 (decisions and ADRs to accept first); §3 F1; §9 row Q-01-T02; §11 R3
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T02
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- ADRs: ADR-087, ADR-088; drafts P-55 and P-54
- Code: `work/tasks/TASK-014-staging-deploy.md`, `docs/adr/` (new files for ADR-129 and ADR-130)

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is red)

Steps:
1. [ ] Read TASK-014 as it stands and rewrite its plan section
2. [ ] Draft the two ADRs with context, decision, consequences, deciders and risk zone red
3. [ ] Mark both open by Thu Oct 22; accept per the plan's dates (P-55 by Fri Oct 30)

Files to create or change:
- work/tasks/TASK-014-staging-deploy.md (plan section)
- docs/adr/ADR-129-*.md (new)
- docs/adr/ADR-130-*.md (new)
- docs/product/decision-log.md

Tests to write (mapped to ACs):
- AC-7 → doc check: TASK-014 plan titled 'Staging and production on AWS through Terraform'; both ADR drafts exist with the builder as decider; `validate_docs` passes

## Definition of done
- [ ] All listed ACs have passing tests (or recorded manual evidence for apply-dependent checks) that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies beyond the allowlist rows listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] `terraform apply` was run by the builder by hand where the task needs it, never from a session; plan output is in the progress log
- [ ] Module README and relevant docs updated
- [ ] Decisions below recorded; ADR raised where needed

Commands:
```
make check
```

## New dependencies
| Package | Version | Why | Decision |
|---|---|---|---|
| none | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — Task file written at kickoff (SU-14). No work started.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- Depends on F-02-T02 (ADR reservations). Use the next free ADR numbers on main if ADR-129 or ADR-130 are taken.
- Region is us-east-2 (DEC-03).

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Open TASK-014 and rewrite its plan, then draft P-55 and P-54.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
