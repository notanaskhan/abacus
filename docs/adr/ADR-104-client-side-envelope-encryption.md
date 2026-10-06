---
id: ADR-104
title: Client-side envelope encryption under per-tenant keys
status: accepted
date: 2026-10-06
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-035 encrypts evidence files with SSE-KMS under each firm's key. Locally, evidence lives in Versity Gateway (ADR-016's write-once store), which has no KMS. SSE-KMS in AWS plus something else locally would mean two code paths for the most sensitive data we hold, and the local one would be the one tested most.

## Decision
The application encrypts every evidence object and raw payload before storing it, the same way in every environment:
- a fresh 256-bit data key per object, and AES-256-GCM;
- the data key is wrapped by the firm's tenant key through a `KeyService`: AWS KMS (one key per firm) in AWS, and HKDF from a local master secret in local and test only;
- the tenant ID and the content fingerprint are bound as associated data.

Objects stay content-addressed by the SHA-256 of their plaintext, under Object Lock (ADR-016). This refines ADR-035's mechanism. Its intent (per-firm keys, crypto-shredding on offboarding) is unchanged.

## Options considered
### Client-side envelope encryption — chosen
- Pros: one code path everywhere; the store never sees plaintext; crypto-shredding by destroying the firm's KMS key still works, including for write-once objects and backups.
- Cons: presigned direct downloads would return ciphertext, so downloads go through the API.
### SSE-KMS in AWS, different locally
- Pros: S3 does the work; presigned downloads work.
- Cons: two code paths; the tested path isn't the production one.
- Rejected.

## Consequences
**Positive**
- Every evidence download is authorised and audited by the application.

**Negative / costs accepted**
- Download throughput goes through the API, not straight from S3.
- ADR-016's presigned URLs apply only to non-evidence, non-confidential objects, if any.

**Follow-up work**
- `KmsKeyService` and per-firm KMS keys (TASK-014). Until it exists, AWS environments refuse to start.

## Enforcement
- STORE-001: `boto3` only in `abacus.kernel.storage`. CRYPTO-001: `cryptography` only in `abacus.kernel.crypto`.
- The local key service refuses to run outside local and test.
- Tests: an object can't be decrypted under another tenant's key or with a different fingerprint; a tampered object is refused.

## Guidance for agents
**Do**
```python
stored = await evidence_storage.put(tenant, content)
```
**Don't**
```python
s3.put_object(Bucket=b, Key=k, Body=content, ServerSideEncryption="aws:kms")
```

## Revisit when
The store gains a per-tenant key mechanism we can use identically in every environment.

## Related
- ADR-016
- ADR-035
