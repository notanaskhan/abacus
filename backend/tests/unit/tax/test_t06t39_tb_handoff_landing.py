"""T-06-T39 (TASK-8830; SPEC-702 F6; TXP-13 d, TXP-02; DEC-5832): the tax-side hand-off landing.

Row acceptance: "Replaying the event creates no second issue, the banner reads 'From FY2026 audit
· Final TB · handed off Nov 9', and nothing is written to the audit engagement."
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from abacus.kernel.uow import OutboxEvent
from abacus.modules.tax import tb_handoff_landing as landing


def test_ac_banner_source_label() -> None:
    assert landing.source_label("audit_release", 2026) == "FY2026 audit"
    assert landing.source_label("close_lock", 2026) == "FY2026 December close"


def test_item_titles_are_code_words() -> None:
    title = landing.item_title("passed_adjustment", {"ref": "AJE-3"}, Decimal("-68400"))
    assert title == "Passed audit adjustment AJE-3 (68,400) handed off: consider it for the M-1"


def test_draft_mapping_from_choices() -> None:
    rows = [
        SimpleNamespace(account_no="1000", tax_line_code="L1", travel="prior_year",
                        suggestion_id=None),
        SimpleNamespace(account_no="2255", tax_line_code=None, travel="blank", suggestion_id=None),
    ]  # fmt: skip
    assert landing.draft_mapping(list[object](rows)) == [
        {
            "account_no": "1000",
            "tax_line_code": "L1",
            "source": "prior_year",
            "suggestion_id": None,
        },
        {"account_no": "2255", "tax_line_code": None, "source": "blank", "suggestion_id": None},
    ]
    assert landing.mapping_source("suggested") == "tb_mapper"


class _Session:
    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, stmt: object, params: object) -> SimpleNamespace:
        assert "tax_handoff_landings" in str(stmt)
        return SimpleNamespace(first=lambda: SimpleNamespace(id=uuid.uuid4()))


def test_ac_replay_creates_no_second_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.ledger.api import tb_handoff

    touched: list[str] = []

    async def handoff_of(*_a: object) -> None:
        touched.append("ledger")

    monkeypatch.setattr(landing, "tenant_session", lambda _t: _Session())  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType] -- a monkeypatched double
    monkeypatch.setattr(tb_handoff, "handoff_of", handoff_of)
    event = OutboxEvent(uuid.uuid4(), uuid.uuid4(), "tb_handoff.created",
                        {"tb_handoff_id": str(uuid.uuid4())})  # fmt: skip
    asyncio.run(landing.on_tb_handoff_created(event))
    assert touched == []  # the landing exists: nothing read, nothing raised, nothing written


def test_ac_nothing_written_to_the_source() -> None:
    import inspect

    source = inspect.getsource(landing)
    for statement in ("INSERT INTO", "UPDATE ", "DELETE "):
        for line in source.splitlines():
            if statement in line:
                assert "tax_handoff_landings" in line  # the only table the landing writes


def test_subscribed() -> None:
    from abacus.modules.tax.api import SUBSCRIPTIONS

    assert SUBSCRIPTIONS["tb_handoff.created"] is landing.on_tb_handoff_created
