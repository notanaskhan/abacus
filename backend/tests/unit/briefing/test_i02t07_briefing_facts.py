"""I-02-T07 (TASK-7716; I-02 §6; DEC-4719): the Today brief's facts collector.

Row acceptance: "Ridgeline at E0 yields its gates with 28,595 and 6,200 as registered facts, an
offshore viewer without consent is refused with consent_7216 before any model call, and the hash
is stable across runs."
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from abacus.modules.agents.blocks import Fact
from abacus.modules.agents.briefing import facts as bf
from abacus.modules.agents.briefing.facts import (
    ConsentRequired,
    Contribution,
    GateFact,
    Subject,
    fact_id,
    hash_of,
)

RULE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


class _Result:
    """A SQL result double: `scalars()` or `first()` as the source reads them."""

    def __init__(self, scalars: list[object] | None = None, first: object = None) -> None:
        self._scalars = scalars or []
        self._first = first

    def scalars(self) -> list[object]:
        return self._scalars

    def first(self) -> object:
        return self._first


def test_fact_ids_follow_the_blocks_rule() -> None:
    gate = uuid.uuid4()
    assert RULE.match(fact_id("gate", gate, "due"))
    assert RULE.match(fact_id("tie_out", "item_l_m2"))
    assert RULE.match(fact_id(2025, "x"))  # a leading digit gets a letter


def test_the_hash_is_stable_and_order_free() -> None:
    g1 = GateFact(
        uuid.uuid4(), "decision", "decision", uuid.uuid4(), None, date(2026, 9, 15), True, None
    )
    g2 = GateFact(uuid.uuid4(), "sign_off", "workpaper", uuid.uuid4(), None, None, False, None)
    f = {"a": Fact(id="a", kind="money", value="6200", basis="x")}
    s = [Subject(uuid.uuid4(), True, 2025)]
    assert hash_of([g1, g2], f, s) == hash_of([g2, g1], f, s)
    assert hash_of([g1], f, s) != hash_of([g1, g2], f, s)


def test_the_tax_source_registers_6200_and_28595(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.tax import briefing_source as source
    from abacus.modules.tax import entity_schedules, entity_tri
    from abacus_tools.synthetic.scenarios.brightwater_hale import entity_slice

    ret = uuid.uuid4()
    values = {a: {"v": v} for a, v in entity_slice.ridgeline_cells()}

    class _Session:
        def __init__(self) -> None:
            self.n = 0

        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def execute(self, statement: object, params: dict[str, Any]) -> Any:  # noqa: ANN401
            sql = str(statement)
            if "FROM tax_returns" in sql:
                return _Result(scalars=[ret])
            row = type("T", (), {"price": Decimal(360000), "display_name": "Pell Street II LLC"})()
            return _Result(first=row)

    async def wb(tenant: object, return_id: object) -> dict[str, Any]:  # Any: a test double
        return values

    async def subjects(tenant: object, return_id: object) -> tuple[Any, ...]:  # Any: a test double
        return ()

    def session_of(tenant: object) -> _Session:
        return _Session()

    monkeypatch.setattr(source, "tenant_session", session_of)
    monkeypatch.setattr(entity_schedules, "workbook_values", wb)
    monkeypatch.setattr(entity_tri, "entity_return_subjects", subjects)
    found = asyncio.run(source.entity_briefing(object(), uuid.uuid4()))  # type: ignore[arg-type] -- a test double stands in for the typed object
    by_id = {f.id: f.value for f in found.facts}
    assert by_id["tie_out_item_l_m2"] == "6200"
    assert by_id["section_754_placeholder"] == "28595"  # 360,000 - 331,405


def test_a_tri_subject_without_consent_is_refused_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.engagements import api as engagements_api
    from abacus.modules.requests import api as requests_api
    from abacus.modules.review import api as review_api

    async def gates(ctx: object, **kw: object) -> Any:  # noqa: ANN401
        return type("P", (), {"items": []})()

    async def none(*a: object) -> Any:  # noqa: ANN401
        return {} if len(a) == 2 and isinstance(a[1], list) else []

    async def source(tenant: object, engagement: object) -> Contribution:
        return Contribution(subjects=[Subject(uuid.uuid4(), True, 2025)])

    async def refused(tenant: object, subjects: object, at: object) -> bool:
        return False

    monkeypatch.setattr(review_api, "gates_waiting_on", gates)
    monkeypatch.setattr(engagements_api, "work_item_ids_of", none)
    monkeypatch.setattr(requests_api, "pbc_counts", none)
    monkeypatch.setattr(bf, "_SOURCES", {"t": source})
    monkeypatch.setattr(bf, "_consented", refused)
    viewer: Any = type(  # Any: a test double
        "V", (), {"tenant": object(), "user_id": uuid.uuid4()}
    )()  # Any: a test double
    from abacus.kernel import clock

    async def now(tenant: object) -> Any:  # noqa: ANN401
        return None

    monkeypatch.setattr(clock, "now", now)
    with pytest.raises(ConsentRequired):
        asyncio.run(bf.collect(viewer, uuid.uuid4()))
