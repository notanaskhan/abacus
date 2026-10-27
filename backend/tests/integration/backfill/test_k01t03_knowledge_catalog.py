"""K-01-T03 (TASK-1426; K-01 §3.1; KNW-01): the knowledge catalog's read model, over HTTP.

Acceptance (K-01.tasks.csv): `GET /v1/knowledge/items` returns the live methodology cards with
facet counts, an unregistered category returns no count, and a walled engagement is never counted
or listed. Also: the Draft counting rule (a draft under a published card is a review-queue row,
not a Draft card; AC1.4), drafts hidden from readers who neither manage nor approve (AC1.6, at
the API), lexical search with match ranges in the title (AC1.7), the change log naming the person
(AC1.5), and the flag and client gates (AC1.10).
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from typing import cast

import pytest
from openpyxl import Workbook

from .support import Json, Net, Person, Site

pytestmark = pytest.mark.asyncio

ITEMS = "/v1/knowledge/items"


def _workbook(*descriptions: str) -> bytes:
    book = Workbook()
    areas = book.active
    assert areas is not None
    areas.title = "Areas"
    areas.append(["code", "name"])
    areas.append(["MAT", "Materiality and scoping"])
    requests = book.create_sheet("Requests")
    requests.append(["area_code", "description", "tier"])
    for description in descriptions:
        requests.append(["MAT", description, "D"])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


async def _import(net: Net, who: Person, name: str, *descriptions: str) -> uuid.UUID:
    response = await net.http.post(
        f"/v1/methodology/templates/{name}/versions?engagement_type=ebp_audit",
        content=_workbook(*descriptions),
        headers={**net.headers(who), "Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(cast(str, response.json()["version_id"]))


@dataclass(frozen=True)
class Library:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    margaret: Person  # quality partner: manages and approves
    daniel: Person  # engagement partner on both clients
    lena: Person  # staff on both clients, walled from Ashford in the wall test
    ashford: Site
    bayside: Site
    v2: uuid.UUID  # BH Audit Methodology v2, published, pinned by both engagements
    v1: uuid.UUID  # v1, superseded
    pbc: uuid.UUID  # a PBC template (no family)

    async def get(self, who: Person, path: str) -> Json:
        response = await self.net.call("GET", path, who)
        assert response.status_code == 200, response.text
        return cast(Json, response.json())


async def _flag(net: Net, tenant: uuid.UUID, flag: str) -> None:
    await net.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'K-01-T03') "
        "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = 'true'",
        tenant,
        flag,
    )


@pytest.fixture
async def library(net: Net) -> Library:
    seed = net.seed
    tenant = await seed.firm()
    await _flag(net, tenant, "knowledge.catalog")
    admin = await seed.person(tenant, "firm_admin")
    margaret = await seed.person(tenant, "quality_partner")
    daniel = await seed.person(tenant)
    lena = await seed.person(tenant)
    ashford = await seed.site(tenant, admin.user_id, "Ashford")
    bayside = await seed.site(tenant, admin.user_id, "Bayside")
    for site in (ashford, bayside):
        await seed.member(site, daniel, "engagement_partner")
        await seed.member(site, lena, "staff")
    v1 = await _import(net, admin, "BH Audit Methodology", "Plan document")
    v2 = await _import(net, admin, "BH Audit Methodology", "Plan document", "Form 5500")
    pbc = await _import(net, admin, "BH PBC Core", "Bank statements")
    # Owner seeding (the lifecycle's supersede is K-01-T06; `family` is set at insert by the
    # document import, K-01-T18): the template is a methodology, v1 superseded by v2.
    await seed.run_untriggered(
        "UPDATE methodology_templates SET family = 'ebp' WHERE tenant_id = $1 AND name = $2",
        tenant,
        "BH Audit Methodology",
    )
    await seed.run_untriggered(
        "UPDATE methodology_version_states SET status = 'superseded', "
        "default_for_new_engagements = false WHERE version_id = $1",
        v1,
    )
    for site in (ashford, bayside):
        await seed.run_untriggered(
            "UPDATE engagements SET methodology_version_id = $1 WHERE id = $2",
            v2,
            site.engagement_id,
        )
    return Library(net, tenant, admin, margaret, daniel, lena, ashford, bayside, v2, v1, pbc)


def _by_id(page: Json) -> dict[str, Json]:
    return {cast(str, i["id"]): i for i in cast(list[Json], page["items"])}


async def test_ac_the_live_methodology_cards_with_facet_counts(library: Library) -> None:
    page = await library.get(library.daniel, f"{ITEMS}?category=methodology")
    cards = _by_id(page)
    assert set(cards) == {str(library.v1), str(library.v2)}
    v2, v1 = cards[str(library.v2)], cards[str(library.v1)]
    assert (v2["title"], v2["status"], v2["version_label"]) == (
        "BH Audit Methodology",
        "published",
        "v2",
    )
    assert v2["subtitle"] == "EBP · 2 requests"
    assert (v2["usage_count"], v2["usage_kind"]) == (2, "engagements")
    assert v2["route"] == f"/knowledge/methodology/{library.v2}/programs"
    assert (v1["status"], v1["version_label"]) == ("superseded", "v1")
    assert page["counts"] == {"published": 1, "draft": 0, "superseded": 1}
    facets = {f["value"]: f["n"] for f in cast(list[Json], cast(Json, page["facets"])["category"])}
    # Only the registered categories carry a count; firm standards etc. have none (AC1.2).
    assert facets == {"methodology": 2, "pbc_templates": 1}


async def test_ac_an_unregistered_category_returns_no_count_and_no_cards(
    library: Library,
) -> None:
    page = await library.get(library.daniel, f"{ITEMS}?category=firm_standards")
    assert page["items"] == [] and page["total"] == 0
    facets = cast(list[Json], cast(Json, page["facets"])["category"])
    assert "firm_standards" not in {f["value"] for f in facets}


async def test_ac_inv3_a_walled_engagement_is_never_counted(library: Library) -> None:
    before = _by_id(await library.get(library.lena, f"{ITEMS}?category=methodology"))
    assert before[str(library.v2)]["usage_count"] == 2
    await library.net.wall(library.admin, library.lena, library.ashford)
    after = _by_id(await library.get(library.lena, f"{ITEMS}?category=methodology"))
    assert after[str(library.v2)]["usage_count"] == 1
    daniel = _by_id(await library.get(library.daniel, f"{ITEMS}?category=methodology"))
    assert daniel[str(library.v2)]["usage_count"] == 2


async def test_ac17_search_returns_match_ranges_in_the_title(library: Library) -> None:
    page = await library.get(library.daniel, f"{ITEMS}?q=audit")
    cards = _by_id(page)
    assert set(cards) == {str(library.v1), str(library.v2)}
    assert cards[str(library.v2)]["match"] == [{"start": 3, "end": 8}]
    # Found by an area name too, with no range in the title.
    page = await library.get(library.daniel, f"{ITEMS}?q=materiality")
    assert {c["match"] == [] for c in cast(list[Json], page["items"])} == {True}
    assert page["total"] == 3


async def test_ac14_ac16_drafts_are_review_rows_and_hidden_from_readers(
    library: Library,
) -> None:
    await _flag(library.net, library.tenant_id, "methodology.lifecycle")
    under = await _import(library.net, library.admin, "BH Audit Methodology", "Plan", "5500", "x")
    alone = await _import(library.net, library.admin, "BH Section 754 Memo", "Elections")
    margaret = await library.get(library.margaret, ITEMS)
    cards = _by_id(margaret)
    assert str(under) not in cards  # under a published card: the review queue's
    assert cards[str(alone)]["status"] == "draft"
    assert cast(Json, margaret["counts"])["draft"] == 1
    queue = await library.get(library.margaret, "/v1/knowledge/review-queue")
    assert {i["object_id"] for i in cast(list[Json], queue["items"])} == {str(under), str(alone)}
    assert {i["status"] for i in cast(list[Json], queue["items"])} == {"needs_review"}
    # A reader who neither manages nor approves sees no draft, at the API (AC1.6).
    lena = await library.get(library.lena, ITEMS)
    assert str(alone) not in _by_id(lena)
    assert cast(Json, lena["counts"])["draft"] == 0
    assert (await library.get(library.lena, "/v1/knowledge/review-queue"))["items"] == []
    changes = await library.get(library.lena, "/v1/knowledge/change-log")
    assert str(alone) not in {i["object_id"] for i in cast(list[Json], changes["items"])}


async def test_ac15_the_change_log_names_the_person_oldest_first(library: Library) -> None:
    page = await library.get(library.daniel, "/v1/knowledge/change-log")
    items = cast(list[Json], page["items"])
    assert [i["object_id"] for i in items] == [str(library.v1), str(library.v2), str(library.pbc)]
    first = items[0]
    assert first["title"] == "BH Audit Methodology · v1"
    assert first["kind"] == "imported"
    actor = cast(Json, first["actor"])
    assert (actor["kind"], actor["user_id"], actor["name"]) == (
        "human",
        str(library.admin.user_id),
        "Test person",
    )


async def test_ac110_flag_off_and_client_principals_get_nothing(library: Library) -> None:
    await library.net.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'knowledge.catalog'",
        library.tenant_id,
    )
    response = await library.net.call("GET", ITEMS, library.daniel)
    assert response.status_code == 404
    contact = await library.net.seed.client_contact(library.bayside)
    response = await library.net.call("GET", ITEMS, contact)
    assert response.status_code in (403, 404)
