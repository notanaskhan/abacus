"""Typed settings from the environment (prefix `ABACUS_`). TASK-005 design §8.

Local and test defaults point at `docker compose`. Outside local and test, every connection setting
must be set explicitly, or startup fails: production can never run on a local default.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from abacus.kernel.classification import classified
from abacus.kernel.work_class import WORK_CLASSES, WorkClass

Environment = Literal["local", "test", "staging", "production"]
_LOCAL_DB = "postgresql+asyncpg://abacus_app:abacusapp@127.0.0.1:55432/abacus"
_LOCAL_MIGRATIONS_DB = "postgresql+asyncpg://abacus_owner:abacusowner@127.0.0.1:55432/abacus"
_LOCAL_RELAY_DB = "postgresql+asyncpg://abacus_relay:abacusrelay@127.0.0.1:55432/abacus"
_LOCAL_IDENTITY_DB = "postgresql+asyncpg://abacus_identity:abacusidentity@127.0.0.1:55432/abacus"
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
    "temporal_payload_key",
)
_LOCAL_DEFAULTS: dict[str, object] = {
    "database_url": _LOCAL_DB,
    "migrations_database_url": _LOCAL_MIGRATIONS_DB,
    "relay_database_url": _LOCAL_RELAY_DB,
    "identity_database_url": _LOCAL_IDENTITY_DB,
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


class ProviderLimits(BaseModel):
    """One model's limits, set at 80% of the provider's published or contracted ones (Q5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rpm: Annotated[int, Field(ge=1, le=1_000_000), classified("internal")]
    tpm: Annotated[int, Field(ge=1, le=100_000_000), classified("internal")]


class Settings(BaseSettings):
    # hide_input_in_errors: a validation error must never echo environment values (secrets).
    model_config = SettingsConfigDict(
        env_prefix="ABACUS_", extra="forbid", frozen=True, hide_input_in_errors=True
    )

    environment: Annotated[Environment, classified("internal")] = "local"
    database_url: Annotated[SecretStr | None, classified("restricted")] = None
    migrations_database_url: Annotated[SecretStr | None, classified("restricted")] = None
    relay_database_url: Annotated[SecretStr | None, classified("restricted")] = None
    identity_database_url: Annotated[SecretStr | None, classified("restricted")] = None
    # Who may sign users in (ADR-029): the issuer and audience tokens must carry, and the
    # provider's public JWKS as JSON. Public keys, not secrets.
    identity_issuer: Annotated[str | None, classified("internal")] = None
    identity_audience: Annotated[str | None, classified("internal")] = None
    identity_jwks: Annotated[str | None, classified("internal")] = None
    database_statement_timeout_ms: Annotated[int, classified("internal")] = 30_000
    s3_endpoint_url: Annotated[str | None, classified("internal")] = None
    s3_access_key: Annotated[SecretStr | None, classified("restricted")] = None
    s3_secret_key: Annotated[SecretStr | None, classified("restricted")] = None
    s3_region: Annotated[str, classified("internal")] = "us-east-1"
    # Write-once evidence storage (ADR-016, ADR-104).
    evidence_bucket: Annotated[str | None, classified("internal")] = None
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
    }
    # Temporal Cloud needs TLS and an API key; both are required outside local and test.
    temporal_tls: Annotated[bool, classified("internal")] = False
    temporal_api_key: Annotated[SecretStr | None, classified("restricted")] = None
    # Encrypts every workflow payload before it leaves the process (ADR-017). KMS in TASK-014.
    temporal_payload_key: Annotated[SecretStr | None, classified("restricted")] = None
    # Observability (ADR-022; TASK-013). Traces export over OTLP only when an endpoint is set;
    # errors go to Sentry only when a DSN is set. Neither is required locally.
    # None: debug locally and in tests, info elsewhere.
    log_level: Annotated[
        Literal["debug", "info", "warning", "error"] | None, classified("internal")
    ] = None
    otlp_endpoint: Annotated[str | None, classified("internal")] = None
    sentry_dsn: Annotated[SecretStr | None, classified("restricted")] = None
    release: Annotated[str | None, classified("internal")] = None

    @model_validator(mode="before")
    @classmethod
    def _local_defaults(cls, data: object) -> object:
        """Local and test only: fill unset connection settings with the compose stack's values."""
        if not isinstance(data, dict):
            return data
        values = dict(cast(dict[str, object], data))
        if values.get("environment", "local") in ("local", "test"):
            for name, value in _LOCAL_DEFAULTS.items():
                values.setdefault(name, value)
        return values

    @model_validator(mode="after")
    def _fake_connector_local_only(self) -> Self:
        if self.fake_connector_dir is not None and self.environment not in ("local", "test"):
            raise ValueError("fake_connector_dir is for local runs and tests only")
        return self

    @model_validator(mode="after")
    def _no_public_keys_outside_local(self) -> Self:
        key = self.temporal_payload_key
        if key is not None:
            value = key.get_secret_value()
            if len(value) < 32 or len(set(value)) < 8:
                raise ValueError("temporal_payload_key must be at least 32 varied characters")
            if self.environment not in ("local", "test") and value.startswith("example-"):
                raise ValueError("temporal_payload_key must be a real secret outside local/test")
        if self.environment not in ("local", "test") and (
            not self.temporal_tls or self.temporal_api_key is None
        ):
            raise ValueError("Temporal needs TLS and an API key outside local and test")
        return self

    # Model provider capacity (ADR-072): per model, shared by every process (migration 0014).
    model_provider: Annotated[str, classified("internal")] = "fake"
    provider_limits: Annotated[dict[str, ProviderLimits], classified("internal")] = {
        "fake-small": ProviderLimits(rpm=600, tpm=1_000_000),
        "fake-medium": ProviderLimits(rpm=600, tpm=1_000_000),
        "fake-large": ProviderLimits(rpm=600, tpm=1_000_000),
    }

    @model_validator(mode="after")
    def _every_work_class(self) -> Self:
        # Limits for exactly the four classes: an override names all of them.
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
    def _explicit_outside_local(self) -> Self:
        missing = [name for name in _CONNECTIONS if getattr(self, name) is None]
        if missing:
            raise ValueError(
                f"{', '.join(missing)} must be set explicitly in environment {self.environment!r}"
            )
        return self


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
