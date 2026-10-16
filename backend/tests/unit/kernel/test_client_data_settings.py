"""SPEC-036 AC-1, AC-8 (TASK-075): `client_data` only in staging and production, on Bedrock alone,
while the provider terms register covers Bedrock today (ADR-114)."""

from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from abacus.kernel import _provider_terms
from abacus.kernel.config import CatalogModel, Settings
from abacus.kernel.provider_terms import TermsEntry, covering

from .test_model_data_boundary_settings import (
    _environment,  # pyright: ignore[reportPrivateUsage] -- shared setup
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith("ABACUS_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)


def _catalog() -> dict[str, CatalogModel]:
    def model(name: str, model_id: str) -> CatalogModel:
        return CatalogModel(
            name=name,
            ids={"bedrock": f"us.anthropic.{model_id}-v1:0", "direct": model_id},
            usd_in=Decimal(1),
            usd_out=Decimal(5),
        )

    return {
        "small": model("haiku", "claude-haiku-4-5-20251001"),
        "medium": model("sonnet", "claude-sonnet-4-5-20250929"),
        "large": model("opus", "claude-opus-4-1-20250805"),
    }


def _terms(monkeypatch: pytest.MonkeyPatch, *, review_in_days: int) -> None:
    today = date.today()
    entry = TermsEntry(
        "bedrock",
        "Amazon Web Services",
        "us-east-1",
        today - timedelta(days=10),
        today + timedelta(days=review_in_days),
    )
    monkeypatch.setattr(_provider_terms, "ENTRIES", (entry,))


def _client_data(**extra: object) -> Settings:
    return Settings(
        model_data_boundary="client_data",
        model_catalog=_catalog(),  # pyright: ignore[reportArgumentType] -- the validator under test
        **extra,  # pyright: ignore[reportArgumentType] -- as above
    )


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac1_client_data_on_bedrock_with_current_terms(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _environment(monkeypatch, environment)
    _terms(monkeypatch, review_in_days=100)
    found = _client_data(model_routes=("bedrock",))
    assert found.model_data_boundary == "client_data"


@pytest.mark.parametrize("environment", ["evaluation", "local", "test"])
def test_ac1_client_data_is_for_staging_and_production(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _environment(monkeypatch, environment)
    _terms(monkeypatch, review_in_days=100)
    with pytest.raises(ValidationError, match="staging and production"):
        _client_data(model_routes=("bedrock",))


def test_ac1_the_direct_route_is_never_allowed_with_client_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _environment(monkeypatch, "production")
    _terms(monkeypatch, review_in_days=100)
    with pytest.raises(ValidationError, match="bedrock"):
        _client_data(model_routes=("bedrock", "direct"))


def test_ac1_without_terms_client_data_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _environment(monkeypatch, "production")
    monkeypatch.setattr(_provider_terms, "ENTRIES", ())
    with pytest.raises(ValidationError, match="provider-terms"):
        _client_data(model_routes=("bedrock",))


def test_ac8_terms_past_their_review_date_refuse_client_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _environment(monkeypatch, "production")
    _terms(monkeypatch, review_in_days=-1)
    with pytest.raises(ValidationError, match="none covers today"):
        _client_data(model_routes=("bedrock",))


def test_ac8_covering_picks_the_newest_current_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date.today()
    old = TermsEntry("bedrock", "AWS", "us-east-1", today - timedelta(300), today + timedelta(60))
    new = TermsEntry("bedrock", "AWS", "us-east-1", today - timedelta(5), today + timedelta(300))
    monkeypatch.setattr(_provider_terms, "ENTRIES", (old, new))
    assert covering("bedrock", today) == new
    assert covering("direct", today) is None
    assert covering("bedrock", today + timedelta(301)) is None
