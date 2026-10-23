---
id: TASK-937
title: SES per-firm sender identity port (Q-01-T47, local parts)
spec: SPEC-050
acceptance_criteria: [AC-21]
risk_zone: amber
status: in-review
epic: Q-01
plan_key: Q-01-T47
branch: q01-t47-ses-identities
created: 2026-10-23
updated: 2026-10-23
---

## Objective
Build the SES sender-identity port for R-01's ADM-10 (Q-01-T47; platform-ops contract §3.8): create with Easy DKIM and a custom MAIL FROM domain, read status, delete. The task's acceptance is "A test identity reaches DKIM verified on staging, and a code mailed to a sink address is readable by the harness within 30 seconds". It needs staging and the sink, so it is verified on staging later.

## Plan
- `communications/ses_identities.py`:
  - `SesIdentityPort`, with `DnsRecord`, `IdentitySetup` and `IdentityStatus` as frozen dataclasses;
  - `SesIdentities`, over the client from `kernel.storage.sesv2_client()`, with errors classified by `kernel.storage.error_code` (STORE-001);
  - `InMemorySesIdentities` for local and test runs;
  - `ses_identities()` and `configure_ses_identities()`, which select the same way `transport()` does.
- How the port behaves:
  - It always asks for Easy DKIM (`RSA_2048_BIT`) and a custom MAIL FROM domain (`BehaviorOnMxFailure = USE_DEFAULT_VALUE`).
  - A new identity is attached to the environment's configuration set, so its delivery events reach the Q-01-T46 drain.
  - `create_identity` is idempotent (`AlreadyExistsException` reads the existing DKIM tokens).
  - `delete_identity` for an unknown domain is a no-op.
  - Any other SES error raises `SesIdentityUnavailable`, which carries the error code and never the domain.
  - A malformed domain or subdomain never reaches SES.
- Exported from `communications.api`. Module README and contract §3.8 updated.
- Tests: `tests/contracts/platform_ops/test_ses_identity_port.py`, run against a real botocore client under `Stubber` and against the in-memory port.
- Rollback: revert the commit. No schema or settings change.

## What changed
- As planned. 19 tests in `tests/contracts/platform_ops/test_ses_identity_port.py` (CI runs them in `ci-contracts`).

## Not done (infra and operations)
- **The staging mail sink.** `infra/modules/ses` is still a skeleton README, and `infra/envs/staging` composes no resources yet. The sink is therefore not a small addition. It needs:
  - an SES receiving domain with MX;
  - a receipt rule set and rule, in a receiving region (us-west-2 per Q-01 R6, still to verify);
  - an S3 bucket with a 7-day expiry and a bucket policy for SES;
  - read access for F-04-T22's mailbox reader.

  It is left for an infra task.
- **The staging check.** A test identity reaching DKIM verified, and a code readable within 30 seconds, need the sink applied and a real domain's DNS. No session runs `terraform apply`.
- **The SES task-role permissions.** `ses:CreateEmailIdentity`, `PutEmailIdentityMailFromAttributes`, `GetEmailIdentity` and `DeleteEmailIdentity` must be granted to whichever role runs ADM-10 (R-01).

## Progress log
- 2026-10-23: the port tests, the SES transport acceptance tests, the replay tests, the API, identity and communications unit suites, banned patterns, lint-imports, validate_docs, secrets_scan and check-generated all pass.
