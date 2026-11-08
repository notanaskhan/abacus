"""A-06-T29 (TASK-6020; DEC-2615): the financial statements composed for C11, without Pango.

The row's acceptance: "Two renders of Northwind v3 are byte-identical, the client copy carries
DRAFT and no checklist or sources." Here: the same version composes the same blocks and the same
HTML, a draft's HTML carries the DRAFT mark, the body holds no citation, source or checklist
text, a preparation engagement (AR-C 70) carries "No assurance is provided.", and C11's rules
for a composed kind. The PDF bytes and per-page checks run in the image
(`tests/golden_render/test_a06t29_fs_render.py`, `make golden-render`).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from pydantic import TypeAdapter

from abacus.modules.reporting import api as c11
from abacus.modules.reporting import documents as docs
from abacus.modules.reporting.contract import DocBlock
from abacus.modules.reporting.fs_render import (
    KIND,
    NO_ASSURANCE,
    Heading,
    Line,
    Note,
    UnknownStatement,
    amount,
    compose_body,
    lines_of,
    period_text,
)
from abacus.modules.reporting.render.core import RenderInput, build_html

AS_OF = datetime(2026, 10, 2, 14, 10, tzinfo=UTC)
NORTHWIND = Heading(
    "Northwind Robotics 401(k) Plan", date(2025, 12, 31), preparation=False, plan=True
)
# Northwind v3's statement of net assets, from the figure book (16,861,000 = 16,812,400 + 48,600).
LINES = [
    Line(
        "net_assets",
        "Investments at fair value",
        0,
        {2025: Decimal("16812400.00"), 2024: Decimal("15900000.00")},
    ),
    Line("net_assets", "Contributions receivable", 1, {2025: Decimal("48600.00")}),
    Line("net_assets", "Net assets available for benefits", 2, {2025: Decimal("16861000.00")}),
    Line("changes", "Benefits paid to participants", 3, {2025: Decimal("-797800.00")}),
]
NOTES = [Note(1, "Description of the Plan", "The plan is a defined contribution plan.")]
SOURCES = ("TB!", "certified", "Harborline Net Trust", "Disclosure checklist", "cite")


def _of(blocks: list[object], kind: str) -> list[dict[str, object]]:
    typed = [cast(dict[str, object], b) for b in blocks if isinstance(b, dict)]
    return [b for b in typed if b.get("type") == kind]


def _body(heading: Heading = NORTHWIND) -> list[object]:
    return compose_body(heading, LINES, NOTES)


def _html(blocks: list[object], mode: str = "draft") -> str:
    request = RenderInput(
        layout_key="financial_statements",
        blocks=blocks,
        values={},
        title="Financial statements",
        as_of=AS_OF,
        mode=mode,  # type: ignore[arg-type]  # a literal from the test's own list
        content_hash="f" * 64,
    )
    document, css, _citations = build_html(request)
    return document + css


def test_ac_the_same_version_composes_the_same_blocks_and_html() -> None:
    first, second = _body(), _body()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert _html(first) == _html(second)
    shuffled = compose_body(NORTHWIND, list(reversed(LINES)), NOTES)
    assert shuffled == first  # order is the lines' positions, never the read order


def test_ac_the_body_is_c11_blocks_and_the_draft_carries_the_mark() -> None:
    blocks = _body()
    TypeAdapter(list[DocBlock]).validate_python(blocks)
    assert "DRAFT" in _html(blocks)
    assert "DRAFT" not in _html(blocks, mode="final")


def test_ac_the_client_copy_has_no_checklist_sources_or_citations() -> None:
    text = json.dumps(_body())
    for leak in SOURCES:
        assert leak not in text


def test_the_tables_and_headings() -> None:
    blocks = _body()
    headings = [b["text"] for b in _of(blocks, "heading")]
    assert headings == [
        "Northwind Robotics 401(k) Plan",
        "Statements of Net Assets Available for Benefits",
        "Statement of Changes in Net Assets Available for Benefits",
        "Notes to Financial Statements",
        "1. Description of the Plan",
    ]
    tables = _of(blocks, "table")
    rows = [cast(list[list[str]], t["rows"]) for t in tables]
    assert rows[0][0] == ["Investments at fair value", "16,812,400.00", "15,900,000.00"]
    assert rows[0][2] == ["Net assets available for benefits", "16,861,000.00", ""]
    assert rows[1] == [["Benefits paid to participants", "(797,800.00)"]]


def test_ar_c_70_preparation_carries_the_legend_and_an_audit_does_not() -> None:
    prepared = compose_body(
        Heading(NORTHWIND.entity_name, NORTHWIND.period_end, preparation=True, plan=True),
        LINES,
        NOTES,
    )
    legends = _of(prepared, "legend")
    assert legends == [{"type": "legend", "text": NO_ASSURANCE}]
    assert not _of(_body(), "legend")


def test_captions_follow_the_engagement_and_the_years() -> None:
    from abacus.modules.reporting.fs_render import statement_title

    assert statement_title("financial_position", 2, plan=False) == (
        "Statements of Financial Position"
    )
    assert statement_title("activities", 1, plan=False) == "Statement of Activities"
    assert statement_title("financial_position", 2, plan=True) == (
        "Statements of Net Assets Available for Benefits"
    )
    assert statement_title("activities", 1, plan=True) == (
        "Statement of Changes in Net Assets Available for Benefits"
    )
    with pytest.raises(UnknownStatement):
        statement_title("net_assets", 1, plan=False)  # a plan's statement on an entity's paper


def test_an_unknown_statement_is_refused_not_guessed() -> None:
    with pytest.raises(UnknownStatement):
        compose_body(NORTHWIND, [Line("cash_flows", "Cash", 0, {2025: Decimal(1)})], [])


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (Decimal("16861000"), "16,861,000.00"),
        (Decimal("-14850.5"), "(14,850.50)"),
        (Decimal("0"), "0.00"),
    ],
)
def test_amounts_are_code_formatted(value: Decimal, shown: str) -> None:
    assert amount(value) == shown


def test_period_words() -> None:
    end = date(2025, 12, 31)
    assert period_text("net_assets", end, [2025, 2024]) == "December 31, 2025 and 2024"
    assert period_text("changes", end, [2025]) == "Year ended December 31, 2025"
    assert period_text("activities", end, [2025, 2024]) == (
        "Years ended December 31, 2025 and 2024"
    )


def test_line_rows_group_by_line_with_their_years() -> None:
    line = uuid.uuid4()
    base: dict[str, object] = {
        "line_id": line,
        "statement_key": "net_assets",
        "label": "Investments",
        "position": 0,
    }
    rows: list[dict[str, object]] = [
        {**base, "year": 2025, "value": Decimal("16812400.00")},
        {**base, "year": 2024, "value": Decimal("15900000.00")},
    ]
    assert lines_of(rows) == [
        Line(
            "net_assets",
            "Investments",
            0,
            {2025: Decimal("16812400.00"), 2024: Decimal("15900000.00")},
        )
    ]


def test_c11_a_composed_kind_takes_no_template_and_seals_its_body() -> None:
    assert c11.document_kind(KIND).body_provider is not None
    request = c11.RenderRequest(
        kind=KIND,
        owner_ref=c11.OwnerRef("statement_version", uuid.uuid4()),
        scope=c11.RenderScope(client_id=uuid.uuid4()),
        template_version_id=None,
        requested_by=c11.Requester("human", user_id=uuid.uuid4()),
    )
    c11.check_render_request(request)  # no template version: allowed for a composed kind
    with pytest.raises(c11.RenderRefused) as refused:
        c11.check_render_request(replace(request, template_version_id=uuid.uuid4()))
    assert refused.value.code == "unknown_layout"


def test_c11_a_template_snapshot_is_unchanged_and_a_composed_one_carries_its_body() -> None:
    common: dict[str, object] = {
        "layout": "letter",
        "template_version_id": None,
        "variables": {},
        "clause_states": {},
        "overrides": {},
    }
    assert "body" not in docs.snapshot_of(**common)  # type: ignore[arg-type]  # the five keyword parts, as a dict
    sealed = docs.snapshot_of(**common, body=_body())  # type: ignore[arg-type]  # the same, with a body
    assert sealed["body"] == _body()


def test_c11_a_firm_template_may_not_choose_the_composed_layout() -> None:
    from abacus.modules.reporting.render.layouts import LAYOUTS as RENDER_LAYOUTS
    from abacus.modules.reporting.templates import LAYOUTS as TEMPLATE_LAYOUTS

    assert "financial_statements" in RENDER_LAYOUTS
    assert "financial_statements" not in TEMPLATE_LAYOUTS
