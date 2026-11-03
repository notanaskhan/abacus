"""AUD-16's contract widening (A-06-T22; DEC-2254): the O3 send preview stub on C8 and the SUM
view's statement, evaluation and counts on `SumOut`. Both stay 501 until their service rows."""

from __future__ import annotations

import json
from typing import Any, cast

from abacus.api.export_openapi import document

Json = dict[str, Any]  # Any: the OpenAPI document as JSON

DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, Json], DOC["paths"])
SCHEMAS = cast(
    dict[str, Json],
    DOC["components"]["schemas"],
)
PREVIEW = "/v1/work-items/{work_item_id}/proposed-entries:send-preview"


def test_send_preview_is_a_read_that_answers_501_until_built() -> None:
    op = PATHS[PREVIEW]["get"]
    assert "501" in op["responses"]
    ok = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ok.endswith("/SendPreviewOut")
    params = {p["name"] for p in op["parameters"]}
    assert "entry_ids" in params
    assert set(PATHS[PREVIEW]) == {"get"}


def test_preview_carries_template_wording_and_no_model_text() -> None:
    props = SCHEMAS["SendPreviewOut"]["properties"]
    assert {"recipient_contact_id", "wording_template_version_id", "entries"} <= set(props)
    entry = SCHEMAS["SendPreviewEntryOut"]["properties"]
    assert {"ref", "amount", "client_wording"} <= set(entry)


def test_sum_view_carries_rows_thresholds_factors_and_conclusion() -> None:
    props = SCHEMAS["SumOut"]["properties"]
    for field in (
        "thresholds",
        "rows",
        "totals",
        "footnote",
        "below_ct_count",
        "factors",
        "booked",
        "conclusion",
        "sign_off",
        "counts",
        "aggregate_view",
    ):
        assert field in props, field
    # The older required set is unchanged: the widening adds only defaulted fields.
    assert "rows" not in SCHEMAS["SumOut"].get("required", [])


def test_a_sum_row_has_every_statement_column() -> None:
    row = SCHEMAS["SumRowOut"]["properties"]
    assert {
        "assets",
        "liabilities",
        "net_assets",
        "change_in_net_assets",
        "carried_from_py",
        "group",
        "type",
    } <= set(row)
