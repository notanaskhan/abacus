"""T-04-T30 (TASK-6805; T-04 §3.10 AC-10.1 to AC-10.4; DEC-3405): worksheet fields in the engine
exchange, in code.

Row acceptance: "An export uses only fields from the current approved checkpoint, an import
changes no value until a person approves its checkpoint, a 23,014 vs 23,015 difference raises one
engine_diagnostic issue, and the never-transmit tests stay green."
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from abacus.modules.integrations.api import engine_field_profile
from abacus.modules.tax.export_fields import (
    EngineField,
    EngineFieldUnmapped,
    merge_export,
    tie_outs,
)

SHEET = uuid.uuid4()
NYC = EngineField(SHEET, "nyc_tax", "NYC tax", "nyc.tax", "formula")
LINE_20 = EngineField(SHEET, "line20", "IT-201 line 20", "it201.line20", "input")
NY_TAX = EngineField(SHEET, "ny_tax", "NY tax", "it201.line39", "engine")


def test_ac_10_1_worksheet_fields_join_under_their_engine_key() -> None:
    values = merge_export(
        {"f1040.l2a": {"t": "decimal", "v": "1550"}},
        [LINE_20, NY_TAX],
        {SHEET: {"line20": {"t": "decimal", "v": "1550"}, "ny_tax": {"t": "decimal", "v": "9"}}},
    )
    assert values == {
        "f1040.l2a": {"t": "decimal", "v": "1550"},
        "it201.line20": {"t": "decimal", "v": "1550"},
    }  # the engine-computed NY tax line is the engine's own: never sent back


def test_ac_10_1_a_key_outside_the_profile_blocks_the_export() -> None:
    odd = EngineField(SHEET, "line20", "IT-201 line 20", "IT201 LINE 20", "input")
    with pytest.raises(EngineFieldUnmapped):
        merge_export({}, [odd], {SHEET: {"line20": {"t": "decimal", "v": "1"}}})


def test_the_profile_accepts_validated_key_shapes() -> None:
    profile = engine_field_profile()
    assert profile.valid_key("it201.line20") and profile.valid_key("it360_1.recompute")
    assert not profile.valid_key("line20") and not profile.valid_key("IT201.line20")
    assert profile.columns == ("field_key", "form", "line", "value")


def test_ac_10_3_a_one_dollar_difference_is_one_tie_out() -> None:
    found = tie_outs(
        {"nyc.tax": {"t": "decimal", "v": "23015"}, "it201.line39": {"t": "decimal", "v": "1"}},
        [NYC, NY_TAX],
        {SHEET: {"nyc_tax": {"t": "decimal", "v": "23014"}}},
    )
    assert [(t.engine_field_key, t.label) for t in found] == [("nyc.tax", "NYC tax")]


def test_ac_10_3_equal_or_missing_figures_are_not_differences() -> None:
    assert (
        tie_outs(
            {"nyc.tax": {"t": "decimal", "v": "23014.00"}},
            [NYC],
            {SHEET: {"nyc_tax": {"t": "decimal", "v": "23014"}}},
        )
        == []
    )
    assert tie_outs({}, [NYC], {SHEET: {"nyc_tax": {"t": "decimal", "v": "23014"}}}) == []
    assert tie_outs({"nyc.tax": {"t": "decimal", "v": "1"}}, [NYC], {}) == []


def test_ac_10_4_nothing_here_transmits() -> None:
    source = (
        Path(__file__).resolve().parents[3] / "src/abacus/modules/tax/export_fields.py"
    ).read_text(encoding="utf-8")
    for module in ("import httpx", "import requests", "import smtplib", "egress"):
        assert module not in source, module
