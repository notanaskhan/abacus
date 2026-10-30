# ac-test-author: ayushkbhatia
"""T-01-T30 (ADR-078; TASK-2418): one purpose per signed document (Treas. Reg. §301.7216-3; C19 §1
and §2), written from the C19 contract and SPEC-501, not from the code.

The row's acceptance includes "a planted combined use-and-disclosure document that is refused":
a firm template published for `use` whose terms carry `ai_disclosure`, or one template version
offered for both purposes, is refused with 422 `one_purpose_per_document` before anything is
rendered or drafted. Collaborators are stand-ins at their APIs; the database half is in
`tests/integration/test_t01t30_consents_independent.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.organisations.consents import FilingUnit, Signer
from abacus.modules.organisations.consents_contract import ConsentRequestIn
from abacus.modules.tax import consent_capture as capture

TENANT = uuid.uuid4()
UNIT = FilingUnit(
    client_id=uuid.uuid4(),
    entity_id=uuid.uuid4(),
    entity_name="Feld household",
    entity_type="household_mfj",
    signers=(Signer(uuid.uuid4(), "taxpayer", "Claire Feld"),),
)
CTX = SimpleNamespace(
    tenant=TenantContext(TENANT, "human", "grace"),
    tenant_id=TENANT,
    user_id=uuid.uuid4(),
    client=False,
    is_support=False,
)


def _published(terms_purpose: str, version_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        template_id=uuid.uuid4(),
        name="BH §7216 consent",
        version=SimpleNamespace(
            version_id=version_id,
            consent=SimpleNamespace(purpose=terms_purpose, expiry_months=None),
        ),
    )


@pytest.fixture
def drafted(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Everything before the templates passes; what reaches rendering is recorded."""
    reached: list[object] = []

    async def unit(ctx: object, entity_id: uuid.UUID) -> FilingUnit:
        return UNIT

    async def nothing(*args: object, **kwargs: object) -> None:
        return None

    async def clock(tenant: object) -> datetime:
        return datetime(2026, 9, 14, 14, 24, tzinfo=UTC)

    async def render(*args: object, **kwargs: object) -> object:
        reached.append(args)
        raise AssertionError("a combined document must be refused before rendering")

    monkeypatch.setattr(capture, "filing_unit", unit)
    monkeypatch.setattr(capture, "refuse_declined", nothing)
    monkeypatch.setattr(capture, "now", clock)
    monkeypatch.setattr(capture, "check_scope", lambda *a, **k: None)
    monkeypatch.setattr(capture, "_render", render)
    return reached


def _ask() -> ConsentRequestIn:
    return ConsentRequestIn.model_validate(
        {
            "client_entity_id": str(UNIT.entity_id),
            "purposes": ["use", "ai_disclosure"],
            "tax_years": [2025],
        }
    )


async def test_ac_a_template_carrying_another_purpose_is_refused(
    monkeypatch: pytest.MonkeyPatch, drafted: list[object]
) -> None:
    combined = uuid.uuid4()

    async def published(ctx: object, purpose: str) -> SimpleNamespace:
        return _published("use", combined)  # the "use" document also asks to disclose

    monkeypatch.setattr(capture, "published_consent_template", published)
    with pytest.raises(capture.OnePurposePerDocument):
        await capture.Capture().request(CTX, _ask())  # pyright: ignore[reportArgumentType] -- a stand-in context
    assert drafted == []


async def test_ac_one_version_for_two_purposes_is_refused(
    monkeypatch: pytest.MonkeyPatch, drafted: list[object]
) -> None:
    shared = uuid.uuid4()

    async def published(ctx: object, purpose: str) -> SimpleNamespace:
        return _published(purpose, shared)  # one document answering for both purposes

    monkeypatch.setattr(capture, "published_consent_template", published)
    with pytest.raises(capture.OnePurposePerDocument):
        await capture.Capture().request(CTX, _ask())  # pyright: ignore[reportArgumentType] -- a stand-in context
    assert drafted == []
