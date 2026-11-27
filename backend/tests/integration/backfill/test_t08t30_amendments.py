# ac-test-author: ayushkbhatia
"""T-08-T30 (TASK-9005; SPEC-710 AC6.1 to AC6.4; TAX-16 a, d; DEC-6011) on the migrated Postgres.
Row acceptance: "Okafor's 1040-X foots to (2,708), refund 2,708 and IL (495), the original is never
written, and it reads Superseded only after the amendment's ack."""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.tax import amendments

from .okafor_amendment import AMENDED, Okafor, engine_summary

pytestmark = pytest.mark.asyncio


async def _original_state(w: Okafor) -> tuple[object, ...]:
    rows = await w.seed.rows(
        "SELECT status, row_version, amends_return_id FROM tax_returns WHERE work_item_id = $1",
        w.original,
    )
    summaries = await w.seed.value(
        "SELECT count(*) FROM return_engine_summaries WHERE work_item_id = $1", w.original
    )
    return (rows[0]["status"], rows[0]["row_version"], rows[0]["amends_return_id"], summaries)


async def test_t08t30_acceptance_okafor_amendment(okafor: Okafor) -> None:
    w = okafor
    before = await _original_state(w)
    made = await w.net.call(
        "POST",
        f"/v1/tax-returns/{w.original}/amendments",
        w.yusuf,
        body={"kind": "amended_return", "jurisdictions": ["federal", "il"]},
        headers=w.net.keyed(),
    )
    assert made.status_code == 201, made.text
    body = made.json()
    amendment, new_return = body["amendment_id"], uuid.UUID(body["work_item_id"])
    assert (body["status"], body["total_change"], body["original_superseded"]) == (
        "draft",
        "0.00",
        False,
    )
    form = await w.seed.rows(
        "SELECT form, tax_year, amends_return_id FROM tax_returns WHERE work_item_id = $1",
        new_return,
    )
    assert (form[0]["form"], form[0]["tax_year"], form[0]["amends_return_id"]) == (
        "1040x",
        2025,
        w.original,
    )
    baseline = await w.seed.value(
        "SELECT baseline_checkpoint_id IS NOT NULL FROM amendments WHERE id = $1",
        uuid.UUID(amendment),
    )
    assert baseline is True

    # The engine's amended figures arrive on the new return only.
    await engine_summary(w.seed, w.tenant, new_return, AMENDED)
    federal = (await w.net.call("GET", f"/v1/amendments/{amendment}", w.yusuf)).json()
    assert (federal["total_change"], federal["refund_due"], federal["balance_due"]) == (
        "-2708.00",
        "2708.00",
        None,
    )
    assert {ln["value_source"] for ln in federal["lines"]} == {"engine"}
    il = await w.net.call("GET", f"/v1/amendments/{amendment}?jurisdiction=il", w.yusuf)
    assert il.status_code == 200, il.text
    assert il.json()["total_change"] == "-495.00"

    explained = await w.net.call(
        "PUT",
        f"/v1/amendments/{amendment}/explanation",
        w.yusuf,
        body={"text": "Mortgage interest from a missed Form 1098 and depreciation on the roof."},
        headers={"If-Match": str(federal["row_version"])},
    )
    assert explained.status_code == 200, explained.text
    assert explained.json()["explanation"].startswith("Mortgage interest")
    stale = await w.net.call(
        "PUT",
        f"/v1/amendments/{amendment}/explanation",
        w.yusuf,
        body={"text": "again"},
        headers={"If-Match": str(federal["row_version"])},
    )
    assert stale.status_code == 409, stale.text

    again = await w.net.call(
        "POST",
        f"/v1/tax-returns/{w.original}/amendments",
        w.yusuf,
        body={"kind": "amended_return", "jurisdictions": ["federal"]},
        headers=w.net.keyed(),
    )
    assert again.status_code == 409 and "amendment_exists" in again.text, again.text

    # Superseded only after the amendment's accepted ack, never by the original's own.
    ack = OutboxEvent(
        uuid.uuid4(),
        w.tenant,
        "filing.acknowledged",
        {"return_id": str(new_return), "status": "accepted", "jurisdictions": ["federal"]},
    )
    await amendments.on_filing_acknowledged(ack)  # no ack row yet: nothing happens
    assert (await w.net.call("GET", f"/v1/amendments/{amendment}", w.yusuf)).json()[
        "original_superseded"
    ] is False
    await w.seed.run(
        "INSERT INTO efile_acks (tenant_id, return_id, jurisdiction, status, submission_id_last4, "
        "received_at, source, recorded_by, evidence_version_id) VALUES ($1, $2, 'federal', "
        "'accepted', '2708', abacus_now(), 'manual', $3, $4)",
        w.tenant,
        new_return,
        w.yusuf.user_id,
        w.site.version_id,
    )
    await amendments.on_filing_acknowledged(ack)
    await amendments.on_filing_acknowledged(ack)  # a replay supersedes once
    assert (
        await w.seed.value(
            "SELECT count(*) FROM return_supersessions WHERE original_work_item_id = $1",
            w.original,
        )
        == 1
    )
    done = (await w.net.call("GET", f"/v1/amendments/{amendment}", w.yusuf)).json()
    assert done["original_superseded"] is True
    assert await _original_state(w) == before  # the original is never written


async def test_t08t30_only_an_accepted_return_with_a_baseline_is_amended(okafor: Okafor) -> None:
    w = okafor
    await w.seed.run_untriggered(
        "UPDATE tax_returns SET status = 'filed' WHERE work_item_id = $1", w.original
    )
    early = await w.net.call(
        "POST",
        f"/v1/tax-returns/{w.original}/amendments",
        w.yusuf,
        body={"jurisdictions": ["federal"]},
        headers=w.net.keyed(),
    )
    assert early.status_code == 409 and "return_not_accepted" in early.text, early.text
    stranger = await w.seed.person(await w.seed.firm())
    absent = await w.net.call(
        "POST",
        f"/v1/tax-returns/{w.original}/amendments",
        stranger,
        body={"jurisdictions": ["federal"]},
        headers=w.net.keyed(),
    )
    assert absent.status_code in (403, 404), absent.text
