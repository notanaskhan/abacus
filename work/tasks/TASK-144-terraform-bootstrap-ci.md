---
id: TASK-144
title: "Q-01-T03 · Terraform bootstrap and infra CI: infra/bootstrap (state bucket with native S3 locking, GitHub OIDC providers, read-only plan role, main-only apply role), module skeleton, pinned versions and .terraform.lock.hcl, infra.yml (fmt, validate, tflint, trivy config, per-environment plan comment, nightly drift issue)"
spec: SPEC-050
acceptance_criteria: [AC-6]
risk_zone: red
status: todo
epic: Q-01
plan_key: Q-01-T03
branch: task-144-terraform-bootstrap-ci
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
An infra-only PR receives a plan comment from the read-only role, a public-bucket fixture fails trivy, and no person or session holds apply credentials.

## Scope
**In**
- `infra/bootstrap`: state bucket with native S3 locking, GitHub OIDC providers, read-only plan role, main-only apply role
- Module skeleton, pinned versions and `.terraform.lock.hcl`
- `infra.yml`: `fmt -check`, `validate`, `tflint`, `trivy config`, per-environment plan comment, nightly drift issue
- Deny `terraform apply/destroy` for sessions in `.claude/settings.json`; `guard_bash.py` blocks `terraform state` and `aws --profile *prod`

**Out**
- Environment compositions (T07 and later)
- Running apply from a session or CI without the builder

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-6; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §3 F1 (last bullet: Terraform and infra.yml); §9 row Q-01-T03; §10 Tests and gates
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T03
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- ADRs: ADR-087, ADR-088
- Code: `infra/bootstrap/`, `infra/modules/`, `.github/workflows/infra.yml`, `.claude/settings.json`, `guard_bash.py`
- Reference pattern to copy: `.claude/skills/infra-terraform/SKILL.md` arrives in Q-01-T57; until then follow chapter 06 §1

## Plan
- [x] Plan written into this file before any build step (required for amber and red; zone is red)

SU-20 session plan (2026-10-20, branch `setup/su-20`; no apply, no AWS calls, no commit):
1. Layout: `infra/{bootstrap,modules,envs/{shared,staging,production,production-dr},policies}`; `landing-zone/` stays. Envs get backend + provider + README only. Modules are README skeletons.
2. `infra/bootstrap` (Terraform >= 1.10, `hashicorp/aws ~> 6.0`): state bucket in `shared` (versioning, dedicated KMS key with rotation, SSE-KMS, public access block, TLS-only policy, native S3 locking via `use_lockfile` in env backends), GitHub OIDC provider, per-environment read-only plan role (sub `pull_request` and `ref:refs/heads/main`), one apply role per environment trusted only for `ref:refs/heads/main`. Account IDs are variables; outputs are role names only. Lock file for linux_amd64 and darwin_arm64.
3. `.github/workflows/infra.yml`: PR checks (fmt, validate, tflint, trivy config), plan matrix using `vars.AWS_PLAN_ROLE_<ENV>` (skipped with a notice when unset) plus summary comment; nightly drift job with `plan -detailed-exitcode` opening or updating one `infra-drift` issue. No apply. Actions pinned to SHAs; `id-token: write` only on plan jobs.
4. `infra/README.md`: "Terraform bootstrap (SU-20)" section with the one-time commands and where repo variables go. No account IDs.
5. Verify: `terraform init -backend=false`, `fmt -check`, `validate`, `make check-fast`.
Deferred (not in SU-20): trivy fixture bucket (step 4 below), `.claude/settings.json` and `guard_bash.py` edits, tflint/trivy local runs (tools not installed locally; CI runs them).

Steps:
1. [ ] Write the bootstrap module and run the first apply by hand (builder)
2. [ ] Create the OIDC providers and the read-only and main-only apply roles
3. [ ] Write `infra.yml` with the checks and the plan-comment step
4. [ ] Add the fixture bucket that fails trivy; confirm the check fails on it
5. [ ] Confirm sessions hold no apply credentials

Files to create or change:
- infra/bootstrap/*.tf (new)
- infra/modules/ (skeleton)
- .terraform.lock.hcl
- .github/workflows/infra.yml (new)
- .claude/settings.json
- guard_bash.py

Tests to write (mapped to ACs):
- AC-6 → CI: infra-only PR gets a plan comment from the read-only role; public-bucket fixture fails trivy; no session credential can apply

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
terraform fmt -check -recursive infra
terraform -chdir=infra/bootstrap validate
tflint --recursive
trivy config infra
make check
```

## New dependencies
| Package | Version | Why | Decision |
|---|---|---|---|
| none | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — Task file written at kickoff (SU-14). No work started.
- `2026-10-20` — SU-20 session: built infra/ layout, bootstrap, modules/github-oidc, env roots, locks, infra.yml, README section. fmt/validate pass; check-fast passes. tflint/trivy not installed locally (CI runs them). No apply, no AWS calls, nothing committed. Remaining: fixture bucket for trivy, .claude/settings.json deny and guard_bash.py, builder runs bootstrap apply.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- Terraform apply and every console step are run by the builder by hand, never from a session.
- Depends on Q-01-T01 and F-01-T06 (CI rebuild).

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Write the bootstrap module and plan it read-only.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
