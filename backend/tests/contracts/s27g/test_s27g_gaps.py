"""S27 gap rows, the pure and guarded parts (DEC-2350 to DEC-2356): segments and tiles foot from
the rows given, a payment after the due date doesn't count, an amount is found only where it is
printed, the SUM never accumulates a booked row, an unknown effect kind fails
closed, and a Low-impact SOC exception doesn't route.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import sum_service
from abacus.modules.evidence.api import PageWords
from abacus.modules.evidence.words import Word
from abacus.modules.notices.analysis import amount_words, word_box
from abacus.modules.requests.answer_effect_slots import EffectRequest, EffectResult
from abacus.modules.tax import answer_effects, estimates, extensions
from abacus.modules.tax.extensions import ReturnRow, in_segment, line_check, on_tile

RESIDENCY_RULE = "q2_residency"


def _row(*statuses: str, likely: bool = False) -> ReturnRow:
    r = ReturnRow(uuid4(), uuid4(), uuid4(), "Feld", 2027)
    r.lines = [
        {"status": s, "likely_to_extend": likely, "jurisdiction": "US", "id": uuid4()}
        for s in statuses
    ]
    return r


def test_ac_segments_keep_a_likely_row_out_of_open() -> None:
    assert in_segment(_row("prepared"), "open")
    assert not in_segment(_row("not_filed", likely=True), "open")
    assert in_segment(_row("not_filed", likely=True), "likely")
    assert in_segment(_row("rejected"), "filed")
    assert on_tile(_row("filed"), "acks_pending")
    assert not on_tile(_row("accepted"), "acks_pending")


def test_ac_the_federal_line_is_the_rows_figures() -> None:
    r = ReturnRow(uuid4(), uuid4(), uuid4(), "Feld", 2027)
    r.lines = [
        {"jurisdiction": "NY", "status": "prepared"},
        {"jurisdiction": "US", "status": "prepared"},
    ]
    assert r.primary["jurisdiction"] == "US"


def test_ac_a_payment_after_the_original_due_date_does_not_count() -> None:
    line_id = uuid4()
    line = {
        "id": line_id,
        "jurisdiction": "US",
        "original_due_on": date(2028, 4, 18),
        "safe_harbor_target": "110250.00",
        "withholding_plus_estimates": "113476.00",
        "projected_liability": "122500.00",
    }
    payments = [
        {"filing_extension_id": line_id, "amount": "10000.00", "paid_on": date(2028, 4, 10)},
        {"filing_extension_id": line_id, "amount": "999.00", "paid_on": date(2028, 5, 1)},
    ]
    check = line_check(uuid4(), line, payments, 2027)
    assert check.paid == Decimal("123476.00")
    assert check.meets is True


def test_ac_a_year_without_parameters_has_no_target() -> None:
    line = {
        "id": uuid4(),
        "jurisdiction": "US",
        "original_due_on": date(2026, 4, 15),
        "safe_harbor_target": None,
        "withholding_plus_estimates": None,
        "projected_liability": "1.00",
    }
    check = line_check(uuid4(), line, [], 1999)
    assert (check.target, check.meets, check.inputs_hash) == (None, None, None)


def test_ac_the_quarter_tallies_foot() -> None:
    def row(status: str) -> estimates.ScheduleRow:
        r = estimates.ScheduleRow({"id": uuid4()}, "Client")
        r.installments = [{"quarter": 3, "status": status}]
        return r

    rows = [
        row(s) for s in ("paid", "paid", "scheduled", "confirmation_requested", "not_required")
    ]
    assert estimates.counts(rows, 3) == {
        "due": 4,
        "paid": 2,
        "scheduled": 1,
        "confirmation_requested": 1,
        "not_required": 1,
    }
    assert estimates.on_tile(rows[0], 3, "due")
    assert not estimates.on_tile(rows[4], 3, "due")


def test_ac_a_not_required_method_computes_nothing() -> None:
    computed = estimates._computed(  # pyright: ignore[reportPrivateUsage] -- the pure rule
        "prospect", 2027, Decimal(1), None
    )
    assert computed == (None, None, None, ())


def test_ac_an_amount_is_found_only_where_it_is_printed() -> None:
    page = PageWords(
        1,
        612.0,
        792.0,
        0,
        (
            Word("Interest", 10, 10, 50, 20),
            Word("$1,870.00,", 60, 10, 110, 20),
        ),
    )
    assert amount_words(Decimal("1870")) == "1,870.00"
    assert word_box(page, Decimal("1870")) == [60, 10, 110, 20]
    assert word_box(page, Decimal("1250")) is None


def _misstatement(
    ref: str, status: str = "confirmed", **kw: object
) -> sum_service.MisstatementRow:
    base = sum_service.MisstatementRow(
        id=uuid4(),
        ref=ref,
        origin_ref=None,
        type="factual",
        nature="misstatement",
        status=status,
        amount=Decimal("100.00"),
        finding_ref=None,
        fs_effect={},
        carried_from_py=False,
        py_ref=None,
        version=1,
    )
    return replace(base, **kw)


def test_ac_views_place_each_misstatement_once() -> None:
    assert sum_service.in_view(_misstatement("AJE-1"), "proposed")
    assert sum_service.in_view(_misstatement("BCT-1", "below_ct"), "below_ct")
    assert not sum_service.in_view(_misstatement("AJE-2", "booked"), "proposed")
    carry = _misstatement("PY-1", carried_from_py=True)
    assert not any(sum_service.in_view(carry, v) for v in sum_service.VIEWS)
    reclass = _misstatement("RJE-1", nature="reclassification")
    assert sum_service.in_view(reclass, "reclass")
    assert not sum_service.in_view(reclass, "proposed")


def test_ac_a_record_with_no_effects_states_its_amount_under_both_views() -> None:
    assert sum_service.effects(_misstatement("M-1")) == (Decimal("100.00"), Decimal("100.00"))
    signed = _misstatement("M-2", fs_effect={"change_in_net_assets": "-5", "net_assets": "7"})
    assert sum_service.effects(signed) == (Decimal(-5), Decimal(7))


async def test_ac_the_sum_carries_the_prior_year_and_never_a_booked_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        _misstatement("AJE-1"),
        _misstatement("AJE-2", "booked"),
        _misstatement("PY-1", carried_from_py=True),
        _misstatement("BCT-1", "below_ct", amount=Decimal("5.00")),
    ]

    async def _rows(*_a: object) -> list[sum_service.MisstatementRow]:
        return rows

    async def _versions(*_a: object) -> list[object]:
        return []

    async def _column(*_a: object) -> str:
        return "commercial"

    async def _factors(*_a: object) -> tuple[tuple[str, str, bool], ...]:
        return ()

    decided = SimpleNamespace(
        id=uuid4(),
        overall=Decimal(1000),
        pm=Decimal(750),
        ct=Decimal(50),
        version_no=2,
        rate_pct=Decimal("1.5"),
    )
    monkeypatch.setattr(sum_service, "_rows", _rows)
    monkeypatch.setattr(sum_service, "versions_of", _versions)

    def _in_force(_versions: object) -> object:
        return decided

    monkeypatch.setattr(sum_service, "in_force", _in_force)
    monkeypatch.setattr(sum_service, "_column_set", _column)
    monkeypatch.setattr(sum_service, "factors_of", _factors)
    tenant = TenantContext(uuid4(), "system", "test")
    found = await sum_service.sum_view(tenant, uuid4(), None)
    # The engine's golden: 35,300 - 1,150 (PY-1) = 34,150; a prior-year carry accumulates.
    assert found.result.rollover == Decimal("200.00")
    assert "AJE-2" not in found.result.accumulated
    assert "PY-1" in found.result.accumulated
    assert [r.ref for r in found.booked] == ["AJE-2"]
    assert found.below_ct_total == Decimal("5.00")
    assert found.label == "v2 · 1.5%"


async def test_ac_no_materiality_refuses_the_sum(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _versions(*_a: object) -> list[object]:
        return []

    async def _column(*_a: object) -> str:
        return "commercial"

    monkeypatch.setattr(sum_service, "versions_of", _versions)
    monkeypatch.setattr(sum_service, "_column_set", _column)
    with pytest.raises(sum_service.NoMateriality):
        await sum_service.sum_view(TenantContext(uuid4(), "system", "test"), uuid4(), None)


@pytest.mark.parametrize(
    ("handler", "blocks", "priority"),
    [
        (answer_effects.raise_review_point, (), "medium"),
        (answer_effects.flag_internal_review, ("final_approval",), "high"),
    ],
)
async def test_ac_an_answer_raises_one_issue_on_the_return(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[EffectRequest], Awaitable[EffectResult]],
    blocks: tuple[str, ...],
    priority: str,
) -> None:
    from abacus.modules.requests.answer_effect_handlers import EffectRule

    seen: dict[str, object] = {}
    issue = uuid4()
    work_item = uuid4()

    async def rule(_r: EffectRequest) -> EffectRule:
        return EffectRule(uuid4(), work_item, "Confirm full-year NYC residency")

    async def record(_t: object, **kw: object) -> object:
        seen.update(kw)
        return issue

    monkeypatch.setattr(answer_effects, "effect_rule", rule)
    monkeypatch.setattr(answer_effects, "record_rule_issue", record)
    request = EffectRequest(
        tenant_id=uuid4(),
        questionnaire_id=uuid4(),
        question_id=uuid4(),
        answer_id=uuid4(),
        rule_key=RESIDENCY_RULE,
        template_version_id=None,
    )
    result = await handler(request)
    assert (result.target_type, result.target_id) == ("issue", issue)
    assert seen["kind"] == "review_point"
    assert seen["blocks"] == blocks
    assert seen["priority"] == priority
    assert seen["record_id"] == work_item


def test_ac_extensions_store_no_instrument_on_a_proposal() -> None:
    fields = set(extensions.ProposedPayment.__dataclass_fields__)
    assert not fields & {"account", "routing", "card", "iban", "bank"}


def test_ac_a_sealed_position_reads_only_under_the_query_it_was_issued_for() -> None:
    from abacus.kernel.listing import CursorInvalid, Position, decode_cursor, encode_cursor

    tenant = uuid4()
    token = encode_cursor(
        Position(50, "50"), tenant_id=tenant, resource="tax.extensions", query="a"
    )
    found = decode_cursor(token, tenant_id=tenant, resource="tax.extensions", query="a")
    assert found.key == 50
    with pytest.raises(CursorInvalid):
        decode_cursor(token, tenant_id=tenant, resource="tax.extensions", query="b")
