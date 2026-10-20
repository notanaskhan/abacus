---
id: TASK-148
title: "Q-01-T07 · Terraform envs/shared: ECR (immutable tags, scan on push, replication to production and us-west-2), abacus-shared-artifacts, -previews (14-day expiry) and -design-baselines with a CI read role for F-05, Route 53 zones, GitHub OIDC deploy roles per environment, weekly git bundle backup"
spec: SPEC-050
acceptance_criteria: [AC-11, AC-12]
risk_zone: red
status: todo
epic: Q-01
plan_key: Q-01-T07
branch: task-148-terraform-shared
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
Shared applies from CI on merge, F-05's CI reads the baselines bucket through OIDC, and ECR refuses a tag overwrite.

## Scope
**In**
- `infra/envs/shared`: ECR with immutable tags, scan on push, replication to production and us-west-2
- Buckets `abacus-shared-artifacts`, `abacus-shared-previews` (14-day expiry) and `abacus-shared-design-baselines` with a CI read role for F-05
- Route 53 zones; GitHub OIDC deploy roles per environment; weekly git bundle backup
- Every bucket private, TLS-only, versioned and SSE-KMS with a platform key

**Out**
- Staging and production environments
- Running apply from a session

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-11, AC-12; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §3 F2 (environments from Terraform), F5; §9 row Q-01-T07; §10 R0 bullet 1
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T07
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- ADRs: ADR-087, ADR-088
- Code: `infra/envs/shared/`, `infra/modules/`

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is red)

Steps:
1. [ ] Write the modules and the shared composition
2. [ ] Plan read-only; the builder applies by hand
3. [ ] Verify an ECR tag overwrite is refused
4. [ ] Verify F-05's role can read the baselines bucket through OIDC

Files to create or change:
- infra/envs/shared/*.tf (new)
- infra/modules/* (ECR, bucket, OIDC role)
- infra/tests/ plan assertions

Tests to write (mapped to ACs):
- AC-11 → manual + plan assertion: ECR immutable tags and replication; a tag overwrite is refused
- AC-12 → plan assertion: buckets private, TLS-only, versioned and SSE-KMS; previews expire at 14 days; baselines readable through OIDC

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
- Terraform apply and every console step are run by the builder by hand, never from a session.
- Depends on Q-01-T03.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Write the ECR and bucket modules and plan the shared environment.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
