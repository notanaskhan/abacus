"""T-05-T42 (TASK-7703; T-05 F7, F8; TXP-07, TXP-10; DEC-4705, DEC-4706): section sign-offs and
the post-run tie-outs.

Row acceptance: "Run 2 raises the M-2 issue linked to its cells, and Capital Accounts signs off
only with a note while the tie-out is off." Tie-outs are code; "Why this was surfaced" is a fixed
template; a passing tie-out resolves its issue as the system; a cell edit makes the section's
hash move (stale sign-offs).
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from typing import Any

import pytest

from abacus.modules.tax import entity_sections as es
from abacus.modules.tax.entity_sections import (
    SECTIONS,
    TieOutOff,
    section_hash,
    section_tie_outs,
    tie_outs,
)

D = Decimal


def _cells(rows: dict[str, str]) -> dict[str, dict[str, object]]:
    return {k: {"t": "decimal", "v": v} for k, v in rows.items()}


RUN_2 = _cells(
    {
        # 05 Capital: name, beginning, contributions, distributions, income, ending
        "05!A2": "Meera Shah",
        "05!B2": "2000000",
        "05!C2": "0",
        "05!D2": "100000",
        "05!E2": "477356",
        "05!F2": "2377356",
        "05!A3": "Jonah Feld",
        "05!B3": "4000000",
        "05!C3": "0",
        "05!D3": "300000",
        "05!E3": "782644",
        "05!F3": "4482644",
        # 07 M-2 line 9 as drafted (omits the 6,200 of tax-exempt interest)
        "07!B9": "6853800",
        # 06 Schedule K and 09 K-1 shares
        "06!A2": "1",
        "06!C2": "1256200",
        "09!B1": "Meera Shah",
        "09!C1": "Jonah Feld",
        "09!B2": "477356",
        "09!C2": "778844",
        # 01 TB: two accounts and the total row
        "01!A2": "1000",
        "01!F2": "500",
        "01!A3": "2000",
        "01!F3": "-500",
        "01!F4": "0",
    }
)


def _by_key(values: dict[str, dict[str, object]]) -> dict[str, es.TieOut]:
    return {t.key: t for t in tie_outs(values)}


def test_run_2_raises_the_m2_tie_out_off_6200_linked_to_its_cells() -> None:
    found = _by_key(RUN_2)
    m2 = found["item_l_m2"]
    assert (m2.state, m2.difference, m2.section) == ("off", D(6200), "capital-accounts")
    assert m2.links == ({"sheet": "05", "range": "F2:F3"}, {"sheet": "07", "range": "B9"})
    assert m2.why == (
        "M-2 line 9 is 6,853,800; the partners' ending capital on 05 totals 6,860,000; off 6,200."
    )
    assert found["capital_rollforward"].state == "tie"
    assert found["tb_foots"].state == "tie"


def test_k1_sum_k_names_the_line_that_does_not_foot() -> None:
    assert _by_key(RUN_2)["k1_sum_k"].state == "tie"  # 477,356 + 778,844 = 1,256,200
    k = _by_key({**RUN_2, "09!C2": {"t": "decimal", "v": "778843"}})["k1_sum_k"]
    assert (k.state, k.difference) == ("off", D(1))  # one line off
    assert k.why == "1 Schedule K lines do not equal the sum of the partners' K-1 shares."
    assert {"sheet": "06", "range": "C2"} in k.links
    assert {"sheet": "09", "range": "B2:C2"} in k.links


def test_the_section_hash_moves_with_its_cells_only() -> None:
    capital = next(s for s in SECTIONS if s.key == "capital-accounts")
    before = section_hash(capital, RUN_2)
    edited = {**RUN_2, "07!B9": {"t": "decimal", "v": "6860000"}}
    other = {**RUN_2, "06!C2": {"t": "decimal", "v": "1"}}
    assert section_hash(capital, edited) != before  # an earlier sign-off computes stale
    assert section_hash(capital, other) == before
    assert _by_key(edited)["item_l_m2"].state == "tie"
    assert [t.key for t in section_tie_outs(capital, edited)] == [
        "capital_rollforward",
        "item_l_m2",
    ]


class _Signed:
    id = uuid.uuid4()


@pytest.fixture
def stubs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:  # Any: recorded calls
    seen: dict[str, Any] = {"signed": [], "values": RUN_2}  # Any: a test double

    async def ensure(
        ctx: object, return_id: object, engagement_id: object
    ) -> dict[str, Any]:  # Any: a test double
        return {s.key: uuid.uuid4() for s in SECTIONS}

    async def current(
        tenant: object, target: str, target_id: object
    ) -> dict[str, Any]:  # Any: a test double
        return seen["values"]

    async def sign(*args: object) -> _Signed:
        seen["signed"].append(args)
        return _Signed()

    from abacus.modules.review import api as review_api

    monkeypatch.setattr(es, "ensure_sections", ensure)
    monkeypatch.setattr(es, "current_values", current)
    monkeypatch.setattr(review_api, "sign_target", sign)
    return seen


def test_signing_with_the_tie_out_off_and_no_note_is_409(
    stubs: dict[str, Any],  # Any: a test double
) -> None:  # Any: a test double
    ctx: Any = type(  # Any: a test double
        "C", (), {"tenant": object(), "tenant_id": uuid.uuid4(), "user_id": uuid.uuid4()}
    )()
    with pytest.raises(TieOutOff) as caught:
        asyncio.run(
            es.sign_section(
                ctx,
                return_id=uuid.uuid4(),
                engagement_id=uuid.uuid4(),
                key="capital-accounts",
                level=3,
                seen_hash="sha256:" + "a" * 64,
                note="  ",
            )
        )
    assert caught.value.facts == {"count": 1}
    assert stubs["signed"] == []  # P-04 was never asked


def test_a_section_with_every_tie_out_passing_needs_no_note(
    stubs: dict[str, Any],  # Any: a test double
    monkeypatch: pytest.MonkeyPatch,  # Any: a test double
) -> None:
    stubs["values"] = {**RUN_2, "07!B9": {"t": "decimal", "v": "6860000"}}
    ctx: Any = type(  # Any: a test double
        "C", (), {"tenant": object(), "tenant_id": uuid.uuid4(), "user_id": uuid.uuid4()}
    )()

    class _Tx:
        def __init__(self) -> None:
            self.records: list[str] = []
            self.session = self

        async def execute(self, *a: object) -> None:  # no write without an off tie-out
            raise AssertionError("no acknowledgement row")

        def record(self, action: str, **kw: object) -> None:
            self.records.append(action)

    tx = _Tx()

    class _Uow:
        async def __aenter__(self) -> _Tx:
            return tx

        async def __aexit__(self, *a: object) -> None:
            return None

    monkeypatch.setattr(es, "uow", lambda tenant: _Uow())
    done = asyncio.run(
        es.sign_section(
            ctx,
            return_id=uuid.uuid4(),
            engagement_id=uuid.uuid4(),
            key="capital-accounts",
            level=3,
            seen_hash="sha256:" + "a" * 64,
            note=None,
        )
    )
    assert done.acknowledged_off == 0 and tx.records == ["tax_section.signed_off"]


def test_tie_out_check_raises_off_and_resolves_passing(monkeypatch: pytest.MonkeyPatch) -> None:
    raised: list[dict[str, Any]] = []  # Any: a test double
    resolved: list[list[str]] = []
    return_id = uuid.uuid4()

    async def engagement(tenant: object, work_item: object) -> uuid.UUID:
        return uuid.uuid4()

    async def current(
        tenant: object, target: str, target_id: object
    ) -> dict[str, Any]:  # Any: a test double
        return RUN_2

    async def raise_issue(system: object, **kw: object) -> tuple[uuid.UUID, bool]:
        raised.append(kw)
        return uuid.uuid4(), True

    async def resolve(system: object, work_item: object, refs: list[str]) -> list[uuid.UUID]:
        resolved.append(list(refs))
        return []

    from abacus.modules.engagements import api as engagements_api
    from abacus.modules.review import api as review_api

    monkeypatch.setattr(engagements_api, "work_item_engagement", engagement)
    monkeypatch.setattr(es, "current_values", current)
    monkeypatch.setattr(review_api, "record_self_check_issue", raise_issue)
    monkeypatch.setattr(review_api, "system_resolve_self_checks", resolve)
    asyncio.run(es.tie_out_check(uuid.uuid4(), return_id))
    refs = {r["source_ref"] for r in raised}
    assert "tie_out:item_l_m2" in refs
    m2 = next(r for r in raised if r["source_ref"] == "tie_out:item_l_m2")
    assert m2["title"] == "Item L ties M-2: off 6,200" and m2["work_item_id"] == return_id
    assert "tie_out:tb_foots" in resolved[0] and "tie_out:capital_rollforward" in resolved[0]
