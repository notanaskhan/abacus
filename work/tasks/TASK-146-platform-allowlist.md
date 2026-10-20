---
id: TASK-146
title: "Q-01-T05 · Platform allowlist PR (protected): workos approved (DEC-22); containers clamav/clamav, aws-otel-collector and the Python base image; a terraform section (terraform, hashicorp/aws) enforced by check_dependencies; @sentry/browser; types-boto3 extras kms, sesv2, secretsmanager, ssm, sqs"
spec: SPEC-050
acceptance_criteria: [AC-9]
risk_zone: red
status: todo
epic: Q-01
plan_key: Q-01-T05
branch: task-146-platform-allowlist
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
One protected PR adds every row with its reason, and check_dependencies enforces the new terraform section.

## Scope
**In**
- Add to the dependency allowlist: `workos` approved (DEC-22); containers `clamav/clamav`, `aws-otel-collector` and the Python base image; a `terraform` section (`terraform`, `hashicorp/aws`); `@sentry/browser`; `types-boto3` extras `kms`, `sesv2`, `secretsmanager`, `ssm`, `sqs`
- Extend `check_dependencies` to enforce the terraform section
- Give every row its reason

**Out**
- Using any of the new dependencies
- Other allowlist changes

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-9; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §0 (decisions); §3 F3 (adapters); §9 row Q-01-T05
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T05
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- Code: `docs/architecture/dependency-allowlist.yaml` (protected), `check_dependencies`
- Protected paths: `docs/architecture/protected-paths.md`

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is red)

Steps:
1. [ ] Add each row with its reason
2. [ ] Add the terraform section and extend `check_dependencies`
3. [ ] Add a test that the check fails for an unlisted terraform provider
4. [ ] Run `make check`; merge on green

Files to create or change:
- docs/architecture/dependency-allowlist.yaml
- tooling for `check_dependencies`
- its test

Tests to write (mapped to ACs):
- AC-9 → unit: `check_dependencies` rejects an unlisted terraform provider and accepts `hashicorp/aws`

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
- Protected paths: no approvals needed under the solo amendment; the builder edits and merges after `make check` passes.
- No dependency in this row is used until its own task.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Open the allowlist file and add the rows.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
