"""T-01-T11 (TASK-2212; SPEC-501 AC-17 to AC-23; T-01 §3.2; ADR-167): gateway condition 6.

A call whose context carries TRI data subjects is refused with `consent_7216` unless every
subject holds both §7216 consents: on every route (`fake` included), for every firm (a synthetic
one too, before the synthetic pass), fail closed when the check is unregistered or a subject is
unresolved, audited and counted, never retried; and model text never carries a full TIN.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

import pytest

from abacus.ai_gateway import ContextBuilder, DataSubject, ProviderError, boundary, sanitise_text
from abacus.ai_gateway.boundary import REASONS, DataBoundaryRefused, enforce_boundary
from abacus.kernel.db import TenantContext

PROMPT = "evidence.screen@v0"
FERRIS = DataSubject(uuid.uuid4(), 2025)


class _Tx:
    def __init__(self, records: list[str]) -> None:
        self.records = records

    def record(self, action: str, **_: object) -> None:
        self.records.append(action)


@pytest.fixture
def audited(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    records: list[str] = []

    @asynccontextmanager
    async def fake_uow(tenant: object) -> AsyncGenerator[_Tx]:
        yield _Tx(records)

    monkeypatch.setattr(boundary, "uow", fake_uow)
    monkeypatch.setattr(boundary, "_check", None)
    monkeypatch.setattr(boundary, "_tri_consent", None)
    boundary.clear_cache()
    return records


def _tenant() -> TenantContext:
    return TenantContext(uuid.uuid4(), "system", "test")


def _consents(monkeypatch: pytest.MonkeyPatch, answer: tuple[uuid.UUID, ...] | None) -> list[int]:
    asked: list[int] = []

    async def check(
        _tenant: TenantContext, subjects: tuple[DataSubject, ...], _at: datetime
    ) -> tuple[uuid.UUID, ...] | None:
        asked.append(len(subjects))
        return answer

    monkeypatch.setattr(boundary, "_tri_consent", check)
    return asked


def test_ac17_consent_7216_is_appended_so_recorded_indices_keep_their_meaning() -> None:
    assert REASONS[:9] == (
        "route",
        "terms",
        "firm",
        "agent",
        "engagement",
        "stage",
        "pii_in_context",
        "tax_return_information",
        "ai_paused",
    )
    assert REASONS.index("consent_7216") == 9


@pytest.mark.parametrize("route", ["fake", "direct", "bedrock"])
async def test_ac17_unregistered_means_every_route_refuses_tri(
    audited: list[str], route: str
) -> None:
    with pytest.raises(DataBoundaryRefused) as refused:
        await enforce_boundary(_tenant(), route, PROMPT, subjects=(FERRIS,))  # pyright: ignore[reportArgumentType] -- a route code
    assert refused.value.reason == "consent_7216"
    assert audited == ["ai.boundary_refused"]


async def test_ac17_a_synthetic_firm_is_gated_before_its_pass(
    audited: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def synthetic(_tenant: TenantContext) -> bool:
        return True

    monkeypatch.setattr(boundary, "_check", synthetic)
    _consents(monkeypatch, None)  # Ferris 1 of 2 signed: the check finds no covering set
    with pytest.raises(DataBoundaryRefused) as refused:
        await enforce_boundary(_tenant(), "direct", PROMPT, subjects=(FERRIS,))
    assert refused.value.reason == "consent_7216"


async def test_ac18_both_consents_in_force_proceed_to_the_other_conditions(
    audited: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = _consents(monkeypatch, (uuid.uuid4(), uuid.uuid4()))
    assert await enforce_boundary(_tenant(), "fake", PROMPT, subjects=(FERRIS,)) is None
    assert asked == [1] and audited == []


async def test_ac19_nothing_is_cached_so_a_revocation_binds_the_next_call(
    audited: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = _tenant()
    _consents(monkeypatch, (uuid.uuid4(),))
    await enforce_boundary(tenant, "fake", PROMPT, subjects=(FERRIS,))
    _consents(monkeypatch, None)  # revoked between the calls
    with pytest.raises(DataBoundaryRefused):
        await enforce_boundary(tenant, "fake", PROMPT, subjects=(FERRIS,))


@pytest.mark.parametrize("unresolved", [DataSubject(None, 2025), DataSubject(uuid.uuid4(), None)])
async def test_ac20_an_unresolved_subject_is_refused_whatever_the_check_says(
    audited: list[str], monkeypatch: pytest.MonkeyPatch, unresolved: DataSubject
) -> None:
    asked = _consents(monkeypatch, (uuid.uuid4(),))
    with pytest.raises(DataBoundaryRefused) as refused:
        await enforce_boundary(_tenant(), "fake", PROMPT, subjects=(FERRIS, unresolved))
    assert refused.value.reason == "consent_7216" and asked == []


async def test_ac17_no_tri_subjects_leaves_the_boundary_as_it_was(audited: list[str]) -> None:
    assert await enforce_boundary(_tenant(), "fake", PROMPT) is None
    assert audited == []


def test_ac17_the_refusal_is_never_retried() -> None:
    assert not issubclass(DataBoundaryRefused, ProviderError)


def test_ac17_the_context_carries_its_subjects() -> None:
    spouse = DataSubject(uuid.uuid4(), 2025)
    built = ContextBuilder().subjects(FERRIS, spouse, FERRIS).task({"a": 1}).build()
    assert built.data_subjects == (FERRIS, spouse)
    assert ContextBuilder().task({"a": 1}).build().data_subjects == ()


def test_ac23_model_text_never_carries_a_full_tin() -> None:
    masked = sanitise_text("Taxpayer 123-45-6789 filed.")
    assert "123-45-6789" not in masked and "•••-••-6789" in masked
    assert sanitise_text("No identifiers here.") == "No identifiers here."
