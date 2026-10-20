---
id: TASK-128
title: "F-05-T02 · Allowlist bundle #1: Fontsource Geist/Geist Mono/Arimo/Gelasio, react-table, react-virtual, Radix overlay packages, packages/ui exports map"
spec: SPEC-048
acceptance_criteria: [AC-13]
risk_zone: red
status: done
epic: F-05
plan_key: F-05-T02
branch: task-128-allowlist-bundle-1
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
One protected PR adds the allowlist rows, package.json and lockfile changes installed by a founder by hand, and check_dependencies passes.

## Scope
**In**
- Add allowlist rows for @fontsource/geist, geist-mono, arimo, gelasio (exact names confirmed at install), @tanstack/react-table, @tanstack/react-virtual and the Radix overlay packages
- Update package.json files and lockfile; add the packages/ui exports map

**Out**
- Removing Source Sans 3 and Newsreader (F-05-T34)
- Using the new packages (T04 onward)

## Context to load
- Spec: `docs/specs/SPEC-048-design-system-core.md` (sections 5 and Task map; ACs AC-13)
- Epic: `docs/plan/epics/F-05.md`: F-05 §0 (DEC-16 dependency batch); F-05 §4/§5 protected-file table lines for dependency-allowlist.yaml and package.json (rows citing F-05-T02); F-05 §10 item 7; F-05 §11 R6, Q5
- Task row: `docs/plan/epics/F-05.tasks.csv`, `F-05-T02`
- Process: `docs/plan/AMENDMENT-solo.md`
- Prior work: TASK-091..101 (Anas: tokens, Geist, components)

## Plan
- [ ] Plan written in this file (required for amber and red)

Steps:
1. [ ] Confirm exact Fontsource package names and versions (pnpm minimum release age, epic R6)
2. [ ] Edit docs/architecture/dependency-allowlist.yaml
3. [ ] Install with pnpm by hand; commit lockfile
4. [ ] Run check_dependencies

Files to create or change:
- docs/architecture/dependency-allowlist.yaml
- packages/ui/package.json
- apps/web/package.json
- pnpm-lock.yaml

Tests to write (mapped to ACs):
- AC-13 -> check_dependencies passes with the new rows; unlisted package fails (existing test)

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
| (listed in the allowlist change) | exact | SPEC-048 AC-13 | builder |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — task file written from the epic (SU-14); nothing built yet.
- 2026-10-20 (SU-21): allowlist bundle #1 landed: workos and @workos-inc/authkit-react approved (DEC-22); @sentry/browser; types-boto3 extras kms, sesv2, secretsmanager, ssm, sqs; containers clamav/clamav, aws-otel-collector, python; a terraform section (terraform, hashicorp/aws) enforced by check_dependencies with tests first; @fontsource/arimo and gelasio, @tanstack/react-table and react-virtual; packages/ui exports map (., theme.css, tokens/*, fonts/*, specimens). Radix overlays are covered by the existing @radix-ui/* row. check_dependencies and make check-fast green.

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
