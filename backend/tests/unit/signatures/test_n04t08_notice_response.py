"""N-04-T08 (TASK-3205; DEC-2205): C7 additive for the notice response, and QN-1's G3 rule.

Row acceptance: "A notice-response envelope with the CP2000 response page as a one-page range
completes in record mode and on the DocuSign demo, and G3 reads met for the Whitley notice
engagement through the covering letter." These unit tests pin the contract pieces; the page
range's database rule is `tests/integration/test_n04t08_page_range_migration.py`. The DocuSign
demo run is an ops check (provider sandbox), not part of this suite.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from abacus.modules.engagements.slots import GateFact
from abacus.modules.signatures import builder, consumers, sources
from abacus.modules.signatures.contract import EnvelopeDocumentOut
from abacus.modules.signatures.events import EnvelopeDeclined


def test_ac1_the_notice_response_source_stays_inside_its_contract() -> None:
    consumers.check_contract("notice_response", "notice_response", "general")
    with pytest.raises(consumers.SourceContractBroken):
        consumers.check_contract("notice_response", "form_8879", "efile_authorization")
    with pytest.raises(consumers.SourceContractBroken):
        consumers.check_contract("notice_response", "notice_response", "consent")


def test_ac1_qn5_never_kba_for_a_notice_response() -> None:
    floor = builder._PURPOSE_DEFAULT_METHODS["notice_response"]  # pyright: ignore[reportPrivateUsage] -- the private helper under test
    assert "kba" not in floor
    assert "email_code" in floor


def test_ac1_a_document_carries_a_page_range() -> None:
    doc = sources.SourceDocument(
        sha256="0" * 64, evidence_version_id=uuid.uuid4(), page_from=3, page_to=3
    )
    assert (doc.page_from, doc.page_to) == (3, 3)
    assert not EnvelopeDocumentOut.model_fields["page_from"].is_required()


def test_ac1_the_decline_names_its_source() -> None:
    fields = EnvelopeDeclined.model_fields
    for name in ("purpose", "source_kind", "source_id"):
        assert name in fields and not fields[name].is_required()


async def test_ac1_g3_is_met_by_a_covering_tax_letter(monkeypatch: pytest.MonkeyPatch) -> None:
    notice, tax = uuid.uuid4(), uuid.uuid4()

    async def own(_tenant: object, engagement_id: uuid.UUID) -> GateFact:
        return (
            GateFact(met=engagement_id == tax)
            if engagement_id == tax
            else GateFact(met=False, blockers=("engagement_letter",))
        )

    async def covering(_tenant: object, engagement_id: uuid.UUID) -> list[uuid.UUID]:
        return [tax] if engagement_id == notice else []

    monkeypatch.setattr(sources, "_own_letter", own)
    monkeypatch.setattr(sources, "covering_letter_engagements", covering)
    tenant = SimpleNamespace()
    assert (await sources.letter_gate(tenant, notice)).met  # type: ignore[arg-type] -- the test reaches past the public type
    unrelated = uuid.uuid4()
    assert not (await sources.letter_gate(tenant, unrelated)).met  # type: ignore[arg-type] -- the test reaches past the public type


async def test_ac1_without_a_covering_letter_g3_keeps_its_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def own(_tenant: object, _engagement_id: uuid.UUID) -> GateFact:
        return GateFact(met=False, blockers=("engagement_letter",))

    async def covering(_tenant: object, _engagement_id: uuid.UUID) -> list[uuid.UUID]:
        return [uuid.uuid4()]

    monkeypatch.setattr(sources, "_own_letter", own)
    monkeypatch.setattr(sources, "covering_letter_engagements", covering)
    fact = await sources.letter_gate(SimpleNamespace(), uuid.uuid4())  # type: ignore[arg-type] -- the test reaches past the public type
    assert not fact.met
    assert fact.blockers == ("engagement_letter",)
