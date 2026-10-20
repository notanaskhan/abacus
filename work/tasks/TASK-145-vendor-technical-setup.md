---
id: TASK-145
title: "Q-01-T04 · Technical vendor set-up after F-09 contracts: Temporal Cloud account, staging namespace and API keys in Secrets Manager; WorkOS staging environment; SES production-access request and platform identity; Bedrock US Geo model access and quota requests; Sentry (US) and Better Stack orgs; Route 53 zones for the product and neutral domains"
spec: SPEC-050
acceptance_criteria: [AC-8]
risk_zone: red
status: todo
epic: Q-01
plan_key: Q-01-T04
branch: task-145-vendor-technical-setup
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
Each item has a dated ticket, every vendor console account is on MFA for the builder, and the neutral domain is delegated to Route 53 by Fri Oct 30.

## Scope
**In**
- Temporal Cloud account, staging namespace and API keys in Secrets Manager
- WorkOS staging environment
- SES production-access request and platform identity
- Bedrock US Geo model access and quota requests
- Sentry (US) and Better Stack orgs
- Route 53 zones for the product and neutral domains, and delegation of the neutral domain
- A dated ticket for each item; MFA on every vendor console account

**Out**
- Vendor order forms, domain purchase and commercial terms (F-09-T09, F-09-T10)
- Production namespaces
- API keys in git

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-8; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §3 F1 and F3 (WorkOS, SES); §9 row Q-01-T04; §11 R4, R5, R6
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T04
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- F-09 rows T09 (domains), T10 (commercial terms) and T11 (SES and Bedrock requests) must be done first
- ADRs: ADR-113, ADR-114

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is red)

Steps:
1. [ ] Confirm F-09-T09 and F-09-T10 are complete
2. [ ] Create each vendor account by hand with MFA; store keys in Secrets Manager
3. [ ] Create the Route 53 zones and delegate the neutral domain at the registrar
4. [ ] Open a dated ticket per item

Files to create or change:
- infra/README.md (console log entries)
- tickets (one per item)

Tests to write (mapped to ACs):
- AC-8 → manual: each item has a dated ticket; MFA confirmed on every vendor console; `dig NS` on the neutral domain returns Route 53 name servers by Fri Oct 30

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
- Terraform apply and every console step are run by the builder by hand, never from a session.
- Depends on Q-01-T01, F-09-T09 and F-09-T10.
- Portal domain must never contain 'accrued' (AC-11 in SPEC-049).

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Check F-09-T09 and F-09-T10 status, then create the Temporal Cloud account.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
