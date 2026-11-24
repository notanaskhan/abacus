"""C-02-T35 (TASK-8922; CLS-11 a, a2, c, d, d2; DEC-5924): the console's additive reads.

The posting log carries each batch's total, when it posted and who ran it (CLS-11a: "$31,480.00 ·
Aug 11, 2:41 PM · Raj Malhotra"); the Failures band lists failed attempts newest first with the
resolver's name read now; and "Request reconnect…" previews the Reconnect request email to the
owners it would reach, after the request's own authorisation and before anything is sent (row
acceptance: "Request reconnect shows the POR-20 preview before sending").
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.integrations import ledger_console as lc
from abacus.modules.integrations import reconnect as rc
from abacus.modules.integrations import w1_contract as w1

pytestmark = pytest.mark.asyncio

RAJ = uuid4()
AUG11_1438 = datetime(2026, 8, 11, 19, 38, tzinfo=UTC)
AUG11_1441 = datetime(2026, 8, 11, 19, 41, tzinfo=UTC)


async def _names(ids: object) -> dict[UUID, str]:
    return {RAJ: "Raj Malhotra"} if RAJ in list(ids) else {}  # type: ignore[call-overload]


async def test_ac_the_log_row_carries_amount_posted_time_and_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = lc.LogRow(uuid4(), "2026-07-A", "2026-07", "posted", 6, 6, "47602", "47607", 1, 1,
                    AUG11_1441, RAJ, Decimal("31480.00"))  # fmt: skip
    monkeypatch.setattr(w1, "names_of", _names)
    out = w1._log_row(row, await w1._log_names([row]))  # pyright: ignore[reportPrivateUsage]
    assert (out.amount, out.posted_at, out.posted_by) == (
        Decimal("31480.00"), AUG11_1441, "Raj Malhotra",
    )  # fmt: skip
    proposed = lc.LogRow(uuid4(), "2026-08-A", "2026-08", "proposed", 5, 0, None, None, 0, 0,
                         None, None, Decimal("34920.00"))  # fmt: skip
    assert w1._log_row(proposed, {}).posted_by is None  # pyright: ignore[reportPrivateUsage]


async def test_ac_failures_read_newest_first_with_the_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    older = lc.PostingFailure(datetime(2026, 6, 10, tzinfo=UTC), "2026-05-A", "AJE-01", None,
                              "stale", None, None)  # fmt: skip
    resolved = lc.PostingFailure(AUG11_1438, "2026-07-A", "AJE-03", "Depreciation",
                                 "QuickBooks Online: account 'Accumulated Depreciation' is "
                                 "inactive", AUG11_1441, RAJ)  # fmt: skip
    monkeypatch.setattr(lc, "names_of", _names)
    facts = lc.PostingFacts((), 0, None, (older, resolved))
    band = await lc._failures(facts)  # pyright: ignore[reportPrivateUsage]
    assert [f["entry_ref"] for f in band] == ["AJE-03", "AJE-01"]
    assert (band[0]["resolved_at"], band[0]["resolved_by"]) == (AUG11_1441, "Raj Malhotra")
    assert band[1]["resolved_by"] is None
    out = w1.W1PostingFailureOut.model_validate(band[0])
    assert out.entry_description == "Depreciation"


class _Ref:
    id = uuid4()
    client_id = uuid4()


def _stub(monkeypatch: pytest.MonkeyPatch, *, rendered: object, calls: list[str]) -> None:
    async def entity_of(_ctx: object, _c: object) -> UUID:
        calls.append("entity")
        return uuid4()

    async def authorised(_ctx: object, _e: object, action: str) -> _Ref:
        calls.append(action)
        return _Ref()

    async def flag(*_a: object) -> bool:
        return True

    async def provider(*_a: object) -> str:
        return "quickbooks_online"

    async def owners(*_a: object, **_k: object) -> list[UUID]:
        return [RAJ]

    async def names(_ids: object) -> dict[UUID, str]:
        return {RAJ: "Tess Moreno"}

    async def shared(*_a: object) -> dict[str, str]:
        return {"firm_name": "Brightwater Hale", "connection_name": "QuickBooks Online",
                "portal_link": "https://app.example/portal"}  # fmt: skip

    async def preview(_t: object, key: str, values: dict[str, str], width: int) -> object:
        calls.append(f"render:{key}:{values['client_first_name']}:{width}")
        return rendered

    monkeypatch.setattr(rc, "entity_of_connection", entity_of)
    monkeypatch.setattr(rc, "authorised_engagement", authorised)
    monkeypatch.setattr(rc, "flag_enabled", flag)
    monkeypatch.setattr(rc, "provider_of", provider)
    monkeypatch.setattr(rc, "client_owners", owners)
    monkeypatch.setattr(rc, "names_of", names)
    monkeypatch.setattr(rc, "_shared", shared)
    monkeypatch.setattr(rc, "filled_preview", preview)


async def test_ac_the_reconnect_preview_authorises_then_renders_for_the_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    shown = SimpleNamespace(
        rendered=SimpleNamespace(subject="Please reconnect QuickBooks Online for your monthly "
                                 "close", html="<p>Hi Tess</p>", text="Hi Tess"),
        from_display="Brightwater Hale",
    )  # fmt: skip
    _stub(monkeypatch, rendered=shown, calls=calls)
    out = await rc.reconnect_preview(SimpleNamespace(tenant=None, tenant_id=uuid4()), uuid4())  # type: ignore[arg-type]  # a stand-in
    assert calls == ["entity", "connection.reconnect_request", "render:reconnect_request:Tess:600"]
    assert out.recipients == ["Tess Moreno"] and not out.template_missing
    assert out.subject is not None and out.subject.startswith("Please reconnect")


async def test_ac_no_template_says_so_and_a_refusal_renders_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    _stub(monkeypatch, rendered=None, calls=calls)
    out = await rc.reconnect_preview(SimpleNamespace(tenant=None, tenant_id=uuid4()), uuid4())  # type: ignore[arg-type]  # a stand-in
    assert out.template_missing and out.html is None

    async def walled(*_a: object) -> object:
        raise NotFound("client_entity")

    calls.clear()
    monkeypatch.setattr(rc, "authorised_engagement", walled)
    with pytest.raises(NotFound):
        await rc.reconnect_preview(SimpleNamespace(tenant=None), uuid4())  # type: ignore[arg-type]  # a stand-in
    assert not any(c.startswith("render") for c in calls)


async def test_ac_sync_events_merge_runs_posts_failures_and_the_closing_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import date

    from abacus.modules.connections import api as connections_api
    from abacus.modules.connections.api import FinishedRun

    sep14_0902 = datetime(2026, 9, 14, 14, 2, tzinfo=UTC)
    sep14_0802 = datetime(2026, 9, 14, 13, 2, tzinfo=UTC)
    july = lc.LogRow(uuid4(), "2026-07-A", "2026-07", "posted", 6, 6, "47602", "47607", 1, 1,
                     AUG11_1441, RAJ, Decimal("31480.00"))  # fmt: skip
    august = lc.LogRow(uuid4(), "2026-08-A", "2026-08", "proposed", 5, 0, None, None, 0, 0,
                       None, None, Decimal("34920.00"))  # fmt: skip
    failure = lc.PostingFailure(AUG11_1438, "2026-07-A", "AJE-03", "Depreciation", None,
                                AUG11_1441, RAJ)  # fmt: skip
    closing = lc.ClosingDate(date(2026, 7, 31), RAJ, datetime(2026, 8, 11, 19, 42, tzinfo=UTC))
    facts = lc.PostingFacts((august, july), 1, closing, (failure,))

    async def qbo(*_a: object) -> object:
        return SimpleNamespace(id=uuid4())

    async def posting(*_a: object) -> lc.PostingFacts:
        return facts

    async def runs(*_a: object, **_k: object) -> list[FinishedRun]:
        return [
            FinishedRun(sep14_0902, "succeeded", None),
            FinishedRun(sep14_0802, "failed", "rate_limited"),
        ]

    monkeypatch.setattr(lc, "_qbo", qbo)
    monkeypatch.setattr(lc, "posting_facts", posting)
    monkeypatch.setattr(connections_api, "finished_runs", runs)
    monkeypatch.setattr(lc, "names_of", _names)
    found = await lc.ledger_activity(SimpleNamespace(tenant=None), uuid4(), kind=None)  # type: ignore[arg-type]  # a stand-in
    shown = [(e.kind, e.batch_code, e.entry_ref, e.provider_code, name) for e, name in found]
    assert shown == [
        ("sync", None, None, None, None),
        ("sync_failed", None, None, "rate_limited", None),
        ("closing_date", None, None, None, "Raj Malhotra"),
        ("post", "2026-07-A", None, None, "Raj Malhotra"),
        ("sync_failed", "2026-07-A", "AJE-03", None, None),
    ]
