---
id: RB-01
title: Deploy and rollback
owner: builder
alarms: [SLO-01, SLO-10, deploy-rollback]
last_rehearsed: never
rehearse_by: 2026-11-13
---
# RB-01 · Deploy and rollback

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 to SEV1 |
| Linked from | SLO-01 fast and slow burn, SLO-10 (canary failed twice), an ECS deployment rollback |
| SLO affected | SLO-01, SLO-10 |
| Kill switches that apply | none needed for a code rollback; read-only mode (Q-01-T37) if a release corrupts writes |
| Rehearse by | R0 (Fri Nov 13, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

How code reaches an environment (Q-01-T11, T18, T34): `build.yml` builds one image per SHA on every push to `main`; `deploy-staging.yml` is dispatched once per merge window; production changes only by merging a PR that edits `deploy/production/release.json`. This runbook covers a normal deploy, a deploy that fails, and putting the previous release back.

Release-specific one-off steps (a secret to set before the image starts, a migration's up/down/up on a staging copy, a backfill per tenant after the deploy) are listed per release in `docs/runbooks/demo-tenant.md` sections 4 and 5; S9's are the run-record pepper (#422), 0172 on a copy (#424) and the masked-rendition backfill (#419).

## 1. Recognise it
- A deploy run is red (GitHub Actions, `deploy-staging` or `deploy-production`), or a step reports "rolled back" (the ECS circuit breaker or an alarm rolled a service back).
- SLO-01 burns right after a deploy, or the canary (SLO-10) fails twice after one.
- Check the time of the last deploy against the start of the burn: `make deploy-lock ENV=<env>` shows a deploy in flight; `aws ssm get-parameter --name /abacus/<env>/release` shows the current release and when it landed. If the burn started before the deploy, this is not the scenario: RB-06 (load) or RB-23 (workflow engine).

## 2. Contain
Put the previous release back: Actions, `rollback`, Run workflow, choose the environment and give a reason (the ticket). Or:

```
gh workflow run rollback.yml -f environment=<staging|production> -f reason="RB-01: <ticket>"
```

It takes the deploy lock, re-points the workers and then the API to the previous image digest (with the same circuit breaker), publishes the previous SPA bundle and its `runtime-config.json`, and swaps the release records. It never runs a migration. Its job times out at 15 minutes.

If the deploy itself is still running and is the cause: cancel it in Actions. The lock step releases the lock on cancellation; the migrate step, if it already ran, stays applied (expand-only, step 6).

## 3. Preserve
Before anything else changes: the failing run's URL, the release records (`/abacus/<env>/release` and `release-previous`), the ECS service events (`aws ecs describe-services --cluster <cluster> --services <service> --query 'services[0].events[:20]'`), and the API's error-rate graph for the window. No request bodies or client content in the ticket.

## 4. Assess
- Is it the code (the previous release is healthy after rollback) or the environment (both are unhealthy: RB-06, RB-23, RB-24)?
- Did the release include a migration? If so, the rolled-back code runs against the expanded schema: that is safe only because every migration is expand-only within a release (P-38). If a migration was not expand-only, this is SEV1: stop and open RB-02.
- Which firms saw errors (tenant UUIDs from the per-firm dashboard; never names).

## 5. Notify
Production: post on the status page (`docs/ops/incident-templates.md`, SEV2 template) when customers saw errors for more than five minutes. Staging: no notice.

## 6. Recover
1. Fix forward: a new PR with the fix, merged in the next window (or as a production-broken exception, CLAUDE.md working agreement 1).
2. Staging: dispatch `deploy-staging.yml` for the new SHA (`gh workflow run deploy-staging.yml -f sha=<sha>`). If its `infra_sha` changed, apply `infra/envs/staging` by hand first and dispatch with `-f infra_applied=true` (SPEC-050 AC-6).
3. Production: `make release-pr SHA=<sha>` once staging verified it; merge after the gates pass. A held lock makes the run wait up to 30 minutes; a stale lock (`make deploy-lock` says `stale`) is released by an ops request naming the holder's run: `python -m abacus_tools.deploy_lock release --env <env> --run-ref <the holder's run url>`.
4. A Temporal workflow change that misbehaves rolls forward with a new `workflow.patched` branch (ADR-090), never by deleting histories.

## 7. Verify
The rollback run is green; `/abacus/<env>/release` names the previous SHA with `rolled_back_by`; the API's 5xx rate is back under the SLO-01 burn threshold; two consecutive canary runs pass (SLO-10).

## 8. Review
Open the blameless review. Typical actions: a test that would have caught the change, a smoke step, an alarm that fires sooner.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
