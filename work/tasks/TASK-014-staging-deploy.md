---
id: TASK-014
title: Staging and production on AWS through Terraform
spec: SPEC-000
acceptance_criteria: [AC-21]
risk_zone: red
status: in-progress
branch:
worktree:
created: 2026-10-06
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan below first, then build.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Solo builder: `docs/plan/AMENDMENT-solo.md` overrides any two-founder process.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Run Accrued on AWS from Terraform, in two stages:

1. **R0, synthetic staging, by Fri Nov 13, 2026 (M2).** The walking skeleton passes on staging: a merge to main builds one image, and that same image is deployed to staging through Terraform, where the flow in Stories 1 to 6 works, with WorkOS in place of the fake identity provider (SPEC-000 AC-21).
2. **R1, production with the synthetic canary, by Fri Dec 11, 2026 (M4).** The same image and the same modules, promoted through the release-manifest PR.

Replaces the earlier objective, which was deferred on 2026-10-06 until TASKs 004 to 013 were done; they are, and the AWS foundation is decided (DEC-03).

## Scope
In: Q-01 rows T01 to T22 for R0 (steps 1 to 18), and the R1 outline below. Out: observability depth, SLOs, kill switches, tenant provisioning, previews and the portal custom host (Q-01 S3 to S5 rows), which follow after R1.

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md` (AC-21 only)
- ADRs: ADR-021, ADR-029, ADR-087, ADR-088, ADR-141 (authentication, WorkOS), ADR-142 (AWS topology and regions)
- Plan: `docs/plan/epics/Q-01.md` sections 0 and 9; `docs/plan/06-platform-ops-security.md` section 0.2 (D-OPS table), section 1 headings, sections 2.3 to 2.5
- `infra/README.md` and `work/tasks/TASK-142-aws-landing-zone.md`

## Plan
- [x] Plan written below (red: plan first, then build; optional self-review with the reviewer subagents).

Steps in dependency order. Row = Q-01 task id; sprint dates: S0 Oct 19 to 30, S1 Nov 2 to 13, S2 Nov 16 to 27, S3 Nov 30 to Dec 11. Every PR says "holding for the batch".

| # | Step | Row | Sprint | State |
|---|---|---|---|---|
| 1 | Landing zone: Organizations, Control Tower, Identity Center MFA, root SCPs, AI opt-out, budget alarms. Accounts shared, staging, production and sandbox and the root SCPs are still to create (builder, console, logged in `infra/README.md`) | T01 (TASK-142) | S0, M1 Oct 30 | in progress |
| 2 | Platform allowlist PR (workos, clamav, ADOT, Python base image, terraform section) | T05 | S0 | done (SU-21) |
| 3 | Container image: multi-stage, `uv sync --locked --no-dev`, digest-pinned base, non-root, read-only root filesystem | T06 | S0 | to do |
| 4 | Terraform state and infra CI: `infra/bootstrap`, S3 native locking, GitHub OIDC, read-only plan role, main-only apply role, `infra.yml` | T03 | S0 | in progress (SU-20) |
| 5 | Terraform `envs/shared`: ECR, shared-artifacts, previews and design-baselines buckets | T07 | S0 | to do |
| 6 | Independent AC tests for the KMS, keyring, SES and ClamAV adapters, written first from the P-55 and P-64 text | T12 | S0 | to do |
| 7 | Production adapters: KMS and keyring (P1, P2); SES transport and ClamAV client (P3, P4) | T08, T09 | S0 | to do |
| 8 | Build once (ADR-088): `build.yml` builds the image once with digest, SBOM, provenance and scan | T11 | S0 | to do |
| 9 | Platform-ops contract stub `docs/contracts/platform-ops.md` v1 | T13 | S1 | to do |
| 10 | Terraform staging network and data: VPC, endpoints, DNS Firewall allowlist, RDS, buckets, keys | T14 | S1 | to do |
| 11 | Terraform staging compute and edge: ECS cluster, services, scanner, ADOT sidecar, one-off migrate, bootstrap and ops tasks, CloudFront and WAF | T15 | S1 | to do |
| 12 | Operational routes and middleware (`/healthz`, `/readyz`, ROUTE-001); needs the P-45 ADR draft (T10, S0) | T16 | S1 | to do |
| 13 | WorkOS adapter and staging identity; needs the vendor set-up (T04, S0) | T17 | S1 | to do |
| 14 | Migration `platform_tenancy`: firm region and key columns, platform controls | T19 | S1 | to do |
| 15 | Staging deploy workflow `deploy-staging.yml`: concurrency, SSM deploy lock, pre-flight | T18 | S1 | to do |
| 16 | R0 bring-up on staging: bootstrap task, first migrate, Temporal namespace and queues, WorkOS redirects, SES; run the Stories 1 to 6 smoke (AC-21) | T20 | S1, M2 Nov 13 | to do |
| 17 | R0 runbooks: deploy and rollback (RB-01), failed migration (RB-02), scanner down (RB-24) | T21 | S1 | to do |
| 18 | ADR drafts P-65 tenant key provisioning and P-66 platform controls | T22 | S1 | to do |

Tests for steps 12, 13 and 15 onward are written independently (T24, S1; T44, S3), as the Q-01 plan allocates.

**R1 outline (detailed when S2 starts):** observability and Temporal Schedules (T25, T26), tenant keys (T27), production Terraform from the same modules (T28), DR pilot light (T29), CanaryWorkflow (T30) in S2; production release path through the release-manifest PR (T34), canary tenant (T35), kill switches (T36, T37), restore-drill tooling and first drill (T38, T39) in S3.

## Decisions
Taken with the plan's default, per the solo amendment (`docs/plan/06-platform-ops-security.md` section 0.2):

| Decision | Default taken | Source |
|---|---|---|
| Region and accounts | us-east-2 primary, us-west-2 DR; us-east-1 only for global edge and Bedrock US Geo. Organizations plus Control Tower: management, log-archive, audit, shared, staging, production, optional sandbox that never holds data | DEC-03, D-OPS-02, D-OPS-03, ADR-142 |
| Database | RDS for PostgreSQL 17, Multi-AZ, pgvector and pg_trgm, 35-day PITR, cross-region backups to us-west-2, vault-locked copy in `audit`; no RDS Proxy, no Aurora | D-OPS-05 |
| Object Lock | GOVERNANCE for evidence and documents, bypass only by the dual-control break-glass role; COMPLIANCE for seal manifests and signature and consent packages | D-OPS-06 |
| Tenant keys | One KMS multi-Region key per firm, created by `worker-keyops`, deletion under dual control | D-OPS-07 |
| Workflow engine | Temporal Cloud, a namespace per environment, PrivateLink in production | D-OPS-08 |
| Malware scanning | ClamAV as an internal ECS service on plaintext; not GuardDuty S3 Malware Protection | D-OPS-09 |
| Edge | CloudFront plus WAF; app at `app.<product-domain>`; portal at `<slug>.<neutral-portal-domain>` on a multi-tenant distribution; `/v1/*` same-origin to an internal ALB through a VPC origin | D-OPS-10 |
| Email | SES in us-east-2 outbound, per-firm verified domains; intake through Microsoft Graph | D-OPS-11 |
| Release cadence | Batch merges; one staging deploy per sprint close, never per merge; production through the release-manifest PR | D-OPS-12, DEC-54 |

## Guardrails
- No session holds apply credentials. A session runs `fmt`, `validate`, `tflint`, `trivy config` and read-only `plan`; the builder applies by hand.
- Production applies only through the release-manifest PR.
- Never run a local build, migration or seed against a hosted database. Hosted databases are reached only by ECS one-off `abacus-ops` tasks.
- Before touching staging, run `gh run list --workflow deploy-staging.yml --status in_progress`; do nothing while a deploy is in flight.
- No account IDs, secrets or amounts in git (the repo is public). Say "the DEC-03 envelope"; amounts stay in the vault.

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one added to the dependency allowlist and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|

## Progress log
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.
- `2026-10-20` (SU-22, Q-01-T02) — Plan rewritten as 'Staging and production on AWS through Terraform': 18 steps in dependency order, decisions D-OPS-02/03/05 to 12 recorded with the plan's default, guardrails added. Status moved from blocked to in-progress. Plan box awaits the builder's approval.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
-

## Questions for the human
- Neutral portal domain name (D-OPS-10) is delivered by F-09-T09; step 13 and the edge in step 11 wait on it. Which date?
- Temporal Cloud namespace region is marked [verify] in D-OPS-08; confirm us-east-2 when the order form (F-09-T10) is signed.
- WorkOS commercial check (ADR-029) still pending; step 13 needs the staging environment from T04.
- 4-hour expiry on elevated Identity Center assignments is an open gap (TASK-142); manual removal until automated.

## Handoff
- **Current state:** Plan written (SU-22). Step 1 (T01, TASK-142) in progress; step 2 (T05) done; step 4 (T03) in progress (SU-20). Plan not yet approved.
- **Exact next step:** Builder approves the plan box, then finishes the T01 console steps (accounts shared, staging, production, sandbox; root SCPs) and runs the checks in `infra/README.md` section 3.
