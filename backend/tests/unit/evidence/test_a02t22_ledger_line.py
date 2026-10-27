"""A-02-T22 (TASK-1470; P-48, ADR-166; C4 §3.1): the `ledger_line` citable's verifier.

The verifier authorises `trial_balance.read` on the anchor's engagement before it reads a
snapshot, holds the snapshot to that engagement's entity, and checks the value and quote against
the line. The moved half (a superseded snapshot) is in the integration suite."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.kernel.uow import UnitOfWork
from abacus.modules.evidence.citations import ledger_line
from abacus.modules.evidence.citations.registry import Anchor, CitationClaim, Verdict, citable
from abacus.modules.identity.api import Actor, Forbidden
from abacus.modules.ledger.api import CitedLine

ENTITY, OTHER = uuid.uuid4(), uuid.uuid4()
SNAPSHOT, ENGAGEMENT = uuid.uuid4(), uuid.uuid4()
LINE = CitedLine(
    SNAPSHOT,
    ENTITY,
    date(2026, 6, 30),
    "1000",
    "Cash  and equivalents",
    Decimal("2140000.00"),
    Decimal("0.00"),
)
PAYABLE = CitedLine(
    SNAPSHOT,
    ENTITY,
    date(2026, 6, 30),
    "2000",
    "Accounts payable",
    Decimal("0.00"),
    Decimal("4180000.00"),
)


def test_the_kind_is_registered_from_evidence() -> None:
    found = citable("ledger_line")
    assert found is not None and found.verifier is ledger_line.verify_ledger_line
    assert ledger_line.ledger_match_id(SNAPSHOT, "1000") == f"led:{SNAPSHOT}:1000"


@pytest.mark.parametrize(
    ("line", "quote", "value", "reason"),
    [
        (LINE, None, None, None),
        (LINE, "cash and", "2,140,000.00", None),
        (PAYABLE, None, "-4,180,000.00", None),  # its net
        (PAYABLE, None, "4,180,000.00", None),  # the side it sits on
        (LINE, None, "2,140,000.01", "value_mismatch"),
        (LINE, None, "two million", "value_mismatch"),
        (LINE, "receivable", None, "quote_not_found"),
    ],
)
def test_the_value_and_quote_are_checked_against_the_line(
    line: CitedLine, quote: str | None, value: str | None, reason: str | None
) -> None:
    assert ledger_line.line_reason(line, quote, value) == reason


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    entity: uuid.UUID = ENTITY,
    refused: bool = False,
    found: tuple[uuid.UUID, CitedLine | None] | None = (ENTITY, LINE),
) -> list[str]:
    calls: list[str] = []

    async def get_ref(_actor: object, engagement_id: uuid.UUID) -> object:
        calls.append("ref")
        return SimpleNamespace(client_entity_id=entity, resource=lambda: "engagement")

    async def authorise(_actor: object, action: str, _resource: object) -> None:
        calls.append(f"authorise:{action}")
        if refused:
            raise Forbidden(action, "wall")

    async def snapshot_line(_session: object, snapshot_id: uuid.UUID, code: str) -> object:
        calls.append("read")
        return found

    monkeypatch.setattr(ledger_line, "get_ref", get_ref)
    monkeypatch.setattr(ledger_line, "authorise", authorise)
    monkeypatch.setattr(ledger_line, "snapshot_line", snapshot_line)
    return calls


async def _verify(
    locator: dict[str, object], *, engagement: uuid.UUID | None = ENGAGEMENT, **claim: str
) -> Verdict:
    tx = cast(UnitOfWork, SimpleNamespace(session=object()))
    anchor = Anchor("trial_balance", uuid.uuid4(), engagement_id=engagement)
    return await ledger_line.verify_ledger_line(
        tx, cast(Actor, object()), CitationClaim("ledger_line", locator, **claim), anchor
    )


LOCATOR: dict[str, object] = {"ledger_snapshot_id": str(SNAPSHOT), "account_code": "1000"}


async def test_a_line_of_the_engagements_entity_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch(monkeypatch)
    verdict = await _verify(LOCATOR, value="2,140,000.00", quote="Cash")
    assert verdict.verified is True
    assert verdict.match_id == f"led:{SNAPSHOT}:1000"
    assert verdict.source_type == "ledger_snapshot"
    assert verdict.source_version == str(SNAPSHOT)
    assert calls == ["ref", "authorise:trial_balance.read", "read"]


async def test_a_refused_reader_learns_nothing_and_no_snapshot_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch(monkeypatch, refused=True)
    verdict = await _verify(LOCATOR)
    assert verdict.reason == "source_not_visible"
    assert "read" not in calls
    assert (await _verify(LOCATOR, engagement=None)).reason == "source_not_visible"


async def test_another_entitys_snapshot_is_as_if_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, found=(OTHER, LINE))
    assert (await _verify(LOCATOR)).reason == "source_not_found"
    _patch(monkeypatch, found=None)
    assert (await _verify(LOCATOR)).reason == "source_not_found"
    _patch(monkeypatch, found=(ENTITY, None))
    assert (await _verify(LOCATOR)).reason == "cell_not_found"


async def test_a_malformed_locator_is_kept_unverified(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch(monkeypatch)
    verdict = await _verify({**LOCATOR, "extra": "x"})
    assert verdict.reason == "locator_invalid"
    assert calls == []
