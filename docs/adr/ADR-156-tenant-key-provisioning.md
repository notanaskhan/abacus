---
id: ADR-156
title: Tenant key provisioning - one multi-Region key per firm, created by a keyops worker
status: proposed
date: 2026-10-22
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
**Open by 2026-11-13; accept by 2026-11-27.** ADR-035 says each firm has its own key and that deletion needs dual control, ADR-096 says keys exist in both regions, and ADR-104 seals content client-side under the tenant key. None of them says how a key comes to exist, who may create it, or when a firm may start storing content. Without a defined path, a key is created by hand or by whichever role has the widest rights. This ADR is P-65, drafted under Q-01-T22 and built under Q-01-T19, T27 and T45. The decision below is chapter 06 D-OPS-07 and section 1.9 (the chapter calls the proposal P-38) and the Q-01 epic section F7. It extends ADR-035; it does not replace it.

## Decision
- **One key per firm.** A symmetric KMS multi-Region key, primary in us-east-2, replica in us-west-2, tagged `abacus:env` and `abacus:tenant`. The alias `alias/abacus/tenant/<tenant_id>` exists in both regions. Region is `us` for every firm (`firms.region` CHECK); there is no region argument anywhere.
- **Only one role creates keys.** `TenantKeyWorkflow` runs on the `abacus-keyops` task queue and is executed by `abacus-worker-keyops`, the only task role allowed `kms:CreateKey` (conditioned on the request tag `abacus:env` matching its environment), `ReplicateKey`, `CreateAlias` on the tenant alias prefix and `TagResource`. That role has no data-plane rights. The API and worker roles are refused `CreateKey`; they may only encrypt, decrypt and generate data keys on keys tagged with their environment.
- **Order of steps, and when a firm is ready.** Create the key, replicate it, create both aliases, encrypt and decrypt a probe in the replica region, and only then record `firms.kms_key_arn`, `kms_key_status = 'replica_verified'` and `kms_replica_verified_at`. The states are `none`, `pending`, `active`, `replica_verified`, `pending_deletion`. **A firm whose key is not `replica_verified` stores no client content**; no key exists without a firm, and no firm is provisioned without a key.
- **Provisioning is one audited workflow.** `provision_firm(...)` (a definer function callable only by the EXECUTE-only `abacus_ops` role) creates the firm and records the idempotency key; `TenantProvisioningWorkflow` then runs `TenantKeyWorkflow` as a child, writes plan and entitlement rows, invites the first admins and records `tenant.provisioned`. The same idempotency key returns the same tenant and starts no second workflow. Synthetic tenants (staging, the production canary) get real keys through the same path.
- **Every use is bound to the tenant.** Each `Encrypt` and `Decrypt` carries the encryption context `{"abacus:tenant": <tenant_id>, "abacus:purpose": "dek"}`, so a wrong-tenant unwrap fails at KMS and CloudTrail attributes each call to a tenant. `KeyService.key_id(tenant)` stays the deterministic alias. A key operation that fails fails the caller; there is no fallback to a local key outside `local` and `test`.
- **Deletion is not routine.** `ScheduleKeyDeletion`, `DisableKey` and `PutKeyPolicy` are denied to every principal by an organisation-level policy, except the `abacus-key-custodian` break-glass role. The deletion window is 30 days. Destroying a key is crypto-shredding for offboarding (ADR-034); it makes COMPLIANCE-locked ciphertext unreadable but the bytes persist until their floor date, and the offboarding certificate says so.
- **Dual control in the solo edition.** ADR-035 requires dual control. With one builder, the two controls are (1) a merged ops-request record naming the tenant and the reason, and (2) the 30-day window with an alarm on any `ScheduleKeyDeletion`. When a second person with production access exists, the custodian role requires both people. This reading is the open point to confirm at acceptance.
- **Where the code lives.** `abacus.kernel.crypto` keeps `KmsKeyService`; the workflow, activities (`kms_create_key`, `kms_replicate_key`, `kms_create_aliases`, `kms_verify_replica`, `record_tenant_key`) and the `keyops` work class belong to `platform` and `kernel`; boto3 stays confined to `kernel/storage.py` (STORE-001).

## Options considered
### Option A: a keyops worker creates the key inside a Temporal workflow - chosen
- Pros: the widest KMS right sits in a small role with no data access; the sequence is durable, retried and replayable; the audit trail is the workflow's; synthetic and real tenants take the same path.
- Cons: a fifth task queue and one more service to run and patch.

### Option B: Terraform creates a key per tenant
- Pros: infrastructure as code.
- Cons: tenants are runtime data, not infrastructure; every signup would need an apply, which a Claude Code session may not run (SPEC-050); state churn grows with tenants.
- Why rejected: the control plane for firms is the application, not the infrastructure pipeline.

### Option C: the API or worker role creates the key on demand
- Pros: no new service.
- Cons: puts `CreateKey` in the role with the largest blast radius and the most code.
- Why rejected: it defeats the point of keeping key creation away from application code (ADR-035, ADR-104).

### Option D: a single-Region key per firm, with a second unrelated key in the DR region
- Pros: simpler key objects.
- Cons: ciphertext written in one region is not readable with an unrelated key in the other; regional recovery would need re-encryption of data that is itself unavailable.
- Why rejected: ADR-096 requires that keys exist in both regions and that the drill decrypts samples in the DR region; a multi-Region key does that directly.

## Consequences
**Positive**
- No key can be created outside one audited path, by one role that cannot read data.
- Regional recovery can decrypt tenant data in us-west-2 without a re-encryption step.
- "Ready" has a single definition, so no module stores content for a firm without a verified key.

**Negative / costs accepted**
- A new task queue, a new task role and a per-firm key cost to run.
- A firm is not usable for a short time after creation, until the replica probe passes.
- Dual control is weaker than it reads until a second person exists.

**Follow-up work created**
- Code: migration `00NN_platform_tenancy` (`firms.kms_key_arn`, `kms_key_status`, `kms_replica_verified_at`, `firm_provisioning_requests`, `provision_firm`) in Q-01-T19; the keyops service and workflow in Q-01-T27; `TenantProvisioningWorkflow` and the operator commands in Q-01-T45; keys for the staging and canary tenants in Q-01-T35 and T55.
- Specs: none new; SPEC-050 AC-27 covers the migration.
- Docs: `docs/contracts/platform-ops.md` section 3.6 carries the workflow inputs and outputs; a key-custodian runbook (break-glass, ADR-098).
- Glossary: none.
- Matrix: none (no HTTP surface).
- Registry: `platform` module `registry.py` table owners; keyops added to the worker `MODULES` and `WorkClass`.

## Enforcement
- [ ] Lint rule: none beyond STORE-001 (boto3 only in the storage module).
- [x] Architecture / dependency rule in CI: the IaC plan assertions in `infra/tests` fail when any role other than the keyops role holds `kms:CreateKey`, or when the deletion denial is missing from the landing-zone policies.
- [x] Test: workflow replay fixtures `tenant-key-v1.json` and `tenant-provisioning-v1.json`; an acceptance test that a firm without a `replica_verified` key cannot store content; the existing KMS acceptance tests (`backend/tests/acceptance/test_q01_kms_key_service.py`).
- [x] Hook or protected path: the key, workflow and migration paths are red; the organisation policies are protected.
- [ ] Reviewer agent checklist item: none.
- [ ] Advisory only - reason: n/a

## Guidance for agents
Never create, replicate, alias or delete a KMS key from application code, a script or a migration. Create a firm through `provision_firm` and the workflow. Encrypt through the key service with the tenant ID; never pass a key identifier chosen by the caller.

**Do**
```
await key_service().wrap(tenant_id, data_key)  # alias and encryption context come from the service
```

**Don't**
```
kms.create_key(...)  # outside the keyops worker
```

## Revisit when
A second person gets production access (dual control becomes two people); a region other than the United States is ever offered (a new ADR, since `firms.region` is pinned); the number of firms makes per-firm key cost or the KMS request quota a constraint; or customer-managed key requests (bring your own key) arrive.

## Related
- ADRs: extends ADR-035 (per-tenant keys) with a provisioning path; relies on ADR-034 (crypto-shredding), ADR-096 (keys in both regions), ADR-104 (client-side envelope encryption), ADR-142 (regions); ADR-157 (platform controls) shares the `platform` module and the ops-task path.
- Plan: P-65; Q-01-T19, Q-01-T22, Q-01-T27, Q-01-T45; chapter 06 D-OPS-07 and section 1.9.
- Specs: SPEC-050 (AC-27, AC-30).
- Docs: `docs/contracts/platform-ops.md`.
