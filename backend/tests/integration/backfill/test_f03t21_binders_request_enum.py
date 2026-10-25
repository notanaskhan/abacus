# ac-test-author: ayushkbhatia
"""F-03-T21 (ADR-078) for F-03-T14, T15 and T16: binders 1:n per work item, the chapter 09
§9.5.6 bridge applied to stored rows, draft never client-visible, overdue derived, follow-up
rename.

Promises (F-03 §3.3 Stories 3.1 to 3.3; F-03 §5 migrations 0058 to 0060 as planned, on main
0070, 0071 and 0087; DEC-09, DEC-31, DEC-74; ADR-144; SPEC-306 AC-5; C5 §2 and §3):
- Story 3.2 (DEC-31): a work item holds a second binder, part 2, beside the first; the binder
  status set is `draft · published · unpublished · complete · closed` (BND-01 a, c).
- Story 3.1 / §9.5.6, one test case per bridge row: `open` and not client-visible becomes
  `draft`; `open` becomes `requested`; `received` and `ready_for_review` become `uploaded`;
  `needs_revision` becomes `returned`; `accepted` becomes `received`. Afterwards the stored set
  is the six DEC-09 codes and `overdue` can never be stored.
- Story 3.1 (AUD-03g): `overdue` is derived from `due_on` and the status, and is never stored;
  which statuses count follows DEC-355 (`requested` and `returned`), not the story's wording.
- Story 3.1 (INV-4): a client principal listing requests never gets a draft.
- Story 3.3 (DEC-74 rename only, F-03-T16): no table or route named `reminder` remains, the
  follow-up names exist, and `follow_up.draft` and `follow_up.send` are unchanged.

Boundary: the bridge runs on a database of its own, migrated to head and back down to the
revision before the bridge (0070), seeded as the superuser with the old codes, then upgraded one
step; the rest is `create_app()` over HTTP on the migrated Postgres (`net`, `seed`), business
time frozen. Spec gaps: §9.5.6 keeps `ready_for_review_at`, but no such column exists before the
bridge, so nothing is checked for it; whether a past-due `draft` is overdue is not said, so it is
left untested.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final, cast

import asyncpg
import httpx
import pytest
import yaml

from abacus.api import create_app
from abacus.kernel.clock import frozen
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .support import Net, Person, Role, Seeder, Site

REPO: Final = Path(__file__).resolve().parents[4]
T0: Final = datetime.fromisoformat("2026-11-16T10:00:00-06:00")
PAST: Final = date(2026, 11, 2)
FUTURE: Final = date(2026, 12, 15)
Json = dict[str, object]

# --- §9.5.6, row by row (F-03 §5 0059; ADR-144) --------------------------------------------------

# (case, old code, client-visible before, code after)
BRIDGE: Final[tuple[tuple[str, str, bool, str], ...]] = (
    ("open_not_client_visible", "open", False, "draft"),
    ("open_client_visible", "open", True, "requested"),
    ("received", "received", True, "uploaded"),
    ("ready_for_review", "ready_for_review", True, "uploaded"),
    ("needs_revision", "needs_revision", True, "returned"),
    ("accepted", "accepted", True, "received"),
)


async def _seed_old_rows(seed: Seeder) -> dict[str, uuid.UUID]:
    """At 0070 (before the bridge): a firm, a person, a client, an engagement and a binder, and a
    request per bridge row holding the old code. The binder's work item is not built (no test
    reads it), so that row alone is written with triggers and foreign-key checks off."""
    tenant, work_item, binder = (uuid.uuid4() for _ in range(3))
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Bridge firm')", tenant)
    person = await seed.value(
        "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
        "VALUES ('https://idp.test', $1, $2, 'Bridge person') RETURNING id",
        f"sub-{tenant.hex}",
        f"{tenant.hex}@example.test",
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')",
        tenant,
        person,
    )
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Bridge client') RETURNING id", tenant
    )
    entity = await seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) "
        "VALUES ($1, $2, 'Bridge entity') RETURNING id",
        tenant,
        client,
    )
    engagement = await seed.value(
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by) "
        "VALUES ($1, $2, $3, 'Bridge engagement', '2025-01-01', '2025-12-31', $4) RETURNING id",
        tenant,
        client,
        entity,
        person,
    )
    await seed.run_untriggered(
        "INSERT INTO request_lists (id, tenant_id, engagement_id, work_item_id, name) "
        "VALUES ($1, $2, $3, $4, '2025 Binder')",
        binder,
        tenant,
        engagement,
        work_item,
    )
    ids: dict[str, uuid.UUID] = {}
    for case, old, visible, _ in BRIDGE:
        ids[case] = cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, status, created_by, client_visible) "
                "VALUES ($1, $2, $3, $4, 'Cash', $5, $6, $7) RETURNING id",
                tenant,
                engagement,
                binder,
                f"Bridge row {case}",
                old,
                person,
                visible,
            ),
        )
    return ids


async def _statuses(seed: Seeder) -> dict[uuid.UUID, str]:
    rows = await seed.rows("SELECT id, status FROM request_items")
    return {cast(uuid.UUID, r["id"]): str(r["status"]) for r in rows}


@dataclass(frozen=True)
class Bridged:
    ids: dict[str, uuid.UUID]
    after: dict[uuid.UUID, str]
    superuser_dsn: str


@pytest.fixture(scope="module")
def bridged() -> Iterator[Bridged]:
    with provisioned_database(roundtrip=False) as database:
        migrate(database.owner_url, "0070", down=True)
        old = Seeder(database.superuser_dsn)
        ids = asyncio.run(_seed_old_rows(old))
        migrate(database.owner_url, "0071")
        after = asyncio.run(_statuses(old))
        yield Bridged(ids, after, database.superuser_dsn)


@pytest.mark.parametrize(("case", "old", "visible", "new"), BRIDGE, ids=[row[0] for row in BRIDGE])
def test_ac3_1_each_9_5_6_bridge_row(
    bridged: Bridged, case: str, old: str, visible: bool, new: str
) -> None:
    assert bridged.after[bridged.ids[case]] == new, (old, visible)


def test_ac3_1_the_bridge_keeps_every_row(bridged: Bridged) -> None:
    assert set(bridged.after) == set(bridged.ids.values())


# --- the stored set after the bridge, on head ----------------------------------------------------


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    manager: Person
    site: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    async def call(
        self, who: Person, method: str, path: str, body: Json | None = None
    ) -> httpx.Response:
        headers = {**self.net.headers(who), "Idempotency-Key": uuid.uuid4().hex}
        with frozen(T0):
            return await self.net.http.request(method, path, json=body, headers=headers)

    async def work_item(self) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "SELECT id FROM work_items WHERE engagement_id = $1 ORDER BY created_at LIMIT 1",
                self.site.engagement_id,
            ),
        )

    async def binder(self) -> uuid.UUID:
        response = await self.call(
            self.manager,
            "POST",
            "/v1/binders",
            {"work_item_id": str(await self.work_item()), "kind": "pbc", "name": "2025 Binder"},
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(str(cast(Json, response.json())["id"]))

    async def request(
        self,
        binder: uuid.UUID,
        status: str,
        *,
        due_on: date | None = None,
        wording: str = "Bank statements",
    ) -> uuid.UUID:
        na = status == "not_applicable"
        visible = status != "draft"  # a draft is the firm's alone (§9.5.6: draft = not visible)
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by, status, client_visible, due_on, "
                "na_reason, na_by, na_at) "
                "VALUES ($1, $2, $3, $4, 'Cash', $5, $6, $7, $8, $9, $10, $11) RETURNING id",
                self.tenant_id,
                self.site.engagement_id,
                binder,
                wording,
                self.manager.user_id,
                status,
                visible,
                due_on,
                "firm_waived" if na else None,
                self.manager.user_id if na else None,
                T0 if na else None,
            ),
        )


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant_id)
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'binders.engine', 'true', 'test-seed', 'F-03-T21')",
        tenant_id,
    )
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Copperleaf")
    manager = await seed.person(tenant_id)
    await seed.member(site, manager, cast(Role, "manager"))
    return Firm(net, tenant_id, manager, site)


SIX: Final = ("draft", "requested", "uploaded", "received", "returned", "not_applicable")


@pytest.mark.parametrize(
    "code", ["open", "ready_for_review", "needs_revision", "accepted", "overdue", "late"]
)
async def test_ac3_1_a_retired_or_derived_code_cannot_be_stored(firm: Firm, code: str) -> None:
    binder = await firm.binder()
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.request(binder, code)


@pytest.mark.parametrize("code", SIX)
async def test_ac3_1_each_of_the_six_codes_can_be_stored(firm: Firm, code: str) -> None:
    binder = await firm.binder()
    item = await firm.request(binder, code)
    assert await firm.seed.value("SELECT status FROM request_items WHERE id = $1", item) == code


# --- Story 3.2: binders 1:n per work item (DEC-31) -----------------------------------------------


async def _parts(firm: Firm) -> dict[uuid.UUID, int]:
    rows = await firm.seed.rows(
        "SELECT id, part FROM request_lists WHERE tenant_id = $1 AND work_item_id = $2 "
        "AND kind = 'pbc'",
        firm.tenant_id,
        await firm.work_item(),
    )
    return {cast(uuid.UUID, r["id"]): int(r["part"]) for r in rows}


async def test_ac3_2_a_work_item_holds_a_second_binder_as_the_next_part(firm: Firm) -> None:
    before = await _parts(firm)  # the site's own list may already be part 1
    first = await firm.binder()
    response = await firm.call(firm.manager, "POST", f"/v1/binders/{first}/duplicate")
    assert response.status_code == 201, response.text
    second = uuid.UUID(str(cast(Json, response.json())["id"]))
    after = await _parts(firm)
    assert set(after) == set(before) | {first, second}  # every binder stays on the work item
    assert after[second] == after[first] + 1 == max(after.values())
    assert len(set(after.values())) == len(after)  # one row per part
    for binder in (first, second):
        read = await firm.call(firm.manager, "GET", f"/v1/binders/{binder}")
        assert read.status_code == 200, read.text


async def test_ac3_2_a_second_part_is_a_new_row_beside_the_first(firm: Firm) -> None:
    """The schema half: another `request_lists` row, the next part, on the same work item."""
    await firm.binder()
    nxt = max((await _parts(firm)).values()) + 1
    second = await firm.seed.value(
        "INSERT INTO request_lists (tenant_id, engagement_id, work_item_id, name, kind, part) "
        "VALUES ($1, $2, $3, '2025 Binder pt 2', 'pbc', $4) RETURNING id",
        firm.tenant_id,
        firm.site.engagement_id,
        await firm.work_item(),
        nxt,
    )
    assert second in await _parts(firm)
    with pytest.raises(asyncpg.UniqueViolationError):  # the same kind and part twice
        await firm.seed.run(
            "INSERT INTO request_lists (tenant_id, engagement_id, work_item_id, name, kind, part) "
            "VALUES ($1, $2, $3, 'Again', 'pbc', $4)",
            firm.tenant_id,
            firm.site.engagement_id,
            await firm.work_item(),
            nxt,
        )


async def test_ac3_2_the_binder_status_set_is_the_five(firm: Firm) -> None:
    binder = await firm.binder()
    for code in ("draft", "published", "unpublished", "complete", "closed"):
        await firm.seed.run("UPDATE request_lists SET status = $2 WHERE id = $1", binder, code)
    for code in ("open", "sent", "archived", "done"):
        with pytest.raises(asyncpg.CheckViolationError):
            await firm.seed.run("UPDATE request_lists SET status = $2 WHERE id = $1", binder, code)


# --- Story 3.1: overdue is derived, never stored (AUD-03g) ---------------------------------------


@pytest.mark.parametrize(
    ("status", "due_on", "overdue"),
    [
        ("requested", PAST, True),
        ("uploaded", PAST, False),  # DEC-355: answered, the firm's review is pending
        ("returned", PAST, True),
        ("received", PAST, False),
        ("not_applicable", PAST, False),
        ("requested", FUTURE, False),
        ("requested", None, False),
    ],
)
async def test_ac3_1_overdue_is_derived_from_the_due_date_and_status(
    firm: Firm, status: str, due_on: date | None, overdue: bool
) -> None:
    """F-03 Story 3.1 reads "not `received` or `not_applicable`"; AUD-03 g, SPEC-027 AC-3, C5's
    follow-ups and portal-pbc (`uploaded` reads "Done") read overdue as what the client still owes.
    DEC-355 decides for the latter: `requested` and `returned` past due are overdue, `uploaded` is
    not."""
    binder = await firm.binder()
    item = await firm.request(binder, status, due_on=due_on)
    response = await firm.call(firm.manager, "GET", f"/v1/binders/{binder}/requests")
    assert response.status_code == 200, response.text
    rows = {str(r["id"]): r for r in cast(list[Json], cast(Json, response.json())["items"])}
    assert rows[str(item)]["overdue"] is overdue
    assert rows[str(item)]["status"] == status  # reported beside the status, never instead of it
    stored = await firm.seed.value("SELECT status FROM request_items WHERE id = $1", item)
    assert stored == status


async def test_ac3_1_no_request_column_stores_overdue(firm: Firm) -> None:
    columns = await firm.seed.rows(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'request_items' "
        "AND column_name LIKE '%overdue%'"
    )
    assert columns == []


# --- Story 3.1: a draft is never client-visible (INV-4) ------------------------------------------


async def test_ac3_1_a_client_principal_never_lists_a_draft(firm: Firm) -> None:
    binder = await firm.binder()
    draft = await firm.request(binder, "draft", wording="Draft wording")
    asked = await firm.request(binder, "requested", wording="Asked wording")
    client = await firm.seed.client_contact(firm.site)
    response = await firm.net.call(
        "GET", f"/v1/engagements/{firm.site.engagement_id}/request-items", client
    )
    assert response.status_code == 200, response.text
    ids = {str(r["id"]) for r in cast(list[Json], response.json())}
    assert str(draft) not in ids
    assert "Draft wording" not in response.text
    assert str(asked) in ids  # the client does read its requests: the draft alone is withheld


# --- Story 3.3: the follow-up rename (DEC-74, F-03-T16) ------------------------------------------


async def test_ac3_3_no_table_is_named_reminder(seed: Seeder) -> None:
    rows = await seed.rows(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_name LIKE '%reminder%'"
    )
    assert [r["table_name"] for r in rows] == []
    follow_ups = await seed.rows(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_name LIKE 'follow_up%'"
    )
    assert follow_ups  # the renamed family is there


# Spec drift: F-03-T16 says no route is named reminder, but P-07's later contract
# (`docs/contracts/acceptance-independence.md`, P-07 §5, ENG-05, CLI-08) adds the independence
# confirmation request at `POST …/independence/reminders`. It is not a follow-up; it is allowed.
CONTRACTED_REMINDER_ROUTES: Final = frozenset(
    {"/v1/engagements/{engagement_id}/independence/reminders"}
)


def test_ac3_3_no_route_is_named_reminder_and_follow_ups_exist() -> None:
    paths = list(cast(dict[str, object], create_app().openapi()["paths"]))
    named = {p for p in paths if "reminder" in p.lower()}
    assert named <= CONTRACTED_REMINDER_ROUTES, named
    assert "/v1/engagements/{engagement_id}/follow-ups" in paths


def test_ac3_3_the_follow_up_actions_are_unchanged() -> None:
    matrix = REPO / "docs" / "architecture" / "permission-matrix"
    actions: dict[str, dict[str, object]] = {}
    for path in matrix.glob("*.yaml"):
        loaded = cast(dict[str, object], yaml.safe_load(path.read_text()) or {})
        for value in loaded.values():
            if isinstance(value, dict):
                for key, cell in cast(dict[str, object], value).items():
                    if isinstance(cell, dict):
                        actions[key] = cast(dict[str, object], cell)
    assert "follow_up.draft" in actions and "follow_up.send" in actions
    assert not [a for a in actions if "reminder" in a]
    assert actions["follow_up.send"]["agent"] == "deny"  # a person sends (INV-1)
