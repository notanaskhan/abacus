"""T-06-T44 (TASK-8913; SPEC-702 F7; TAX-11; DEC-78; DEC-5915; amber): the form pages service.

Row acceptance: "Two renders of the same checkpoint are byte-identical, and Item F reads 17,914,500
bound to the TB total-assets line." Here: every manifest binding resolves by code from the
checkpoint's cells (Item F from `L14`, code's sum of the asset and contra-asset lines on sheet 03,
not a cell a person typed), money prints the form's way, TINs are masked before they reach a page,
the content hash (the PDF's identifier and the render cache's key) is a pure function of the
checkpoint, template version and values, and the face's HTML is identical for the same inputs.
The PDF's byte identity runs through WeasyPrint in the image
(`tests/golden_render/test_t06t44_form_face_render.py`, `make golden-render`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.reporting.api import FaceField, FacePage, face_html
from abacus.modules.tax import form_pages_service as fp

AS_OF = datetime(2026, 3, 2, 15, 30, tzinfo=UTC)
CHECKPOINT = UUID(int=44)
VERSION = UUID(int=4413)
BACKEND = Path(fp.__file__).resolve().parents[4]

# The reference set's sides for the keys the cells below use (tax_form_lines 1065 TY2025).
SIDES = {
    "L1": "asset", "L3": "asset", "L9a": "asset", "L9b": "contra_asset", "L11": "asset",
    "L14": "total", "L15": "liability", "L19b": "liability", "L21": "capital", "L22": "total",
    "K 1": "income", "K 2": "income", "K 13a": "deduction",
}  # fmt: skip


def _cell(v: object) -> dict[str, object]:
    return {"v": v}


def _values() -> dict[str, dict[str, object] | None]:
    """Sheet 03's signed nets (debits positive) for a balance sheet that totals 17,914,500;
    06 and 09 for the K lines and two recipients."""
    nets = [
        ("L1", "1240500"), ("L3", "310000"), ("L9a", "18900000"), ("L9b", "-2950000"),
        ("L11", "414000"), ("L15", "-215000"), ("L19b", "-11800000"), ("L21", "-5899500"),
        ("K 2", "-1231600"),
    ]  # fmt: skip
    out: dict[str, dict[str, object] | None] = {}
    for n, (key, net) in enumerate(nets, start=2):
        out[f"03!A{n}"], out[f"03!C{n}"] = _cell(key), _cell(net)
    out |= {
        "06!A2": _cell("2"), "06!B2": _cell("Net rental real estate income"),
        "06!C2": _cell("1231600"), "06!A3": _cell("13a"), "06!B3": _cell("Contributions"),
        "06!C3": _cell("12000"),
        "09!B1": _cell("Calder Holdings LLC"), "09!B2": _cell("1206968"), "09!B3": _cell("11760"),
        "09!C1": _cell("Mara Ostrowski"), "09!C2": _cell("24632"), "09!C3": _cell("240"),
    }  # fmt: skip
    return out


def _field(key: str, kind: str, ref: str, fmt: str, page: str = "p1") -> dict[str, object]:
    return {
        "key": key, "page_key": page, "label": key.upper(), "box": [0.1, 0.1, 0.4, 0.13],
        "format": fmt, "binding": {"kind": kind, "ref": ref},
    }  # fmt: skip


MANIFEST: dict[str, object] = {
    "form": "1065",
    "tax_year": 2025,
    "pages": [
        {"page_key": "p1", "page_no": 1, "title": "Form 1065 page 1"},
        {"page_key": "p4", "page_no": 4, "title": "Schedule K, page 4"},
    ],
    "fields": [
        _field("f", "tb_line", "L14", "whole_dollars"),
        _field("d", "return_fact", "entity.ein", "tin"),
        _field("name", "return_fact", "entity.name", "text"),
        _field("i", "return_fact", "return.k1_count", "text"),
        _field("line_1a", "return_fact", "page_one.line_1a", "money"),
        _field("b_4", "return_fact", "schedule_b.q4", "checkbox"),
        _field("e", "return_fact", "entity.started_on", "date"),
        _field("l_15", "tb_line", "L15", "money", "p4"),
        _field("l_9b", "tb_line", "L9b", "money", "p4"),
        _field("l_22", "tb_line", "L22", "whole_dollars", "p4"),
        _field("l_12a", "tb_line", "L12a", "money", "p4"),
        _field("k_2", "workbook_cell", "06!C2", "money", "p4"),
        _field("analysis_1", "return_fact", "analysis.line_1", "money", "p4"),
        _field("analysis_2d", "return_fact", "analysis.line_2d", "money", "p4"),
        _field("analysis_2b", "return_fact", "analysis.line_2b", "money", "p4"),
    ],
}

RECIPIENTS = [(uuid4(), "Calder Holdings LLC"), (uuid4(), "Mara Ostrowski")]
KINDS = {"Calder Holdings LLC": ("gp", "llc"), "Mara Ostrowski": ("gp", "individual")}


def _facts() -> dict[str, object]:
    facts: dict[str, object] = fp.engine_facts(
        "1065",
        [
            {"line_key": "1065.1a", "amount": "0"},
            {"line_key": "1065.B4", "value": "yes"},
            {"line_key": "1065.item_e", "value": "01/15/2018"},
            {"line_key": "1040.1a", "amount": "99"},  # another form's line is ignored
        ],
    )
    facts |= {
        "entity.name": "Ridgeline Property Partners, LP",
        "entity.ein": fp.masked_tin("ein", "0287"),
        "return.k1_count": "2",
    }
    facts |= fp.analysis_facts(_values(), RECIPIENTS, KINDS)
    return facts


def _preview(values: dict[str, dict[str, object] | None] | None = None) -> fp.Preview:
    fields = fp.resolve(MANIFEST, values or _values(), SIDES, _facts())
    return fp.Preview(
        uuid4(), uuid4(), CHECKPOINT, AS_OF, VERSION, "Form 1065 (TY2025)",
        (("p1", "Form 1065 page 1"), ("p4", "Schedule K, page 4")), fields,
    )  # fmt: skip


def _by_key(found: fp.Preview) -> dict[str, str | None]:
    return {f.key: f.value for f in found.fields}


def test_item_f_reads_17914500_bound_to_the_tb_total_assets_line() -> None:
    found = _preview()
    f = next(x for x in found.fields if x.key == "f")
    assert (f.binding_kind, f.binding_ref, f.value) == ("tb_line", "L14", "17,914,500")
    assert fp.trace(found, "f") == (None, ["L14"])
    # Code's sum: assets plus the contra line's (negative) net, never a typed total.
    lines = fp.mapped_lines(_values())
    assert fp.tb_value("L14", lines, SIDES) == Decimal("17914500")
    assert fp.tb_value("L22", lines, SIDES) == Decimal("17914500")


def test_credit_side_lines_print_as_the_form_shows_them() -> None:
    values = _by_key(_preview())
    assert values["l_15"] == "215,000.00"  # a liability's credit net prints positive
    assert values["l_9b"] == "2,950,000.00"  # less accumulated depreciation, positive
    assert values["l_22"] == "17,914,500"
    assert values["l_12a"] is None  # no mapped line: blank, never zero or a guess
    assert values["k_2"] == "1,231,600.00"


def test_money_formats_whole_dollars_and_parenthesised_negatives() -> None:
    assert fp.money(Decimal("-12250.4"), whole=True) == "(12,250)"
    assert fp.money(Decimal("1234.5"), whole=False) == "1,234.50"
    assert fp.money(None, whole=True) is None
    assert fp.shown("checkbox", "yes") == "X" and fp.shown("checkbox", "no") is None
    assert fp.shown("percent", "49.500") == "49.5%"


def test_the_tin_is_masked_before_it_reaches_a_page() -> None:
    values = _by_key(_preview())
    assert values["d"] == "••-•••0287"
    assert fp.masked_tin("ssn", "4410") == "•••-••-4410"
    assert fp.masked_tin("ein", None) is None
    html = face_html(
        "Form 1065", [FacePage("p1", "Page 1")],
        [FaceField(f.page_key, f.label, f.box, f.value or "") for f in _preview().fields],
        as_of=AS_OF,
    )  # fmt: skip
    assert "••-•••0287" in html and "Draft — not for filing" in html


def test_return_facts_come_from_the_engine_summary_and_code() -> None:
    values = _by_key(_preview())
    assert values["line_1a"] == "0.00"
    assert values["b_4"] == "X"
    assert values["e"] == "01/15/2018"
    assert values["i"] == "2"
    # Analysis of Net Income: line 1 = K 2 - K 13a; the LLC's share in 2d, the individual GP's in
    # 2b (active), by code over 06 and 09.
    assert values["analysis_1"] == "1,219,600.00"
    assert values["analysis_2d"] == "1,195,208.00"
    assert values["analysis_2b"] == "24,392.00"


def test_analysis_columns_follow_the_partner_kind() -> None:
    assert fp.analysis_column("lp", "individual") == "2c"
    assert fp.analysis_column("gp", "individual") == "2b"
    assert fp.analysis_column("lp", "corporation") == "2a"
    assert fp.analysis_column("lp", "partnership") == "2d"
    assert fp.analysis_column("lp", "trust") == "2f"
    assert fp.analysis_column(None, None) == "2f"


def test_the_content_hash_is_a_function_of_checkpoint_version_and_values() -> None:
    first, second = _preview(), _preview()
    assert first.content_hash == second.content_hash
    assert len(first.content_hash) == 64
    changed = _values()
    changed["03!C2"] = _cell("1240501")
    assert _preview(changed).content_hash != first.content_hash
    moved = fp.Preview(
        first.return_id, first.engagement_id, UUID(int=45), AS_OF, VERSION, first.title,
        first.pages, first.fields,
    )  # fmt: skip
    assert moved.content_hash != first.content_hash


def test_the_face_html_is_identical_for_the_same_checkpoint() -> None:
    def html(found: fp.Preview) -> str:
        return face_html(
            found.title, [FacePage(k, t) for k, t in found.pages],
            [FaceField(f.page_key, f.label, f.box, f.value or "") for f in found.fields],
            as_of=found.recorded_at,
        )  # fmt: skip

    assert html(_preview()) == html(_preview())


def test_fields_of_a_page_and_unknown_keys() -> None:
    found = _preview()
    assert {f.key for f in fp.fields_of(found, "p4")} >= {"l_15", "k_2", "analysis_1"}
    with pytest.raises(NotFound):
        fp.fields_of(found, "p9")
    with pytest.raises(NotFound):
        fp.trace(found, "nope")
    assert fp.trace(found, "k_2") == ("06!C2", [])
    assert fp.trace(found, "d") == (None, [])


def test_k1_box_2_sums_against_schedule_k_line_2() -> None:
    found = fp.k1_box_2(_values(), RECIPIENTS)
    assert [a for _p, _n, a in found.items] == [Decimal("1206968"), Decimal("24632")]
    assert found.box_2_total == found.schedule_k_line_2 == Decimal("1231600")
    assert found.tally == "tie"
    off = _values()
    off["09!C2"] = _cell("24000")
    assert fp.k1_box_2(off, RECIPIENTS).tally == "off"


def test_the_routes_call_the_service_not_a_stub() -> None:
    contract = (BACKEND / "src/abacus/modules/tax/entity_depth_contract.py").read_text(
        encoding="utf-8"
    )
    for call in (
        "await fp.pages(ctx, return_id, checkpoint)",
        "fp.fields_of(found, page_key)",
        "await fp.page_png(ctx, return_id, page_key)",
        "await fp.k1_previews(ctx, return_id)",
        "await fp.download_draft(ctx, return_id)",
    ):
        assert call in contract
    assert "NotImplementedYet" not in contract
    service = Path(fp.__file__).read_text(encoding="utf-8")
    assert '"form_preview.downloaded"' in service
    assert "ON CONFLICT (work_item_id" in service  # one cache row per (checkpoint, version, page)
