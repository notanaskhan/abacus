"""T-01-T10 (TASK-2306; SPEC-501 AC-32 to AC-38; T-01 §3.1 Stories 1.1 to 1.5): §7216 consent
capture.

The row's acceptance: Feld's two documents arrive in one envelope as two consents, Kai Ferris
unsigned leaves the set Requested with 1 of 2 signed, and a renewal for Harold Stein answers 409.
These unit tests prove the capture's own logic with organisations, methodology, reporting and
signatures stubbed at their APIs. The database half (the 0402 rows, the partial index behind 409
`consent_declined`, signing on completion) is proven by T-01-T30's independent suite (S19).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import OutboxEvent
from abacus.modules.organisations import consents as rows
from abacus.modules.organisations.consents import ConsentDraft, FilingUnit, Signer
from abacus.modules.organisations.consents_contract import ConsentRequestIn
from abacus.modules.tax import consent_capture as capture

TENANT = uuid.uuid4()
ON = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
CLAIRE, DANIEL = uuid.uuid4(), uuid.uuid4()
FELD = FilingUnit(
    client_id=uuid.uuid4(),
    entity_id=uuid.uuid4(),
    entity_name="Feld household",
    entity_type="household_mfj",
    signers=(Signer(CLAIRE, "taxpayer", "Claire Feld"), Signer(DANIEL, "spouse", "Daniel Feld")),
)


class _Ctx:
    tenant = TenantContext(TENANT, "human", "grace")
    tenant_id = TENANT
    user_id = uuid.uuid4()
    client = False
    is_support = False


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """Every collaborator stubbed at its API; records what the capture asked."""
    seen: dict[str, list[Any]] = {"drafts": [], "records": [], "stored": [], "rendered": []}

    async def filing_unit(ctx: object, entity_id: uuid.UUID) -> FilingUnit:
        return FELD

    async def refuse_declined(*args: object) -> None:
        return None

    async def template(ctx: object, purpose: str) -> object:
        return _template(purpose)

    def render(request: Any) -> Any:
        seen["rendered"].append(request)
        sha = format(len(seen["rendered"]), "064x")
        return type("Out", (), {"pdf": b"%PDF", "render_hash": sha, "page_count": 2})()

    async def put_record(*args: object) -> None:
        seen["stored"].append(args)

    async def retain(*args: object) -> datetime:
        return ON

    async def create_draft(ctx: object, kind: str, set_id: uuid.UUID) -> uuid.UUID:
        draft = await capture._draft_source(ctx, set_id)  # pyright: ignore[reportPrivateUsage, reportArgumentType] -- the source the builder calls
        seen["drafts"].append((kind, draft))
        return uuid.uuid4()

    async def record_request(*args: Any, **kwargs: Any) -> list[uuid.UUID]:
        seen["records"].append((args, kwargs))
        return [uuid.uuid4() for _ in args[3]]

    async def consent_outs(ctx: object, ids: list[uuid.UUID]) -> list[object]:
        return []

    async def now(tenant: object) -> datetime:
        return ON

    recipients = type("R", (), {"line": "Amazon Web Services (Bedrock) · model inference · US"})
    recipients.provider_terms_version = "f" * 64  # type: ignore[attr-defined]  # a stand-in

    for name, value in {
        "filing_unit": filing_unit,
        "refuse_declined": refuse_declined,
        "_template": template,
        "render_isolated": render,
        "put_record": put_record,
        "retain_until_for": retain,
        "create_draft": create_draft,
        "record_request": record_request,
        "consent_outs": consent_outs,
        "now": now,
        "consent_recipients": lambda on: recipients,
    }.items():
        monkeypatch.setattr(capture, name, value)
    return seen


def _template(purpose: str) -> Any:
    terms = type("T", (), {"purpose": purpose, "expiry_months": None})()
    version = type(
        "V",
        (),
        {
            "version_id": uuid.uuid4(),
            "layout_key": "consent_7216",
            "body": [],
            "clauses": [],
            "content_sha256": "a" * 64,
            "consent": terms,
        },
    )()
    return type(
        "P", (), {"template_id": uuid.uuid4(), "name": f"BH §7216 {purpose}", "version": version}
    )()


async def test_ac32_feld_gets_two_documents_in_one_envelope(wired: dict[str, list[Any]]) -> None:
    body = ConsentRequestIn(
        client_entity_id=FELD.entity_id, purposes=["use", "ai_disclosure"], tax_years=[2025]
    )
    await capture.CAPTURE.request(_Ctx(), body)  # type: ignore[arg-type]  # a stand-in context
    [(kind, draft)] = wired["drafts"]
    assert kind == "consent_set" and draft.purpose == "consent_7216"
    assert len(draft.documents) == 2  # one document per purpose
    assert {s.contact_id for s in draft.signers} == {CLAIRE, DANIEL}  # both spouses
    assert draft.signer_order == "parallel"
    [(args, kwargs)] = wired["records"]
    drafts: list[ConsentDraft] = args[3]
    assert [d.purpose for d in drafts] == ["use", "ai_disclosure"]
    assert all(d.provider_terms_version == "f" * 64 for d in drafts)
    assert len(wired["stored"]) == 2  # each document written once to COMPLIANCE storage


async def test_ac33_values_come_from_the_database_and_the_register(
    wired: dict[str, list[Any]],
) -> None:
    body = ConsentRequestIn(
        client_entity_id=FELD.entity_id, purposes=["use"], tax_years=[2024, 2025]
    )
    await capture.CAPTURE.request(_Ctx(), body)  # type: ignore[arg-type]  # a stand-in context
    [request] = wired["rendered"]
    assert request.mode == "final" and request.layout_key == "consent_7216"
    assert request.values["taxpayer.names"] == "Claire Feld and Daniel Feld"
    assert request.values["tax_years"] == "2024 and 2025"
    assert request.values["consent.recipients"].startswith("Amazon Web Services (Bedrock)")


async def test_ac32_a_purpose_named_twice_is_one_document(wired: dict[str, list[Any]]) -> None:
    body = ConsentRequestIn(
        client_entity_id=FELD.entity_id, purposes=["use", "use"], tax_years=[2025]
    )
    await capture.CAPTURE.request(_Ctx(), body)  # type: ignore[arg-type]  # a stand-in context
    assert len(wired["drafts"][0][1].documents) == 1


async def test_ac34_a_render_refusal_drafts_nothing(
    wired: dict[str, list[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus.modules.reporting.api import RenderingRefused

    def refuse(request: object) -> object:
        raise RenderingRefused("missing_variable")

    monkeypatch.setattr(capture, "render_isolated", refuse)
    body = ConsentRequestIn(client_entity_id=FELD.entity_id, purposes=["use"], tax_years=[2025])
    with pytest.raises(capture.ConsentRenderRefused):
        await capture.CAPTURE.request(_Ctx(), body)  # type: ignore[arg-type]  # a stand-in context
    assert wired["drafts"] == [] and wired["records"] == []


def test_ac35_third_party_scope_names_only_years_that_ended() -> None:
    rows.check_scope("third_party_disclosure", {"returns": "TY2024"}, [2024], date(2025, 8, 1))
    with pytest.raises(rows.ScopeNotInExistence):
        rows.check_scope("third_party_disclosure", {"returns": "TY2025"}, [2025], date(2025, 8, 1))
    rows.check_scope("use", {"returns": "TY2025"}, [2025], date(2025, 8, 1))  # only third party


def test_ac36_the_template_expiry_wins_else_one_year() -> None:
    signed = datetime(2026, 9, 9, 15, tzinfo=UTC)
    assert rows.expiry(signed, None) == datetime(2027, 9, 9, 15, tzinfo=UTC)
    assert rows.expiry(signed, 4) == datetime(2027, 1, 9, 15, tzinfo=UTC)


async def test_ac37_only_consent_set_envelopes_sign_consents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[uuid.UUID] = []

    async def completed(tenant: object, envelope_id: uuid.UUID, **kw: object) -> list[uuid.UUID]:
        called.append(envelope_id)
        return []

    async def versions(tenant: object, envelope_id: uuid.UUID) -> dict[uuid.UUID, uuid.UUID]:
        return {}

    async def months(tenant: object, ids: list[uuid.UUID]) -> dict[uuid.UUID, int | None]:
        return {}

    monkeypatch.setattr(capture, "envelope_completed", completed)
    monkeypatch.setattr(capture, "consent_template_versions_on", versions)
    monkeypatch.setattr(capture, "consent_expiry_months", months)
    other = OutboxEvent(
        uuid.uuid4(),
        TENANT,
        "envelope.completed",
        {"source_kind": "engagement_letter", "envelope_id": str(uuid.uuid4())},
    )
    await capture.on_envelope_completed(other)
    assert called == []
    mine = uuid.uuid4()
    await capture.on_envelope_completed(
        OutboxEvent(
            uuid.uuid4(),
            TENANT,
            "envelope.completed",
            {"source_kind": "consent_set", "envelope_id": str(mine), "provider": "fake"},
        )
    )
    assert called == [mine]


def test_ac38_the_capture_and_the_source_are_registered() -> None:
    import abacus.modules.tax.api  # noqa: F401 -- registration happens at import
    from abacus.modules.organisations.slots import consent_capture
    from abacus.modules.signatures.api import envelope_source

    assert consent_capture() is capture.CAPTURE
    assert envelope_source("consent_set").draft is not None
