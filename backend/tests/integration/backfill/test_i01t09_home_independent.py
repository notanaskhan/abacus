# ac-test-author: ayushkbhatia
"""I-01-T09 (ADR-078): the independent acceptance suite for the amber home work (I-01-T10, T12,
T13), read from I-01 §3 (F3 to F5), §4.3 and `docs/contracts/home-and-gates.md`, not from the
implementation.

- **ADR-024, DEC-20:** a firm admin's Home is metadata only: no work band, admin tiles only, no
  client name anywhere in the answer.
- **DEC-30:** an office narrows, never authorises: a person keeps their own work whatever office it
  files under, and an office filter only takes rows away.
- **INV-3, DEC-43:** a wall takes a client out of the work band and the deadlines, and the answer
  keeps its shape.
- **INV-4, INV-1:** `home.read` answers a client principal 404 and refuses the agent and the
  system.
- **P-01 R4:** the SHL-04 Approvals tab's number is the counts endpoint's, which is the list's.
- **I-01-T12** (client activity rows hold identifiers and codes only) is a strict xfail citing
  TASK-1510 until the projection lands.

ADR-078 note (DEC-650): written in the builder's session after I-01-T10, from the contract; it
must pass with T10 unchanged.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import ActorKind
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.practice.home_contract import home_route

from .support import Json, Net, Person, Site

pytestmark = pytest.mark.asyncio
HOME: Final = "/v1/home"
FLAGS: Final = ("home.dashboard", "review.grammar_api")


async def _firm(net: Net) -> tuple[uuid.UUID, Person, Person, Site, Site]:
    seed = net.seed
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'I-01-T09')",
            tenant,
            flag,
        )
    admin = await seed.person(tenant, "firm_admin")
    kevin = await seed.person(tenant)
    ashford = await seed.site(tenant, admin.user_id, "Ashford")
    bayside = await seed.site(tenant, admin.user_id, "Bayside")
    for site in (ashford, bayside):
        await seed.member(site, kevin, "staff")
    return tenant, admin, kevin, ashford, bayside


async def _assigned(
    net: Net, site: Site, who: Person, by: Person, due: date, office: uuid.UUID | None = None
) -> None:
    item = await net.seed.value(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, due_on, "
        "office_id, created_by) VALUES ($1, $2, $3, 'tax_return', $4, $5, $6, $7) RETURNING id",
        site.tenant_id,
        site.engagement_id,
        site.client_id,
        f"Form 1065 {site.marker}",
        due,
        office,
        by.user_id,
    )
    await net.seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, 'preparer', $5)",
        site.tenant_id,
        item,
        site.engagement_id,
        who.user_id,
        by.user_id,
    )


async def _home(net: Net, who: Person, query: str = "") -> Json:
    response = await net.call("GET", f"{HOME}{query}", who)
    assert response.status_code == 200, response.text
    return cast(Json, response.json())


def _rows(body: Json) -> list[Json]:
    work = cast(Json | None, body["your_work"])
    return [] if work is None else cast(list[Json], work["rows"])


async def test_adr024_a_firm_admins_home_is_metadata_only(net: Net) -> None:
    _tenant, admin, kevin, ashford, _ = await _firm(net)
    await _assigned(net, ashford, kevin, admin, date.today() + timedelta(days=2))
    body = await _home(net, admin)
    assert body["your_work"] is None
    assert cast(Json, body["deadlines"])["rows"] == []
    assert {t["key"] for t in cast(list[Json], body["tiles"])} <= {
        "signatures_out",
        "inbox_waiting",
        "portal_invites_pending",
        "binders",
    }
    assert ashford.marker not in str(body)  # no client or work item name reaches an admin


async def test_dec30_an_office_narrows_and_never_authorises(net: Net) -> None:
    tenant, admin, kevin, ashford, bayside = await _firm(net)
    denver = cast(
        uuid.UUID,
        await net.seed.value(
            "INSERT INTO offices (tenant_id, name) VALUES ($1, 'Denver') RETURNING id", tenant
        ),
    )
    soon = date.today() + timedelta(days=4)
    await _assigned(net, ashford, kevin, admin, soon, denver)
    await _assigned(net, bayside, kevin, admin, soon)
    everything = await _home(net, kevin)
    assert len(_rows(everything)) == 2  # Kevin's own work, whatever office it files under
    narrowed = await _home(net, kevin, f"?office_id={denver}")
    assert [r["client"] for r in _rows(narrowed)] == [
        r["client"] for r in _rows(everything) if ashford.marker in cast(str, r["name"])
    ]
    assert len(_rows(await _home(net, kevin, f"?office_id={uuid.uuid4()}"))) == 0


async def test_inv3_a_wall_takes_the_client_out_and_keeps_the_shape(net: Net) -> None:
    _tenant, admin, kevin, ashford, bayside = await _firm(net)
    soon = date.today() + timedelta(days=3)
    await _assigned(net, ashford, kevin, admin, soon)
    await _assigned(net, bayside, kevin, admin, soon)
    before = await _home(net, kevin)
    await net.wall(admin, kevin, ashford)
    after = await _home(net, kevin)
    assert set(after) == set(before)
    assert set(cast(Json, after["deadlines"])) == set(cast(Json, before["deadlines"]))
    assert ashford.marker not in str(after)
    assert len(_rows(after)) == 1
    assert len(cast(list[Json], cast(Json, after["deadlines"])["rows"])) == 1


async def test_inv4_a_client_principal_is_404(net: Net) -> None:
    _tenant, _admin, _kevin, ashford, _ = await _firm(net)
    client = await net.seed.client_contact(ashford)
    assert (await net.call("GET", HOME, client)).status_code == 404


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_inv1_the_agent_and_the_system_are_refused(net: Net, kind: str) -> None:
    tenant, admin, *_ = await _firm(net)
    ctx = AuthContext(
        TenantContext(tenant, cast(ActorKind, kind), str(admin.user_id)),
        admin.user_id,
        uuid.uuid4(),
        "firm_admin",
        datetime.now(UTC) - timedelta(minutes=1),
    )
    with pytest.raises(Forbidden):
        await home_route(ctx, None)


async def test_p01_r4_the_approvals_number_is_the_counts_endpoints(net: Net) -> None:
    _tenant, _admin, kevin, *_ = await _firm(net)
    counts = await net.call("GET", "/v1/human-gates/counts", kevin)
    listed = await net.call("GET", "/v1/human-gates?assignee=me", kevin)
    assert counts.status_code == listed.status_code == 200
    assert cast(Json, counts.json())["total"] == cast(Json, listed.json())["total"]


@pytest.mark.xfail(strict=True, reason="TASK-1510: client activity lands with I-01-T12")
async def test_i01t12_activity_rows_hold_identifiers_and_codes_only(net: Net) -> None:
    _tenant, admin, kevin, ashford, _ = await _firm(net)
    await _assigned(net, ashford, kevin, admin, date.today())
    rows = cast(list[Json], (await _home(net, kevin))["client_activity"])
    assert rows, "the projection lists the firm's client activity"
    for row in rows:
        for value in cast(Json, row["facts"]).values():
            assert isinstance(value, int | bool) or "_" in str(value) or len(str(value)) <= 64
