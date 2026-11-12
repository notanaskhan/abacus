"""T-04-T42 (ADR-078; TASK-7412): independent acceptance tests for T-04-T14 (the tax form line as a
citable kind), T-04-T19 (the tax tools on C17) and T-04-T30 (engine field mapping), written from
SPEC-649 and the rows' acceptance, not from the implementation.

Row acceptance: "Each property fails when its guard is removed, and no tool or export path returns
a full TIN or changes a value without a human approval." Each test names the guard it holds:
removing the guard (the scrub, the consent requirement, the propose-only output, the published
key check, the derivation filter, the tie-out comparison) makes it fail.
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from abacus.api import create_app  # every module's tools register at import
from abacus.kernel.tin_patterns import scrub_tins
from abacus.modules.agents.tools.registry import registered_tools
from abacus.modules.tax.export_fields import (
    EngineField,
    EngineFieldUnmapped,
    merge_export,
    tie_outs,
)
from abacus.modules.tax.form_line_citations import amount, box_claim, linked_label

SSN = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b")
EIN = re.compile(r"\b\d{2}-?\d{7}\b")
assert callable(create_app)
TAX_TOOLS = {n: t for n, t in registered_tools().items() if n.startswith("tax.")}


# --- T-04-T19: the tax tools ------------------------------------------------------------------


def test_t19_the_tax_tools_are_registered_with_their_kinds() -> None:
    kinds = {n: t.kind for n, t in TAX_TOOLS.items()}
    for name in ("tax.read_return", "tax.list_documents", "tax.read_worksheet"):
        assert kinds[name] == "read", name
    for name in ("tax.compare_years", "tax.compute_residency_facts"):
        assert kinds[name] == "compute", name
    for name in (
        "tax.propose_field_changes",
        "tax.propose_pass_through_treatments",
        "tax.propose_residency",
    ):
        assert kinds[name] == "propose", name


def test_t19_every_tax_read_and_compute_tool_is_tri_so_consent_gates_it_before_any_query() -> None:
    """Guard: `data_class="tri"` is what makes the runtime refuse `consent_required` before the
    handler runs (C19 at the tool layer); a tax read declared anything else would skip it."""
    for name, t in TAX_TOOLS.items():
        if t.kind in ("read", "compute"):
            assert t.data_class == "tri", name


def test_t19_every_propose_tool_answers_a_proposal_never_a_value() -> None:
    """Guard: a propose tool's output carries the proposal's identifiers only, so no propose
    path can hand back (or change) a value; a person approves it in SHL-10."""
    for name, t in TAX_TOOLS.items():
        if t.kind != "propose":
            continue
        fields = set(t.output_model.model_fields)
        assert "proposal_id" in fields, name
        assert fields <= {"proposal_id", "state", "row_count"}, (name, fields)
        assert t.action == "proposal.create", name


def test_t19_no_tool_output_model_has_a_field_that_could_hold_a_full_tin() -> None:
    for name, t in TAX_TOOLS.items():
        for field in t.output_model.model_fields:
            low = field.lower()
            if any(low.endswith(s) for s in ("tin", "ssn", "ein", "itin")):
                raise AssertionError(f"{name}.{field} could carry a full TIN")


def test_t19_every_tax_tool_pins_its_scope_to_the_runs_engagement() -> None:
    """Guard: a targeted tool's targets are the run's engagement and the named taxpayer only; a
    model cannot widen them by naming another engagement."""
    from abacus.modules.tax.tools import FieldChange, FieldChangesIn

    class _Agent:
        engagement_id = uuid.uuid4()

    taxpayer = uuid.uuid4()
    args = FieldChangesIn(
        client_entity_id=taxpayer,
        tax_year=2025,
        changes=[FieldChange(worksheet_id=uuid.uuid4(), field_key="l20", after=Decimal(1550))],
    )
    targets = args.tool_targets(_Agent())  # type: ignore[arg-type]
    assert targets.engagement_ids == (_Agent.engagement_id,)
    assert [(s.entity_id, s.tax_year) for s in targets.tri_subjects] == [(taxpayer, 2025)]
    with pytest.raises(ValueError):  # extra fields (another engagement) are refused
        FieldChangesIn.model_validate(
            {"client_entity_id": str(taxpayer), "tax_year": 2025, "engagement_id": "x",
             "changes": []}
        )  # fmt: skip


# --- offshore masking: no path returns a full TIN ---------------------------------------------


@given(
    st.integers(min_value=1, max_value=899),
    st.integers(min_value=1, max_value=99),
    st.integers(min_value=1, max_value=9999),
)
def test_t19_the_scrub_leaves_no_full_ssn(area: int, group: int, serial: int) -> None:
    """Guard: `scrub_tins` on every tool result (offshore and onshore alike)."""
    ssn = f"{area:03d}-{group:02d}-{serial:04d}"
    out = scrub_tins(f"Taxpayer SSN {ssn} on the W-2")
    assert ssn not in out
    assert ssn.replace("-", "") not in scrub_tins(f"ssn {ssn.replace('-', '')}")
    assert out.endswith(" on the W-2")


def test_t19_the_scrub_masks_an_ein_and_keeps_the_last_four() -> None:
    out = scrub_tins("EIN 12-3456789 for Ridgeline")
    assert "12-3456789" not in out and "6789" in out


# --- T-04-T14: the tax form line as a citation ------------------------------------------------


@pytest.mark.parametrize(
    ("printed", "value"),
    [
        ("14,820", Decimal(14_820)),
        ("$14,820.00", Decimal("14820.00")),
        ("(1,550)", Decimal(-1_550)),
        ("-23,014", Decimal(-23_014)),
        ("n/a", None),
        ("", None),
    ],
)
def test_t14_a_printed_amount_reads_as_its_number_or_none(
    printed: str, value: Decimal | None
) -> None:
    """Guard: the verifier compares the claimed figure as a number; a fabricated one never equals
    the field's (`value_mismatch`)."""
    assert amount(printed) == value


@given(st.integers(min_value=0, max_value=10**9))
def test_t14_the_linked_figure_label_is_codes(value: int) -> None:
    label = linked_label("1040", "3b", Decimal(value))
    assert label == f"Form 1040 · Line 3b {value:,}"
    assert linked_label("1040", "3b", None) == "Form 1040 · Line 3b"


def test_t14_a_box_is_cited_by_its_page_and_bbox_for_the_word_layer_reread() -> None:
    version = uuid.uuid4()
    claim = box_claim(version, 3, (0.1, 0.2, 0.3, 0.4), "1,550")
    assert claim.kind == "document_text"
    assert claim.locator == {
        "evidence_version_id": str(version),
        "page": 3,
        "bbox": [0.1, 0.2, 0.3, 0.4],
    }
    assert claim.value == "1,550" and claim.quote is None


# --- T-04-T30: the export and the import ------------------------------------------------------

WS = uuid.uuid4()


def _field(key: str, engine: str, derivation: str) -> EngineField:
    return EngineField(WS, key, f"Line {key}", engine, derivation)


def test_t30_the_export_carries_accrued_fields_and_never_an_engine_computed_line() -> None:
    """Guard: the derivation filter; an engine line (NY tax) is the engine's, never exported."""
    fields = [
        _field("l20", "it201.line20", "input"),
        _field("l39", "it201.line39", "engine"),
    ]
    values: dict[uuid.UUID, dict[str, dict[str, object]]] = {
        WS: {"l20": {"t": "decimal", "v": "1550"}, "l39": {"t": "decimal", "v": "41070"}}
    }
    out = merge_export({}, fields, values, valid_key=lambda _k: True)
    assert out == {"it201.line20": {"t": "decimal", "v": "1550"}}


def test_t30_an_unmapped_engine_key_refuses_the_export() -> None:
    with pytest.raises(EngineFieldUnmapped):
        merge_export(
            {},
            [_field("l20", "not.a.key", "input")],
            {WS: {"l20": {"t": "decimal", "v": "1"}}},
            valid_key=lambda k: k.startswith("it201."),
        )


def test_t30_a_one_dollar_difference_raises_one_tie_out_and_equal_figures_none() -> None:
    """Guard: code compares engine and Accrued figures (23,014 vs 23,015: one diagnostic)."""
    fields = [_field("l47", "it201.line47", "formula"), _field("l20", "it201.line20", "input")]
    accrued = {WS: {"l47": {"t": "decimal", "v": "23014"}, "l20": {"t": "decimal", "v": "1550"}}}
    engine = {"it201.line47": {"t": "decimal", "v": "23015"}, "it201.line20": {"v": "1550"}}
    found = tie_outs(engine, fields, accrued)
    assert [t.engine_field_key for t in found] == ["it201.line47"]
    same = {"it201.line47": {"v": "23014"}, "it201.line20": {"v": "1550"}}
    assert tie_outs(same, fields, accrued) == []
    assert tie_outs({}, fields, accrued) == []  # no figure on one side is not a difference


def test_t30_never_transmit_no_efile_channel_in_the_export_or_tools() -> None:
    """NEVER-ERO-001: nothing in the export path or the tools names an IRS e-file channel."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "src" / "abacus" / "modules" / "tax"
    banned = re.compile(r"\b(mef|efile_submit|transmit_return|ero_pin|etin)\b", re.IGNORECASE)
    for name in ("export_fields.py", "tools.py", "export.py"):
        text = (root / name).read_text(encoding="utf-8")
        hits = [m.group(0) for m in banned.finditer(text)]
        assert hits == [], (name, hits)
