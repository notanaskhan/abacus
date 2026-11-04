"""N-04-T11 (TASK-3259; DEC-2239): the notice analysis.

Row acceptance: "The Whitley analysis shows 412 to 3,532, two cited 1099-INTs not on the return,
an agreeing bracket check and a decision card reserved to Daniel Reyes with Agree preselected
only when the agent is live." Here: the comparison by code, the fail-closed agent step and the
signer-reserved card; the seeded Whitley figures run in N-04-T15's suite.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from uuid import uuid4

from abacus.modules.notices import analysis

WHITLEY_ITEMS: list[dict[str, Any]] = [  # Any: test doubles and JSON
    {"kind": "line_change", "line_key": "interest", "label": "Taxable interest",
     "amount_shown": Decimal("412.00"), "amount_irs": Decimal("3532.00"),
     "payer_name": None, "info_form": None},
    {"kind": "payer_item", "line_key": "interest", "label": "Front Range Bank",
     "amount_shown": None, "amount_irs": Decimal("1870.00"),
     "payer_name": "Front Range Bank", "info_form": "1099-INT"},
    {"kind": "payer_item", "line_key": "interest", "label": "Lakeview Credit Union",
     "amount_shown": None, "amount_irs": Decimal("1250.00"),
     "payer_name": "Lakeview Credit Union", "info_form": "1099-INT"},
]  # fmt: skip
SNAPSHOT = {"filing_status": "mfj", "lines": [{"key": "interest", "value": "412.00"}]}


def test_whitley_interest_412_to_3532_explained_by_two_1099_ints() -> None:
    out = analysis.compare(SNAPSHOT, WHITLEY_ITEMS, tax_year=2024)
    (row,) = out["rows"]
    assert (row["as_filed"], row["irs"], row["difference"]) == ("412.00", "3532.00", "3120.00")
    assert [i["payer_name"] for i in out["information_returns"]] == [
        "Front Range Bank",
        "Lakeview Credit Union",
    ]
    assert all(not i["on_return"] for i in out["information_returns"])
    assert out["checks"]["difference_explained"] is True
    assert out["analysis_kind"] == "underreporter_comparison"


def test_the_same_inputs_hash_the_same_and_a_change_moves_it() -> None:
    a = analysis.compare(SNAPSHOT, WHITLEY_ITEMS, tax_year=2024)["inputs_hash"]
    b = analysis.compare(SNAPSHOT, WHITLEY_ITEMS[:2], tax_year=2024)["inputs_hash"]
    assert a == analysis.compare(SNAPSHOT, WHITLEY_ITEMS, tax_year=2024)["inputs_hash"]
    assert a != b


def test_no_agent_hook_or_a_refusing_one_gives_no_recommendation() -> None:
    analysis._AGENT_HOOK.clear()  # pyright: ignore[reportPrivateUsage] -- the private helper under test
    off = asyncio.run(analysis._agent_step(object(), uuid4(), {}))  # type: ignore[arg-type] -- boto3 ships no stubs
    assert (off.stage, off.recommended_position) == ("off", None)

    async def failing(*_: object) -> analysis.AgentStep:
        raise RuntimeError("model unavailable")

    async def shadow(*_: object) -> analysis.AgentStep:
        return analysis.AgentStep("shadow", uuid4(), "agree")

    analysis.register_agent_step(failing)
    refused = asyncio.run(analysis._agent_step(object(), uuid4(), {}))  # type: ignore[arg-type] -- boto3 ships no stubs
    assert (refused.stage, refused.recommended_position) == ("refused", None)
    analysis.register_agent_step(shadow)
    quiet = asyncio.run(analysis._agent_step(object(), uuid4(), {}))  # type: ignore[arg-type] -- boto3 ships no stubs
    assert (quiet.stage, quiet.recommended_position) == ("shadow", None)
    analysis._AGENT_HOOK.clear()  # pyright: ignore[reportPrivateUsage] -- the private helper under test


def test_the_position_card_is_reserved_to_the_signer_with_code_options() -> None:
    from abacus.modules.review.slots import decision_kind

    analysis.register_position_kind()
    kind = decision_kind(analysis.POSITION_KIND)
    assert kind.reserved_role == "signer"
    assert list(analysis.POSITIONS) == ["agree", "partially_agree", "disagree"]
