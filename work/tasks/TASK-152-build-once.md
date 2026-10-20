---
id: TASK-152
title: "Q-01-T11 · Build once (ADR-088): build.yml on push to main builds the image once (digest, SBOM, provenance, Inspector scan) into ECR, builds each SPA entry present into shared-artifacts/web/<sha>/ with a SHA-256 manifest, writes release.json, and rebuilds the base image weekly"
spec: SPEC-050
acceptance_criteria: [AC-19]
risk_zone: red
status: todo
epic: Q-01
plan_key: Q-01-T11
branch: task-152-build-once
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
Two runs on one SHA yield one digest, every deploy input references digests only, and a fixable critical Inspector finding marks the release unpromotable.

## Scope
**In**
- `build.yml` on push to main: build the image once (digest, SBOM, provenance, Inspector scan) into ECR
- Build each SPA entry present into `shared-artifacts/web/<sha>/` with a SHA-256 manifest
- Write `release.json` with git_sha, image_digest, spa_manifest_sha256, alembic_head, openapi_sha256, infra_sha
- Rebuild the base image weekly

**Out**
- Deploying anywhere (T18)
- A per-merge deploy

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-19; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §3 F5 (build once); §9 row Q-01-T11; §10 Tests and gates
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T11
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- ADRs: ADR-088, ADR-090, ADR-089
- Code: `.github/workflows/build.yml`, `backend/Dockerfile`, `infra/envs/shared`

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is red)

Steps:
1. [ ] Write `build.yml` using OIDC; push by digest
2. [ ] Add the SPA manifest and `release.json` steps
3. [ ] Add the Inspector gate and the weekly base rebuild
4. [ ] Run twice on one SHA and compare digests

Files to create or change:
- .github/workflows/build.yml (new)
- scripts to compute the manifest and release.json

Tests to write (mapped to ACs):
- AC-19 → CI: two runs on one SHA yield one digest; release.json references digests only; a fixable critical Inspector finding blocks promotion

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
- Depends on Q-01-T06, Q-01-T07 and F-01-T06.
- Per the working agreements, a push builds; it does not deploy.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Write the build job after TASK-147 and TASK-148 are done.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
