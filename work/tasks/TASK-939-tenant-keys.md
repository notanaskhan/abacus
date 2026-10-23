---
id: TASK-939
title: Tenant keys - TenantKeyWorkflow on the keyops queue, verified in both regions (Q-01-T27)
spec: SPEC-050
acceptance_criteria: [AC-13]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T27
branch: q01-t27-tenant-keys
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"A new synthetic tenant gets a verified key in both regions, and the API task role is refused CreateKey" (Q-01-T27; P-65, ADR-035, ADR-104, ADR-156).

## What changed
- **`keyops` work class:**
  - It has its own queue and limits.
  - Outside local and test, the worker serves keyops only when named (`--classes keyops`), so only the keyops service, whose task role is the one allowed `kms:CreateKey`, ever runs key work.
  - A `work_classes` override written for the four admission classes keeps the keyops defaults.
- **`TenantKeyWorkflow`** (`tenant_key:<tenant>`, keyops). Every step runs as the provisioning operator and is idempotent:
  - create a multi-Region key tagged `abacus:env` and `abacus:tenant`, with the tenant alias, reusing an existing alias;
  - replicate it to `kms_replica_region` (us-west-2) and set the alias there too;
  - verify that a value encrypted in the primary region decrypts in the replica, under the tenant context.
  - The firm is `active` after the create and `replica_verified` only after the verify (ADR-156). That is recorded through `identity.api.record_tenant_key` and audited.
- **Provisioning:** `KMS_CHILD_PATCH` is on. `platform.request_tenant_key` dispatches the key workflow through `kernel.dispatch`. It is a separate run, not a child: DISPATCH-001 keeps task queues out of workflow modules.
- **KMS port:**
  - `KmsTenantKeyOps` uses the kernel's clients (STORE-001).
  - `InMemoryTenantKeyOps` serves local runs and tests, so they never call AWS.
- **Histories:** provisioning v3 and tenant-key v1 are recorded, and v1 and v2 still replay.

## Not done (infra, needs a human)
- The `abacus-worker-keyops` ECS service and its task role (the only `kms:CreateKey` holder, conditioned on the `abacus:env` tag).
- The SCP reserving key deletion and policy changes to `abacus-key-custodian`.
- A refusal check that the API task role is refused `CreateKey`. All three are Terraform; no session applies it.

## Progress log
- 2026-10-23: the provisioning tests (12) pass twice, along with the replays (196), the worker, kernel and work-class units, and `make check-fast`.
