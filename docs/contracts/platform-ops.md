# Platform operations (v1)

| Field | Value |
|---|---|
| Register row | Platform interfaces (unnumbered) in `docs/contracts/README.md` |
| Version | v1 |
| Status | frozen v1 (Q-01-T57, 2026-10-23); stub was Q-01-T13 |
| Provider epic | Q-01 |
| Consumers | P-01 (sign-in, notifications), P-08 (portal sign-in, branding, invitations), F-04 (seed loader, canary, mailbox reader), G-04 (tenant console, provisioning patch), F-01 (`db_guard`), R-01 (sender identities, ADM-10), Q-04 (release train, on-call) |
| Freeze sprint | S5 (starts 2026-12-28) |
| Flag | none. Kill switches are `platform_controls` rows, not flags (Q-01 epic, ADR-089) |
| Spec | `docs/specs/SPEC-050-aws-landing-zone-platform.md` (AC-21) |
| ADRs | ADR-035, ADR-097, ADR-104, ADR-141 (P-54), ADR-142 (P-55), ADR-152 (P-45), ADR-153 (P-64), ADR-156 (P-65, proposed), ADR-157 (P-66, proposed) |

## 1. Purpose

The platform layer gives the product modules nine things to build against, so no consumer reaches for AWS, WorkOS or an operator's laptop directly:

1. a WorkOS adapter port (`identity/workos.py`);
2. the `runtime-config.json` schema the SPA reads before it boots;
3. the public-route list and readiness checks (`/healthz`, `/readyz`);
4. the deploy lock and the command that shows its holder;
5. the operator commands that run as one-off ops tasks;
6. the `TenantProvisioningWorkflow` inputs and outputs;
7. `platform.api.control_active`, the one reader of the kill switches, and the rule for adding a switch;
8. the SES sender-identity port;
9. the already-built adapters (KMS key service, payload keyring, SES transport, ClamAV scanner), listed so consumers know their names.

This file describes interfaces only. Infrastructure, account layout, sizing and cost live in `infra/`, `docs/ops/` and the ADRs above. A consumer that needs something not listed here asks for a v1 addition before it builds a private workaround.

## 2. Who may call it

This contract has almost no HTTP surface. Operations are Python ports, static files and commands.

| Interface | Surface | Caller | Agent or system principal |
|---|---|---|---|
| WorkOS adapter port | `abacus.modules.identity.workos` (section 3.1) | `identity` (tokens, session BFF); P-01 and P-08 through `identity.api` | system contexts only for token verification; denied for any agent context |
| Runtime config | `GET /runtime-config.json` per host, static | every browser; no token | n/a (static, no data) |
| Public routes | `GET /healthz`, `GET /readyz` | load balancer only; blocked at the edge | n/a (no principal; ADR-152) |
| Deploy lock | SSM parameter `/abacus/<env>/deploy-lock`; `make deploy-lock ENV=<env>` | deploy workflows (write); any operator (read) | denied |
| Ops tasks | `ops-task.yml` allowlisted commands (section 3.5) | a named operator | denied |
| `TenantProvisioningWorkflow` | Temporal, `background` class | `provision_firm` (called by the ops task) | denied from agent contexts |
| `control_active` | `abacus.modules.platform.api` (section 3.7) | any module, read-only | allowed (read-only; a switch may only stop an agent, never start one) |
| SES identity port | `abacus.modules.communications.ses_identities` (section 3.8) | `communications` for R-01 | denied |
| Existing adapters | section 3.9 | kernel and `communications`, as today | as today |

The only HTTP route in the router tree that touches this contract is `POST /v1/telemetry/errors` (Q-01-T48, matrix action `telemetry.error.report`); it is documented in the epic and is not repeated here.

## 3. Models

Every field carries a data classification (ADR-031). `Internal` unless stated. No field in this contract is Restricted, except the two settings marked below, which are never logged.

### 3.1 WorkOS adapter port

Module `abacus.modules.identity.workos` (new in Q-01-T17). The port is a `Protocol`; the production class calls WorkOS, the fake in `abacus_tools.fakes` (F-04-T27) conforms to the same protocol. Nothing outside `identity` imports the SDK.

```python
class WorkOSPort(Protocol):
    async def discovery(self) -> OidcDiscovery: ...
    async def jwks(self) -> JwkSet: ...
    async def exchange_code(
        self, *, code: str, code_verifier: str, redirect_uri: str
    ) -> TokenSet: ...
    async def lookup_user(self, *, provider_user_id: str) -> ProviderUser: ...
    async def revoke_session(self, *, provider_session_id: str) -> None: ...
```

| Model | Fields | Classification |
|---|---|---|
| `OidcDiscovery` | `issuer: str`, `authorization_endpoint: str`, `token_endpoint: str`, `jwks_uri: str` | Public |
| `JwkSet` | `keys: tuple[Jwk, ...]`, `fetched_at: datetime` | Public |
| `TokenSet` | `access_token: str`, `id_token: str`, `expires_in: int`, `provider_session_id: str` | Restricted (never logged) |
| `ProviderUser` | `provider_user_id: str`, `email: str`, `email_verified: bool`, `display_name: str \| None` | Confidential |

Rules the port keeps:

- `identity/tokens.py` verifies against the keys from `jwks()` and requires the issuer and audience of this environment's WorkOS application. A token minted by another WorkOS environment is rejected (SPEC-050 AC-25).
- Every method raises `IdentityProviderUnavailable` (a `ServiceUnavailable`) on a network or provider error. No fallback to a local key set outside `local` and `test`.
- Settings: `workos_client_id` (Internal), `workos_api_key` (Restricted; read from the task environment, never written to a log or an error text). Outside `local` and `test`, settings validation refuses to start without both.

### 3.2 `runtime-config.json`

Served as a static file next to the SPA at `/runtime-config.json` on each host (the firm host, the neutral portal host, a custom portal host). The deploy uploads it after the hashed assets and before it invalidates `index.html` (Q-01-T18). On portal hosts the entry files are never cached at the edge, so no invalidation is needed there; the deploy reads `portal_base_domain` from the SSM parameter `/abacus/<env>/runtime-config/portal_base_domain` (Q-01-T56, `infra/README.md` "Portal edge"). Locally it is `apps/web/public/runtime-config.json`.

```json
{
  "environment": "staging",
  "oidc": { "authority": "https://auth.example.test", "client_id": "client_example" },
  "sentry": { "dsn": "https://key@o0.ingest.example.test/0", "tunnel": "/v1/telemetry/errors" },
  "release": "0123456789abcdef0123456789abcdef01234567",
  "portal_base_domain": "portal.example.test"
}
```

| Field | Type | Rule | Classification |
|---|---|---|---|
| `environment` | `"local" \| "staging" \| "production"` | required | Public |
| `oidc.authority` | URL string | required; the only place the identity authority is configured for a deployed bundle | Public |
| `oidc.client_id` | string | required | Public |
| `sentry.dsn` | URL string | optional; absent means browser error reporting is off | Public |
| `sentry.tunnel` | same-origin path string | optional; the browser posts error envelopes here (`/v1/telemetry/errors`, Q-01-T48) and never to the ingest directly; absent, or not a path on this origin, means browser error reporting is off (Q-01-T50) | Public |
| `release` | string | required; the git SHA of the build | Public |
| `portal_base_domain` | hostname string | required | Public |

Rules: the file holds no secret and no tenant data. Unknown keys are ignored (additive changes are allowed in place). A missing, non-JSON or schema-invalid file renders a plain error state before the router starts, never a blank page. The bundle contains no authority or client ID literal (Q-01-T23, tested by Q-01-T31). The schema is mirrored as a TypeScript type in `apps/web/src/app-core/runtime-config.ts`; the two are checked against the same fixture.

### 3.3 Public routes and readiness

The list is `abacus.api.public_routes.PUBLIC_ROUTES`, held to `PUBLIC_ROUTE_EXCEPTIONS` by ROUTE-001 (ADR-152). v1 holds `GET /healthz` and `GET /readyz`; P-08 adds `GET /v1/portal/branding` and P-01 adds its pre-session auth routes through their own proposals. Adding a path is an ADR change, not a contract change.

| Route | Answers | Body |
|---|---|---|
| `GET /healthz` | process liveness, no dependency call | `{"status": "ok"}` |
| `GET /readyz` | 200 when every check passes, else 503 | `{"status": "ready"}` or `{"status": "unavailable", "failed": ["<check>", ...]}` |

`READINESS_CHECKS` names, in order: `database`, `identity_database`, `temporal`, `scanner`, `platform_key`. A check name is the only thing a failure reveals; no error text, version or hostname leaves the process. The edge answers 403 for both paths; only the load balancer reaches them. Adding a check is additive: consumers must tolerate a new name in `failed`.

### 3.4 Deploy lock

| Item | Definition |
|---|---|
| Store | SSM parameter `/abacus/<env>/deploy-lock`, one per environment (`staging`, `production`) |
| Value | JSON `{"holder": str, "run_ref": str, "git_sha": str, "taken_at": datetime, "purpose": "deploy" \| "ops-task"}`. Internal; no client data |
| Taken by | `deploy-staging.yml`, `deploy-production.yml`, `rollback.yml` and `ops-task.yml`, after the GitHub `concurrency` group and before the first change |
| Released by | the same workflow, on success, failure and cancellation; a lock older than its workflow's maximum run time is reported as stale by `make deploy-lock`, never silently taken |
| Read | `make deploy-lock ENV=<env>` prints the holder and its age, or `free`. Read-only; it cannot take or release the lock |
| Consumer | F-01's `db_guard` refuses any operator action (migration, seed, local build against that database) while the lock is held; F-04's loaders take the lock as `purpose: ops-task` |

A second deploy waits; it does not queue behind a stale lock without an operator releasing it by an ops request.

### 3.5 Ops-task commands

Operator commands run as ECS one-off `abacus-ops` tasks through `ops-task.yml`, never from a laptop. The workflow takes the deploy lock, runs exactly one allowlisted command name, and records the run. Production commands run only after a PR that adds `deploy/production/ops-requests/<date>-<slug>.yaml` merges (the PR is the change record; the two-person approval of the plan is void under `docs/plan/AMENDMENT-solo.md`).

| Command | Arguments | Effect | Audit |
|---|---|---|---|
| `abacus_tools.tenants provision` | `--name`, `--slug`, `[--synthetic]`, `--plan`, `--admins`, `--idempotency-key`, `--operator` | `provision_firm(...)`, then starts `TenantProvisioningWorkflow` (section 3.6) | `tenant.provisioned` |
| `abacus_tools.tenants status` | `--slug` or `--tenant` | read-only: key status, entitlements, workflow state | none |
| `abacus_tools.tenants key` | `--tenant`, `--operator` | `TenantKeyWorkflow` for an existing tenant | `tenant.key_created`, `tenant.key_replica_verified` |
| `make entitlement` | `FIRM`, `MODULE`, `ENABLED`, `SEATS`, `OPERATOR`, `REASON` | one `tenant_entitlements` row changes | `tenant.entitlements_changed` |
| `abacus_tools.platform_control set` | `--control`, `--scope`, `[--tenant]`, `[--route]`, `--active`, `--operator`, `--reason`, `[--request-ref]` | calls `set_platform_control(...)` | `platform_control.changed` (firm scope); `platform_control_changes` row (always) |
| `abacus_tools.platform_control show` | `[--tenant]` | read-only: active rows | none |
| `abacus_tools.drill verify` | `--env` | read-only restore-drill verification | drill record, no data |
| `make deploy-lock` | `ENV` | read-only (section 3.4) | none |

`--operator` is the operator's handle, never an email address. `--reason` is at most 200 characters and holds no client data. A command missing an argument exits non-zero before it touches anything. Commands that mutate are idempotent for the same idempotency key or the same arguments.

### 3.6 `TenantProvisioningWorkflow`

Workflow ID `tenant_provision:<tenant_id>`; work class `background`; started by the ops task after `provision_firm`. Child workflow `TenantKeyWorkflow` (ID `tenant_key:<tenant_id>`) runs on the `abacus-keyops` task queue. Replay fixtures `tenant-provisioning-v1.json` and `tenant-key-v1.json`; G-04 changes the workflow only through the patch point `g04_plan_v2` (ADR-090).

```python
class ProvisionTenantInput(BaseModel):
    tenant_id: UUID                 # Internal; created by provision_firm
    name: str                       # Confidential (firm name)
    slug: str                       # Internal
    synthetic: bool                 # set only by the definer, never by the app role
    plan: str                       # Internal; a plan key from the entitlements tables
    admins: tuple[AdminInvite, ...] # AdminInvite.email is Confidential; never logged
    idempotency_key: str            # Internal
    operator: str                   # Internal; handle

class ProvisionTenantResult(BaseModel):
    tenant_id: UUID
    key_status: Literal["replica_verified"]
    entitlement_rows: int
    invitations_sent: int
    already_provisioned: bool       # true when the idempotency key was seen before
```

Steps (activities): child `TenantKeyWorkflow`, `set_plan_entitlements`, `invite_first_admins`, `emit_tenant_provisioned`. Region is fixed to `us` by the definer; there is no region argument. Re-running with the same idempotency key returns the same tenant and starts no second workflow. A failure after the firm row exists leaves the firm with `kms_key_status` other than `replica_verified`; no module may treat such a firm as ready (a firm without a verified key stores no client content).

**Built in v1 (Q-01-T45).** The input is a frozen dataclass of strings in `abacus.modules.platform.workflow_types` (`tenant_id`, `slug`, `synthetic`, `plan`, `admins` as a tuple of addresses, `idempotency_key`, `operator`); the firm name stays on the firm row and is not repeated in the payload. The result is `ProvisionTenantResult(tenant_id, key_status, entitlement_rows, invitations_sent)`; `already_provisioned` is reported by the command, not the workflow. v1 runs only `emit_tenant_provisioned`, so `key_status` is `none`, and `entitlement_rows` and `invitations_sent` are 0. The key child (Q-01-T27), the entitlement and first-admin steps (each waiting on a migration), and G-04's `g04_plan_v2` each land behind their own `workflow.patched(...)` id (`tenant_key_v1`, `plan_entitlements_v1`, `first_admins_v1`, `g04_plan_v2`). `status` takes `--tenant` only: firms have no slug column. `make entitlement` writes through the owner role until a definer for `abacus_ops` exists.

`TenantKeyWorkflow` input is `{tenant_id}`. Its result is `{kms_key_arn, kms_key_status, kms_replica_verified_at}`; the three values are recorded on `firms` and the ARN is Internal and never appears in a log line or an event payload.

### 3.7 Kill switches and `platform.api.control_active`

```python
ControlName = Literal[
    "ai_pause", "model_route_block", "email_pause", "read_only", "portal_sign_in"
]

def control_active(
    control: ControlName, tenant_id: UUID | None = None, *, route: str | None = None
) -> bool: ...
```

`control_active` is the one reader of the switches. It returns true when a platform-wide row for the control is active, or a firm row for `tenant_id` is active; for `model_route_block` it also requires a matching `route`. It reads `platform_control_state()` through a 10-second in-process cache (setting `platform_controls_cache_seconds`). It never writes, never raises for an unknown tenant, and has no agent-callable form.

| Control (stored value) | `control_active` name | Scope | Effect | Enforced by |
|---|---|---|---|---|
| `ai_pause` | `ai_pause` | platform or firm | `ai_gateway` refuses every call before any network call; runs end in the existing degraded state | `ai_gateway` |
| `model_route_block` | `model_route_block` | platform, with `route` | route selection skips the route as if an outage block had fired; client data is not rerouted off Bedrock | `ai_gateway` |
| `email_pause` | `email_pause` | platform or firm | the transport records the message `blocked` with violation `platform_paused`; the SES configuration-set pause is the second line | `communications.transport` |
| `read_only` | `read_only` | platform or firm | every non-GET route answers 503 `read_only`, except sign-in, support-session and operational routes | `AbacusRoute` |
| `portal_sign_in` (the plan's epic text says `portal_sign_in_disabled`; see section 11) | `portal_sign_in` | firm | P-08's BFF refuses `start` with the neutral branding card | P-08 BFF |

Tables behind it (owned by `platform`, no app privileges): `platform_controls`, insert-only `platform_control_changes`, and the definers `platform_control_state()` (EXECUTE to the app role) and `set_platform_control(...)` (EXECUTE to `abacus_ops` only). A switch is changed only through `abacus_tools.platform_control` (section 3.5). Existing pauses stay as they are: `firms.agents_paused_at`, per-engagement pause, feature flags.

**The rule for adding a kill switch.** The `control` CHECK list on `platform_controls` is the kill-switch registry; there is no other. The epic that adds a switch (A-02 integration and write-capability pauses, Q-03's webhook pause and API-key revoke-all, Q-05's `destruction_execute`) ships, in its own protected change:

1. a migration that widens the `control` CHECK (and the `route`-style column CHECK when the switch is keyed);
2. `set_platform_control` and `abacus_tools.platform_control` support for the new value;
3. a reader through `control_active` (a new `ControlName` member) and the enforcement point;
4. a row in the table above;
5. an entry in the kill-switch game-day list.

A switch that bypasses `control_active`, or a second registry, is a defect.

### 3.8 SES sender-identity port

Module `abacus.modules.communications.ses_identities` (new in Q-01-T47). For R-01's ADM-10 "Sender domain". The port calls SES in the configured region only (a US region, ADR-142).

```python
class SesIdentityPort(Protocol):
    def create_identity(
        self, *, domain: str, mail_from_subdomain: str
    ) -> IdentitySetup: ...
    def identity_status(self, *, domain: str) -> IdentityStatus: ...
    def delete_identity(self, *, domain: str) -> None: ...
```

| Model | Fields | Classification |
|---|---|---|
| `DnsRecord` | `type: Literal["CNAME", "MX", "TXT"]`, `name: str`, `value: str` | Internal |
| `IdentitySetup` | `domain: str`, `dns_records: tuple[DnsRecord, ...]` (Easy DKIM CNAMEs, custom MAIL FROM MX and SPF TXT) | Internal |
| `IdentityStatus` | `domain: str`, `verification: Literal["pending", "verified", "failed"]`, `dkim: Literal["pending", "verified", "failed"]`, `mail_from: Literal["pending", "verified", "failed"]` | Internal |

**Built in v1 (Q-01-T47).** The models are frozen dataclasses. `SesIdentities(client, *, region, configuration_set=None)` is the SES v2 adapter. `InMemorySesIdentities` is the port for local and test runs; its `set_states(...)` stands in for the DNS checks. `ses_identities()` and `configure_ses_identities(...)` select between them. Three errors can be raised:
- `SesIdentityInvalid`: the domain, or the subdomain (a single label), is not a lower-case host name. The client is never called.
- `SesIdentityNotFound`: `identity_status` for an unknown domain.
- `SesIdentityUnavailable`: any other SES error. It carries the SES error code only.

`delete_identity` for an unknown domain is not an error. A new identity is attached to the environment's configuration set, so its delivery events reach the Q-01-T46 drain.

Rules: Easy DKIM and a custom MAIL FROM domain are always requested. `create_identity` is idempotent for the same domain. The port returns machine states; the words "Pending DNS" and "Verified" belong to ADM-10 and enter the status registry in R-01, not here. A client portal never shows "Accrued" in a sender identity (DEC-01, ADR-133). The staging sink (a receipt rule delivering to a short-lived bucket, read by F-04's mailbox reader) is an environment detail described in `docs/ops/environments.md`, not an interface.

### 3.9 Existing adapters (live)

These exist today. Their names are stable; consumers import them and never the vendor SDK (STORE-001).

| Port | Module and names | Selected when | Notes |
|---|---|---|---|
| Key service | `abacus.kernel.crypto`: `KeyService`, `KmsKeyService`, `LocalKeyService`, `key_service()`, `check_platform_key()` | `ABACUS_ENVIRONMENT` is `staging` or `production` | wraps each data key with the tenant's key; encryption context binds the tenant and the purpose `dek`; key identifier is the alias `alias/abacus/tenant/<tenant_id>`; any KMS error raises `KeyServiceUnavailable`; no local fallback (ADR-035, ADR-104) |
| Payload keyring | `abacus.kernel.crypto.payload_codec`; settings `temporal_payload_keys`, `temporal_payload_current` | the keys setting is present | several key identifiers, one current; a payload sealed under a retired key that is still present decodes |
| Mail transport | `abacus.modules.communications.transport`: `Transport`, `SesTransport`, `LocalMailbox`, `transport()` | `ses_configuration_set` is set | the mechanical body check runs before any client call; a blocked message never reaches SES; tags carry `tenant_id` and `message_id` only; `TransportError` on failure |
| Scanner | `abacus.kernel.scanning`: `Scanner`, `ScanResult`, `ClamdScanner`, `LocalScanner`, `scanner()`, `check_scanner()` | `scanner_endpoint` is set | `ScanResult(clean, reason)` with reason `malware`, `archive_bomb` or `unscannable`; any error or unexpected reply is `unscannable` (fail closed, ADR-153) |

Outside `local` and `test`, settings validation refuses to start without the key service, keyring, scanner and mail settings; `production` also refuses an `anthropic_api_key` (ADR-113). KMS and SES regions must be US regions (ADR-142).

## 4. Status words

None added. Kill-switch state is a boolean (`active`), not a status. SES identity and key states are machine values (`pending`, `verified`, `failed`; `none`, `pending`, `active`, `replica_verified`, `pending_deletion`) and are not shown to users in this contract's words; any screen that shows them takes its labels from `docs/product/status-vocabulary.yaml`. Never invent a synonym (`docs/product/glossary.md`).

## 5. Human-only actions

Every mutating operation in section 3.5 is an operator action: it needs a named operator handle (`--operator`), runs as the EXECUTE-only `abacus_ops` database role, and is refused to every agent and system principal (the ops task is not reachable from any agent context, ADR-005). A kill switch can stop an agent; no operation in this contract can start, approve or accept anything on an agent's behalf. Tenant creation and region pinning are definer functions the app role cannot call.

## 6. Errors

| Status | Body | When |
|---|---|---|
| 503 | `{"status": "unavailable", "failed": ["scanner"]}` | `/readyz`, one or more checks fail |
| 503 | `{"detail": "read_only"}` | a non-GET route while `read_only` is active for the platform or the caller's firm |
| 503 | `{"detail": "service_unavailable"}` | a port raised `IdentityProviderUnavailable`, `KeyServiceUnavailable` or `TransportError` |
| 400 | host not trusted | request `Host` not in `trusted_hosts` |
| 413 | body too large | JSON over 1 MB, other bodies over the upload limit |
| n/a | plain error state in the SPA | `runtime-config.json` missing or invalid |

The `read_only` and `service_unavailable` codes join the error-code catalogue (`error-codes.yaml`, F-03) when Q-01-T37 lands.

## 7. Audit and outbox events

| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `tenant.provisioned` | the workflow's last step | `tenant_id`, `plan`, `synthetic`, `operator` |
| `tenant.key_created` | the key exists in the primary region | `tenant_id`, `operator` |
| `tenant.key_replica_verified` | a probe round trips in the second region | `tenant_id`, `verified_at` |
| `tenant.entitlements_changed` | `make entitlement` changes a row | `tenant_id`, `module`, `enabled`, `seats`, `operator`, `reason` |
| `platform_control.changed` | a firm-scoped switch changes; written into that firm's `audit_events` (actor kind `system`, actor `operator:<handle>`) and the outbox | `control`, `scope`, `route`, `active`, `reason`, `request_ref` |

Platform-wide switch changes are rows in the insert-only `platform_control_changes`, not firm audit events. No payload carries an email address, a key identifier or a client name.

## 8. Example payloads

Synthetic values only. Hosts use the reserved `.test` suffix.

`GET /readyz`, scanner down:

```json
{ "status": "unavailable", "failed": ["scanner"] }
```

Provision the synthetic Brightwater Hale tenant on staging:

```text
python -m abacus_tools.tenants provision \
  --name "Brightwater Hale LLP" --slug brightwater-hale --synthetic \
  --plan pilot --admins admin@sink.example.test \
  --idempotency-key provision-brightwater-hale-1 --operator <handle>
```

`ProvisionTenantResult` for that run, and for a repeat with the same key:

```json
{ "tenant_id": "00000000-0000-4000-8000-000000000001", "key_status": "replica_verified",
  "entitlement_rows": 6, "invitations_sent": 1, "already_provisioned": false }
```

```json
{ "tenant_id": "00000000-0000-4000-8000-000000000001", "key_status": "replica_verified",
  "entitlement_rows": 6, "invitations_sent": 0, "already_provisioned": true }
```

Pause email for one firm:

```text
python -m abacus_tools.platform_control set --control email_pause --scope firm \
  --tenant 00000000-0000-4000-8000-000000000001 --active true \
  --operator <handle> --reason "bounce spike under investigation"
```

`control_active("email_pause", tenant_id)` returns `True` within 10 seconds on every process.

## 9. Consumer contract tests

- Existing adapters and routes: `backend/tests/acceptance/test_q01_kms_key_service.py`, `test_q01_payload_keyring.py`, `test_q01_ses_transport.py`, `test_q01_clamd_scanner.py`, `test_q01_settings_validators.py`, `test_q01_public_routes.py`, `test_q01_edge_middleware.py` (TASK-352).
- Planned with the code, under `backend/tests/contracts/platform_ops/`: WorkOS port conformance (run against the production class with a recorded transport and against the F-04 fake), `control_active` reads and cache window (Q-01-T36, T37), `TenantProvisioningWorkflow` replay and idempotency (Q-01-T45, T52), SES identity port against a stubbed client (Q-01-T47).
- TypeScript: `apps/web/src/app-core/runtime-config.test.ts` asserts the schema in section 3.2 against valid, missing and malformed fixtures (Q-01-T23, T31).

These run in the provider's CI and must stay green for any change to this file.

## 10. Versioning

Additive changes (a new optional `runtime-config.json` key, a new readiness check name, a new `ControlName`, a new ops command) go in place with this file updated in the same commit. Breaking changes (removing or renaming a key, a command or a control; changing a type; changing a lock value shape) ship as v2 with one sprint of overlap (`docs/contracts/README.md`).

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | 2026-10-23 (Q-01-T57) | n/a | frozen as written. Live behind it: sections 3.2 (schema and the TypeScript mirror), 3.3, 3.6 (v1 shape), 3.8 and 3.9. Still to be built against the frozen text: 3.1 (Q-01-T17), 3.4 and 3.5 (Q-01-T18 and the ops-task workflow), 3.7 (Q-01-T36, T37). The frozen parts are pinned by `backend/tests/contracts/platform_ops/test_platform_ops_frozen.py` |

## 11. Open points

- Behaviour of `control_active` when `platform_control_state()` cannot be read beyond the cache window (stop or carry on): decided in ADR-157 (P-66), proposed there as fail closed for `ai_pause` and `read_only` and carry on for the rest.
- The stored value `portal_sign_in_disabled` in the Q-01 epic text against the reader name `portal_sign_in`: ADR-157 proposes `portal_sign_in` for both, and the Q-01-T19 migration (not yet written) would use it.
- Region of record for the tenant key, the multi-Region layout and the dual-control rule for key deletion: ADR-156 (P-65). This contract fixes only the result fields in section 3.6.
- WorkOS port method signatures are final at Q-01-T17; this stub types them from the epic text (discovery and JWKS, code exchange, user lookup, session revoke).
- DEC-22 (authentication vendor) and DEC-03 (AWS foundation) are recorded in `docs/product/decision-log.md`.
