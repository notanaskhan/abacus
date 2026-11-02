"""A-04-T22 (TASK-3008; A-04 §6; DEC-2058): the gap mode's prompt and mapping.

Row acceptance: "On the fake model the Keystone cell carries two verified citations (BH-EBP-110
step 4 and SOC 1 p.14), the draft records 2 waiting inputs, and the gap cases pass." The run's
verification is the workflow's (A-04-T11's suite); here: the gap mode has its own registered
prompt, its mapping turns evidence into D<n> documents and open requests into waiting inputs, a
document citation is a C4 `document_text` claim on its page, and the documents enter the context
as untrusted.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

import abacus.modules.assurance.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the mappings
from abacus.modules.agents.handoff import DraftCitation
from abacus.modules.agents.section_draft import (
    DRAFTER,
    DraftContext,
    _claim,  # pyright: ignore[reportPrivateUsage]
    build_context,
    mode_call,
)
from abacus.modules.agents.section_sources import (
    ModeDocument,
    ModePage,
    SourcePaper,
    mode_mapping,
)
from abacus.modules.agents.spec import spec
from abacus.modules.assurance import draft_mappings

VERSION = uuid.uuid4()
SOC = uuid.uuid4()
PAPER = SourcePaper(
    uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "AUD-04", "General Audit Planning", "planning", 1,
    ("BH-EBP-110:4",), "service_organizations", (),
)  # fmt: skip


def _context() -> DraftContext:
    return DraftContext(
        PAPER,
        VERSION,
        (),
        (),
        (ModeDocument(SOC, "SOC 1 Type 2 report", (ModePage(14, "Section III. Carve-out."),)),),
        ("Bridge letter, Keystone", "SOC 1 report, Ridgeway"),
    )


def test_ac_gap_has_its_own_registered_prompt() -> None:
    prompt, budget = mode_call(spec(DRAFTER), "gap")
    assert prompt == "workpapers.section_draft.gap@v1"
    assert budget > 0
    assert "request_item.read" in spec(DRAFTER).task_scope


def test_ac_gap_has_a_mapping() -> None:
    assert mode_mapping("gap") is draft_mappings.gap_inputs


def test_ac_a_document_citation_is_a_document_text_claim_on_its_page() -> None:
    claim = _claim(DraftCitation(document="D1", page=14, quote="Carve-out."), _context())
    assert claim is not None
    assert claim.kind == "document_text"
    assert claim.locator == {"evidence_version_id": str(SOC), "page": 14}
    assert _claim(DraftCitation(document="D2", page=1, quote="x"), _context()) is None


def test_ac_documents_and_waiting_inputs_enter_the_context() -> None:
    assembled = build_context("gap", _context(), ["cells", "documents"])
    text = str(assembled.messages) if hasattr(assembled, "messages") else str(assembled)
    assert "SOC 1 Type 2 report" in text
    assert "Bridge letter, Keystone" in text


@dataclass(frozen=True)
class _Item:
    description: str
    audit_area: str
    status: str
    evidence_version_id: uuid.UUID | None
    created_at: datetime


@dataclass(frozen=True)
class _Material:
    pages: dict[int, str]


async def test_ac_the_mapping_makes_documents_and_two_waiting_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    at = datetime(2026, 9, 1, tzinfo=UTC)
    items = [
        _Item("SOC 1 report, Keystone", "service_organizations", "received", SOC, at),
        _Item("Bridge letter, Keystone", "service_organizations", "requested", None, at),
        _Item("SOC 1 report, Ridgeway", "service_organizations", "requested", None, at),
        _Item("Bank statements", "cash", "requested", None, at),
    ]

    async def listed(_actor: object, _engagement: uuid.UUID) -> list[_Item]:
        return items

    async def material(_tenant: object, version: uuid.UUID, *, sheets: bool) -> _Material:
        assert version == SOC and sheets is False
        return _Material({14: "Section III.", 1: "Keystone."})

    monkeypatch.setattr(draft_mappings, "request_items_for", listed)
    monkeypatch.setattr(draft_mappings, "review_material", material)
    found = await draft_mappings.gap_inputs(object(), PAPER)  # pyright: ignore[reportArgumentType] -- a stand-in actor
    assert [d.evidence_version_id for d in found.documents] == [SOC]
    assert [p.number for p in found.documents[0].pages] == [1, 14]
    assert found.waiting_on == ("Bridge letter, Keystone", "SOC 1 report, Ridgeway")
