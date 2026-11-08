"""A-05-T58 remainder (S31; TASK-6233; DEC-2828): Schedule H line 4i's column (c) and its C11
render. The loans' description is code's from their terms; the document is composed by code from
the schedule, deterministically, with the handoff's columns, total and footnotes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal as D
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid
from abacus.modules.assurance import ebp_schedule_render as render
from abacus.modules.assurance.compute.ebp import form5500 as engine
from abacus.modules.identity.context import AuthContext
from abacus.modules.reporting import api as c11


def _ctx(kind: str = "human") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type]  # actor kind under test
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


def test_the_loans_description_reads_their_rates_and_last_maturity() -> None:
    assert (
        engine.loans_description([D("9.5"), D("5.25"), D("7")], 2040)
        == "interest rates 5.25%\N{EN DASH}9.50%, maturities through 2040"
    )
    assert engine.loans_description([D("6")], None) == "interest rate 6.00%"
    assert engine.loans_description([], 2031) == "maturities through 2031"
    assert engine.loans_description([], None) == ""


LOANS = "interest rates 5.25%\N{EN DASH}9.50%, maturities through 2040"


def _schedule() -> engine.Schedule4i:
    return engine.schedule_4i(
        [
            engine.HeldAsset(
                "KRS 500 Index Fund", "registered investment company", D("6120450"), None,
                True, True,
            ),
            engine.HeldAsset(
                "Self-directed brokerage accounts (BrokerWindow)", "various", D("1605000"), None,
                False, True,
            ),
            engine.HeldAsset(
                "Participant loans", LOANS, D("312400"), D(0), True, False,
            ),
        ],
        D("8037850"),
    )  # fmt: skip


def test_the_document_is_the_schedule_with_its_total_and_footnotes() -> None:
    blocks = render.compose_4i("Northwind Robotics 401(k) Plan", date(2025, 12, 31), _schedule())
    assert blocks[0] == {"type": "heading", "level": 1, "text": "Northwind Robotics 401(k) Plan"}
    assert blocks[1] == {"type": "heading", "level": 2, "text": render.TITLE_4I}
    table = blocks[3]
    assert isinstance(table, dict)
    assert table["columns"] == list(render.COLUMNS_4I)
    assert table["rows"] == [
        ["*", "KRS 500 Index Fund", "registered investment company", "**", "6,120,450"],
        ["", "Self-directed brokerage accounts (BrokerWindow)", "various", "**", "1,605,000"],
        [
            "*",
            "Participant loans",
            LOANS,
            "0",
            "312,400",
        ],
        ["", "Total", "", "", "8,037,850"],
    ]
    texts = [
        cast(list[dict[str, str]], b["runs"])[0]["text"]
        for b in cast(list[dict[str, object]], blocks)
        if b["type"] == "paragraph"
    ]
    assert texts == ["December 31, 2025", *render.FOOTNOTES_4I]


def test_the_same_schedule_composes_the_same_blocks() -> None:
    one = render.compose_4i("Plan", date(2025, 12, 31), _schedule())
    assert one == render.compose_4i("Plan", date(2025, 12, 31), _schedule())


def test_the_kind_is_code_composed_in_the_statements_layout() -> None:
    render.ensure_kind()
    kind = c11.document_kind(render.KIND)
    assert kind.layout == "financial_statements"
    assert kind.body_provider is not None


async def test_only_a_person_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    async def allowed(*_args: object) -> uuid.UUID:
        return uuid.uuid4()

    monkeypatch.setattr(render.ebp_form5500, "authorise_on", allowed)
    with pytest.raises(DomainInvalid):
        await render.render_4i(_ctx("agent"), uuid.uuid4())
