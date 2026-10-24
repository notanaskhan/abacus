# ac-test-author: ayushkbhatia
"""Q-03-T012 (D1, pen scope): ethical walls and need to know, on every surface a person reaches.

Lena Park is walled from Ashford (INV-3). On each of the seven surfaces Q-03 §D1 names (records,
lists, search, counts, notifications, exports and agent sessions) Ashford answers as if it did not
exist: 404 `{"detail": "not found"}` by id, absent from every row, total, count and facet, and no
field anywhere says a client is hidden (SPEC-002 AC-4, AC-5, AC-7; DEC-43, admins included). The
control is Granite, a client she works on the same way: it must show, so an empty or refused
surface cannot pass by accident. A client-level resource is walled like its engagements
(DEC-233), and a firm admin sees an engagement's metadata but none of its content (ADR-024,
clarified by ADR-147 / ADR P-10; `security_admin` holds no content action).

The suite fails on a seeded bypass: `test_d1_a_seeded_wall_bypass_fails_every_surface` lifts the
wall in the database, behind the product's back, and requires every surface probe to report
Ashford. Boundary: `create_app()` over HTTP on the migrated testcontainer Postgres, seeded as the
superuser, plus the public `identity.api.authorise` for an agent acting for Lena (SPEC-002 AC-7).
Expectations come from SPEC-002, DEC-43, DEC-233, ADR-024, ADR-026, ADR-145, ADR-147 and the
contracts (`clients.md`, `engagements-v2.md`, `agent-runs.md`, `notifications.md`).

G-01-T09 extends it to walls v2 and offshore (DEC-52): Remy Vidal, an offshore member with no
offshore-disclosure consent for Ashford, gets the same answers on every surface and route as
walled Lena (Granite, consented, is his control), and with no consent provider at all he reaches
no client; a partner walled from Ashford learns nothing of it from the wall routes v2 adds.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast

import httpx
import pytest
from sqlalchemy import ColumnElement, literal

from abacus.api import create_app
from abacus.kernel.db import TenantContext
from abacus.modules.identity import slots
from abacus.modules.identity.api import Forbidden, Resource, agent_context_for_run, authorise
from abacus_tools.codegen.security_tests import served

from .support import FIRM_ROLES, ROLES, Net, Person, Role, Seeder, Site

Json = dict[str, object]
NOT_FOUND: Final = {"detail": "not found"}
FLAGS: Final = (
    "clients.v2",
    "contacts.v2",
    "engagements.v2",
    "engagements.work_items_api",
    "notifications.v2",
    "compliance.legal_holds",
    "evidence.viewer_v1",
    "binders.engine",
    "firm_settings.v2",  # G-01-T09: the wall preview, approval, log and the offshore group
)
# Words that would tell someone a client exists behind a wall (DEC-43: nothing says one is hidden).
HIDDEN_WORDS: Final = re.compile(r"hidden_by_wall|walled|ethical wall|hidden", re.IGNORECASE)


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    ashford: Site
    granite: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    async def get(self, who: Person, path: str) -> httpx.Response:
        return await self.net.call("GET", path, who)

    def leaks(self, response: httpx.Response) -> list[str]:
        """What of Ashford is in the body: its ids and its name."""
        a = self.ashford
        tokens = (a.client_id, a.entity_id, a.engagement_id, a.item_id, a.version_id, a.marker)
        return [str(t) for t in tokens if str(t) in response.text]


@dataclass(frozen=True)
class Lena:
    """Lena Park on both engagements (a manager there), walled from Ashford by the admin."""

    person: Person
    role: str
    ashford_run: uuid.UUID
    granite_run: uuid.UUID


async def _run(seed: Seeder, firm_id: uuid.UUID, site: Site, initiator: Person) -> uuid.UUID:
    """A finished agent run on the site's engagement that Lena started (C6 lists and traces it)."""
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "evidence_version_id, initiator_user_id, task_scope, status, finished_at) "
            "VALUES ($1, 'evidence.screener', 1, $2, $3, $4, '{}', 'completed', now()) "
            "RETURNING id",
            firm_id,
            site.engagement_id,
            site.version_id,
            initiator.user_id,
        ),
    )


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    for name in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'Q-03-T012')",
            tenant_id,
            name,
        )
    admin = await seed.person(tenant_id, "firm_admin")
    ashford = await seed.site(tenant_id, admin.user_id, "Ashford")
    granite = await seed.site(tenant_id, admin.user_id, "Granite")
    for site in (ashford, granite):
        await seed.run(  # past due, so the overdue counts have something to count
            "UPDATE request_items SET due_on = '2020-01-01' WHERE id = $1", site.item_id
        )
        await seed.run(
            "INSERT INTO findings (tenant_id, engagement_id, title, raised_by) "
            "VALUES ($1, $2, $3, $4)",
            tenant_id,
            site.engagement_id,
            f"Cut-off error {site.marker}",
            admin.user_id,
        )
    return Firm(net, tenant_id, admin, ashford, granite)


async def _lena(firm: Firm, role: str) -> Lena:
    seed = firm.seed
    firm_role = role if role in (*FIRM_ROLES, "security_admin") else None
    person = await seed.person(firm.tenant_id, firm_role)
    await seed.run("UPDATE users SET display_name = 'Lena Park' WHERE id = $1", person.user_id)
    member = "manager" if firm_role else role
    for site in (firm.ashford, firm.granite):
        await seed.member(site, person, cast(Role, member))
        await seed.run(
            "INSERT INTO notifications (tenant_id, recipient_user_id, kind, event_id, "
            "engagement_id, subject_type, subject_id) "
            "VALUES ($1, $2, 'evidence.uploaded', $3, $4, 'evidence_version', $5)",
            firm.tenant_id,
            person.user_id,
            uuid.uuid4(),
            site.engagement_id,
            site.version_id,
        )
    ashford_run = await _run(seed, firm.tenant_id, firm.ashford, person)
    granite_run = await _run(seed, firm.tenant_id, firm.granite, person)
    await firm.net.wall(firm.admin, person, firm.ashford)
    return Lena(person, role, ashford_run, granite_run)


# --- the seven surfaces, as probes ---------------------------------------------------------------
# Each probe returns what it found wrong for Lena: an empty list is a wall that holds. The holding
# tests assert `== []`; the bypass test asserts each one finds Ashford once the wall is gone.

Probe = Callable[[Firm, Lena], Awaitable[list[str]]]


def _not_found(path: str, response: httpx.Response, firm: Firm) -> list[str]:
    found: list[str] = []
    if response.status_code != 404:
        found.append(f"{path}: {response.status_code}, not 404")
    elif response.json() != NOT_FOUND:
        found.append(f"{path}: 404 body {response.text}")
    found += [f"{path}: leaks {token}" for token in firm.leaks(response)]
    return found


def _no_leak(path: str, response: httpx.Response, firm: Firm) -> list[str]:
    found = [f"{path}: leaks {token}" for token in firm.leaks(response)]
    if response.status_code < 300 and HIDDEN_WORDS.search(response.text):
        found.append(f"{path}: says something is hidden")
    return found


async def records(firm: Firm, lena: Lena) -> list[str]:
    a = firm.ashford
    paths = (
        f"/v1/engagements/{a.engagement_id}",
        f"/v1/engagements/{a.engagement_id}/request-items",
        f"/v1/engagements/{a.engagement_id}/evidence-versions",
        f"/v1/engagements/{a.engagement_id}/team",
        f"/v1/engagements/{a.engagement_id}/board-summary",
        f"/v1/clients/{a.client_id}",  # DEC-233: a client-level resource is walled too
        f"/v1/clients/{a.client_id}/overview",
        f"/v1/clients/{a.client_id}/relationships",
        f"/v1/engagements/{a.engagement_id}/request-items/{a.item_id}/uploads",
    )
    found: list[str] = []
    for path in paths:
        found += _not_found(path, await firm.get(lena.person, path), firm)
    return found


async def lists(firm: Firm, lena: Lena) -> list[str]:
    found: list[str] = []
    for path in ("/v1/engagements", "/v1/engagements/index", "/v1/clients", "/v1/work-items"):
        found += _no_leak(path, await firm.get(lena.person, path), firm)
    return found


async def search(firm: Firm, lena: Lena) -> list[str]:
    found: list[str] = []
    for path in (
        "/v1/firm/search/request-items?q=Bank%20confirmation",
        f"/v1/firm/search/request-items?q={firm.ashford.marker}",
        "/v1/firm/search/findings?q=Cut-off",
        f"/v1/firm/clients/search?q={firm.ashford.marker}",
        "/v1/firm/clients/search?q=Ashford",
        "/v1/firm/clients/search?q=Client",
    ):
        found += _no_leak(path, await firm.get(lena.person, path), firm)
    return found


def _int(body: object, *keys: str) -> int | None:
    value: object = body
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = cast(Json, value).get(key)
    return value if isinstance(value, int) else None


async def counts(firm: Firm, lena: Lena) -> list[str]:
    """Every total and count is Granite's alone: the firm has two clients and Lena sees one."""
    found: list[str] = []
    for path in (
        "/v1/firm/waiting/overdue",
        "/v1/firm/waiting/review",
        "/v1/firm/waiting/fieldwork",
    ):
        found += _no_leak(path, await firm.get(lena.person, path), firm)
    for path in ("/v1/clients", "/v1/engagements/index"):
        response = await firm.get(lena.person, path)
        found += _no_leak(path, response, firm)
        if response.status_code != 200:
            found.append(f"{path}: {response.status_code}")
            continue
        body = cast(Json, response.json())
        total = _int(body, "total")
        if total != 1:
            found.append(f"{path}: total {total}, not 1")
        tiles = body.get("counts")
        if isinstance(tiles, dict):
            summed = sum(v for v in cast(Json, tiles).values() if isinstance(v, int))
            if summed > 1:
                found.append(f"{path}: counts sum to {summed}")
    return found


async def notifications(firm: Firm, lena: Lena) -> list[str]:
    response = await firm.get(lena.person, "/v1/notifications")
    found = _no_leak("/v1/notifications", response, firm)
    unread = _int(response.json(), "unread_count") if response.status_code == 200 else None
    if unread != 1:
        found.append(f"/v1/notifications: unread_count {unread}, not 1")
    feed = await firm.get(lena.person, "/v1/notifications/feed?tab=all")
    found += _no_leak("/v1/notifications/feed", feed, firm)
    if feed.status_code == 200 and _int(feed.json(), "unread_count") != 1:
        found.append(f"/v1/notifications/feed: unread_count {feed.json()}")
    return found


async def exports(firm: Firm, lena: Lena) -> list[str]:
    path = f"/v1/agent-runs/{lena.ashford_run}/trace-exports"
    response = await firm.net.call("POST", path, lena.person, body={"format": "json"})
    return _not_found(path, response, firm)


async def agent_sessions(firm: Firm, lena: Lena) -> list[str]:
    a = firm.ashford
    found: list[str] = []
    for path in (
        f"/v1/engagements/{a.engagement_id}/agent-runs?state=recent",
        f"/v1/agent-runs/{lena.ashford_run}/trace",
        f"/v1/engagements/{a.engagement_id}/agent",
    ):
        found += _not_found(path, await firm.get(lena.person, path), firm)
    # SPEC-002 AC-7: the agent acting for Lena is refused Ashford at its next step, at the wall.
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=lena.ashford_run,
        agent_id="evidence.screener",
        engagement_id=a.engagement_id,
        task_scope=frozenset({"evidence.read", "request_item.read"}),
        initiator_user_id=lena.person.user_id,
    )
    for action in ("evidence.read", "request_item.read"):
        try:
            await authorise(
                agent, action, Resource.engagement(firm.tenant_id, a.engagement_id, archived=False)
            )
        except Forbidden as denied:
            if denied.layer != "wall":
                found.append(f"agent {action}: denied at {denied.layer}, not the wall")
        else:
            found.append(f"agent {action}: allowed on Ashford")
    return found


SURFACES: Final[dict[str, Probe]] = {
    "records": records,
    "lists": lists,
    "search": search,
    "counts": counts,
    "notifications": notifications,
    "exports": exports,
    "agent_sessions": agent_sessions,
}


# --- the wall holds on every surface, whatever Lena's role ---------------------------------------


@pytest.mark.parametrize("role", ROLES)
async def test_d1_records_answer_404_by_id(firm: Firm, role: str) -> None:
    lena = await _lena(firm, role)
    assert await records(firm, lena) == []
    g = firm.granite
    for path in (f"/v1/engagements/{g.engagement_id}", f"/v1/clients/{g.client_id}"):
        control = await firm.get(lena.person, path)
        assert control.status_code == 200, (path, control.text)


@pytest.mark.parametrize("role", ROLES)
async def test_d1_lists_carry_no_row_of_ashford(firm: Firm, role: str) -> None:
    lena = await _lena(firm, role)
    assert await lists(firm, lena) == []
    for path in ("/v1/engagements", "/v1/clients"):
        control = await firm.get(lena.person, path)
        assert control.status_code == 200, (path, control.text)
        assert (
            str(
                firm.granite.engagement_id if path == "/v1/engagements" else firm.granite.client_id
            )
            in control.text
        )


@pytest.mark.parametrize("role", ROLES)
async def test_d1_search_finds_nothing_of_ashford(firm: Firm, role: str) -> None:
    lena = await _lena(firm, role)
    assert await search(firm, lena) == []
    control = await firm.get(lena.person, "/v1/firm/search/request-items?q=Bank%20confirmation")
    assert control.status_code == 200, control.text
    assert str(firm.granite.item_id) in control.text
    exact = await firm.get(lena.person, f"/v1/firm/search/request-items?q={firm.ashford.marker}")
    assert exact.json() == []


@pytest.mark.parametrize("role", ROLES)
async def test_d1_counts_and_totals_leave_ashford_out_with_no_hidden_count(
    firm: Firm, role: str
) -> None:
    """DEC-43: nobody sees a hidden count, admins included; `total` is Granite's alone."""
    lena = await _lena(firm, role)
    assert await counts(firm, lena) == []


@pytest.mark.parametrize("role", ROLES)
async def test_d1_notifications_about_ashford_are_neither_shown_nor_counted(
    firm: Firm, role: str
) -> None:
    lena = await _lena(firm, role)
    assert await notifications(firm, lena) == []
    control = await firm.get(lena.person, "/v1/notifications")
    assert str(firm.granite.engagement_id) in control.text


async def test_d1_a_trace_export_of_an_ashford_run_answers_404(firm: Firm) -> None:
    """C6: a manager may export a run's trace with fresh MFA; Ashford's answers as unknown."""
    lena = await _lena(firm, "manager")
    assert await exports(firm, lena) == []
    control = await firm.net.call(
        "POST",
        f"/v1/agent-runs/{lena.granite_run}/trace-exports",
        lena.person,
        body={"format": "json"},
    )
    assert control.status_code == 201, control.text
    unknown = await firm.net.call(
        "POST",
        f"/v1/agent-runs/{uuid.uuid4()}/trace-exports",
        lena.person,
        body={"format": "json"},
    )
    assert unknown.status_code == 404
    assert unknown.json() == NOT_FOUND  # walled and unknown read the same


@pytest.mark.parametrize("role", ["engagement_partner", "manager", "senior", "staff"])
async def test_d1_agent_sessions_on_ashford_answer_404_and_the_agent_is_walled(
    firm: Firm, role: str
) -> None:
    lena = await _lena(firm, role)
    assert await agent_sessions(firm, lena) == []
    control = await firm.get(lena.person, f"/v1/agent-runs/{lena.granite_run}/trace")
    assert control.status_code == 200, control.text


# --- every route, swept: walled reads the same as never-existed ----------------------------------

_ROUTES: Final = served(create_app())[0]
_PARAM: Final = re.compile(r"\{(\w+)\}")


def _fill(path: str, firm: Firm, lena: Lena, *, real: bool) -> str:
    a = firm.ashford
    known = {
        "engagement_id": a.engagement_id,
        "client_id": a.client_id,
        "item_id": a.item_id,
        "version_id": a.version_id,
        "run_id": lena.ashford_run,
    }

    def one(match: re.Match[str]) -> str:
        name = match.group(1)
        if name == "page_no":
            return "1"
        if name in ("which", "section", "target_type", "field_key", "ref"):
            return "x"
        return str(known[name] if real and name in known else uuid.uuid4())

    return _PARAM.sub(one, path)


def _walled_routes() -> list[str]:
    """Every GET whose path names one of Ashford's engagement, client, version or run."""
    prefixes = (
        "/v1/engagements/{engagement_id}",
        "/v1/clients/{client_id}",
        "/v1/evidence-versions/{version_id}",
        "/v1/agent-runs/{run_id}",
    )
    return sorted({p for m, p, _ in _ROUTES if m == "GET" and p.startswith(prefixes)})


@pytest.mark.parametrize("role", ["manager", "firm_admin"])
async def test_d1_every_record_route_reads_ashford_as_if_it_never_existed(
    firm: Firm, role: str
) -> None:
    """SPEC-002 AC-4 over the served route table: for each GET naming Ashford's engagement,
    client, version or run, Lena's answer is a 404 and is the same as for an id that never
    existed, so the response says nothing of Ashford."""
    lena = await _lena(firm, role)
    found: list[str] = []
    routes = _walled_routes()
    assert len(routes) > 60  # the sweep is the API surface, not a sample
    for route in routes:
        walled = await firm.get(lena.person, _fill(route, firm, lena, real=True))
        never = await firm.get(lena.person, _fill(route, firm, lena, real=False))
        if walled.status_code < 400:
            found.append(f"{route}: {walled.status_code}")
        elif (walled.status_code, walled.text) != (never.status_code, never.text):
            found.append(f"{route}: {walled.status_code} {walled.text} vs {never.status_code}")
        found += [f"{route}: leaks {t}" for t in firm.leaks(walled)]
    assert found == []


@pytest.mark.parametrize("role", ["manager", "firm_admin", "practice_leader", "quality_partner"])
async def test_d1_no_list_route_carries_ashford(firm: Firm, role: str) -> None:
    """SPEC-002 AC-5 over the served route table: every GET without a path parameter (the
    lists, searches, counts and feeds a person reaches) carries nothing of Ashford."""
    lena = await _lena(firm, role)
    found: list[str] = []
    paths = sorted(
        {p for m, p, _ in _ROUTES if m == "GET" and "{" not in p and p.startswith("/v1/")}
    )
    assert len(paths) > 60
    for path in paths:
        if path.startswith(("/v1/walls", "/v1/firm/clients", "/v1/firm/members")):
            continue  # wall management, firm admin only: Lena is not the admin who walls
        found += _no_leak(path, await firm.get(lena.person, path), firm)
        found += _no_leak(path, await firm.get(lena.person, f"{path}?q=Ashford&limit=100"), firm)
    assert found == []


# --- admins see metadata, not content (ADR-024, ADR-147) -----------------------------------------


@pytest.mark.parametrize("firm_role", ["firm_admin", "security_admin"])
async def test_d1_an_admin_off_the_team_reads_metadata_but_no_content(
    firm: Firm, firm_role: str
) -> None:
    admin = await firm.seed.person(firm.tenant_id, firm_role)
    g = firm.granite
    if firm_role == "firm_admin":  # ADR-024: name, status, team and progress, without joining
        meta = await firm.get(admin, f"/v1/engagements/{g.engagement_id}")
        assert meta.status_code == 200, meta.text
        assert str(g.engagement_id) in meta.text
        assert f"Bank confirmation {g.marker}" not in meta.text  # an item's contents is content
    for path in (
        f"/v1/engagements/{g.engagement_id}/request-items",
        f"/v1/engagements/{g.engagement_id}/evidence-versions",
        f"/v1/engagements/{g.engagement_id}/request-items/{g.item_id}/uploads",
        f"/v1/engagements/{g.engagement_id}/board-summary",
    ):
        response = await firm.get(admin, path)
        assert response.status_code == 403, (path, response.status_code, response.text)
        assert g.marker not in response.text
    search = await firm.get(admin, "/v1/firm/search/request-items?q=Bank%20confirmation")
    assert g.marker not in search.text  # content reaches nobody off the team through search


async def test_d1_a_walled_admin_gets_no_metadata_either(firm: Firm) -> None:
    """ADR-026: walls override every role, firm admin included; ADR-024's metadata stops at the
    wall, and the clients index counts one client, not two (DEC-43)."""
    grace = await firm.seed.person(firm.tenant_id, "firm_admin")
    await firm.net.wall(firm.admin, grace, firm.ashford)
    meta = await firm.get(grace, f"/v1/engagements/{firm.ashford.engagement_id}")
    assert meta.status_code == 404
    assert meta.json() == NOT_FOUND
    index = await firm.get(grace, "/v1/engagements")
    assert firm.leaks(index) == []
    assert str(firm.granite.engagement_id) in index.text
    clients = await firm.get(grace, "/v1/clients")
    assert clients.status_code == 200, clients.text
    assert firm.leaks(clients) == []
    assert _int(clients.json(), "total") == 1


# --- and the file fails on a seeded bypass ------------------------------------------------------


@pytest.mark.parametrize("surface", list(SURFACES))
async def test_d1_a_seeded_wall_bypass_fails_every_surface(firm: Firm, surface: str) -> None:
    """Q-03-T012's acceptance: lift Lena's wall in the database, with no route, no audit and no
    cache invalidation, and each surface's probe must report Ashford. A probe that still finds
    nothing would be passing by construction."""
    lena = await _lena(firm, "manager")
    probe = SURFACES[surface]
    assert await probe(firm, lena) == []  # the wall holds
    await firm.seed.run(
        "UPDATE ethical_walls SET status = 'removed', removed_at = now(), removed_by = $2 "
        "WHERE user_id = $1",
        lena.person.user_id,
        firm.admin.user_id,
    )
    assert await probe(firm, lena) != []  # the bypass is caught


# --- G-01-T09: offshore is a wall around every client without a consent (DEC-52) ----------------


@pytest.fixture
def granite_consented(firm: Firm) -> Iterator[None]:
    """T-01's provider stand-in: an offshore-disclosure consent covers Granite, not Ashford."""
    granite = firm.granite.client_id

    async def check(_tenant: TenantContext, client: uuid.UUID, _p: str, _at: datetime) -> bool:
        return client == granite

    def column(client_id: object, _purpose: str) -> ColumnElement[bool]:
        return cast(ColumnElement[uuid.UUID], client_id) == literal(granite)

    slots.register_consent_check(slots.OFFSHORE_DISCLOSURE, check, column)
    yield
    slots._CONSENTS.pop(slots.OFFSHORE_DISCLOSURE, None)  # pyright: ignore[reportPrivateUsage] -- drops the stand-in
    slots._CONSENT_COLUMNS.pop(slots.OFFSHORE_DISCLOSURE, None)  # pyright: ignore[reportPrivateUsage] -- drops the stand-in


async def _remy(firm: Firm, role: str) -> Lena:
    """Remy Vidal set up exactly as Lena, but offshore instead of walled: Ashford has no
    consent, so it must read the same as Lena's walled Ashford."""
    lena = await _lena_unwalled(firm, role)
    await firm.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        lena.person.user_id,
    )
    return lena


async def _lena_unwalled(firm: Firm, role: str) -> Lena:
    seed = firm.seed
    firm_role = role if role in (*FIRM_ROLES, "security_admin") else None
    person = await seed.person(firm.tenant_id, firm_role)
    await seed.run("UPDATE users SET display_name = 'Remy Vidal' WHERE id = $1", person.user_id)
    member = "manager" if firm_role else role
    for site in (firm.ashford, firm.granite):
        await seed.member(site, person, cast(Role, member))
        await seed.run(
            "INSERT INTO notifications (tenant_id, recipient_user_id, kind, event_id, "
            "engagement_id, subject_type, subject_id) "
            "VALUES ($1, $2, 'evidence.uploaded', $3, $4, 'evidence_version', $5)",
            firm.tenant_id,
            person.user_id,
            uuid.uuid4(),
            site.engagement_id,
            site.version_id,
        )
    ashford_run = await _run(seed, firm.tenant_id, firm.ashford, person)
    granite_run = await _run(seed, firm.tenant_id, firm.granite, person)
    return Lena(person, role, ashford_run, granite_run)


@pytest.mark.parametrize("surface", list(SURFACES))
@pytest.mark.parametrize("role", ["manager", "staff", "firm_admin"])
async def test_i_offshore_every_surface_hides_a_non_consented_client(
    firm: Firm, granite_consented: None, surface: str, role: str
) -> None:
    """I-OFFSHORE: Ashford, without a consent, is walled off from offshore Remy on all seven
    surfaces (404, no row, no count, nothing says it is hidden), and Granite still shows."""
    remy = await _remy(firm, role)
    assert await SURFACES[surface](firm, remy) == []


@pytest.mark.parametrize("surface", list(SURFACES))
async def test_i_offshore_a_seeded_bypass_fails_every_surface(
    firm: Firm, granite_consented: None, surface: str
) -> None:
    """The offshore probes aren't vacuous: turning offshore off in the database, behind the
    product's back, makes every surface report Ashford."""
    remy = await _remy(firm, "manager")
    probe = SURFACES[surface]
    assert await probe(firm, remy) == []
    await firm.seed.run(
        "UPDATE memberships SET offshore = false WHERE user_id = $1", remy.person.user_id
    )
    assert await probe(firm, remy) != []


@pytest.mark.parametrize("role", ["manager", "firm_admin"])
async def test_i_offshore_every_record_route_reads_ashford_as_if_it_never_existed(
    firm: Firm, granite_consented: None, role: str
) -> None:
    remy = await _remy(firm, role)
    found: list[str] = []
    for route in _walled_routes():
        hidden = await firm.get(remy.person, _fill(route, firm, remy, real=True))
        never = await firm.get(remy.person, _fill(route, firm, remy, real=False))
        if hidden.status_code < 400:
            found.append(f"{route}: {hidden.status_code}")
        elif (hidden.status_code, hidden.text) != (never.status_code, never.text):
            found.append(f"{route}: {hidden.status_code} {hidden.text} vs {never.status_code}")
        found += [f"{route}: leaks {t}" for t in firm.leaks(hidden)]
    assert found == []


async def test_i_offshore_with_no_consent_provider_no_client_is_reached(firm: Firm) -> None:
    """DEC-52 fail closed: before T-01 registers its provider, both clients read as unknown."""
    remy = await _remy(firm, "manager")
    clients = await firm.get(remy.person, "/v1/clients")
    assert clients.status_code == 200, clients.text
    assert _int(clients.json(), "total") == 0
    for site in (firm.ashford, firm.granite):
        for path in (f"/v1/clients/{site.client_id}", f"/v1/engagements/{site.engagement_id}"):
            response = await firm.get(remy.person, path)
            assert (response.status_code, response.json()) == (404, NOT_FOUND), path
    index = await firm.get(remy.person, "/v1/engagements/index")
    assert _int(index.json(), "total") == 0


# --- G-01-T09: the wall routes v2 adds say nothing of a client the reader is walled from -------


async def test_d1_a_walled_partner_learns_nothing_of_ashford_from_the_v2_wall_routes(
    firm: Firm,
) -> None:
    lena = await _lena(firm, "staff")
    daniel = await firm.seed.person(firm.tenant_id)
    await firm.seed.run(
        "UPDATE memberships SET level = 'partner' WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        daniel.user_id,
    )
    await firm.net.wall(firm.admin, daniel, firm.ashford)
    a, unknown = firm.ashford.client_id, uuid.uuid4()
    for template in (
        "/v1/walls/preview?user_id={u}&client_id={c}",
        "/v1/walls/preview?user_id={u}&client_id={c}&limit=1",
    ):
        walled = await firm.get(daniel, template.format(u=lena.person.user_id, c=a))
        never = await firm.get(daniel, template.format(u=lena.person.user_id, c=unknown))
        assert (walled.status_code, walled.text) == (never.status_code, never.text)
        assert walled.status_code == 404
    listed = await firm.get(daniel, "/v1/walls")
    assert listed.status_code == 200, listed.text
    assert firm.leaks(listed) == []
    walls = await firm.seed.rows(
        "SELECT id, user_id FROM ethical_walls WHERE client_id = $1", firm.ashford.client_id
    )
    assert len(walls) == 2  # Lena's and Daniel's own
    for wall in walls:
        wall_id = wall["id"]
        calls = [("GET", f"/v1/walls/{wall_id}/events"), ("POST", f"/v1/walls/{wall_id}/approve")]
        if wall["user_id"] != daniel.user_id:  # his own answers own_wall (AC8.4)
            calls.append(("POST", f"/v1/walls/{wall_id}/remove"))
        for method, path in calls:
            response = await firm.net.call(method, path, daniel)
            never = await firm.net.call(
                method, path.replace(str(wall_id), str(uuid.uuid4())), daniel
            )
            assert (response.status_code, response.text) == (never.status_code, never.text), path
