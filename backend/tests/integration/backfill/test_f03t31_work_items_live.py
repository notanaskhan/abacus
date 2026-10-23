# ac-test-author: ayushkbhatia
"""F-03-T31 (TASK-389), C1 live: `GET /v1/work-items` and `EngagementOut.allowed_actions`.

Q-03-T011 catch-up lane (ADR-078). F-03-T34's suite (`test_f03_independent_acceptance.py`) covers
the list envelope itself (fields, counts ignoring the status filter, cursors, page sizes, walls);
no plan row owes T31's own promises, so this file writes them from the row's acceptance ("lists
Brightwater Hale work items of all five kinds with per-status counts"), C1 v1
(`docs/contracts/work-items.md` §2, §3, §7), the permission matrix (`work_item.read_metadata`:
firm roles and the engagement team; no client role) and F-03 Stories 6.1 and 6.2.

HTTP through `create_app()` against the migrated Postgres. Work items are made through the public
`engagements.api.create_work_item`, as their owners do; nothing reads a module's internals.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import cast

import httpx
import pytest

# Each registers its work-item kind, as the app does at start-up.
import abacus.modules.closes.api  # pyright: ignore[reportUnusedImport] -- registers the kind
import abacus.modules.notices.api  # pyright: ignore[reportUnusedImport] -- registers the kind
import abacus.modules.tax.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the kind
from abacus.kernel.db import TenantContext
from abacus.modules.engagements.api import create_work_item
from abacus.modules.identity.api import AuthContext, Forbidden

from .support import Net, Person, Role, Seeder, Site

Json = dict[str, object]
ROW_FIELDS = {
    "id",
    "engagement_id",
    "kind",
    "name",
    "status",
    "period_start",
    "period_end",
    "due_on",
}
FIVE_KINDS = {"assurance", "tax_return", "close", "notice", "advisory_project"}


def _ctx(who: Person) -> AuthContext:
    return AuthContext(
        TenantContext(who.tenant_id, "human", str(who.user_id)),
        who.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC) - timedelta(minutes=1),
    )


async def _all_kinds(seed: Seeder, partner: Person, site: Site) -> None:
    """The engagement's assurance item comes from the database; add the other four kinds, then
    archive the notice."""
    ctx = _ctx(partner)
    await create_work_item(
        ctx,
        site.engagement_id,
        "tax_return",
        name="1040 2025",
        client_entity_id=site.entity_id,
        details={"form": "1040", "tax_year": 2025},
    )
    await create_work_item(
        ctx, site.engagement_id, "close", name="Jan close", details={"period": "2026-01"}
    )
    await create_work_item(
        ctx,
        site.engagement_id,
        "notice",
        name="CP2000",
        details={"notice_code": "CP2000", "received_on": date(2026, 9, 1)},
    )
    await create_work_item(
        ctx, site.engagement_id, "advisory_project", name="Review", details={"name": "Review"}
    )
    await seed.run(
        "UPDATE work_items SET status = 'archived' WHERE engagement_id = $1 AND kind = 'notice'",
        site.engagement_id,
    )


async def _list(net: Net, who: Person, **params: str) -> httpx.Response:
    return await net.http.get("/v1/work-items", params=params, headers=net.headers(who))


async def _page(net: Net, who: Person, **params: str) -> Json:
    response = await _list(net, who, **params)
    assert response.status_code == 200, response.text
    return cast(Json, response.json())


def _items(page: Json) -> list[Json]:
    return cast(list[Json], page["items"])


async def _firm(seed: Seeder) -> tuple[uuid.UUID, Person, Site, Site]:
    """A firm with a partner on two engagements, A (all five kinds) and B (its assurance item)."""
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    a = await seed.site(tenant, partner.user_id, "A")
    b = await seed.site(tenant, partner.user_id, "B")
    for site in (a, b):
        await seed.member(site, partner, "engagement_partner")
    await _all_kinds(seed, partner, a)
    return tenant, partner, a, b


# --- AC: all five kinds, with per-status counts --------------------------------------------------


async def test_ac1_an_engagement_lists_work_items_of_all_five_kinds_with_per_status_counts(
    seed: Seeder, net: Net
) -> None:
    _, partner, a, _ = await _firm(seed)
    page = await _page(net, partner, engagement_id=str(a.engagement_id))
    items = _items(page)
    assert {i["kind"] for i in items} == FIVE_KINDS
    assert page["total"] == 5
    assert page["counts"] == {"active": 4, "archived": 1}
    assert all(set(i) == ROW_FIELDS for i in items)  # C1 §3 WorkItemRowOut, nothing more
    assert {i["engagement_id"] for i in items} == {str(a.engagement_id)}
    archived = [i["kind"] for i in items if i["status"] == "archived"]
    assert archived == ["notice"]


async def test_ac1_without_a_filter_the_list_spans_the_callers_engagements(
    seed: Seeder, net: Net
) -> None:
    _, partner, a, b = await _firm(seed)
    page = await _page(net, partner)
    assert {i["engagement_id"] for i in _items(page)} == {
        str(a.engagement_id),
        str(b.engagement_id),
    }
    assert page["total"] == 6
    assert page["counts"] == {"active": 5, "archived": 1}


async def test_ac1_the_engagement_filter_keeps_other_engagements_out_of_items_and_counts(
    seed: Seeder, net: Net
) -> None:
    _, partner, _, b = await _firm(seed)
    page = await _page(net, partner, engagement_id=str(b.engagement_id))
    assert [i["kind"] for i in _items(page)] == ["assurance"]
    assert page["total"] == 1
    assert page["counts"] == {"active": 1}


async def test_ac1_the_kind_filter_applies_to_items_total_and_counts(
    seed: Seeder, net: Net
) -> None:
    _, partner, _, _ = await _firm(seed)
    page = await _page(net, partner, kind="assurance")
    assert {i["kind"] for i in _items(page)} == {"assurance"}
    assert page["total"] == 2  # one per engagement
    assert page["counts"] == {"active": 2}
    notices = await _page(net, partner, kind="notice")
    assert notices["total"] == 1 and notices["counts"] == {"archived": 1}


# --- Who reads which work items (matrix `work_item.read_metadata`; Story 6.1) --------------------


async def test_ac2_a_staff_member_reads_only_the_work_items_of_their_engagements(
    seed: Seeder, net: Net
) -> None:
    tenant, _, a, b = await _firm(seed)
    senior = await seed.person(tenant)
    await seed.member(b, senior, "senior")
    page = await _page(net, senior)
    assert {i["engagement_id"] for i in _items(page)} == {str(b.engagement_id)}
    assert page["total"] == 1 and page["counts"] == {"active": 1}
    other = await _page(net, senior, engagement_id=str(a.engagement_id))
    assert _items(other) == [] and other["total"] == 0 and other["counts"] == {}


async def test_ac2_a_firm_administrator_off_the_team_reads_every_engagements_work_items(
    seed: Seeder, net: Net
) -> None:
    tenant, _, a, b = await _firm(seed)
    admin = await seed.person(tenant, "firm_admin")
    page = await _page(net, admin)
    assert {i["engagement_id"] for i in _items(page)} == {
        str(a.engagement_id),
        str(b.engagement_id),
    }
    assert page["total"] == 6


def _reads_nothing(response: httpx.Response) -> bool:
    """C1 §2 lists who may read; it doesn't say whether anyone else is refused or shown an empty
    list. Either way, not one row and not one count."""
    if response.status_code == 403:
        return True
    body = cast(Json, response.json())
    return response.status_code == 200 and body["items"] == [] and body["total"] == 0


async def test_ac2_a_member_with_no_firm_role_and_no_team_reads_no_work_item(
    seed: Seeder, net: Net
) -> None:
    tenant, _, a, _ = await _firm(seed)
    nobody = await seed.person(tenant)
    assert _reads_nothing(await _list(net, nobody))
    assert _reads_nothing(await _list(net, nobody, engagement_id=str(a.engagement_id)))


async def test_ac2_a_client_user_reads_no_work_item_even_on_their_own_engagement(
    seed: Seeder, net: Net
) -> None:
    _, _, a, _ = await _firm(seed)
    client = await seed.client_contact(a)
    assert _reads_nothing(await _list(net, client))
    assert _reads_nothing(await _list(net, client, engagement_id=str(a.engagement_id)))


async def test_ac2_another_firms_work_items_never_appear(seed: Seeder, net: Net) -> None:
    _, partner, _, _ = await _firm(seed)
    _, stranger, theirs, _ = await _firm(seed)
    mine = await _page(net, partner)
    assert str(theirs.engagement_id) not in {i["engagement_id"] for i in _items(mine)}
    probe = await _page(net, partner, engagement_id=str(theirs.engagement_id))
    assert _items(probe) == [] and probe["total"] == 0
    assert (await _page(net, stranger))["total"] == 6  # their own, untouched


# --- EngagementOut.allowed_actions (Story 6.2; C1 §3) --------------------------------------------


async def _offered(net: Net, who: Person, site: Site) -> set[str]:
    response = await net.call("GET", f"/v1/engagements/{site.engagement_id}", who)
    assert response.status_code == 200, response.text
    return set(cast(list[str], response.json()["allowed_actions"]))


async def test_ac3_allowed_actions_follow_the_callers_engagement_role(
    seed: Seeder, net: Net
) -> None:
    tenant, partner, a, _ = await _firm(seed)
    senior, staff = await seed.person(tenant), await seed.person(tenant)
    await seed.member(a, senior, "senior")
    await seed.member(a, staff, "staff")
    by_partner = await _offered(net, partner, a)
    # matrix: work_item.create is the engagement partner's and manager's, never a senior's or
    # staff's; "the actions the caller may offer" are offers, so a read is not among them
    assert "work_item.create" in by_partner
    for who in (senior, staff):
        offered = await _offered(net, who, a)
        assert "work_item.create" not in offered
        assert offered < by_partner  # a narrower role never offers what the partner can't


@pytest.mark.parametrize("role", ["senior", "staff"])
async def test_ac3_an_action_left_out_of_allowed_actions_is_refused_when_tried(
    seed: Seeder, net: Net, role: Role
) -> None:
    tenant, _, a, _ = await _firm(seed)
    who = await seed.person(tenant)
    await seed.member(a, who, role)
    assert "work_item.create" not in await _offered(net, who, a)
    with pytest.raises(Forbidden):
        await create_work_item(
            _ctx(who), a.engagement_id, "advisory_project", name="X", details={"name": "X"}
        )


async def test_ac3_reading_the_projection_and_the_list_writes_no_audit_event(
    seed: Seeder, net: Net
) -> None:
    """C1 §7: reads write none; allowed_actions is computed without recording a check."""
    tenant, partner, a, _ = await _firm(seed)
    before = await seed.actions(tenant)
    await _offered(net, partner, a)
    await _page(net, partner)
    assert await seed.actions(tenant) == before
