"""A-05-T28 (TASK-3208; ADR P-58; DEC-2208): the ledger's document-extraction path.

Row acceptance: "A trust-report TB with one unverified line or a footing difference is refused,
and an adopted snapshot shows its 'document extraction' provenance on AUD-06." The refusals come
before any write; the stored provenance is the 0659 CHECK and the snapshot's columns
(`tests/integration/test_a05t28_ledger_document_migration.py`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest

from abacus.kernel.uow import UnitOfWork
from abacus.modules.ledger.api import (
    DocumentUnbalanced,
    LineUnverified,
    record_document_snapshot,
)
from abacus.modules.ledger.normalise import LedgerLine, NormalisedTrialBalance

START, END = date(2025, 1, 1), date(2025, 12, 31)


def _tb(debit: str = "1366900.00", credit: str = "1366900.00") -> NormalisedTrialBalance:
    lines = (
        LedgerLine("1000", "Cash and equivalents", Decimal(debit), Decimal(0), "p3:l1"),
        LedgerLine("3000", "Net assets available", Decimal(0), Decimal(credit), "p3:l2"),
    )
    return NormalisedTrialBalance(START, END, "USD", lines, Decimal(debit), Decimal(credit))


async def _never(_ids: object) -> frozenset[uuid.UUID]:
    raise AssertionError("no C4 call for a TB that does not foot")


async def test_a_footing_difference_is_refused_before_anything() -> None:
    with pytest.raises(DocumentUnbalanced):
        await record_document_snapshot(
            cast(UnitOfWork, object()),
            client_entity_id=uuid.uuid4(),
            period_start=START,
            period_end=END,
            tb=_tb(credit="1366800.00"),
            line_citations={"p3:l1": uuid.uuid4(), "p3:l2": uuid.uuid4()},
            source_evidence_version_id=uuid.uuid4(),
            extraction_run_id=uuid.uuid4(),
            pulled_at=datetime.now(UTC),
            supported=_never,
        )


async def test_one_uncited_line_is_refused() -> None:
    with pytest.raises(LineUnverified) as caught:
        await record_document_snapshot(
            cast(UnitOfWork, object()),
            client_entity_id=uuid.uuid4(),
            period_start=START,
            period_end=END,
            tb=_tb(),
            line_citations={"p3:l1": uuid.uuid4()},
            source_evidence_version_id=uuid.uuid4(),
            extraction_run_id=uuid.uuid4(),
            pulled_at=datetime.now(UTC),
            supported=_never,
        )
    assert caught.value.facts == {"account_code": "3000"}


async def test_one_unverified_citation_is_refused() -> None:
    good, bad = uuid.uuid4(), uuid.uuid4()

    async def supported(ids: object) -> frozenset[uuid.UUID]:
        return frozenset({good})

    with pytest.raises(LineUnverified) as caught:
        await record_document_snapshot(
            cast(UnitOfWork, object()),
            client_entity_id=uuid.uuid4(),
            period_start=START,
            period_end=END,
            tb=_tb(),
            line_citations={"p3:l1": good, "p3:l2": bad},
            source_evidence_version_id=uuid.uuid4(),
            extraction_run_id=uuid.uuid4(),
            pulled_at=datetime.now(UTC),
            supported=supported,
        )
    assert caught.value.facts == {"account_code": "3000"}
