---
id: TASK-343
title: "Q-01-T08, Q-01-T09, Q-01-T12 and Q-01-T24 · KMS, keyring, SES and ClamAV adapters, and their acceptance tests"
spec: SPEC-050
acceptance_criteria: [AC-13, AC-14, AC-15, AC-16, AC-17, AC-20, AC-24, AC-32]
risk_zone: red
status: in-progress
epic: Q-01
plan_key: Q-01-T08, Q-01-T09, Q-01-T12, Q-01-T24
branch: worktree-agent-a64d084b1209211aa
worktree: agent-a64d084b1209211aa
created: 2026-10-21
updated: 2026-10-21
---

> **Rules for the agent working this task**
> - Solo edition: one builder, no approvals, no reviewers to wait for (`docs/plan/AMENDMENT-solo.md`).
> - Local stack only. No AWS call, no credentials, no account ID, no real ARN anywhere; fake values only (`111111111111`). The repository is public.
> - No `terraform plan` or `apply`. No new dependency (boto3 and the `types-boto3` kms/sesv2 stubs are on the allowlist).
> - Planning files for the same rows exist from kickoff: TASK-149 (T08), TASK-150 (T09), TASK-153 (T12). This task supersedes them for the build.

## Objective

Replace the fail-closed placeholders with real adapters that still fail closed, selected by configuration and never by default in local development or tests, then prove them with acceptance tests written from the spec text.

## Scope

**In**
- **T08 / P1.** `KmsKeyService` in `kernel/crypto`: KMS `Encrypt` and `Decrypt` of each per-object data key with encryption context `{"abacus:tenant": <id>, "abacus:purpose": "dek"}`; `key_id(tenant)` is the deterministic alias `alias/abacus/tenant/<tenant_id>` (synchronous); any KMS error fails the operation; no fallback to `LocalKeyService`.
- **T08 / P2.** The Temporal payload keyring: several key IDs, one current. The values come from Secrets Manager into the task definition's environment (`ABACUS_TEMPORAL_PAYLOAD_KEYS`, `ABACUS_TEMPORAL_PAYLOAD_CURRENT`), so the process makes no Secrets Manager call. A payload sealed under a retired-but-present ID still decodes.
- **T08 / settings (AC-17).** Outside local and test the process refuses to start without the KMS, keyring, scanner and SES settings; production also refuses `anthropic_api_key`; KMS and SES regions must be US regions (ADR-142). **Deferred:** refusing the `fake` model route in production (see Decisions).
- **T09 / P3.** `SesTransport` in `communications/transport.py`: configuration set, the firm's display name, Reply-To, tags carry `tenant_id` and `message_id` only. The mechanical body check (no SSN, TIN, account number or tax amount) runs before any client call; a blocked message never reaches the SES client.
- **T09 / P4.** `ClamdScanner` in `kernel/scanning.py`: `INSTREAM` to the scanner service, 60 MB stream limit, 30 s timeout, archive-bomb checks first, any error is `unscannable`.
- **T12, T24.** Independent acceptance tests (below), in a separate commit, written from SPEC-050, ADR-142, ADR-152, ADR-153 and the epic text, not from the adapters.

**Out**
- Tenant key creation (`TenantKeyWorkflow`, sprint 2) and `firms.kms_key_arn` (P-65; needs a migration).
- SES events and suppression (T46), SES identity port (T47).
- The WorkOS adapter (T17 is not built): its settings validators and its T24 tests are skipped here. The AC-17 validator lists KMS, keyring, scanner and SES now; WorkOS joins it in T17.
- The IaC plan assertions of T24 (`infra/tests` over `terraform show -json`): they need Terraform plans from T14 to T17, which do not exist, and no plan may run here.
- A real clamd testcontainer is not added to `docker-compose.yml` (see decisions).

## Plan

### Selection by configuration

| Adapter | Chosen when | Local and test by default |
|---|---|---|
| `KmsKeyService` | `ABACUS_ENVIRONMENT` is `staging` or `production` | `LocalKeyService` (loopback S3 and the public master key only) |
| payload keyring | `ABACUS_TEMPORAL_PAYLOAD_KEYS` is set | the single local key, id `platform-v1` |
| `SesTransport` | `ABACUS_SES_CONFIGURATION_SET` is set | `LocalMailbox` |
| `ClamdScanner` | `ABACUS_SCANNER_ENDPOINT` is set (required outside local and test) | `LocalScanner` |

Outside local and test the validators require every one of them, so a deployment cannot start on a local fallback.

### Steps

1. `kernel/storage.py` gains `kms_client`, `sesv2_client` and `AwsError`: it is the only module that may import boto3 (STORE-001).
2. Settings and validators in `kernel/config.py`.
3. `KmsKeyService`, `KeyServiceUnavailable`, the platform-key probe; `_from_settings` selects KMS outside local and test.
4. Keyring loading in `kernel/temporal.py`.
5. `ClamdScanner`, selected by `scanner()`.
6. `communications/body_check.py`, `SesTransport`, the widened `Transport` protocol, and the callers that now pass `tenant_id` and `message_id`.
7. Acceptance tests (T12, T24), one commit, written from the spec text.

### Interface the tests are written against

The spec fixes behaviour, not signatures. These are the signatures the tests use, recorded here before the tests are written:

- `KmsKeyService(client, *, alias_prefix, platform_key)`, with the `KeyService` protocol's methods. `client` is a boto3 KMS client (tests give it a stubbed or in-memory one).
- `ClamdScanner(endpoint, *, timeout_seconds)` with `scan(content) -> ScanResult`; `endpoint` is `host:port`.
- `SesTransport(client, *, configuration_set, from_address)` with `send(*, to, subject, body, sender_name=None, reply_to=None, tenant_id, message_id)`.
- `PUBLIC_ROUTES` is not used by the tests: they drive `create_app()` over HTTP and read `app.routes`.

Rollback: revert the commits. No migration, no dependency, no change to local behaviour.

## Definition of done

- [ ] `make check-fast`, `cd backend && uv run pytest tests/unit -q`, and the integration tests for what is touched pass.
- [ ] The acceptance tests fail on the code before T08, T09 and T16, and pass unedited on it (AC-20, AC-32).
- [ ] Nothing in code or tests names a real account, key, ARN or endpoint.

## New dependencies

None.

## Progress log

- `2026-10-21` Task file written with the plan before the build.

## Decisions made during this task

| Decision | Reason | Needs ADR? |
|---|---|---|
| The keyring is read from the environment, not fetched from Secrets Manager by the app | The epic lists `temporal_payload_keys` as a restricted settings map; ECS injects a Secrets Manager secret as an environment value, so the app needs no SDK call and no extra IAM | no |
| A transient KMS error raises `KeyServiceUnavailable` (a `ServiceUnavailable`, so 503), not `DecryptionError` | `evidence.storage._verified` treats `DecryptionError` as "this version does not open" and moves on; an outage must not look like that. Only a refusal (wrong context, wrong key, disabled or missing key) is `DecryptionError` | no |
| KMS, SES and Secrets Manager clients are built in `kernel/storage.py` | STORE-001 confines the AWS SDK to that module, and a new confined module would need a rule change | no |
| Production's refusal of the `fake` model route (AC-17, second half) is not built | SPEC-036's settings tests load production on the default route, and the provider terms register that lets Bedrock run (ADR-114) is empty, so production could not start at all. It lands with the first production model route (Q-02). The anthropic key refusal is built. An `xfail(strict)` test records the gap | no |
| `scanner()` prefers a configured endpoint over the local scanner in any environment; `transport()` likewise for SES | "Selected by configuration": setting the endpoint is the opt-in, and local runs without it keep the local adapters | no |
| The existing production-environment key service test now expects `KmsKeyService` | It asserted the placeholder ("refuses to start in AWS environments"), which AC-13 replaces; a second test pins that it does not start without KMS settings | no |
| The body check also runs in `LocalMailbox` | Local runs and tests then meet the same refusals as production | no |
| `Transport.send` gains optional `reply_to`, `tenant_id` and `message_id`; `SesTransport` requires the two IDs | Delivery events are correlated by `message_id` (T46); a send without them could not be attributed | no |

## Gotchas and discoveries

- `ClamdScanner` is blocking; `uploads.screened` already calls `scan` off the event loop.

## Questions for the human

- [ ] None.

## Handoff

See the progress log.
