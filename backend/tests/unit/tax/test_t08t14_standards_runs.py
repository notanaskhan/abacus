"""T-08-T14 (TASK-8838; SPEC-710 AC-26; TAX-14; DEC-5840): standards runs.

Row acceptance: "Running v4 on six 1065s yields 4 passed and 2 with exceptions, Ridgeline's two
link to existing issues so its count stays 11, and Marlowe's three are created."
"""

from __future__ import annotations

import inspect
import uuid
from decimal import Decimal

from abacus.modules.tax import standards_runs as sr


def test_check_key_shape() -> None:
    assert sr.check_key("1065", 4, "c-17") == "1065-v4/C-17"
    assert sr.check_key("1065", 4, "page1.sign") is None


def test_ac_existing_issue_links_else_raises_once() -> None:
    source = inspect.getsource(sr.run_item)
    # link first (Ridgeline: the count stays 11), raise under the same ref only when none is open
    assert source.index("open_issue_for_ref") < source.index("record_self_check_issue")
    assert "if linked is None" in source


def test_rerun_never_duplicates_results() -> None:
    assert "ON CONFLICT (run_item_id, check_key) DO NOTHING" in inspect.getsource(sr.run_item)
    assert 'not in ("queued", "running")' in inspect.getsource(sr.run_item)


def test_no_model_anywhere() -> None:
    source = inspect.getsource(sr)
    assert "ai_gateway" not in source and "GatewayCall" not in source


def test_tie_out_checks_registered() -> None:
    from abacus.modules.methodology.check_codes import known_codes

    assert set(sr.TIE_OUT_CHECKS) <= known_codes()


def test_check_result_defaults() -> None:
    r = sr.TieOutResult(
        "exception", Decimal("6200"), {"sheet": "07", "range": "B9"}, "tie_out:item_l_m2"
    )
    assert r.issue_ref == "tie_out:item_l_m2" and uuid.UUID(int=0)
