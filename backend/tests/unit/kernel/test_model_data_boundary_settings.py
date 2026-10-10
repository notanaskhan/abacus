"""SPEC-026 AC-1, AC-4, AC-8 (TASK-049): a real model only where data is synthetic, pinned, and
its key never shown."""

from __future__ import annotations

import os
import secrets
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from abacus.kernel.config import CatalogModel, Settings

_EXPLICIT = {
    "database_url": "postgresql+asyncpg://app@db.example.test:5432/abacus",
    "migrations_database_url": "postgresql+asyncpg://owner@db.example.test:5432/abacus",
    "relay_database_url": "postgresql+asyncpg://relay@db.example.test:5432/abacus",
    "identity_database_url": "postgresql+asyncpg://identity@db.example.test:5432/abacus",
    "identity_issuer": "https://idp.example.test",
    "identity_audience": "abacus-api",
    "identity_jwks": '{"keys": []}',
    "temporal_target": "temporal.example.test:7233",
    "temporal_payload_key": "test-payload-key-Zq8Xv2Lm9Wd4Rt7Bn3Hs",
    "temporal_tls": "true",
    "temporal_api_key": "test-temporal-api-key",
    "evidence_bucket": "test-evidence-bucket",
}


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith("ABACUS_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)


def _environment(monkeypatch: pytest.MonkeyPatch, environment: str) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    if environment not in ("local", "test"):
        for name, value in _EXPLICIT.items():
            monkeypatch.setenv(f"ABACUS_{name.upper()}", value)
        for name in Settings.model_fields:
            if name.startswith("s3_"):
                monkeypatch.setenv(f"ABACUS_{name.upper()}", "https://s3.example.test")


def _catalog(small: str = "claude-haiku-4-5-20251001") -> dict[str, CatalogModel]:
    def model(name: str, model_id: str) -> CatalogModel:
        return CatalogModel(
            name=name, ids={"direct": model_id}, usd_in=Decimal(1), usd_out=Decimal(5)
        )

    return {
        "small": model("haiku", small),
        "medium": model("sonnet", "claude-sonnet-5-5"),
        "large": model("opus", "claude-opus-5-5"),
    }


@pytest.mark.parametrize("environment", ["staging", "production", "test", "local"])
def test_ac1_a_real_route_is_refused_where_data_may_not_be_synthetic(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _environment(monkeypatch, environment)
    with pytest.raises(ValidationError, match="evaluation environment only"):
        Settings(model_routes=("direct",), model_catalog=_catalog())  # pyright: ignore[reportArgumentType] -- the validator under test


def test_ac1_real_embeddings_are_refused_outside_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _environment(monkeypatch, "staging")
    with pytest.raises(ValidationError, match="evaluation environment only"):
        Settings(embedding_provider="bedrock-titan")


def test_ac1_evaluation_allows_the_real_route(monkeypatch: pytest.MonkeyPatch) -> None:
    _environment(monkeypatch, "evaluation")
    found = Settings(model_routes=("direct",), model_catalog=_catalog())  # pyright: ignore[reportArgumentType] -- as above
    assert found.model_routes == ("direct",)
    assert found.model_data_boundary == "synthetic_only"


def test_ac1_local_allows_it_only_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    _environment(monkeypatch, "local")
    found = Settings(
        model_routes=("direct",),
        model_catalog=_catalog(),  # pyright: ignore[reportArgumentType] -- as above
        allow_real_model_locally=True,
    )
    assert found.allow_real_model_locally


def test_ac1_the_boundary_has_one_value(monkeypatch: pytest.MonkeyPatch) -> None:
    _environment(monkeypatch, "evaluation")
    with pytest.raises(ValidationError):
        Settings(model_data_boundary="client_data")  # pyright: ignore[reportArgumentType] -- refused by type


@pytest.mark.parametrize(
    "model_id", ["claude-haiku-4-5-latest", "claude-latest", "haiku", "claude-haiku"]
)
def test_ac4_an_unpinned_model_id_is_refused(
    monkeypatch: pytest.MonkeyPatch, model_id: str
) -> None:
    _environment(monkeypatch, "evaluation")
    with pytest.raises(ValidationError, match="pinned"):
        Settings(model_routes=("direct",), model_catalog=_catalog(model_id))  # pyright: ignore[reportArgumentType] -- as above


def test_ac4_a_tier_without_a_model_for_the_route_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _environment(monkeypatch, "evaluation")
    with pytest.raises(ValidationError, match="no model for route"):
        Settings(model_routes=("direct",))  # the default catalog is fake-only


def test_ac8_the_key_never_shows(monkeypatch: pytest.MonkeyPatch) -> None:
    _environment(monkeypatch, "evaluation")
    secret = secrets.token_hex(16)  # made per run: never a literal key in the repository
    monkeypatch.setenv("ABACUS_ANTHROPIC_API_KEY", secret)
    found = Settings(model_routes=("direct",), model_catalog=_catalog())  # pyright: ignore[reportArgumentType] -- as above
    assert isinstance(found.anthropic_api_key, SecretStr)
    assert secret not in repr(found) and secret not in str(found.model_dump())
    monkeypatch.setenv("ABACUS_MODEL_DATA_BOUNDARY", secret)
    with pytest.raises(ValidationError) as raised:
        Settings()
    assert secret not in str(raised.value)
