---
id: TASK-142
title: "Q-01-T01 · AWS landing zone: Organizations, Control Tower, Identity Center with passkey or hardware-key MFA, accounts management/log-archive/audit/shared/staging/production/sandbox, root SCPs (regions, no IAM users, protected security services, no leaving the org), AI-services opt-out policy, budget alarms at the DEC-03 envelope, infra/README.md console log"
spec: SPEC-050
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: red
status: in-progress
epic: Q-01
plan_key: Q-01-T01
branch: task-142-aws-landing-zone
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
Six member accounts run under Control Tower with the builder on Identity Center MFA, a test call to eu-west-1 is denied by SCP, and infra/README.md records every console step by Fri Oct 30 (M1).

## Scope
**In**
- Create the AWS Organization and enrol Control Tower (home region us-east-2) with accounts management, log-archive, audit, shared, staging, production and sandbox
- Configure Identity Center with passkey or hardware-key MFA and `ReadOnly` as the default permission set; define `BreakGlassAdmin`, `abacus-retention-override` and `abacus-key-custodian` with a 4-hour expiry and a CloudTrail → EventBridge alert to the builder within 5 minutes
- Apply root SCPs: regions us-east-2 and us-west-2 only (global-service exceptions per AC-1), deny `iam:CreateUser` and `iam:CreateAccessKey`, protect security services, no leaving the org
- Apply the AI-services opt-out policy; keep Bedrock model-invocation logging off in production
- Set budget alarms at the DEC-03 envelope after DEC-03 is recorded (Fri Oct 23)
- Record every console step in `infra/README.md` with date and operator

**Out**
- Terraform for the organisation (T03 builds the bootstrap; the console steps stay manual)
- Any workload resource
- Any amount in git

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-1, AC-2, AC-3, AC-4, AC-5; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §3 F1 (landing zone, residency and access); §9 row Q-01-T01; §10 R0 bullet 1; §11 R1, R3
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T01
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- ADRs: ADR-035, ADR-087, ADR-114; ADR-142 (P-55, AWS topology) and ADR-141 (P-54, WorkOS)
- Code: `infra/README.md` (new)

## Plan
- [x] Plan written into this file before any build step (required for amber and red; zone is red)

Plan (2026-10-20): the session prepares, the builder clicks. Policies are files in `infra/landing-zone/` (region guard with us-east-1 open only for CloudFront, ACM, WAF, Shield and Bedrock US Geo; no IAM users or access keys; protected CloudTrail, Config, GuardDuty, Security Hub, Access Analyzer, Macie; no leaving the org; AI-services opt-out). `infra/README.md` holds the eight console steps, the SSO profile block, the checks and the console log. Control Tower's own Region deny control stays off because the custom SCP replaces it. Rollback: detach an SCP at the root. Gap: Identity Center cannot expire an assignment, so 4-hour expiry is by hand plus the EventBridge alert until a Q-01 automation lands.

Steps:
1. [ ] Builder: create the organisation and enrol Control Tower by hand; log each step in `infra/README.md`
2. [ ] Builder: Identity Center with MFA, ReadOnly default, the three elevated permission sets with expiry and alert
3. [ ] Builder: root SCPs and the AI-services opt-out; test a call to eu-west-1 and record the denial
4. [ ] Builder: budget alarms after DEC-03 is recorded; confirm the log is complete by Fri Oct 30

Files to create or change:
- infra/README.md (new, console log)
- reference copies of the SCP and opt-out policy documents (under infra/)

Tests to write (mapped to ACs):
- AC-1 → manual: a call to eu-west-1 from staging or production is denied by SCP; us-east-1 exceptions confirmed
- AC-2 → manual: sign-in requires passkey or hardware key; default permission set is ReadOnly; a CreateUser call is denied
- AC-3 → manual: break-glass assignment expires within 4 hours and the alert reaches the builder within 5 minutes
- AC-4 → manual: opt-out policy attached at the root; invocation logging off
- AC-5 → doc check: README lists every console step with date and operator

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
- 2026-10-20 (SU-19): policies and runbook written; waiting on the builder's console steps and the checks in infra/README.md §3.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- Terraform apply and every console step are run by the builder by hand, never from a session.
- DEC-03 is recorded Fri Oct 23; build the organisation from Mon Oct 19 and set budget alarms afterwards.
- The plan's other-founder assignment rule for elevated access is void (solo).

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Create the Organization and enrol Control Tower in us-east-2, logging each console step.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
