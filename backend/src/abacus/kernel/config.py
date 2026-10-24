"""Typed settings from the environment (prefix `ABACUS_`). TASK-005 design §8.

Local and test defaults point at `docker compose`. Outside local and test, every connection setting
must be set explicitly, or startup fails: production can never run on a local default.
"""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import Annotated, Final, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from abacus.kernel import provider_terms
from abacus.kernel.classification import classified
from abacus.kernel.work_class import WORK_CLASSES, WorkClass

Environment = Literal["local", "test", "evaluation", "staging", "production"]
# Where synthetic data may stand in for clients' systems: the fake connector and the fake model.
# `evaluation` (SPEC-005 Q4) runs evaluation suites on synthetic firms only, never client data.
SYNTHETIC_ENVIRONMENTS: tuple[str, ...] = ("local", "test", "evaluation")
# Environments that run on the local compose stack, with its defaults and no TLS to Temporal.
# `evaluation` is one (SPEC-026, TASK-049): its runs use throwaway local containers, and the
# runner refuses any destination off this machine (`abacus_tools.evals.runner.guard`).
LOCAL_STACK: tuple[str, ...] = ("local", "test", "evaluation")
_LOCAL_DB = "postgresql+asyncpg://abacus_app:abacusapp@127.0.0.1:55432/abacus"
_LOCAL_MIGRATIONS_DB = "postgresql+asyncpg://abacus_owner:abacusowner@127.0.0.1:55432/abacus"
_LOCAL_RELAY_DB = "postgresql+asyncpg://abacus_relay:abacusrelay@127.0.0.1:55432/abacus"
_LOCAL_IDENTITY_DB = "postgresql+asyncpg://abacus_identity:abacusidentity@127.0.0.1:55432/abacus"
_LOCAL_OPS_DB = "postgresql+asyncpg://abacus_ops:abacusops@127.0.0.1:55432/abacus"
MIN_EVIDENCE_RETENTION_DAYS = 365
_CONNECTIONS = (
    "database_url",
    "migrations_database_url",
    "relay_database_url",
    "identity_database_url",
    "identity_issuer",
    "identity_audience",
    "identity_jwks",
    "s3_endpoint_url",
    "s3_access_key",
    "s3_secret_key",
    "evidence_bucket",
    "temporal_target",
    "trusted_hosts",
)
_LOCAL_DEFAULTS: dict[str, object] = {
    "database_url": _LOCAL_DB,
    "migrations_database_url": _LOCAL_MIGRATIONS_DB,
    "relay_database_url": _LOCAL_RELAY_DB,
    "identity_database_url": _LOCAL_IDENTITY_DB,
    "ops_database_url": _LOCAL_OPS_DB,
    # The fake identity provider (abacus_tools.fakes.identity) signs with a key made per run; local
    # runs and tests install its public JWKS. An empty key set verifies nothing: fail closed.
    "identity_issuer": "https://identity.abacus.local",
    "identity_audience": "abacus-api",
    "identity_jwks": '{"keys": []}',
    "s3_endpoint_url": "http://127.0.0.1:7070",
    "s3_access_key": "abacus",
    "s3_secret_key": "abacuslocal",
    "evidence_bucket": "abacus-evidence",
    # Local and test only: tenant keys are derived from this (ADR-104). Never used elsewhere.
    "local_master_key": "example-local-master-key-public-not-secret",
    "temporal_target": "127.0.0.1:7233",
    # Local and test only: workflow payloads are encrypted with a key derived from this (public).
    "temporal_payload_key": "example-temporal-payload-key-public-not-secret",
    # The API answers to any Host locally and in tests (httpx's test clients send `test`).
    "trusted_hosts": ("*",),
}


class WorkClassLimits(BaseModel):
    """One work class's worker pool: activities and workflow tasks run at once (ADR-071)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_activities: Annotated[int, Field(ge=1), classified("internal")]
    max_workflow_tasks: Annotated[int, Field(ge=1), classified("internal")]
    # Slots (SPEC-003 Q4, Q6): concurrent workflows per firm and per engagement (0 pauses), in the
    # whole class across every process, and how long work may wait before `capacity_timeout`.
    firm_cap: Annotated[int, Field(ge=0), classified("internal")]
    engagement_cap: Annotated[int, Field(ge=0), classified("internal")]
    class_capacity: Annotated[int, Field(ge=1), classified("internal")]
    max_wait_seconds: Annotated[int, Field(ge=1), classified("internal")]
    # Admission (SPEC-003 Q5, D4): the share of a provider's capacity this class leaves for
    # higher classes. A deferrable agent uses the next class's reserve.
    admission_reserve_pct: Annotated[int, Field(ge=0, le=99), classified("internal")]


_US_REGIONS = ("us-east-2", "us-west-2")  # the primary and the DR region (ADR-142)
_KEY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
_HOST_PORT = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?:\d{1,5}$")
_EMAIL = re.compile(r"^[^@\s<>,;]+@[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}$")
# Settings a staging or production process needs for its AWS adapters (SPEC-050 AC-17). The
# WorkOS ones join when its adapter is built (Q-01-T17).
_ADAPTER_SETTINGS = (
    "kms_platform_key_alias",
    "temporal_payload_keys",
    "temporal_payload_current",
    "scanner_endpoint",
    "ses_configuration_set",
    "ses_from_address",
)
_DOMAIN = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
Route = Literal["fake", "direct", "bedrock"]
ModelTier = Literal["small", "medium", "large"]
# ADR-074: an exact model version, e.g. `claude-haiku-4-5-20251001`; Bedrock IDs carry a provider
# prefix and a revision. Never an alias such as `-latest`.
_PINNED = re.compile(
    r"^(?:[a-z]{2}\.)?(?:anthropic\.)?claude-[a-z]+-\d+-\d+"
    r"(?:-\d{8})?(?:-v\d+:\d+)?$"
)


class CatalogModel(BaseModel):
    """One tier's logical model and its ID on each route (SPEC-010): the same model family on
    every route (ADR-073). A route without an ID can't serve the tier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=100), classified("internal")]
    ids: Annotated[dict[Route, str], classified("internal")]
    usd_in: Annotated[Decimal, Field(ge=0), classified("internal")]  # per million tokens
    usd_out: Annotated[Decimal, Field(ge=0), classified("internal")]
    # The sampling temperature pinned for this model, so evaluations repeat. Only where the model
    # accepts one: Claude 5 models reject `temperature` as deprecated, so theirs stays None.
    temperature: Annotated[float | None, Field(ge=0, le=1), classified("internal")] = None


class ParityRecord(BaseModel):
    """A passing route parity report (SPEC-010 Q2): when it ran and the committed file's hash."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    checked_on: Annotated[date, classified("internal")]
    report_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]


def _fake_catalog() -> dict[ModelTier, CatalogModel]:
    return {
        "small": CatalogModel(
            name="fake-small",
            ids={"fake": "fake-small"},
            usd_in=Decimal("0.80"),
            usd_out=Decimal("4.00"),
        ),
        "medium": CatalogModel(
            name="fake-medium",
            ids={"fake": "fake-medium"},
            usd_in=Decimal("3.00"),
            usd_out=Decimal("15.00"),
        ),
        "large": CatalogModel(
            name="fake-large",
            ids={"fake": "fake-large"},
            usd_in=Decimal("15.00"),
            usd_out=Decimal("75.00"),
        ),
    }


class ProviderLimits(BaseModel):
    """One model's limits, set at 80% of the provider's published or contracted ones (Q5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rpm: Annotated[int, Field(ge=1, le=1_000_000), classified("internal")]
    tpm: Annotated[int, Field(ge=1, le=100_000_000), classified("internal")]


# Q-01-T27 (P-65): tenant keys, one at a time, never competing with firms' work.
KEYOPS_LIMITS: Final = WorkClassLimits(
    max_activities=2,
    max_workflow_tasks=2,
    firm_cap=1,
    engagement_cap=1,
    class_capacity=4,
    max_wait_seconds=3600,
    admission_reserve_pct=0,
)


class Settings(BaseSettings):
    # hide_input_in_errors: a validation error must never echo environment values (secrets).
    model_config = SettingsConfigDict(
        env_prefix="ABACUS_", extra="forbid", frozen=True, hide_input_in_errors=True
    )

    environment: Annotated[Environment, classified("internal")] = "local"
    # F-04-T02 (ADR-143): the process demo clock, "demo" or an ISO instant; local and staging
    # only (kernel.clock refuses it in production).
    demo_clock: Annotated[str | None, classified("internal")] = None
    database_url: Annotated[SecretStr | None, classified("restricted")] = None
    migrations_database_url: Annotated[SecretStr | None, classified("restricted")] = None
    relay_database_url: Annotated[SecretStr | None, classified("restricted")] = None
    identity_database_url: Annotated[SecretStr | None, classified("restricted")] = None
    # Q-01-T45 (ADR-156): operator commands (`abacus_tools.tenants`) connect as `abacus_ops`, the
    # EXECUTE-only role (secret `abacus/<env>/db/ops`, read only by the ops task). The API and
    # worker never use it, so it is not required to start them.
    ops_database_url: Annotated[SecretStr | None, classified("restricted")] = None
    # Who may sign users in (ADR-029): the issuer and audience tokens must carry, and the
    # provider's public JWKS as JSON. Public keys, not secrets.
    identity_issuer: Annotated[str | None, classified("internal")] = None
    identity_audience: Annotated[str | None, classified("internal")] = None
    identity_jwks: Annotated[str | None, classified("internal")] = None
    # P-01-T09 (ADR-141, ADR-165): the staff session BFF signs in with this OIDC client, at the
    # provider's authorize and code-exchange endpoints. Its callback is
    # `<web_origin>/v1/auth/callback`, and it accepts cookie refreshes only from `web_origin`.
    # Unset: staff sign-in answers 503 (docs/architecture/authkit-staff-sign-in.md).
    identity_client_id: Annotated[str | None, classified("internal")] = None
    identity_authorize_url: Annotated[str | None, classified("internal")] = None
    identity_exchange_url: Annotated[str | None, classified("internal")] = None
    web_origin: Annotated[str | None, classified("internal")] = None
    # SPEC-012 (Q4): platform staff sign in with a separate issuer (never a firm membership).
    # Unset means no staff can authenticate (break-glass is unavailable).
    staff_issuer: Annotated[str | None, classified("internal")] = None
    staff_audience: Annotated[str | None, classified("internal")] = None
    staff_jwks: Annotated[str | None, classified("internal")] = None
    # P-08-T06 (DEC-155): WorkOS User Management and MFA for portal clients. Unset outside AWS:
    # local runs and tests use the in-memory provider, and a deployed process without them answers
    # portal sign-in with 503 rather than fall back.
    workos_api_key: Annotated[SecretStr | None, classified("restricted")] = None
    workos_client_id: Annotated[str | None, classified("internal")] = None
    database_statement_timeout_ms: Annotated[int, classified("internal")] = 30_000
    s3_endpoint_url: Annotated[str | None, classified("internal")] = None
    s3_access_key: Annotated[SecretStr | None, classified("restricted")] = None
    s3_secret_key: Annotated[SecretStr | None, classified("restricted")] = None
    s3_region: Annotated[str, classified("internal")] = "us-east-1"
    # Write-once evidence storage (ADR-016, ADR-104).
    evidence_bucket: Annotated[str | None, classified("internal")] = None
    # Q-02-T24 (C-09): records kept in COMPLIANCE mode (chain anchors, seal manifests, consent and
    # signature evidence). Unset: writing a record fails closed (no fallback to the evidence one).
    records_bucket: Annotated[str | None, classified("internal")] = None
    evidence_retention_days: Annotated[int, classified("internal")] = 2555
    local_master_key: Annotated[SecretStr | None, classified("restricted")] = None
    # The fake connector serves provider-shaped JSON from here (TASK-010; local and test only).
    fake_connector_dir: Annotated[str | None, classified("internal")] = None
    temporal_target: Annotated[str | None, classified("internal")] = None
    temporal_namespace: Annotated[str, classified("internal")] = "default"
    # The base name of the task queues: one per work class, `<base>-<class>` (ADR-071, SPEC-003).
    # The base queue itself is served for one release, until no workflow remains on it (AC-16).
    # Remove it once this query is empty in every environment:
    # temporal workflow list --query "TaskQueue='abacus' AND ExecutionStatus='Running'"
    temporal_task_queue: Annotated[str, classified("internal")] = "abacus"
    serve_legacy_queue: Annotated[bool, classified("internal")] = True
    # Each work class's limits (TASK-018 design §3); 018b and 018c add caps and thresholds here.
    work_classes: Annotated[dict[WorkClass, WorkClassLimits], classified("internal")] = {
        "interactive": WorkClassLimits(
            max_activities=10,
            max_workflow_tasks=10,
            firm_cap=20,
            engagement_cap=10,
            class_capacity=50,
            max_wait_seconds=120,
            admission_reserve_pct=0,
        ),
        "time_sensitive": WorkClassLimits(
            max_activities=10,
            max_workflow_tasks=10,
            firm_cap=20,
            engagement_cap=10,
            class_capacity=50,
            max_wait_seconds=600,
            admission_reserve_pct=0,
        ),
        "background": WorkClassLimits(
            max_activities=5,
            max_workflow_tasks=5,
            firm_cap=10,
            engagement_cap=5,
            class_capacity=20,
            max_wait_seconds=6 * 3600,
            admission_reserve_pct=25,
        ),
        "batch": WorkClassLimits(
            max_activities=2,
            max_workflow_tasks=2,
            firm_cap=5,
            engagement_cap=2,
            class_capacity=10,
            max_wait_seconds=24 * 3600,
            admission_reserve_pct=50,
        ),
        "keyops": KEYOPS_LIMITS,  # Q-01-T27
    }
    # Temporal Cloud needs TLS and an API key; both are required outside local and test.
    temporal_tls: Annotated[bool, classified("internal")] = False
    temporal_api_key: Annotated[SecretStr | None, classified("restricted")] = None
    # Encrypts every workflow payload before it leaves the process (ADR-017). Local and test use
    # this one key (id `platform-v1`); staging and production use the keyring below instead.
    temporal_payload_key: Annotated[SecretStr | None, classified("restricted")] = None
    # The payload keyring (SPEC-050 AC-14; P2): key ID to secret, as a JSON object, from the
    # `abacus/<env>/temporal/payload-keyring` secret. Payloads are sealed under
    # `temporal_payload_current` and opened under any ID present, so a key can be added and then
    # retired without stranding recorded histories. Never remove an ID histories still use (RB-09).
    temporal_payload_keys: Annotated[dict[str, SecretStr] | None, classified("restricted")] = None
    temporal_payload_current: Annotated[str | None, classified("internal")] = None
    # AWS adapters (SPEC-050; ADR-142, ADR-104, ADR-153). Chosen by configuration, never by default
    # in local development or tests. KMS: each tenant's key is the alias `<prefix><tenant id>`
    # (P1); the platform key is the one `/readyz` probes. Regions are the primary or the DR one.
    kms_alias_prefix: Annotated[str, classified("internal")] = "alias/abacus/tenant/"
    kms_region: Annotated[str, classified("internal")] = "us-east-2"
    # Q-01-T27 (P-65): each tenant key is multi-Region and replicated here; a firm stores client
    # content only once a decrypt has been verified in this region (ADR-156).
    kms_replica_region: Annotated[str, classified("internal")] = "us-west-2"
    kms_platform_key_alias: Annotated[str | None, classified("internal")] = None
    # The ClamAV scanner service, `host:port` (P4). Unset: the local scanner (synthetic only).
    scanner_endpoint: Annotated[str | None, classified("internal")] = None
    scanner_timeout_seconds: Annotated[int, Field(ge=1, le=120), classified("internal")] = 30
    # SES (P3): the environment's configuration set and the platform's sending address. Unset:
    # the local mailbox (synthetic only).
    ses_region: Annotated[str, classified("internal")] = "us-east-2"
    ses_configuration_set: Annotated[str | None, classified("internal")] = None
    ses_from_address: Annotated[str | None, classified("internal")] = None
    # Q-01-T46: SES delivery events reach this SQS queue (configuration set to EventBridge to
    # SQS); unset, nothing drains. Suppressed addresses are kept only as an HMAC under the
    # pepper; local and test runs use a fixed one when it is unset.
    ses_events_queue_url: Annotated[str | None, classified("internal")] = None
    email_suppression_pepper: Annotated[SecretStr | None, classified("restricted")] = None
    # P-07-T10 (DEC-52, DEC-223): a TIN's fingerprint is an HMAC under a per-firm key derived
    # from this pepper, so the same TIN is found on file without opening an envelope. Local and
    # test runs use a fixed public one when it is unset; anywhere else sealing fails closed.
    tin_fingerprint_pepper: Annotated[SecretStr | None, classified("restricted")] = None
    # F-04-T22 (F-04.22, SPEC-307 AC-5): a synthetic firm's mail goes only to this sink domain.
    # Unset, local, test and evaluation runs use the scenario's `.test` sink; any other
    # environment then refuses every synthetic send. Staging sets its SES receipt-rule domain,
    # whose S3 bucket and prefix the staging mailbox reader lists (Q-01-T47).
    mail_sink_domain: Annotated[str | None, classified("internal")] = None
    mail_sink_bucket: Annotated[str | None, classified("internal")] = None
    mail_sink_prefix: Annotated[str, classified("internal")] = "sink/"
    # Observability (ADR-022; TASK-013). Traces export over OTLP only when an endpoint is set;
    # errors go to Sentry only when a DSN is set. Neither is required locally.
    # None: debug locally and in tests, info elsewhere.
    log_level: Annotated[
        Literal["debug", "info", "warning", "error"] | None, classified("internal")
    ] = None
    otlp_endpoint: Annotated[str | None, classified("internal")] = None
    sentry_dsn: Annotated[SecretStr | None, classified("restricted")] = None
    release: Annotated[str | None, classified("internal")] = None
    # HTTP edge (ADR-152, P-45; Q-01-T16). The Host values the API answers to: exact names, `*.`
    # suffixes, IP addresses or CIDR networks (a load balancer probes by target IP). A comma
    # separated list or a JSON array. Explicit outside local and test, never `*`.
    trusted_hosts: Annotated[tuple[str, ...] | None, NoDecode, classified("internal")] = None
    # The neutral domain portals are served under: `<slug>.<portal_base_domain>` is a trusted
    # host. Only a branding hint; tenant resolution never reads the Host header (INV-4).
    portal_base_domain: Annotated[str | None, classified("internal")] = None
    # Peers whose X-Forwarded-For and X-Forwarded-Proto are believed (the load balancer's subnets,
    # as addresses or CIDR networks). Empty: proxy headers are ignored.
    proxy_trusted_hosts: Annotated[tuple[str, ...], NoDecode, classified("internal")] = ()

    @field_validator("trusted_hosts", "proxy_trusted_hosts", mode="before")
    @classmethod
    def _list_from_text(cls, value: object) -> object:
        """A comma separated list or a JSON array in the environment."""
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.startswith("["):
            return json.loads(text)
        return [part.strip() for part in text.split(",") if part.strip()]

    @model_validator(mode="before")
    @classmethod
    def _local_defaults(cls, data: object) -> object:
        """Local, test and evaluation only: fill unset connection settings with the compose
        stack's values (evaluations use throwaway local containers; the runner refuses more)."""
        if not isinstance(data, dict):
            return data
        values = dict(cast(dict[str, object], data))
        if values.get("environment", "local") in LOCAL_STACK:
            for name, value in _LOCAL_DEFAULTS.items():
                values.setdefault(name, value)
        return values

    @model_validator(mode="after")
    def _fake_connector_local_only(self) -> Self:
        if self.fake_connector_dir is not None and self.environment not in SYNTHETIC_ENVIRONMENTS:
            raise ValueError("fake_connector_dir is for local runs, tests and evaluations only")
        return self

    @model_validator(mode="after")
    def _no_public_keys_outside_local(self) -> Self:
        key = self.temporal_payload_key
        if key is not None:
            value = key.get_secret_value()
            if len(value) < 32 or len(set(value)) < 8:
                raise ValueError("temporal_payload_key must be at least 32 varied characters")
            if self.environment not in LOCAL_STACK and value.startswith("example-"):
                raise ValueError("temporal_payload_key must be a real secret outside local/test")
        if self.environment not in LOCAL_STACK and (
            not self.temporal_tls or self.temporal_api_key is None
        ):
            raise ValueError("Temporal needs TLS and an API key outside local and test")
        return self

    # Model routes (SPEC-010; ADR-073): enabled routes in order, each tier's model per route, and
    # each real route's passing parity report (Q2). `fake` is for synthetic environments only.
    model_routes: Annotated[tuple[Route, ...], Field(min_length=1), classified("internal")] = (
        "fake",
    )
    model_catalog: Annotated[dict[ModelTier, CatalogModel], classified("internal")] = Field(
        default_factory=_fake_catalog
    )
    route_parity: Annotated[dict[Route, ParityRecord], classified("internal")] = {}
    anthropic_api_key: Annotated[SecretStr | None, classified("restricted")] = None
    # SPEC-026 (TASK-049): what a real model may see. `synthetic_only`: synthetic firms only.
    # SPEC-036 (TASK-075): `client_data` also lets real firms through the gateway's five-part
    # check, in staging and production, on Bedrock, while the provider terms register covers it
    # (ADR-114).
    model_data_boundary: Annotated[
        Literal["synthetic_only", "client_data"], classified("internal")
    ] = "synthetic_only"
    # SPEC-026 Q3: a real model on a developer's machine (prompt work), synthetic firms only.
    allow_real_model_locally: Annotated[bool, classified("internal")] = False
    bedrock_region: Annotated[str, classified("internal")] = "us-east-1"
    # Q3: an outage (5xx, timeout, connection) blocks that route's model this long.
    outage_block_seconds: Annotated[int, Field(ge=1, le=600), classified("internal")] = 30
    # SPEC-010 Q5: the real embedding model is Titan v2 on Bedrock.
    embedding_provider: Annotated[Literal["fake", "bedrock-titan"], classified("internal")] = (
        "fake"
    )
    # Output controls (ADR-065; SPEC-006 Q1): hosts whose links may stay in model text; empty means
    # every external link is removed.
    output_link_allowlist: Annotated[tuple[str, ...], classified("internal")] = ()
    # Budgets (ADR-069; SPEC-007 Q1, Q3 to Q5): soft limits alert and defer deferrable work; hard
    # limits allow essential work only (the platform's daily hard limit stops everything).
    engagement_budget_usd: Annotated[tuple[Decimal, Decimal], classified("internal")] = (
        Decimal(50),
        Decimal(100),
    )
    firm_budget_usd: Annotated[tuple[Decimal, Decimal], classified("internal")] = (
        Decimal(500),
        Decimal(1000),
    )
    platform_daily_budget_usd: Annotated[tuple[Decimal, Decimal], classified("internal")] = (
        Decimal(200),
        Decimal(400),
    )
    firm_budget_cap_usd: Annotated[Decimal, classified("internal")] = Decimal(1000)
    retrieval_daily_cap: Annotated[int, classified("internal")] = 50
    screening_daily_cap: Annotated[int, classified("internal")] = 200
    anomaly_multiple: Annotated[Decimal, classified("internal")] = Decimal(5)
    anomaly_floor_usd: Annotated[Decimal, classified("internal")] = Decimal(5)
    # Methodology workbooks (SPEC-008 §12) and the unmapped-account gap (Q5: any non-zero balance).
    methodology_max_bytes: Annotated[int, classified("internal")] = 5 * 1024 * 1024
    methodology_max_areas: Annotated[int, classified("internal")] = 50
    methodology_max_items: Annotated[int, classified("internal")] = 2000
    methodology_max_rules: Annotated[int, classified("internal")] = 2000
    unmapped_gap_min_abs_usd: Annotated[Decimal, classified("internal")] = Decimal(0)
    # SPEC-015: links in emails point at the SPA; the local mailbox stands in for SES (Q1).
    app_base_url: Annotated[str, classified("internal")] = "http://localhost:5173"
    local_mailbox_dir: Annotated[str, classified("internal")] = ".local/mailbox"
    # Knowledge retrieval (SPEC-009): the embedding model and its price, and the limits (§7).
    embedding_model: Annotated[str, classified("internal")] = "fake-embed"
    embedding_dimensions: Annotated[int, classified("internal")] = 1024
    embedding_usd_per_million: Annotated[Decimal, classified("internal")] = Decimal("0.02")
    knowledge_max_bytes: Annotated[int, classified("internal")] = 1024 * 1024
    knowledge_max_chunks_per_document: Annotated[int, classified("internal")] = 2000
    knowledge_max_chunks_per_firm: Annotated[int, classified("internal")] = 50_000
    provider_limits: Annotated[dict[str, ProviderLimits], classified("internal")] = {
        "fake-small": ProviderLimits(rpm=600, tpm=1_000_000),
        "fake-medium": ProviderLimits(rpm=600, tpm=1_000_000),
        "fake-large": ProviderLimits(rpm=600, tpm=1_000_000),
        "fake-embed": ProviderLimits(rpm=600, tpm=1_000_000),
    }

    @model_validator(mode="after")
    def _edge_hosts(self) -> Self:
        if self.portal_base_domain is not None and not _DOMAIN.fullmatch(self.portal_base_domain):
            raise ValueError("portal_base_domain must be a lower-case DNS name")
        # ADR-163 section 2: the neutral portal domain never names the product in any label.
        if self.portal_base_domain is not None and "accrued" in self.portal_base_domain.lower():
            raise ValueError("portal_base_domain must be a neutral domain (ADR-163)")
        if self.environment not in LOCAL_STACK:
            # Unset is reported by `_explicit_outside_local`; a bad value is reported here.
            if self.trusted_hosts is not None and (
                not self.trusted_hosts or "*" in self.trusted_hosts
            ):
                raise ValueError(f"trusted_hosts must name the hosts in {self.environment!r}")
            if "*" in self.proxy_trusted_hosts:
                raise ValueError("proxy_trusted_hosts must name the load balancer, not '*'")
        return self

    @model_validator(mode="after")
    def _keyring(self) -> Self:
        keys = self.temporal_payload_keys
        if keys is None and self.temporal_payload_current is None:
            return self
        if not keys or self.temporal_payload_current not in keys:
            raise ValueError("temporal_payload_current must be one of the temporal_payload_keys")
        for key_id, secret in keys.items():
            if not _KEY_ID.fullmatch(key_id):
                raise ValueError("temporal_payload_keys ids are short lower-case names")
            value = secret.get_secret_value()
            if len(value) < 32 or len(set(value)) < 8:
                raise ValueError("every temporal_payload_keys secret needs 32 varied characters")
            if self.environment not in LOCAL_STACK and value.startswith("example-"):
                raise ValueError("temporal_payload_keys must be real secrets outside local/test")
        return self

    @model_validator(mode="after")
    def _adapter_values(self) -> Self:
        if not (
            self.kms_alias_prefix.startswith("alias/") and self.kms_alias_prefix.endswith("/")
        ):
            raise ValueError("kms_alias_prefix looks like 'alias/abacus/tenant/'")
        for name in ("kms_region", "kms_replica_region", "ses_region"):
            if getattr(self, name) not in _US_REGIONS:
                raise ValueError(f"{name} must be one of {', '.join(_US_REGIONS)} (ADR-142)")
        if self.scanner_endpoint is not None and not _HOST_PORT.fullmatch(self.scanner_endpoint):
            raise ValueError("scanner_endpoint is host:port")
        if self.ses_from_address is not None and not _EMAIL.fullmatch(self.ses_from_address):
            raise ValueError("ses_from_address is an email address")
        if self.mail_sink_domain is not None and not _EMAIL.fullmatch(
            f"sink@{self.mail_sink_domain}"
        ):
            raise ValueError("mail_sink_domain is a domain name")
        return self

    @field_validator("work_classes", mode="after")
    @classmethod
    def _keyops_by_default(
        cls, value: dict[WorkClass, WorkClassLimits]
    ) -> dict[WorkClass, WorkClassLimits]:
        # Q-01-T27: an override written for the four admission classes keeps keyops' own limits.
        return value if "keyops" in value else {**value, "keyops": KEYOPS_LIMITS}

    @model_validator(mode="after")
    def _every_work_class(self) -> Self:
        # Limits for exactly the classes: an override names all of them (keyops has a default).
        if set(self.work_classes) != set(WORK_CLASSES):
            raise ValueError(f"work_classes needs limits for exactly {', '.join(WORK_CLASSES)}")
        return self

    @model_validator(mode="after")
    def _retention_floor(self) -> Self:
        # Write-once storage is only as good as its retention (ADR-016).
        if self.evidence_retention_days < MIN_EVIDENCE_RETENTION_DAYS:
            raise ValueError(
                f"evidence_retention_days must be at least {MIN_EVIDENCE_RETENTION_DAYS}"
            )
        return self

    @model_validator(mode="after")
    def _real_models_synthetic_only(self) -> Self:
        """SPEC-026 AC-1, AC-4: a real model only where data is synthetic, and pinned. SPEC-036
        AC-1, AC-8: or, with `client_data`, Bedrock alone in staging and production while the
        register covers it today."""
        real: list[Route] = [r for r in self.model_routes if r != "fake"]
        if self.model_data_boundary == "client_data":
            if self.environment not in ("staging", "production"):
                raise ValueError("model_data_boundary client_data is for staging and production")
            if set(real) != {"bedrock"} or self.embedding_provider != "fake":
                raise ValueError(
                    "with client_data, model_routes are bedrock (and fake) only and embeddings "
                    "stay fake (SPEC-036; ADR-113)"
                )
            if provider_terms.covering("bedrock", date.today()) is None:
                raise ValueError(
                    "client_data needs a current bedrock entry in docs/operations/"
                    "provider-terms.yaml (ADR-114); none covers today"
                )
        elif real or self.embedding_provider != "fake":
            allowed = self.environment == "evaluation" or (
                self.environment == "local" and self.allow_real_model_locally
            )
            if not allowed:
                raise ValueError(
                    f"real model routes are for the evaluation environment only (or local with "
                    f"allow_real_model_locally); not {self.environment!r} (SPEC-026: client data "
                    f"needs a later spec, recorded provider terms and staging)"
                )
        for tier, model in self.model_catalog.items():
            for route in real:
                found = model.ids.get(route)
                if found is None:
                    raise ValueError(f"model_catalog[{tier!r}] has no model for route {route!r}")
                if not _PINNED.fullmatch(found) or "latest" in found:
                    raise ValueError(f"model_catalog[{tier!r}][{route!r}] must be a pinned ID")
        return self

    @model_validator(mode="after")
    def _explicit_outside_local(self) -> Self:
        missing = [name for name in _CONNECTIONS if getattr(self, name) is None]
        if missing:
            raise ValueError(
                f"{', '.join(missing)} must be set explicitly in environment {self.environment!r}"
            )
        return self

    @model_validator(mode="after")
    def _adapters_outside_local(self) -> Self:
        """SPEC-050 AC-17: staging and production start only with the real adapters configured,
        so a deployment can't run on a local fallback; production also refuses a direct
        Anthropic key (ADR-113: Bedrock only for client data). The second half of AC-17, refusing
        the `fake` model route in production, is not enforced yet: SPEC-036's settings tests load
        production on the default route, and the register that lets Bedrock run (ADR-114) is
        empty. It lands with the first production model route (Q-02)."""
        if self.environment in LOCAL_STACK:
            return self
        missing = [name for name in _ADAPTER_SETTINGS if getattr(self, name) is None]
        if missing:
            raise ValueError(
                f"{', '.join(missing)} must be set explicitly in environment {self.environment!r}"
            )
        if self.environment == "production" and self.anthropic_api_key is not None:
            raise ValueError("production refuses anthropic_api_key (ADR-113)")
        return self


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
