---
id: TASK-151
title: "Q-01-T10 · ADR drafts P-45 unauthenticated operational routes, P-64 malware scanning service and P-67 observability and on-call vendors (numbers taken as the next free ADR number on main)"
spec: SPEC-050
acceptance_criteria: [AC-18]
risk_zone: red
status: in-review
epic: Q-01
plan_key: Q-01-T10
branch: task-151-ops-adr-drafts
created: 2026-10-20
updated: 2026-10-25
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
All three drafts are open by Fri Oct 30 with their numbers recorded in docs/adr/backlog.md the day drafting starts and accepted by Fri Nov 13, with P-45 defining the exception list that P-01 and P-08 extend.

## Scope
**In**
- Draft ADR P-45, P-64 and P-67 and record their numbers in `docs/adr/backlog.md` the day drafting starts
- Define P-45's public-route exception list that P-01 and P-08 extend
- Accept all three by Fri Nov 13

**Out**
- Implementation of the routes (T16)
- P-65 and P-66 (T22)

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-18; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §0 (decisions and ADRs); §3 F4, F6; §9 row Q-01-T10; §11 R7, R8
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T10
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- ADRs: ADR-093, ADR-098; `docs/adr/backlog.md`

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is red)

Steps:
1. [ ] Mint three numbers (next free on main) and record them in the backlog
2. [ ] Draft each ADR; P-45 lists exactly `/healthz` and `/readyz`
3. [ ] Accept by Fri Nov 13; if rejected, turn the topic into a SPEC inside Q-01 (plan R8)

Files to create or change:
- docs/adr/ADR-NNN-*.md (three new)
- docs/adr/backlog.md

Tests to write (mapped to ACs):
- AC-18 → doc check: three drafts open by Fri Oct 30 with numbers in the backlog; accepted by Fri Nov 13; P-45 defines the exception list

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
- `2026-10-25` — S8b verification. The three drafts are on main as `proposed` since 2026-10-20 with their numbers in `backlog.md`: P-45 = ADR-152, P-64 = ADR-153, P-67 = ADR-154 (AC-18's "open by Fri Oct 30"). ADR-152 defines the ROUTE-001 exception list (`/healthz`, `/readyz`, portal branding and logo) and says later proposals (P-01, P-08) extend it through their own ADRs (AC-18's last clause). Acceptance by Fri Nov 13 is the decider's; none is marked accepted here. No change needed.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- Depends on F-02-T02.
- Other sessions edit `docs/adr/` at setup; start after they finish.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** three ADRs proposed on main; drafting part of AC-18 met.
- **Exact next step:** accept ADR-152, ADR-153 and ADR-154 by Fri 13 Nov.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
