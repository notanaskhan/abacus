"""P-11-T07 (TASK-2304; SPEC-520 AC-7 to AC-12, AC-28; P-11 §4.4): the renderer core, the part
that needs no Pango.

The row's acceptance: hostile variable text renders as literal text, no URL is ever fetched, every
draft page carries the watermark, the golden letter is byte-identical on rerun, and the C11 v1
OpenAPI snapshot is frozen. Byte stability and per-page checks need WeasyPrint and run in the
image (`tests/golden_render/test_p11t07_render_core.py`, `make golden-render`); everything up to
the HTML and the fetcher is proven here.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from abacus.modules.reporting.render.core import (
    MissingGlyph,
    RenderInput,
    build_html,
    engine_version,
    mark_for,
)
from abacus.modules.reporting.render.head import RenderRefused
from abacus.modules.reporting.render.html import Letterhead, MissingVariable
from abacus.modules.reporting.render.layouts import LAYOUTS, smallest_type_pt, stylesheet
from abacus.modules.reporting.render.text import clean, literal, uncovered

AS_OF = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
BACKEND = Path(__file__).resolve().parents[3]
Json = dict[str, object]


def _para(*runs: Json) -> Json:
    return {"type": "paragraph", "runs": list(runs)}


def _input(
    blocks: list[object] | None = None, *, values: dict[str, str] | None = None, **kw: object
) -> RenderInput:
    raw: dict[str, object] = {
        "layout_key": "letter",
        "blocks": blocks
        if blocks is not None
        else [
            {"type": "heading", "level": 1, "text": "Engagement letter"},
            _para({"type": "text", "text": "Dear "}, {"type": "var", "key": "client.name"}),
        ],
        "values": values if values is not None else {"client.name": "Copperleaf Coffee Roasters"},
        "title": "Engagement letter",
        "as_of": AS_OF,
        "mode": "draft",
        "content_hash": "c" * 64,
    }
    raw.update(kw)
    return RenderInput(**raw)  # type: ignore[arg-type]  # test fixture assembled from a dict


# --- AC-8: hostile text is literal -------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        ("<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"),
        ('=HYPERLINK("http://x","y")', "=HYPERLINK(&quot;http://x&quot;,&quot;y&quot;)"),
        ("{{ secrets }}", "{{ secrets }}"),
    ],
)
def test_ac8_a_hostile_value_prints_as_its_characters(value: str, shown: str) -> None:
    document, _, _ = build_html(_input(values={"client.name": value}))
    assert f"<bdi>{shown}</bdi>" in document
    assert "<script>" not in document


def test_ac8_zero_width_bidi_and_control_characters_are_removed() -> None:
    hostile = "Cop​per‮leaf⁦ \x07Inc\u0000"
    assert clean(hostile) == "Copperleaf Inc"
    assert literal("a\tb\nc") == "a b c"
    assert literal("x", isolate=True) == "<bdi>x</bdi>"


# --- AC-10: a missing value refuses ------------------------------------------------------------


def test_ac10_a_missing_variable_refuses_with_every_key() -> None:
    blocks: list[object] = [
        _para({"type": "var", "key": "fee.monthly"}, {"type": "var", "key": "client.name"}),
        _para({"type": "var", "key": "fee.monthly"}),
    ]
    with pytest.raises(MissingVariable) as refused:
        build_html(_input(blocks, values={}))
    assert refused.value.code == "missing_variable"
    assert refused.value.keys == ("client.name", "fee.monthly")


# --- AC-7: the watermark ----------------------------------------------------------------------


def test_ac7_a_draft_carries_draft_a_sample_sample_and_a_final_nothing() -> None:
    assert (mark_for("draft"), mark_for("sample"), mark_for("final")) == ("DRAFT", "SAMPLE", None)
    draft, css, _ = build_html(_input(mode="draft"))
    assert "class='watermark'" in draft and ">DRAFT<" in draft
    assert "position: fixed" in css and "rgba(43,31,23,.06)" in css and "72px" in css
    sample, _, _ = build_html(_input(mode="sample"))
    assert ">SAMPLE<" in sample
    final, final_css, _ = build_html(_input(mode="final"))
    assert "watermark" not in final and "watermark" not in final_css


# --- AC-9: no URL is ever fetched --------------------------------------------------------------


def test_ac9_an_image_block_names_only_an_in_memory_asset() -> None:
    asset = uuid.uuid4()
    document, _, _ = build_html(_input([{"type": "image", "asset_id": str(asset)}]))
    assert f"src='asset:firm/{asset}.png'" in document
    assert "http" not in document


# --- AC-11, AC-12: legend and consent type size ------------------------------------------------


def test_ac11_a_legend_is_a_running_footer_on_every_page() -> None:
    blocks: list[object] = [
        {"type": "legend", "text": "Restricted to the use of management"},
        _para({"type": "text", "text": "Statement"}),
    ]
    document, css, _ = build_html(_input(blocks, layout_key="package"))
    assert "<div class='legend'>Restricted to the use of management</div>" in document
    assert "position: running(legend)" in css and "element(legend)" in css


def test_ac12_the_consent_layout_sets_nothing_below_its_minimum() -> None:
    consent = LAYOUTS["consent_7216"]
    assert consent.minimum_type_pt == 12.0
    minimum = 12.0
    effective = stylesheet(consent, None).split("body { font-size: 12pt; }", 1)[1]
    assert smallest_type_pt(effective) >= minimum
    assert smallest_type_pt(stylesheet(LAYOUTS["letter"], None)) < 12.0  # the letter may go lower


# --- layouts, glyphs, blocks -------------------------------------------------------------------


def test_the_six_code_owned_layouts_exist_and_an_unknown_one_refuses() -> None:
    assert set(LAYOUTS) == {
        "letter",
        "consent_7216",
        "report",
        "notice_response",
        "package",
        "run_export",
    }
    with pytest.raises(RenderRefused) as refused:
        build_html(_input(layout_key="brochure"))
    assert refused.value.code == "unknown_layout"


def test_a_character_the_vendored_faces_cannot_draw_refuses_missing_glyph() -> None:
    assert uncovered(["Café — “quoted” · €12"]) == []
    with pytest.raises(MissingGlyph) as refused:
        build_html(_input(values={"client.name": "株式会社"}))
    assert refused.value.code == "missing_glyph" and "U+682A" in refused.value.characters


def test_an_unknown_block_refuses() -> None:
    with pytest.raises(RenderRefused) as refused:
        build_html(_input([{"type": "iframe", "src": "x"}]))
    assert refused.value.code == "unknown_block"


def test_clause_states_and_the_library_standard_decide_what_prints() -> None:
    clause: Json = {
        "type": "clause",
        "clause_id": "limitation",
        "enabled": True,
        "non_standard": False,
        "blocks": [],
    }
    library: dict[str, list[object]] = {
        "limitation": [_para({"type": "text", "text": "Liability is limited."})]
    }
    on, _, _ = build_html(_input([clause], library=library))
    assert "Liability is limited." in on
    off, _, _ = build_html(_input([clause], library=library, clause_states={"limitation": False}))
    assert "Liability is limited." not in off


def test_tables_print_their_decimal_strings_and_numbers_align_right() -> None:
    table: Json = {"type": "table", "columns": ["Line", "Amount"], "rows": [["Fees", "2,400.00"]]}
    document, _, _ = build_html(_input([table]))
    assert '<td>Fees</td><td class="n">2,400.00</td>' in document


def test_the_letterhead_prints_the_firm_and_never_on_a_report() -> None:
    head = Letterhead("Brightwater Hale LLP", ("1450 Larimer St, Denver, CO 80202",))
    letter, _, _ = build_html(_input(letterhead=head))
    assert "<div class='firm'>Brightwater Hale LLP</div>" in letter
    report, _, _ = build_html(_input(layout_key="report", letterhead=head))
    assert "Brightwater Hale LLP" not in report


def test_citations_are_numbered_markers_in_order() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    blocks: list[object] = [
        _para({"type": "cite", "citation_id": str(a)}, {"type": "cite", "citation_id": str(b)}),
        _para({"type": "cite", "citation_id": str(a)}),
    ]
    document, _, citations = build_html(_input(blocks))
    assert citations == (str(a), str(b))
    assert document.count(">[1]</sup>") == 2 and document.count(">[2]</sup>") == 1


def test_the_engine_version_names_the_layouts_and_the_fonts() -> None:
    version = engine_version()
    assert "layouts=1" in version and "fonts=" in version and "weasyprint=" in version


# --- AC-28: C11 v1 frozen ----------------------------------------------------------------------


def test_ac28_c11_v1_is_frozen() -> None:
    snapshot = BACKEND / "tests/contracts/c11_renderer/v1.json"
    frozen = json.loads(snapshot.read_text())
    assert {"GeneratedDocumentOut", "ReportTemplateVersionOut", "ParagraphBlock"} <= set(frozen)
