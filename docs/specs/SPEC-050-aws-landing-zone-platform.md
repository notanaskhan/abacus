---
id: SPEC-050
title: "Q-01 AWS landing zone, Terraform and platform: sprint 0 and sprint 1 (organisation, state and CI, shared account, production adapters, build once, R0 staging)"
status: approved
owner: builder
risk_zone: red
related_adrs: [ADR-005, ADR-035, ADR-040, ADR-087, ADR-088, ADR-089, ADR-090, ADR-093, ADR-096, ADR-097, ADR-098, ADR-100, ADR-113, ADR-114, ADR-115]
related_specs: [SPEC-000, SPEC-036]
created: 2026-10-20
updated: 2026-10-20
---

> **Instructions for coding agents**
> - Implement only what this spec describes. If anything is ambiguous or contradicts an ADR, record the answer in `docs/product/decision-log.md` or a new ADR using the plan's proposed option, and carry on.
> - Solo edition (`docs/plan/AMENDMENT-solo.md`): one builder. No approver, test author, second signature, merge window or "other founder". Amber and red: write the plan into the task file first, then build. Acceptance tests are written first from this spec and never edited to pass.
> - **Region is us-east-2 (DEC-03).** The only other permitted region is us-west-2 (disaster recovery); the plan's global-service exceptions are in AC-1.
> - **Terraform apply is run by the builder by hand, never from a Claude Code session.** A session writes Terraform and runs `fmt`, `validate`, `tflint`, `trivy config` and a read-only `plan` only. Console steps are done by the builder and logged in `infra/README.md`.
> - Never write an amount: budgets and costs are referenced as "the DEC-03 envelope".
> - Never run a local production build while a hosted build uses the same database.

## 1. Summary
Q-01 builds the AWS foundation: a governed organisation with residency enforced by policy, Terraform for every environment, a container image built once per commit, the fail-closed production adapters (KMS, payload keyring, SES, ClamAV, WorkOS), and the R0 staging environment (M2, Fri Nov 13, 2026). This spec covers its sprint 0 (Mon Oct 19 to Fri Oct 30, M1) and sprint 1 (Mon Nov 2 to Fri Nov 13) rows. Source: `docs/plan/epics/Q-01.md` sections 0, 3, 9, 10 and 11, and `docs/plan/epics/Q-01.tasks.csv`.

## 2. Problem and context
TASK-014 (staging deploy) has been blocked since Oct 6. Without an organisation, state, a build-once pipeline and real adapters, nothing runs outside a laptop, partners cannot be onboarded to synthetic sandboxes, and the real-data gate cannot be met. Residency and "no standing human access" must be facts an auditor can test.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Builder | Runs console steps and every Terraform apply by hand; writes code, tests and runbooks |
| Claude Code session | Writes Terraform, adapters and tests; runs plan-only and `make check`; holds no apply credentials |
| CI (GitHub Actions) | Plan comments, build once, staging train; OIDC roles only |
| AWS accounts | management, log-archive, audit, shared, staging, production, sandbox |

## 4. Goals and non-goals
**Goals**
- Organisation, Identity Center, SCPs, AI-services opt-out and a console log by Fri Oct 30 (M1).
- Terraform state, OIDC and infra CI; the shared account (ECR, artifact buckets).
- Four production adapters plus WorkOS, all failing closed, with acceptance tests written first.
- Build once: one image digest per commit.
- R0 on staging by Fri Nov 13 (M2): staging data plane and compute, operational routes, train deploy, platform tenancy migration, runbooks, runtime config.

**Non-goals**
- Production, DR, observability, canary, kill switches, tenant keys, restore drill, status page (Q-01 sprints 2 to 5).
- Any product screen, feature flag or agent behaviour; Bedrock model evaluation (Q-02).
- Vendor paperwork (F-09): order forms, domain purchase.

## 5. User stories and acceptance criteria
### Story 1: As the builder I want every AWS resource in a governed, US-resident organisation reachable only by short-lived, MFA-bound roles
- **AC-1** Given the organisation root SCPs, when any principal in `staging` or `production` calls a regional API in a region other than us-east-2 or us-west-2, then it is denied; us-east-1 is allowed only for CloudFront, ACM for CloudFront, WAF (`CLOUDFRONT` scope), IAM, Organizations and Bedrock US Geo inference (P-55, R-35). A test call to eu-west-1 is denied by SCP.
- **AC-2** Given Identity Center, when the builder signs in, then passkey or hardware-key MFA is required and the default permission set is `ReadOnly`; `iam:CreateUser` and `iam:CreateAccessKey` are denied everywhere by SCP. Six member accounts (log-archive, audit, shared, staging, production, sandbox) run under Control Tower.
- **AC-3** Given the `BreakGlassAdmin`, `abacus-retention-override` or `abacus-key-custodian` permission set, when it is assigned, then the assignment expires in 4 hours or less, and CloudTrail → EventBridge notifies the builder within 5 minutes. (The plan's other-founder assignment rule is void under the solo amendment.)
- **AC-4** Given the Organizations AI-services opt-out policy at the root, then no AWS AI service may use Accrued content for service improvement; Bedrock model-invocation logging stays off in production (ADR-114).
- **AC-5** Given `infra/README.md`, then every one-time console step (Control Tower enrolment, Identity Center, opt-out policy) is recorded with date and operator, and nothing else is ever done in a console. All of it is recorded by Fri Oct 30 (M1).
- **AC-6** Given Terraform, when any PR touches `infra/**`, then `infra.yml` runs `fmt -check`, `validate`, `tflint`, `trivy config` and a read-only `plan` per environment and comments a summary; an infra-only PR receives a plan comment from the read-only role, a public-bucket fixture fails trivy, and no person or session holds apply credentials (`.claude/settings.json` denies `terraform apply/destroy`; `guard_bash.py` blocks `terraform state` and `aws --profile *prod`). Apply is run by the builder by hand from the main-only apply role.

### Story 2: As the builder I want a plan on record and vendors ready to wire
- **AC-7** Given the TASK-014 plan, then it is rewritten as 'Staging and production on AWS through Terraform' and the ADR drafts P-55 AWS topology (ADR-130) and P-54 authentication and sessions (ADR-129) are open by Thu Oct 22 with the builder as decider.
- **AC-8** Given the technical vendor set-up after F-09 contracts (Temporal Cloud account and staging namespace with API keys in Secrets Manager; WorkOS staging environment; SES production-access request and platform identity; Bedrock US Geo model access and quota requests; Sentry (US) and Better Stack orgs; Route 53 zones for the product and neutral domains), then each item has a dated ticket, every vendor console account is on MFA for the builder, and the neutral domain is delegated to Route 53 by Fri Oct 30.
- **AC-9** Given the platform allowlist PR (protected), then one PR adds every row with its reason: `workos` approved (DEC-22); containers `clamav/clamav`, `aws-otel-collector` and the Python base image; a `terraform` section (`terraform`, `hashicorp/aws`) enforced by `check_dependencies`; `@sentry/browser`; `types-boto3` extras `kms`, `sesv2`, `secretsmanager`, `ssm`, `sqs`; and `check_dependencies` enforces the new terraform section.

### Story 3: As the builder I want one image and one artefact per commit, and a shared account
- **AC-10** Given `backend/Dockerfile` (multi-stage, `uv sync --locked --no-dev`, Python 3.12-slim by digest, non-root, read-only root filesystem with tmpfs `/tmp`, `.dockerignore`, entrypoints for api, worker `--classes`, migrate, bootstrap and ops), then the image builds reproducibly, runs non-root on a read-only root filesystem, and the kernel/isolation child limits pass in a Linux container test.
- **AC-11** Given `infra/envs/shared`, then ECR has immutable tags, scan on push and replication to production and us-west-2, and ECR refuses a tag overwrite.
- **AC-12** Given `infra/envs/shared`, then it creates `abacus-shared-artifacts`, `abacus-shared-previews` (objects expire after 14 days) and `abacus-shared-design-baselines` with a CI read role for F-05, Route 53 zones, GitHub OIDC deploy roles per environment and a weekly git bundle backup; every bucket is private, TLS-only, versioned and SSE-KMS with a platform key; shared applies from CI on merge (run by the builder by hand), and F-05's CI reads the baselines bucket through OIDC.
- **AC-19** Given a push to `main`, then `build.yml` builds the backend image once (BuildKit SBOM and provenance), pushes it to ECR in `shared` by digest, builds each HTML entry present (`index.html` now; `portal.html` from P-08-T07) into `s3://abacus-shared-artifacts/web/<sha>/` with a SHA-256 manifest, and writes `release.json = {git_sha, image_digest, spa_manifest_sha256, alembic_head, openapi_sha256, infra_sha}`. Two runs on one SHA produce one digest and every deploy input references digests only; a fixable critical or high Inspector finding marks the release unpromotable unless the release PR records an exception; the base image is rebuilt weekly.

### Story 4: As the platform I want each fail-closed adapter replaced by a real one that still fails closed
- **AC-13** Given a tenant with a key, when evidence is sealed, then `KmsKeyService.wrap` calls KMS `Encrypt` on the per-object data key with encryption context `{"abacus:tenant": <tenant_id>, "abacus:purpose": "dek"}`; when a different tenant's context is used to unwrap, then KMS refuses and `DecryptionError` is raised (the AAD `abacus-evidence-v1|tenant|fingerprint|key_id` check stays). `key_id(tenant)` stays synchronous and returns the deterministic alias `alias/abacus/tenant/<tenant_id>`; the resolved ARN is recorded on `firms.kms_key_arn` (P-65). Given any KMS error, sealing and opening fail; there is no fallback to `LocalKeyService`, which keeps refusing outside local/test with a loopback S3 endpoint.
- **AC-14** Given `abacus/<env>/temporal/payload-keyring` in Secrets Manager, then the codec loads several key IDs and one current ID; a payload sealed under a retired-but-present ID still decodes; removing a key that histories still use is refused by the rotation runbook (RB-09).
- **AC-15** Given a message that passed `communications/scope.py` and the mechanical body check (no SSN, TIN, account number or tax amount), when it is sent, then `SesTransport` sends through the environment's configuration set with the firm's display name and Reply-To, and message tags carry only `tenant_id` and `message_id` (never an address); given a blocked message, then the SES client is never called.
- **AC-16** Given an upload, when `scan(content)` runs on plaintext in the API before sealing (`evidence/uploads.py`), then `LocalScanner`'s archive-bomb checks run first and `ClamdScanner` streams `INSTREAM` to `scanner.abacus.internal:3310` (`StreamMaxLength 60M`, 30 s timeout); EICAR returns `malware`; any socket error, timeout or unexpected reply returns `unscannable`, which fails closed and shows the existing retryable state. A real clamd testcontainer refuses EICAR and an oversize stream.
- **AC-17** Given `ABACUS_ENVIRONMENT` in `staging` or `production`, then settings validation refuses to start without KMS, keyring, scanner, SES and WorkOS settings; in `production` it also refuses an `anthropic_api_key` (ADR-113: Bedrock only for client data) and a `fake` route. Outside local and test the process refuses to start without KMS and keyring settings.
- **AC-20** Given the acceptance tests for the KMS, keyring, SES and ClamAV adapters written from the P-55 and P-64 text, then they are written before the adapters, fail on today's code, and pass unedited on the adapters, covering wrong tenant, KMS error, key rotation, EICAR, timeout and blocked-body cases.

### Story 5: As the builder I want decisions on record and a contract for consumers
- **AC-18** Given the ADR drafts P-45 unauthenticated operational routes, P-64 malware scanning service and P-67 observability and on-call vendors, then all three drafts are open by Fri Oct 30 with their numbers recorded in `docs/adr/backlog.md` the day drafting starts, and accepted by Fri Nov 13, with P-45 defining the exception list that P-01 and P-08 extend. Numbers are the next free ADR number on `main`.
- **AC-21** Given the platform-ops contract stub `docs/contracts/platform-ops.md` v1 (WorkOS adapter port, `runtime-config.json` schema, deploy-lock command, ops-task commands, `TenantProvisioningWorkflow` inputs and outputs, `platform.api.control_active` and the rule for adding a kill switch, SES identity port), then the stub merges in the first S1 window and each consumer (P-01, P-08, F-04, G-04) is read against it with every signature typed.

### Story 6: As the builder I want R0 staging
- **AC-22** Given `infra/envs/{shared,staging,production,production-dr}`, then each environment is composed only from `infra/modules/*` with environment variables, and the staging data plane applies with no public endpoint: every bucket is private, TLS-only, versioned and SSE-KMS with a platform key; Object Lock is enabled on `abacus-<env>-evidence` (GOVERNANCE default mode, per-object retention) and `abacus-<env>-records` (Object Lock on, no default retention, so P-43 sets COMPLIANCE per object); RDS PostgreSQL 17 is in `data` subnets with no public access, `rds.force_ssl=1`, `log_parameter_max_length=0` and `log_parameter_max_length_on_error=0`; security-group egress is on 443 (plus 3310 to the scanner) only. Given the `app` subnets, when a task resolves a hostname that is not on the DNS Firewall allowlist, then resolution fails; the initial allowlist is Temporal Cloud, WorkOS, the Sentry US ingest, Better Stack heartbeats, `database.clamav.net`, and `api.anthropic.com` in staging only, and AWS APIs resolve to VPC endpoints. The VPC is 10.20.0.0/16 (2 AZ, 1 NAT).
- **AC-23** Given the staging firm host, then it serves the SPA with the CSP header and `/v1` reaches the internal ALB same-origin; the response-headers policy sends HSTS (2 years, `includeSubDomains`), `nosniff`, the referrer policy (portal: `no-referrer`), the permissions policy and the per-build CSP of chapter 04 section 1.4 with minimum TLS `TLSv1.2_2021`; `/readyz` answers 403 at the edge; WAF rules 1 to 7 of chapter 06 section 1.13 run in count mode for two weeks on staging, then block, and WAF logging redacts `authorization` and `cookie`.
- **AC-24** Given `create_app()`, then exactly the routes on the public-route list (P-45) answer without a token: `GET /healthz` (process liveness, no DB) and `GET /readyz` (both app and identity DB roles ping, Temporal reachable, scanner reachable, the platform KMS key usable); ROUTE-001 fails the build for any route outside `AbacusRouter` not on the list. Given the edge, a browser request for `/healthz` or `/readyz` through CloudFront gets 403. Given middleware, JSON bodies over 1 MB and uploads over 50 MB (`MAX_CONTENT_BYTES`) are refused before parsing, a `Host` not matching `trusted_hosts` gets 400, and proxy headers are honoured only from the ALB. CloudFront forwards `Host` as `X-Forwarded-Host` and the API uses it only as a branding hint; tenant resolution still comes from membership or grant (ADR-002, INV-4). `/readyz` fails when a DB role, Temporal, the scanner or the platform KMS key is unreachable.
- **AC-25** Given WorkOS staging, when a synthetic staff user signs in through hosted AuthKit on today's SPA PKCE flow, then `identity/tokens.py` verifies the token against WorkOS JWKS and a token minted by another WorkOS environment is rejected. AuthKit offers Microsoft, Google and email code, requires MFA for non-SSO users, and has no password method (DEC-22). The adapter port (`identity/workos.py`: discovery and JWKS, code exchange, user lookup, session revoke) is what P-01-T09 and P-08-T06 build on.
- **AC-26** Given several approved PRs merged in one window, when the window closes, then exactly one `deploy-staging.yml` run is dispatched for the last green SHA (or "Ship batch" is pressed); a merge never deploys by itself. The deploy takes GitHub `concurrency: deploy-staging` and the SSM parameter `/abacus/staging/deploy-lock`; pre-flight prints `alembic heads` and requires the SHA's replay tests (ADR-090); the `abacus-migrate` task runs `alembic upgrade head` as `abacus_owner` with `lock_timeout=5s`; workers roll before the API, the API with the ECS circuit breaker and alarm-based rollback; hashed assets upload before `index.html`/`portal.html`, then `runtime-config.json`, invalidating only those paths. A held lock blocks a second deploy and F-01's `db_guard`; `make deploy-lock ENV=staging` prints the holder. A failed migration stops the deploy with the old code still serving against the expanded schema.
- **AC-27** Given the migration `00NN_platform_tenancy`, then `firms.region` (CHECK `'us'`), `kms_key_arn`, `kms_key_status`, `kms_replica_verified_at`, `platform_controls`, insert-only `platform_control_changes` and `firm_provisioning_requests` exist, with definers `platform_control_state()`, `set_platform_control()` and `provision_firm()` and an EXECUTE-only `abacus_ops` role in `bootstrap.sql`; the app role reads controls only through the definer, cannot set `synthetic` or `region`, and `schema_check` passes up, down and up. `provision_firm` refuses any region but `us` and records the idempotency key in `firm_provisioning_requests`.
- **AC-28** Given the R0 bring-up on staging (bootstrap task using `bootstrap.sql`, never `bootstrap-local`; first migrate; Temporal namespace with five task queues; WorkOS redirect URIs; SES platform domain DKIM; synthetic tenant Canary & Co through `provision_firm`; first train deploy; `docs/ops/readiness/R0.md`), then every R0 item chapter 06 section 8.2 assigns to Q-01 is checked on Fri Nov 13 with the SPEC-000 walking-skeleton criterion 21 passing on staging (M2).
- **AC-29** Given ADR-098, then each runbook lives in `docs/runbooks/<slug>.md` with frontmatter `id: RB-nn`, `owner`, `alarms`, `last_rehearsed`; by R0: RB-01 deploy and rollback, RB-02 failed migration, RB-24 malware scanner down. Each R0 runbook is rehearsed once on staging with its date recorded, and an alarm without a runbook link fails `validate_docs`.
- **AC-30** Given the ADR drafts P-65 tenant key provisioning and P-66 platform controls and kill switches, then both drafts are open by Fri Nov 13 and accepted by Fri Nov 27 (numbers: next free on `main`).
- **AC-31** Given `app-core/runtime-config.ts` loading `/runtime-config.json` before router boot and `auth/session.ts` reading authority and client ID from it instead of `VITE_OIDC_*`, then one bundle signs in on staging and on the local stack with only `runtime-config.json` changed, and no OIDC authority string is baked into the deployed dist; the `abacus-csp` meta stays for dev and fixture builds while deployed builds rely on the CloudFront header.
- **AC-32** Given acceptance tests for the P-45 routes, middleware and WorkOS adapter, plus IaC plan assertions in `infra/tests` over `terraform show -json` (private buckets, Object Lock, private RDS with `force_ssl`, egress 443 only, no IAM users), then they are written before the code they test, fail before, pass unedited after, and `infra.yml` runs the plan assertions on every infra PR.

## 6. Behaviour and flows
**Happy path**
1. Mon Oct 19: builder creates the AWS organisation and Control Tower by hand and logs each console step (AC-5); opens the allowlist PR (AC-9).
2. Terraform state and OIDC, then infra CI (AC-6); Dockerfile (AC-10).
3. Thu Oct 22: TASK-014 plan and P-55/P-54 drafts (AC-7). Fri Oct 23: DEC-03 and DEC-22 recorded.
4. Week 2: shared account and ECR (AC-11, AC-12); acceptance tests for the four adapters first (AC-20), then the adapters (AC-13 to AC-17); `build.yml` (AC-19). Fri Oct 30 (M1): organisation, state and neutral domain delegation in place (AC-8).
5. S1: staging data and compute, routes and WorkOS, migration, train deploy, bring-up; M2 on Fri Nov 13 (AC-22 to AC-28).

**Alternate paths**
- DEC-03 changes the region or budget: the region SCP is one variable; budget alarms are set after the decision (plan R3).
- Vendor facts unverified: each has a fallback (Temporal in another US region, one distribution per custom domain, staging sink in us-west-2) in plan R6.
- WorkOS staging sign-in blocked: fake OIDC on synthetic staging only (chapter 06 section 7.6).

**State transitions:** N/A (infrastructure; the only entity state is `kms_key_status`, set by sprint 2 work).

## 7. Domain and data changes
- **Entities affected:** `firms` (region, KMS key columns), new `platform_controls`, `platform_control_changes`, `firm_provisioning_requests` (AC-27).
- **Invariants:** `firms.region` is always `'us'`; the app role cannot set `synthetic` or `region`; a firm is created only by `provision_firm(...)` or `firm_signup(...)`.
- **Migrations:** one new migration; reversible; `schema_check` passes up, down, up. Single Alembic head.
- **Versioning and immutability:** `platform_control_changes` is insert-only; container images are immutable by digest; ECR tags are immutable.
- **Retention:** evidence bucket GOVERNANCE default; records bucket COMPLIANCE per object (P-43).

## 8. Interfaces
| Method / event | Path / name | Purpose | Auth required |
|---|---|---|---|
| GET | `/healthz` | process liveness, no DB | none (public-route list, P-45) |
| GET | `/readyz` | DB roles, Temporal, scanner, platform KMS key | none (public-route list); 403 at the edge |
| Port | `identity/workos.py` | discovery and JWKS, code exchange, user lookup, session revoke | internal |
| Static | `/runtime-config.json` | authority and client ID per environment | none |
| Definer | `platform_control_state()`, `set_platform_control()`, `provision_firm()` | controls and firm creation | role-gated (`abacus_ops` EXECUTE-only) |

Schema for `runtime-config.json` and the ops commands is frozen in `docs/contracts/platform-ops.md` (AC-21).

## 9. Authorisation and tenancy
- **Tenant scoping:** KMS encryption context carries `abacus:tenant`; a wrong-tenant unwrap fails (AC-13). Tenant resolution never comes from the Host header (INV-4).
- **Who can do what:** the builder alone holds human access, through Identity Center, short-lived roles, default `ReadOnly`; elevated sets expire within 4 hours with an alert (AC-3).
- **Engagement-level access:** N/A (no engagement data).
- **Ethical walls / independence:** N/A.
- **Client-side access:** none. Operational routes expose no data.

## 10. AI behaviour
N/A: no model calls are built here. Constraints enforced: production refuses `anthropic_api_key` and a `fake` route (AC-17); the AI-services opt-out applies at the root (AC-4); Bedrock access is IAM only.

## 11. Integrations
- **External systems:** AWS, GitHub OIDC, Temporal Cloud, WorkOS, SES, ClamAV, Sentry, Better Stack.
- **Rate limits and quotas:** SES production access and Bedrock quotas are requested in F-09 (AC-8).
- **Retries and backoff:** ECS circuit breaker; ClamAV and KMS fail closed with no retry fallback.
- **Idempotency:** `provision_firm` records its idempotency key; build once yields one digest per SHA.
- **Failure behaviour:** `/readyz` fails when a dependency is down; uploads show the retryable unscannable state.

## 12. Edge cases and failure modes
- Any KMS, scanner or SES error fails closed (AC-13, AC-15, AC-16).
- A payload sealed under a retired key still decodes; removing a key still in use is refused (AC-14).
- A held deploy lock blocks a second deploy and `db_guard` (AC-26).
- A failed migration leaves old code serving on the expanded schema (AC-26).
- The DNS Firewall is VPC-scoped, so `database.clamav.net` resolves for every app task: documented residual (plan R7).
- A fixable critical Inspector finding makes a release unpromotable (AC-19).

## 13. Security and privacy
- **Data classification:** confidential and client financial data (evidence, keys); this spec builds the controls.
- **PII involved:** none stored by this work; no PII in logs, SES tags (AC-15) or telemetry.
- **Secrets used and where they live:** Secrets Manager (keyring, Temporal and WorkOS keys); GitHub OIDC only, no long-lived keys, no IAM users (AC-2). Never commit a secret; the repo is public.
- **Threats considered:** cross-region leakage, standing human access, supply chain (allowlist, Inspector, SBOM, provenance), malware in uploads, host-header tenant spoofing.
- **Mitigations:** SCPs, passkey MFA, immutable tags, digest-only deploys, fail-closed adapters, DNS Firewall allowlist, egress on 443 only.

## 14. Audit trail and evidence integrity
- **Actions logged:** CloudTrail for the organisation; console steps in `infra/README.md`; `platform_control_changes` insert-only; release records.
- **Provenance captured:** `release.json` per SHA with image digest, SPA manifest hash, Alembic head, OpenAPI hash and infra SHA.
- **What must be immutable:** images by digest, ECR tags, `platform_control_changes`, evidence versions.

## 15. Observability
- **Logs:** never log client financial data or PII; log groups are KMS-encrypted (sprint 2).
- **Metrics, traces, alerts:** built in sprint 2 (ADOT, CloudWatch, SLO burn alarms). In this scope every alarm resource must carry a runbook URL (AC-29).

## 16. Performance and scale
- **Expected volumes:** staging only; synthetic data.
- **Latency targets:** rollback within 15 minutes (sprint 3); not measured in this scope.
- **Limits:** JSON body 1 MB, upload 50 MB, ClamAV stream 60 MB with 30 s timeout.

## 17. UX
N/A: no screens. User-visible effects: the retryable unscannable state (AC-16) and the SPA reading `runtime-config.json` (AC-31).

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-5 | manual + doc check | SCP test call to eu-west-1 denied; Identity Center MFA; console log complete by M1 |
| AC-6 | CI | infra-only PR gets plan comment; public-bucket fixture fails trivy |
| AC-7, AC-8, AC-18, AC-30 | doc check | Task plan and ADR drafts open by date; tickets dated; delegation verified |
| AC-9 | integration | `check_dependencies` enforces the terraform section |
| AC-10 | integration | Linux container test of limits; reproducible build |
| AC-11, AC-12, AC-19 | CI / plan assertion | Tag overwrite refused; OIDC read of baselines; two runs one digest |
| AC-13 to AC-17, AC-20 | integration | `test_kms_key_service.py`, `test_clamd_scanner.py`, `test_ses_transport.py`, settings validators; tests written first |
| AC-21 | doc check | Contract stub merged with consumers read against it |
| AC-22, AC-23, AC-32 | plan assertion + manual | `infra/tests` over `terraform show -json`; DNS lookup of a non-allowlisted host fails; headers and edge 403 |
| AC-24, AC-25 | integration | `test_public_routes.py`; WorkOS wrong-environment token rejected |
| AC-26 | integration + dry run | One deploy per window; held lock; failed migration |
| AC-27 | integration | `schema_check` up/down/up; definer boundaries |
| AC-28, AC-29 | e2e + runbook rehearsal | Walking skeleton on staging; rehearsal dates recorded; alarm without runbook fails `validate_docs` |
| AC-31 | e2e | One bundle, two `runtime-config.json` files |

Apply-dependent checks (SCP call, edge 403, DNS) are run by the builder after a hand-run apply and recorded in the task's progress log.

## 19. Rollout
- **Feature flag:** none. Adapters and hosts are runtime configuration.
- **Migration and backfill plan:** one reversible migration before the first real firm; no backfill.
- **Rollback plan:** Terraform changes roll forward by PR; the application rolls back by re-pointing to the previous digest; migrations are never downgraded on hosted databases.

## 20. Open questions
None open. The plan's proposed option was taken for each:
- [x] Should `/v1/telemetry/errors` accept pre-sign-in errors (plan Q1)? No for now: authenticated only (a later sprint's work).
- [x] Canary staff identity in production (Q2)? A canary user whose sessions are refused everywhere except the canary tenant; decided during the canary task.
- [x] Where production ops requests live (Q3)? `deploy/production/ops-requests/` PRs until PLT-01 ships.
- [x] Does the second model route need infra beyond the US Geo profile (Q4)? Q-02 decides; IAM already allows a second Bedrock profile in us-west-2.
- [x] DEC-03 region and budget (R3)? Region us-east-2 with us-west-2 for DR; budget alarms are set after DEC-03 is recorded.
- [x] P-64 to P-67 rejected on Decision Day (R8)? The topics become SPECs inside Q-01 with the same text and no ADR numbers; tasks unchanged.

## 21. Task map
Task files exist for sprint 0 rows (TASK-142 to TASK-153). Sprint 1 rows are mapped for the next kickoff; their task files are not yet written.

| Plan key | Row | AC ids | Task |
|---|---|---|---|
| Q-01-T01 | AWS landing zone, Identity Center, SCPs, AI opt-out, console log | AC-1, AC-2, AC-3, AC-4, AC-5 | TASK-142 |
| Q-01-T02 | TASK-014 plan rewrite; P-55 and P-54 drafts | AC-7 | TASK-143 |
| Q-01-T03 | Terraform bootstrap and infra CI | AC-6 | TASK-144 |
| Q-01-T04 | Technical vendor set-up after F-09 contracts | AC-8 | TASK-145 |
| Q-01-T05 | Platform allowlist PR | AC-9 | TASK-146 |
| Q-01-T06 | Container image | AC-10 | TASK-147 |
| Q-01-T07 | Terraform envs/shared | AC-11, AC-12 | TASK-148 |
| Q-01-T08 | Adapters P1 KMS and P2 keyring; settings validators | AC-13, AC-14, AC-17 | TASK-149 |
| Q-01-T09 | Adapters P3 SES and P4 ClamAV | AC-15, AC-16 | TASK-150 |
| Q-01-T10 | ADR drafts P-45, P-64, P-67 | AC-18 | TASK-151 |
| Q-01-T11 | Build once | AC-19 | TASK-152 |
| Q-01-T12 | Acceptance tests first for the four adapters | AC-20, AC-13, AC-14, AC-15, AC-16 | TASK-153 |
| Q-01-T13 | Platform-ops contract stub | AC-21 | none: sprint 1 |
| Q-01-T14 | Terraform staging network and data | AC-22 | none: sprint 1 |
| Q-01-T15 | Terraform staging compute and edge | AC-23 | none: sprint 1 |
| Q-01-T16 | P-45 operational routes and middleware | AC-24 | none: sprint 1 |
| Q-01-T17 | WorkOS base adapter and staging identity | AC-25, AC-17 | none: sprint 1 |
| Q-01-T18 | Staging train deploy | AC-26 | none: sprint 1 |
| Q-01-T19 | Migration platform_tenancy | AC-27 | none: sprint 1 |
| Q-01-T20 | R0 bring-up on staging | AC-28 | none: sprint 1 |
| Q-01-T21 | R0 runbooks | AC-29 | none: sprint 1 |
| Q-01-T22 | ADR drafts P-65 and P-66 | AC-30 | none: sprint 1 |
| Q-01-T23 | Runtime config for build once | AC-31 | none: sprint 1 |
| Q-01-T24 | Acceptance tests first for routes, middleware, WorkOS; plan assertions | AC-32, AC-22, AC-24, AC-25 | none: sprint 1 |

## 22. Future / explicitly deferred
- Sprints 2 to 5: production and DR, observability, canary, tenant keys, kill switches, restore drill, status page, tenant provisioning workflow, SES events, telemetry tunnel, previews, portal edge.
- Second model route (Q-02).
