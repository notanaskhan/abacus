---
id: TASK-1236
title: Build once, staging train deploy, production release path and rollback, with independent tests (Q-01-T11, Q-01-T18, Q-01-T34, Q-01-T44)
spec: SPEC-050
acceptance_criteria: [AC-19, AC-26]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T11; Q-01-T18; Q-01-T34; Q-01-T44
branch: s8b-platform-ops
created: 2026-10-25
updated: 2026-10-25
---

## Objective
SPEC-050 AC-19 (build once: one digest per SHA, digests only, a fixable critical or high Inspector finding makes a release unpromotable, weekly base refresh), AC-26 (one staging deploy per window, concurrency plus the SSM deploy lock, pre-flight replay and `alembic heads`, migrate as the owner with `lock_timeout=5s`, workers before the API, circuit breaker and alarm rollback, SPA upload order and three-path invalidation, per-environment `runtime-config.json`, smoke, release record, `make deploy-lock`), Q-01-T34 (release PR on `deploy/production/release.json`, `deploy-production.yml` with the staging-verified, replay and Inspector gates, the lock and the staging sequence, canary smoke; `rollback.yml` re-points the previous digest and bundle and never downgrades; production ops requests through `deploy/production/ops-requests/`), Q-01-T44 (independent tests: deploy-lock exclusion, digest-only references, the gates, rollback to the previous digest and bundle, drill detection).

## Plan (red zone)
- **Tool:** `abacus_tools/release.py`: `manifest` (SHA-256 manifest of a built SPA), `record` (release.json: `git_sha`, `image_digest`, `spa_manifest_sha256`, `alembic_head`, `openapi_sha256`, `infra_sha`), `check` (digests only, the six keys, optional `inspector_exception` and `infra_applied_sha` on a production release), `inspector` (fixable critical and high findings from `aws inspector2 list-findings` output), `gate` (production: staging-verified record, replay record, Inspector or a recorded exception, infra applied by hand when `infra_sha` changed), `runtime-config` (contract 3.2), `ops-request` (an allowlisted command file).
- **Workflows (written and unit-tested, never run here):** `build.yml` (push to `main`; an existing tag reuses its digest, so a second run on one SHA builds nothing; BuildKit SBOM and provenance; the Inspector record; each SPA entry present into `web/<sha>/` with its manifest; `releases/<sha>/release.json`; a weekly job opens a PR when `python:3.12-slim` has a newer digest); `deploy-staging.yml` (workflow_dispatch only: the window job or "Ship batch"); `deploy-production.yml` (a merge that changes `deploy/production/release.json`; a placeholder record skips); `rollback.yml` (workflow_dispatch; 15-minute timeout; no migrate step); `ops-task.yml` (staging on dispatch; production on a merged ops-request file). Terraform apply stays by hand (SPEC-050 AC-6): a deploy whose `infra_sha` changed stops until the builder records it applied.
- **Deploy lock:** `make deploy-lock ENV=<env>` (read only); F-01's `db_guard` refuses while the lock of `ABACUS_DEPLOY_LOCK_ENV` is held.
- **Files:** `deploy/production/release.json` (placeholder: `git_sha` null), `deploy/production/README.md`, `deploy/production/ops-requests/README.md`; `make release-pr SHA=<sha>`.
- **Tests:** `tests/unit/tools/test_release.py`, `tests/unit/tools/test_deploy_workflows.py` (shape of the five workflows), `tests/unit/tools/test_q01t44_release_paths_independent.py` (T44); the db_guard lock check is in the T44 file.
- **Rollback:** revert; nothing runs these workflows until their environment variables exist.

## Progress log
- 2026-10-25: plan written.
- 2026-10-25: built. `abacus_tools/release.py`; `deploy/scripts/release.sh` (render task definitions by digest, run one-off tasks, roll services with the circuit breaker and alarm rollback, publish the SPA in order, record the release); `build.yml`, `deploy-staging.yml`, `deploy-production.yml`, `rollback.yml`, `ops-task.yml`; `deploy/production/{release.json,README.md,ops-requests/README.md}`; `make deploy-lock`, `make release-pr`; `db_guard` honours `ABACUS_DEPLOY_LOCK_ENV`. Decisions: Terraform apply stays by hand (SPEC-050 AC-6 over the epic's "infra apply when infra_sha changes"): staging needs the dispatch input `infra_applied`, production needs `infra_applied_sha` in the release PR. The weekly base rebuild is a PR bumping the pinned `python:3.12-slim` digest (build once holds: the merge builds it once). Staging-verified, replay and Inspector facts live beside the release in `s3://abacus-shared-artifacts/releases/<sha>/` so a later staging deploy does not erase them. Tests: `tests/unit/tools/test_release.py` 19, `test_deploy_workflows.py` 13, `test_q01t44_release_paths_independent.py` 15 (T44; same-session authorship, so ADR-078 independence is nominal), `test_db_guard.py` unchanged and green; `infra/tests` 144 passed.
- Human to-dos before any of it runs: Terraform for ECR `abacus-backend` (immutable tags, enhanced scanning), `abacus-shared-artifacts`, a shared-account build role (`AWS_BUILD_ROLE`, push to ECR, read/write `releases/` and `web/`, `inspector2:ListFindings`) and per-environment deploy roles (ECS register/update/run, `iam:PassRole` on the task roles, S3 web buckets, CloudFront invalidation, SSM `/abacus/<env>/{deploy-lock,release,release-previous,runtime-config/*}`, read of `releases/*`); repository variables `AWS_BUILD_ROLE`, `ECR_REPOSITORY`, optional `IMAGE_PLATFORM`; GitHub environments `staging` and `production` with the variables listed in each workflow's header; task definitions whose containers are named `migrate` and `ops`; SSM runtime-config parameters (`oidc_authority`, `oidc_client_id`, `portal_base_domain`, optional `sentry_dsn`); optional secret `SENTRY_AUTH_TOKEN` and variable `SENTRY_ORG`; the deploy smoke config (Q-01-T32) before the first staging deploy.
