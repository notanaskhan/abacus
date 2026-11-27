# ac-test-author: ayushkbhatia
"""T-08-T30 (TASK-9005; SPEC-710 AC6.1 to AC6.4; TAX-16 a, d; DEC-6011) on the migrated Postgres.
Row acceptance: "Okafor's 1040-X foots to (2,708), refund 2,708 and IL (495), the original is never
written, and it reads Superseded only after the amendment's ack."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import cast

import pytest

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.tax import amendments

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio

FILED = {
    "1040.11": "212400",
    "1040.12": "29200",
    "1040.15": "183200",
    "1040.16": "37400",
    "1040.24": "40386",
    "1040.33": "41000",
    "1040.34": "614",
    "il1040.agi": "212400",
    "il1040.tax": "10514",
}
AMENDED = {
    **FILED,
    "1040.12": "38660",
    "1040.15": "173740",
    "1040.16": "35206",
    "1040.24": "37678",
    "1040.34": "3322",
    "il1040.agi": "202400",
    "il1040.tax": "10019",
}


def _lines(values: dict[str, str]) -> str:
    return json.dumps([{"line_key": k, "amount": v} for k, v in values.items()])


@dataclass
class Okafor:
    net: Net
    tenant: uuid.UUID
    yusuf: Person
    site: Site
    original: uuid.UUID

    @property
    def seed(self) -> Seeder:
        return self.net.seed


async def _summary(
    seed: Seeder, tenant: uuid.UUID, item: uuid.UUID, values: dict[str, str]
) -> None:
    await seed.run(
        "INSERT INTO return_engine_summaries (tenant_id, work_item_id, engine_version, kind, "
        "lines, approved_at) VALUES ($1, $2, 'CCH Axcess 2025', 'final', $3::jsonb, now())",
        tenant,
        item,
        _lines(values),
    )


@pytest.fixture
async def okafor(net: Net, seed: Seeder) -> Okafor:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.amendments', 'true', 'test-seed', 'T-08-T30')",
        tenant,
    )
    yusuf = await seed.person(tenant)
    site = await seed.site(tenant, yusuf.user_id, "Okafor")
    await seed.member(site, yusuf, "senior")
    original = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', '2025 Form 1040', $5) "
            "RETURNING id",
            tenant,
            site.engagement_id,
            site.client_id,
            site.entity_id,
            yusuf.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, '1040', 2025)",
        tenant,
        original,
        site.engagement_id,
        site.entity_id,
    )
    await seed.run_untriggered(
        "UPDATE tax_returns SET status = 'accepted' WHERE work_item_id = $1", original
    )
    await seed.run_untriggered(  # an engine import's approved checkpoint, as T-01 records one
        "INSERT INTO checkpoints (id, tenant_id, engagement_id, target_type, target_id, seq, "
        "author_kind, author_ref, cause, status, content_hash) VALUES ($1, $2, $3, 'tax_return', "
        "$4, 1, 'import', 'Imported from CCH Axcess 2025:OkaforD:V1', 'engine_import', "
        "'approved', $5)",
        uuid.uuid4(),
        tenant,
        site.engagement_id,
        original,
        hashlib.sha256(b"okafor-2025").hexdigest(),
    )
    await _summary(seed, tenant, original, FILED)
    return Okafor(net, tenant, yusuf, site, original)


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
    await _summary(w.seed, w.tenant, new_return, AMENDED)
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
