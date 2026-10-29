"""P-07-T15 code gap (TASK-1010; OQ-9, DEC-224; migration 0182): "Not required this year".

With the firm setting `allow_letter_exceptions` on, the engagement partner records G3 as not
required with a reason: G3 is met, an Accepted engagement moves to Contracted and one
`letter.recorded` event is written. A manager (who may record a signed letter) is refused 409
`letter_exceptions_off`, as is anyone while the setting is off; a missing reason is 422
`letter_exception_reason_required` (a blank one is refused by the request's own validation).
Nothing is written for a refusal.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import cast

import httpx
import pytest

from .support import Net, Person, Seeder

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
FLAG = "engagements.v2"
SETTING = "allow_letter_exceptions"
REASON = "Covered by the master services agreement"


@dataclass(frozen=True)
class Firm:
    seed: Seeder
    net: Net
    tenant: uuid.UUID
    admin: Person

    async def call(
        self, method: str, path: str, who: Person, body: Json | None = None
    ) -> httpx.Response:
        return await self.net.http.request(method, path, json=body, headers=self.net.headers(who))

    async def setting(self, on: bool) -> None:
        await self.seed.run(
            "INSERT INTO firm_setting_values (tenant_id, key, value, set_by) "
            "VALUES ($1, $2, $3, $4) ON CONFLICT (tenant_id, key) DO UPDATE SET value = $3",
            self.tenant,
            SETTING,
            on,
            self.admin.user_id,
        )

    async def person(self, level: str) -> Person:
        who = await self.seed.person(self.tenant, None)
        await self.seed.run(
            "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
            self.tenant,
            who.user_id,
            level,
        )
        return who

    async def member(self, engagement: uuid.UUID, who: Person, role: str) -> None:
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant,
            engagement,
            who.user_id,
            role,
        )
        await self.seed.run(
            "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
            "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
            "clock_timestamp()) ON CONFLICT DO NOTHING",
            self.tenant,
            engagement,
            who.user_id,
        )

    async def accepted(self) -> uuid.UUID:
        """An Accepted engagement with its G1 decision ten days ago and no letter."""
        client = await self.seed.value(
            "INSERT INTO clients (tenant_id, name, kind) VALUES ($1, $2, 'business') RETURNING id",
            self.tenant,
            f"Bluestem {uuid.uuid4().hex[:6]}",
        )
        entity = await self.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, "
            "'Bluestem entity') RETURNING id",
            self.tenant,
            client,
        )
        engagement = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, type, "
                "fiscal_period_start, fiscal_period_end, status, created_by) VALUES ($1, $2, $3, "
                "$4, 'fs_audit', $5, $6, 'accepted', $7) RETURNING id",
                self.tenant,
                client,
                entity,
                f"FY2025 FS Audit {uuid.uuid4().hex[:6]}",
                date(2025, 1, 1),
                date(2025, 12, 31),
                self.admin.user_id,
            ),
        )
        decided = datetime.now(UTC).replace(microsecond=0) - timedelta(days=10)
        await self.seed.open_engagement(self.tenant, engagement, decided_at=decided)
        return engagement


async def _firm(net: Net) -> Firm:
    tenant = await net.seed.firm()
    admin = await net.seed.person(tenant, "firm_admin")
    await net.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'P-07-T15')",
        tenant,
        FLAG,
    )
    return Firm(net.seed, net, tenant, admin)


def _exception(reason: str | None = REASON) -> Json:
    return {"mode": "not_required_this_year", "not_required_reason": reason}


async def _letters(firm: Firm, engagement: uuid.UUID) -> int:
    return int(
        cast(
            int,
            await firm.seed.value(
                "SELECT count(*) FROM engagement_letters WHERE tenant_id = $1 "
                "AND engagement_id = $2",
                firm.tenant,
                engagement,
            ),
        )
    )


async def test_the_partner_records_not_required_with_the_setting_on(net: Net) -> None:
    firm = await _firm(net)
    await firm.setting(True)
    engagement = await firm.accepted()
    partner = await firm.person("partner")
    await firm.member(engagement, partner, "engagement_partner")
    response = await firm.call(
        "PUT", f"/v1/engagements/{engagement}/letter/record", partner, _exception()
    )
    assert response.status_code == 200, response.text
    out = cast(Json, response.json())
    assert out["mode"] == "not_required_this_year"  # `status` has only signed and not_signed
    assert out["engagement_status"] == "contracted"
    record = cast(
        Json,
        (await firm.call("GET", f"/v1/engagements/{engagement}/record", partner)).json(),
    )
    gates = {str(g["gate"]): g for g in cast(list[Json], record["gates"])}
    assert gates["G3"]["met"] is True
    assert (await firm.seed.actions(firm.tenant)).count("letter.recorded") == 1


async def test_a_manager_or_the_setting_off_is_refused_and_writes_nothing(net: Net) -> None:
    firm = await _firm(net)
    engagement = await firm.accepted()
    partner = await firm.person("partner")
    manager = await firm.person("manager")
    await firm.member(engagement, partner, "engagement_partner")
    await firm.member(engagement, manager, "manager")
    path = f"/v1/engagements/{engagement}/letter/record"
    off = await firm.call("PUT", path, partner, _exception())
    assert (off.status_code, off.json()["detail"]) == (409, "letter_exceptions_off")
    await firm.setting(True)
    by_manager = await firm.call("PUT", path, manager, _exception())
    assert (by_manager.status_code, by_manager.json()["detail"]) == (
        409,
        "letter_exceptions_off",
    )
    no_reason = await firm.call("PUT", path, partner, _exception(None))
    assert (no_reason.status_code, no_reason.json()["detail"]) == (
        422,
        "letter_exception_reason_required",
    )
    assert await _letters(firm, engagement) == 0
