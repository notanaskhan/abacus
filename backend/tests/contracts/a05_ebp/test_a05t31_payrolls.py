"""EBP-04's payroll timeline read (A-05-T31; DEC-2257): `GET …/ebp/contributions/payrolls` returns
the plan year's payrolls with their deposit lags and a code-computed total, under `ebp.read`."""

from __future__ import annotations

import json
from typing import Any, cast

from abacus.api.export_openapi import document

DOC = cast(dict[str, Any], json.loads(document()))
PATH = "/v1/audits/{work_item_id}/ebp/contributions/payrolls"


def test_payrolls_is_a_read_of_payroll_rows() -> None:
    op = DOC["paths"][PATH]["get"]
    schema = op["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["type"] == "array"
    assert schema["items"]["$ref"].endswith("/PayrollOut")
    assert set(DOC["paths"][PATH]) == {"get"}


def test_a_payroll_carries_its_lags_and_total() -> None:
    props = DOC["components"]["schemas"]["PayrollOut"]["properties"]
    assert {
        "pay_date",
        "deposit_date",
        "deferrals_pretax",
        "deferrals_roth",
        "match",
        "total",
        "business_day_lag",
        "calendar_lag",
        "late",
    } <= set(props)
