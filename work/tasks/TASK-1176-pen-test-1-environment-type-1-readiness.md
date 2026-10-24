---
id: TASK-1176
title: Type I readiness and the pen-test #1 environment — readiness gap register, environment definition and checklist, the AWS configuration-review role written and unapplied (Q-02-T35)
spec: SPEC-051
acceptance_criteria: [AC-1, AC-2]  # the gate tracker's M7-02 row and the control map; Q-02-T35's own acceptance is programme evidence (Q-02 §3.13)
risk_zone: amber
status: in-review
epic: Q-02
plan_key: Q-02-T35
branch: s7c-pentest-readiness
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Every readiness gap has a ticket with an owner and a date before Feb 26, and the tester's accounts work on the pinned build by Fri Feb 12." Q-02-T35; chapter 06 §5.6 and §5.7; DEC-26.

## Plan (amber zone)
- **Documents.**
  - `docs/ops/compliance/type-1-readiness.md` (new): the readiness assessment as it stands on `main`. One row per control-map control that is not `built` or `operating`, with the gap, the closing task, the owner, a due date on or before Fri Feb 26, 2027, and a ticket column that the builder fills in when the ticket is opened (sessions open no issues).
  - `docs/ops/pentests/2027-02-environment.md` (new): the pen-test #1 environment. It covers where the test runs (the staging and production canary, synthetic tenants only), the personas, how they are created (through the product's own provisioning and invitation flows, never a seed against a hosted database), source-review access (the repository is public), the AWS configuration-review role, the build pin, and the rules-of-engagement outline. Vendor, people, addresses and dates of access are vault placeholders. A checklist closes the file.
  - `docs/ops/soc2-control-map.md`: two evidence paths that moved (`feature-flags.yaml` and `permission-matrix.yaml` became directories). No state changes: only the compliance tool's evidence moves a row.
  - Gate tracker `docs/ops/compliance/README.md`: M7-02 points at the readiness file.
- **Terraform (written, never initialised, planned or applied by this session).**
  - `infra/modules/pentest-review-role/` (new, the `github-oidc` module's IAM pattern): one role the tester's own AWS principal assumes, with an external ID, MFA present and an access window that ends on a date. It attaches the AWS-managed `SecurityAudit` and `ViewOnlyAccess` policies, and an inline deny on every data-plane read (S3 objects, KMS decrypt, secrets, parameters, log events, RDS data API, DynamoDB items, Temporal-free). Max session 1 hour. `count` gated on the tester principal, so a root without tfvars plans to nothing.
  - `infra/envs/staging/pentest_review.tf` and `infra/envs/production/pentest_review.tf` call it. They add variables to `variables.tf`, create `envs/production/variables.tf`, and add placeholder lines to the `terraform.tfvars.example` files (`000000000000`, `.test`).
  - `infra/tests/test_pentest_review_role.py` (new): offline assertions. It checks the text only: the role exists only when the principal is set; the trust policy needs an external ID, MFA and the end date; the managed policies are the two read-only ones; and the deny covers the data reads.
  - `infra/README.md`: the builder's apply and removal steps.
- **Decisions:** DEC-306 (the environment's shape: where, personas, no WAF bypass, the review role, the pin).
- **No migration, route, flag or matrix change.**
- **Rollback:** revert the commit. Nothing is applied, so nothing needs removing from AWS. Once the builder has applied it, `pentest_review_principal_arn = null` and an apply remove the role.

## Not done (needs the builder)
- `terraform fmt`, `init -backend=false` and `validate`, then the PR's `infra / plan`, then the apply, each by hand. This session runs no Terraform command beyond `fmt` and downloads no provider.
- Opening the readiness tickets in the tracker and the compliance tool, and writing their ids into the readiness file.
- Everything in the environment checklist marked **human**.

## Progress log
- 2026-10-24: plan written; documents, the module, the two env wirings and the offline tests built. Only `terraform fmt -check` was run on the new files. `init`, `validate`, `plan` and `apply` were not run, so the module is unexercised. The staging and production roots have no network, compute or database yet (Q-01-T14, T15, T28), so the environment can be described but not stood up. The readiness file lists that as the largest gap.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-306 | The plan names the environment (§5.6) but not its personas' provenance, the review role's limits or whether testers bypass the WAF | No (ADR-087, ADR-099, ADR-142) |
