---
id: TASK-147
title: "Q-01-T06 · Container image: backend/Dockerfile (multi-stage, uv sync --locked --no-dev, Python 3.12-slim by digest, non-root, read-only root filesystem with tmpfs /tmp), .dockerignore, entrypoints for api, worker --classes, migrate, bootstrap and ops"
spec: SPEC-050
acceptance_criteria: [AC-10]
risk_zone: red
status: todo
epic: Q-01
plan_key: Q-01-T06
branch: task-147-container-image
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
The image builds reproducibly, runs non-root on a read-only root filesystem, and the kernel/isolation child limits pass in a Linux container test.

## Scope
**In**
- `backend/Dockerfile`: multi-stage, `uv sync --locked --no-dev`, Python 3.12-slim by digest, non-root, read-only root filesystem with tmpfs `/tmp`
- `.dockerignore`
- Entrypoints for api, worker `--classes`, migrate, bootstrap and ops

**Out**
- Pushing to ECR (T11)
- Task definitions (S1)

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-10; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §3 F5 (build once); §9 row Q-01-T06; §10 Tests and gates
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T06
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- ADRs: ADR-088, ADR-052
- Code: `backend/Dockerfile` (new), `backend/pyproject.toml`, `kernel/isolation`

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is red)

Steps:
1. [ ] Write the Dockerfile and pin the base image by digest
2. [ ] Add the entrypoints
3. [ ] Add a Linux container test for the isolation child limits and the read-only root filesystem
4. [ ] Build twice and compare digests

Files to create or change:
- backend/Dockerfile (new)
- backend/.dockerignore (new)
- backend/tests/ container test (new)

Tests to write (mapped to ACs):
- AC-10 → integration: reproducible build; runs non-root on a read-only root filesystem; kernel/isolation child limits pass in a Linux container

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
- Depends on Q-01-T05.
- Do not run the container against a hosted database.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Write the multi-stage Dockerfile.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
