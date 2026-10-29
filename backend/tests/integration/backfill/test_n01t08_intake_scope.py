# ac-test-author: ayushkbhatia
"""N-01-T08 (TASK-1729; N-01 §4.4; DEC-20, DEC-75; DEC-819): the intake scope.

Acceptance (the task row): "Grace Holloway in the Intake team reads unmatched threads and a
walled or non-intake user gets 404 on them."

Also: a matched thread is read as its client is (the wall answers 404), and joining or leaving an
intake team emits `access.changed` for the person.

Boundary: the communications service with each person's own context; rows seeded through SQL.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final, cast

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.communications.intake_scope import readable_thread, unmatched_threads
from abacus.modules.identity.api import AuthContext, member_context

from .support import Net, Person, Site

pytestmark = pytest.mark.asyncio
SUBJECT: Final = "Scanned 1099s"


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    grace: Person  # on the Intake team
    henry: Person  # not
    site: Site
    team_id: uuid.UUID
    unmatched: uuid.UUID
    matched: uuid.UUID


async def _context(firm: Firm, who: Person) -> AuthContext:
    ctx = await member_context(firm.tenant_id, who.user_id)
    assert ctx is not None
    return ctx


async def _thread(net: Net, tenant: uuid.UUID, client_id: uuid.UUID | None) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await net.seed.value(
            "INSERT INTO inbox_threads (tenant_id, source_kind, client_id, subject_display, "
            "sender_display, match_method, first_received_at, last_received_at) "
            "VALUES ($1, 'mailbox', $2, $3, 'feliks@example.test', $4, now(), now()) "
            "RETURNING id",
            tenant,
            client_id,
            SUBJECT,
            "none" if client_id is None else "contact_email",
        ),
    )


@pytest.fixture
async def firm(net: Net) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant, "firm_admin")  # INB-01: Grace Holloway, Firm Admin
    henry = await seed.person(tenant)
    site = await seed.site(tenant, admin.user_id, "Intake")
    team = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO teams (tenant_id, name, kind) VALUES ($1, 'Intake', 'intake') "
            "RETURNING id",
            tenant,
        ),
    )
    await seed.run(
        "INSERT INTO team_rosters (tenant_id, team_id, user_id) VALUES ($1, $2, $3)",
        tenant,
        team,
        grace.user_id,
    )
    unmatched = await _thread(net, tenant, None)
    matched = await _thread(net, tenant, site.client_id)
    return Firm(net, tenant, admin, grace, henry, site, team, unmatched, matched)


# --- The acceptance ------------------------------------------------------------------------------


async def test_ac_grace_in_the_intake_team_reads_unmatched_threads(firm: Firm) -> None:
    grace = await _context(firm, firm.grace)
    listed = await unmatched_threads(grace)
    assert [t.id for t in listed] == [firm.unmatched]
    assert (listed[0].sender_display, listed[0].subject_display) == (
        "feliks@example.test",
        SUBJECT,
    )
    assert (await readable_thread(grace, firm.unmatched)).client_id is None


async def test_ac_a_non_intake_user_gets_404_on_unmatched_threads(firm: Firm) -> None:
    henry = await _context(firm, firm.henry)
    with pytest.raises(NotFound):
        await unmatched_threads(henry)
    with pytest.raises(NotFound):
        await readable_thread(henry, firm.unmatched)


async def test_ac_a_walled_user_gets_404_on_the_clients_thread(firm: Firm) -> None:
    await firm.net.wall(firm.admin, firm.grace, firm.site)
    grace = await _context(firm, firm.grace)
    with pytest.raises(NotFound):
        await readable_thread(grace, firm.matched)


# --- The rest of the row ------------------------------------------------------------------------


async def test_the_intake_scope_reads_a_matched_thread_of_a_client_it_may_read(
    firm: Firm,
) -> None:
    grace = await _context(firm, firm.grace)
    assert (await readable_thread(grace, firm.matched)).client_id == firm.site.client_id


async def test_leaving_the_intake_team_ends_the_scope_and_says_so(firm: Firm) -> None:
    response = await firm.net.call(
        "PUT",
        f"/v1/firm/teams/{firm.team_id}/members",
        firm.admin,
        body={"member_ids": [str(firm.henry.user_id)]},
    )
    assert response.status_code == 200, response.text
    with pytest.raises(NotFound):
        await unmatched_threads(await _context(firm, firm.grace))
    assert [t.id for t in await unmatched_threads(await _context(firm, firm.henry))] == [
        firm.unmatched
    ]
    changed = await firm.net.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'access.changed'",
        firm.tenant_id,
    )
    people = {str(row["payload"]) for row in changed}
    assert any(str(firm.grace.user_id) in p for p in people)
    assert any(str(firm.henry.user_id) in p for p in people)
