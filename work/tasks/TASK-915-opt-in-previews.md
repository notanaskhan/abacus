---
id: TASK-915
title: Opt-in PR previews behind a cookie-gated CloudFront host (Q-01-T49)
spec: SPEC-050
acceptance_criteria: [AC-12, AC-22]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T49
branch: TASK-915-opt-in-previews
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"A push without the label builds nothing, a labelled PR gets a private URL that answers 403 without the founder cookie, and closing the PR deletes the prefix" (Q-01-T49; D-OPS-13; chapter 06 section 2.7; Q-01 F5).

## Plan
- `.github/workflows/preview.yml`, on `pull_request` only (`labeled`, `unlabeled`, `synchronize`, `reopened`, `closed`):
  - `build` runs only while the PR carries `preview` (and, on a `labeled` event, only when the label added is `preview`), for this repository's branches only: `vite build --mode fixtures` with `VITE_FIXTURES=1` and the gallery on, upload to `s3://abacus-shared-previews/pr-<n>/` (hashed assets immutable, the rest `no-cache`, so no invalidation), one updatable PR comment with the link;
  - `delete` runs on closing a labelled PR or removing the label: `aws s3 rm` of the prefix;
  - OIDC into `abacus-ci-previews` (repository variable `AWS_PREVIEW_ROLE`), no secrets; both jobs skip with a notice while `AWS_PREVIEW_ROLE` or `PREVIEW_HOST` is unset.
- `infra/modules/previews` (used by `infra/envs/shared/previews.tf`):
  - the bucket: private, TLS-only, versioned, SSE-KMS with its own key, 14-day expiry, noncurrent versions after 1 day;
  - CloudFront with OAC and a viewer-request CloudFront Function (`gate.js`) that answers 403 unless the gate cookie equals `gate-key` in a KeyValueStore. The key is put by hand, so it is in neither git nor state;
  - `/__preview/login?k=` sets the gate cookie (the founder-only link); `/__preview/pr/<n>` selects the PR; other paths are rewritten to `pr-<n>/` with SPA fallback. The bundle stays the plain fixture build at the root path, so the app needs no base-path change;
  - the CI role: trusted for `repo:notanaskhan/abacus:pull_request`, limited to list, put and delete under `pr-*` plus the bucket key.
- Rollback: remove the `preview` label from open PRs, delete `preview.yml`, then destroy `module.previews` by hand.

## What changed
- As planned. `infra/tests/test_previews.py` (14 tests) evaluates both job conditions against the pull_request events GitHub sends: no label means no job; another label means no rebuild; forks never run; close or unlabel means delete only. It also holds the fixture build, the prefix, the pinned actions, the gate function and the 14-day expiry. The gate function was exercised locally under Node with a stubbed store: no cookie, wrong key, empty store and a malformed PR cookie all answer 403.
- `infra.yml` now also runs on changes to `preview.yml`, so the test runs on every change to the workflow. Fixed `role-to-arn` to `role-to-assume` in its two `configure-aws-credentials` steps. The action has no `role-to-arn` input, so once a plan role variable was set, the plan and drift jobs would have run with no credentials.
- The user's opt-in rule: there is no `vercel.json` and no other hosted preview in the repo. `ci.yml` runs checks on push, but it builds no deployable preview. Before this task, nothing built previews at all; the label is now the only trigger.
- Q-01-T07 (the rest of `envs/shared`) has not landed. This task creates only `abacus-shared-previews` and its host, and T07 adds the other shared resources beside them.

## Not done (needs the builder)
- `terraform apply` of `infra/envs/shared`; no session runs it.
- The gate key put into the KeyValueStore; the repository variables `AWS_PREVIEW_ROLE` and `PREVIEW_HOST`; the `preview` label; the live 403 and delete check. All steps are in `infra/README.md`, "PR previews".

## Progress log
- 2026-10-23: `terraform fmt -check` and `validate` (`envs/shared`, no backend, no credentials), `infra/tests` (84 passed, 1 skipped as before: no plan JSON), and a local fixture build all pass.
