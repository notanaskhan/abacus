# Environments

Where Accrued runs, what each environment may hold, and who may change it (ADR-087, ADR-142; Q-01-T57). Settings are `ABACUS_ENVIRONMENT` values in `backend/src/abacus/kernel/config.py`. Infrastructure for each AWS environment is under `infra/envs/<name>/` (`infra/README.md`). No account ID, domain or amount appears here: those live in untracked tfvars, the vault, or the console log in `infra/README.md`.

## Summary

| Environment | `ABACUS_ENVIRONMENT` | Where | Data | Model route | Identity | Email | Changed by |
|---|---|---|---|---|---|---|---|
| Local | `local` | the builder's machine, `make dev` (containers) | the synthetic seed only (`make seed`, Brightwater Hale) | `fake`; a real model only with `allow_real_model_locally` and synthetic firms | local fake OpenID Connect provider | local mailbox | anyone with the repo |
| Test | `test` | CI runners and `make check` | per-test synthetic data in throwaway containers | `fake` | fake | local mailbox | CI |
| Evaluation | `evaluation` | throwaway containers (`abacus_tools.stack`) | the synthetic stack firm | `fake`, or `direct` with the evaluation-only key (`make evals`, costs money) | fake | none | a named builder, by hand |
| PR preview | n/a (static fixture build) | `envs/shared`, `abacus-shared-previews` behind the cookie gate | fixtures only, no backend, no database | none | none | none | the `preview` label (Q-01-T49) |
| Staging | `staging` | `staging` account, us-east-2 (`envs/staging`) | synthetic tenants only, created by `TenantProvisioningWorkflow` with `synthetic = true` | `synthetic_only` until the Bedrock register entry lands (Q-02-T18), then `client_data` on Bedrock for synthetic tenants | WorkOS staging environment | SES; synthetic tenants' mail is rewritten to the sink | `deploy-staging.yml`, one run per batch; Terraform by the builder by hand |
| Production | `production` | `production` account, us-east-2; DR pilot light in us-west-2 (`envs/production`, `envs/production-dr`) | the synthetic canary only before R2; firm data after R2 | Bedrock only for client data (ADR-113); `fake` routes and an Anthropic key are refused at start | WorkOS production environment | SES, per-firm verified domains or the neutral mail domain | the release-manifest PR, then `deploy-production.yml`; Terraform by the builder by hand |
| Sandbox | n/a | `sandbox` account | none, ever (D-OPS-03) | none | none | none | the builder, for console experiments |

## Rules

- **Production data never leaves production** (ADR-087). Restore drills run inside the production account (`drill.yml`, Q-01 F9). Nothing copies production rows, objects or logs into staging, local or a laptop.
- **Never point a local build, migration or seed at a hosted database** (AGENTS.md rule 17). Hosted databases are reached only by ECS one-off `abacus-ops` tasks (`ops-task.yml`, platform-ops contract section 3.5). F-01's `db_guard` refuses an operator action while the deploy lock is held.
- **One staging deploy per batch.** A merge never deploys by itself (DEC-54). Check `gh run list --workflow deploy-staging.yml --status in_progress` before touching staging.
- **No session applies Terraform.** Sessions plan only, through the read-only plan role on the pull request (`.claude/skills/infra-terraform/SKILL.md`).
- **Staging holds synthetic tenants only.** The app role cannot set `synthetic`; only `provision_firm(...)` can (migration 0038 rule, Q-01-T45).
- **Settings refuse to start a hosted environment half-configured.** Outside `local`, `test` and `evaluation`, the key service, keyring, scanner, mail and identity settings are required. `production` also refuses an Anthropic key and a `fake` route. `portal_base_domain` must be a neutral domain (ADR-163).

## Hosts

| Host | Environment | Served by |
|---|---|---|
| `app.<product-domain>` / `app.staging.<product-domain>` | production / staging | the firm distribution (Q-01-T15) |
| `<slug>.<neutral-portal-domain>` | each | the portal multi-tenant distribution, tenant `default` (Q-01-T56) |
| one canary custom domain | staging | the same distribution, tenant `canary`, for pen test 1 (Q-01-T56) |
| `/v1/*` on every host above | each | the internal API load balancer through a CloudFront VPC origin, same origin |
| the preview host | shared | `modules/previews`, cookie-gated |

The neutral portal domain is a setting (`portal_base_domain` in `runtime-config.json`, the API settings and the Terraform tfvars), never a literal in code (ADR-163).

## The staging mail sink

Synthetic tenants never email a real address (F-04-T22, `communications/sink.py`). On staging, every recipient of a synthetic tenant is rewritten to `<local part>@<mail_sink_domain>`. With no sink configured the message is refused and logged without the address. An SES receipt rule on the sink domain delivers into a short-lived bucket (`mail_sink_bucket` under `mail_sink_prefix`), which F-04's mailbox reader reads (`mail.latest()`). The receipt rule and bucket are Q-01-T47's Terraform and are not built yet, so staging has no sink until they are applied.

## Not built yet

Staging and production have no network, database, compute or firm edge in Terraform yet (Q-01-T14, T15, T28, T29). TASK-014 tracks bring-up. The portal edge is written and plans to nothing until its settings exist (`infra/README.md`, "Portal edge").
