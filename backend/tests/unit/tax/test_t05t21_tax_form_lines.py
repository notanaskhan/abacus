"""T-05-T21 (TASK-7409; C21 additive; DEC-4408): the `tax_form_lines` reference kind: its payload
model, the operator CLI's diff identity, the typed reader's shape, and the golden fixture that pins
each reviewed draft's hash and the mappable keys (which cover every key the mapper suite uses)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from abacus.modules.platform.reference_sets import KINDS, ReferencePayloadInvalid, validate_payload
from abacus.modules.platform.reference_sets_contract import TaxFormLinesPayload
from abacus_tools.refdata import IDENTITY

ROOT = Path(__file__).resolve().parents[4]
GOLDEN = ROOT / "backend" / "tests" / "golden" / "reference_sets" / "tax_form_lines.json"
SUITE = ROOT / "evals" / "tax_account_mapper" / "suite.yaml"


def _golden() -> dict[str, Any]:  # Any: the golden file is untyped JSON
    return cast(dict[str, Any], json.loads(GOLDEN.read_text(encoding="utf-8")))  # Any: JSON


def _payload(*rows: dict[str, object]) -> dict[str, object]:
    return {"kind": "tax_form_lines", "form": "1065", "tax_year": 2025, "rows": list(rows)}


ROW: dict[str, object] = {
    "key": "L1",
    "schedule": "L",
    "line": "1",
    "label": "Cash",
    "side": "asset",
}


def test_the_kind_is_registered_with_its_identity() -> None:
    assert KINDS["tax_form_lines"] is TaxFormLinesPayload
    assert IDENTITY["tax_form_lines"] == ("key",)


def test_a_line_set_parses_and_a_total_can_be_marked_unmappable() -> None:
    parsed = validate_payload("tax_form_lines", _payload(ROW))
    assert isinstance(parsed, TaxFormLinesPayload)
    assert parsed.rows[0].mappable is True
    total: dict[str, object] = {
        **ROW,
        "key": "L14",
        "line": "14",
        "label": "Total assets",
        "side": "total",
    }
    marked = validate_payload("tax_form_lines", _payload({**total, "mappable": False}))
    assert isinstance(marked, TaxFormLinesPayload) and marked.rows[0].mappable is False


@pytest.mark.parametrize(
    "bad",
    [
        {**ROW, "schedule": "Q"},
        {**ROW, "side": "maybe"},
        {**ROW, "key": ""},
        {**ROW, "extra": 1},
    ],
)
def test_a_bad_row_is_refused(bad: dict[str, object]) -> None:
    with pytest.raises(ReferencePayloadInvalid):
        validate_payload("tax_form_lines", _payload(bad))


def test_only_form_1065_and_its_own_kind() -> None:
    with pytest.raises(ReferencePayloadInvalid):
        validate_payload("tax_form_lines", {**_payload(ROW), "form": "1040"})
    with pytest.raises(ReferencePayloadInvalid):
        validate_payload("tax_form_lines", {**_payload(ROW), "kind": "legal_holidays"})


def test_the_golden_fixture_pins_both_drafts_hashes() -> None:
    sets = _golden()["sets"]
    assert set(sets) == {"tax_form_lines.1065.ty2025", "tax_form_lines.1065.ty2027"}
    for entry in sets.values():
        assert len(entry["payload_sha256"]) == 64 and int(entry["payload_sha256"], 16) >= 0
        assert entry["rows"] == 112 and entry["form"] == "1065"


def test_every_key_the_mapper_suite_uses_is_published_and_mappable() -> None:
    golden = _golden()
    suite = cast(dict[str, Any], yaml.safe_load(SUITE.read_text(encoding="utf-8")))  # Any: YAML
    assert set(suite["published_keys"]) <= set(golden["mappable_keys"])
    assert not set(golden["mappable_keys"]) & set(golden["totals"])
    assert {"L14", "L22", "M-2 5", "M-2 8", "M-2 9", "K 4c", "M-1 9"} <= set(golden["totals"])
