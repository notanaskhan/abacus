"""x1, x25 and x100 load profiles: N synthetic Brightwater-size firms (Q-03-T044; chapter 10
section 10.11.2; QD-6). `make seed-staging PROFILE=x25`.

Run: python -m abacus_tools.synthetic.fleet --profile x25 [--staging]

Each firm is the Brightwater Hale shape, counted from the F-04 scenario so it cannot drift: its 46
seats across the three offices, its 184 clients, its 27 audit engagements (type, period, status and
due date of each Brightwater audit in turn), one published PBC list per audit with the F-04
generator's request list (`synthetic.requests.request_list`, 16 requests in glossary terms), and
two client people per audit with an engagement grant. Names are numbered placeholders ("Load Firm
007", "Load Client 112 (Firm 007)"), every address on the `.test` sink domain, every firm
`synthetic`. Profiles nest: firm n is the same firm in x1, x25 and x100, so x25 after x1 adds 24.

Clients go through `organisations.api.create_client`, as a person would, under the firm's practice
leader. The firm, its offices, people, engagements, PBC lists and client people have no owning
service yet (tenant provisioning's workflow invites real admins; engagement creation is a
draft-and-accept flow), so they are bootstrapped exactly as the Brightwater loader does it
(DEC-144): one owner transaction per write carrying the tenant, the actor and the business time,
ending with the audit row the service would have written. Every write is keyed by a trace id
derived from `fleet:<FLEET_VERSION>:<firm>:<step>`; a step whose trace already has an audit row is
skipped, so a second run writes nothing. The loader's rollout flags (and the portal pair, P-08-T28)
go on for each firm. No demo clock is set: load runs on the system clock.

Refuses (the Brightwater loader's guard): production always; on a laptop any database that is not
loopback; with `--staging` an environment other than staging (the perf stack runs as a staging
environment on its own database, QD-6) or a staging deploy in flight; with `--staging`, x25 and
x100 on any database host but the perf stack's (`perf_guard`); and any existing firm with a fleet
id that is not synthetic. Every check reads as the firm (`loader.tenant_value`), so it holds under
row-level security as the owner role, not only as a laptop's superuser.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg

from abacus.kernel.clock import frozen
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.organisations.api import NewClient, create_client
from abacus_tools.db_connect import connect as connect_db
from abacus_tools.fakes.identity import ISSUER
from abacus_tools.flags import set_flag
from abacus_tools.synthetic.requests import request_list
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import AUDITS, Audit
from abacus_tools.synthetic.scenarios.brightwater_hale.clients import build_clients
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import (
    DEFAULT_SUPERUSER,
    FLAGS_ON,
    OFFICE_CODES,
    OFFICE_ZONES,
    SUPERUSER_ENV,
    LoadRefused,
    Write,
    bootstrap_write,
    guard,
    tenant_rows,
    tenant_value,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT

FLEET_VERSION: Final = "1"
LOADER: Final = "fleet-loader"
SINK: Final = "sink.load.test"
PROFILES: Final = {"x1": 1, "x25": 25, "x100": 100}
# P-08-T28: the portal rollout flags are on for every synthetic firm.
FLEET_FLAGS: Final = (*FLAGS_ON, "portal.sign_in_v2", "portal.home_v2")
OFFICES: Final = tuple(OFFICE_ZONES)
HQ: Final = "Chicago"


@dataclass(frozen=True)
class FirmShape:
    """What one Brightwater-size firm holds (chapter 10 section 10.11.2's x1 column)."""

    seats: int
    clients: int
    audits: int
    requests_per_audit: int
    portal_people_per_audit: int


def brightwater_shape() -> FirmShape:
    """Counted from the F-04 scenario: 46 seats, 184 clients, 27 audits."""
    return FirmShape(
        seats=len(SEATS),
        clients=len(build_clients()),
        audits=len(AUDITS),
        requests_per_audit=len(request_list().items),
        portal_people_per_audit=2,
    )


@dataclass(frozen=True)
class Firm:
    n: int
    shape: FirmShape

    @property
    def tenant(self) -> UUID:
        return UUID(stable_id(f"fleet:firm:{self.n}"))

    @property
    def name(self) -> str:
        return f"Load Firm {self.n:03d}"

    def id(self, kind: str, k: int | str = 0) -> UUID:
        return UUID(stable_id(f"fleet:{self.n}:{kind}:{k}"))

    def seat_office(self, k: int) -> str:
        return OFFICES[k % len(OFFICES)]

    def firm_role(self, k: int) -> str | None:
        return {0: "firm_admin", 1: "practice_leader"}.get(k)

    def audit_template(self, a: int) -> Audit:
        return AUDITS[a % len(AUDITS)]

    def team(self, a: int) -> tuple[tuple[int, str], ...]:
        """(seat, engagement role): a partner, a manager, a senior and a staff member, spread
        over the firm's seats from seat 2 on (0 and 1 are the admin and the leader)."""
        pool = self.shape.seats - 2
        base = 2 + (a * 4) % pool
        roles = ("engagement_partner", "manager", "senior", "staff")
        return tuple((2 + (base - 2 + i) % pool, role) for i, role in enumerate(roles))


def plan(profile: str, shape: FirmShape | None = None) -> tuple[Firm, ...]:
    if profile not in PROFILES:
        raise ValueError(f"no profile {profile!r}; known: {', '.join(PROFILES)}")
    found = shape or brightwater_shape()
    return tuple(Firm(n, found) for n in range(1, PROFILES[profile] + 1))


# --- writes -------------------------------------------------------------------------------------


def trace_hex(firm: Firm, step: str) -> str:
    return hashlib.sha256(f"fleet:{FLEET_VERSION}:{firm.n}:{step}".encode()).hexdigest()[:32]


@dataclass
class Counts:
    written: int = 0
    skipped: int = 0


async def _done(conn: asyncpg.Connection, firm: Firm, step: str) -> bool:
    return bool(
        await tenant_value(
            conn,
            firm.tenant,
            "SELECT EXISTS (SELECT 1 FROM audit_events WHERE tenant_id = $1 AND trace_id = $2)",
            firm.tenant,
            trace_hex(firm, step),
        )
    )


async def _step(
    conn: asyncpg.Connection, firm: Firm, step: str, actor: str, write: Write, counts: Counts
) -> None:
    """The scenario loader's bootstrap (`loader.bootstrap_write`) for one step, once."""
    if await _done(conn, firm, step):
        counts.skipped += 1
        return
    await bootstrap_write(
        conn,
        tenant=firm.tenant,
        actor_kind="system" if actor == LOADER else "human",
        actor_id=actor,
        at=SETUP_AT,
        trace=trace_hex(firm, step),
        write=write,
    )
    counts.written += 1


async def _firm(conn: asyncpg.Connection, firm: Firm, counts: Counts) -> None:
    async def firm_row() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO firms (tenant_id, name, synthetic, region, time_zone) "
            "VALUES ($1, $2, true, 'us', 'America/Chicago') ON CONFLICT DO NOTHING",
            firm.tenant,
            firm.name,
        )
        return "firm.created", "firm", str(firm.tenant)

    await _step(conn, firm, "firm", LOADER, firm_row, counts)
    for office in OFFICES:

        async def office_row(office: str = office) -> tuple[str, str, str]:
            await conn.execute(
                "INSERT INTO offices (id, tenant_id, name, time_zone, code, is_hq) "
                "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING",
                firm.id("office", office),
                firm.tenant,
                office,
                OFFICE_ZONES[office],
                OFFICE_CODES[office],
                office == HQ,
            )
            return "office.created", "office", str(firm.id("office", office))

        await _step(conn, firm, f"office:{office}", LOADER, office_row, counts)


def seat_user(firm: Firm, k: int) -> UUID:
    return firm.id("user", k)


def seat_initials(k: int) -> str:
    """Two capitals per seat (AA, AB, ...): memberships take one to four capital letters."""
    return chr(65 + k // 26) + chr(65 + k % 26)


def seat_subject(firm: Firm, k: int) -> str:
    """The local sign-in subject of a seat (`abacus_tools.fakes.identity`)."""
    return f"fleet-{firm.n:03d}-staff-{k:02d}"


async def _seats(conn: asyncpg.Connection, firm: Firm, counts: Counts) -> None:
    for k in range(firm.shape.seats):

        async def seat_row(k: int = k) -> tuple[str, str, str]:
            user = seat_user(firm, k)
            await conn.execute(
                "INSERT INTO users (id, idp_issuer, idp_subject, email, display_name) "
                "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
                user,
                ISSUER,
                seat_subject(firm, k),
                f"staff{k:02d}.firm{firm.n:03d}@{SINK}",
                f"Staff {k + 1:02d}, {firm.name}",
            )
            await conn.execute(
                "INSERT INTO memberships (tenant_id, user_id, status, kind, firm_role, office_id, "
                "initials, created_at) VALUES ($1, $2, 'active', 'staff', $3, $4, $5, $6) "
                "ON CONFLICT DO NOTHING",
                firm.tenant,
                user,
                firm.firm_role(k),
                firm.id("office", firm.seat_office(k)),
                seat_initials(k),
                SETUP_AT + timedelta(microseconds=k),
            )
            return "membership.created", "user", str(user)

        await _step(conn, firm, f"seat:{k}", LOADER, seat_row, counts)


def client_ids(firm: Firm, c: int) -> NewClient:
    return NewClient(firm.id("client", c), firm.id("entity", c))


def client_name(firm: Firm, c: int) -> str:
    return f"Load Client {c + 1:03d} ({firm.name})"


async def _clients(conn: asyncpg.Connection, firm: Firm, counts: Counts) -> None:
    """Through `organisations.api` under the firm's practice leader (seat 1)."""
    leader = str(seat_user(firm, 1))
    for c in range(firm.shape.clients):
        ids = client_ids(firm, c)
        exists = await tenant_value(
            conn,
            firm.tenant,
            "SELECT EXISTS (SELECT 1 FROM clients WHERE tenant_id = $1 AND id = $2)",
            firm.tenant,
            ids.client_id,
        )
        if exists:
            counts.skipped += 1
            continue
        name = client_name(firm, c)
        with frozen(SETUP_AT):
            async with uow(TenantContext(firm.tenant, "human", leader)) as tx:
                await create_client(tx, firm.tenant, name, name, ids=ids)
        counts.written += 1


async def _audits(conn: asyncpg.Connection, firm: Firm, counts: Counts) -> None:
    for a in range(firm.shape.audits):
        await _audit(conn, firm, a, counts)


async def _audit(conn: asyncpg.Connection, firm: Firm, a: int, counts: Counts) -> None:
    """One audit engagement, its team, its PBC list and its client people."""
    items = request_list().items
    areas = tuple(dict.fromkeys(i.audit_area for i in items))
    template = firm.audit_template(a)
    engagement = firm.id("engagement", a)
    client = client_ids(firm, a % firm.shape.clients)
    team = firm.team(a)
    partner = seat_user(firm, team[0][0])

    async def engagement_row() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO engagements (id, tenant_id, client_id, client_entity_id, name, type, "
            "fiscal_period_start, fiscal_period_end, status, created_by, created_at, "
            "office_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) "
            "ON CONFLICT DO NOTHING",
            engagement,
            firm.tenant,
            client.client_id,
            client.client_entity_id,
            f"{template.name} (Load {a + 1:02d})",
            template.type,
            template.period[0],
            template.period[1],
            "delivered" if template.status == "archived" else template.status,
            partner,
            SETUP_AT,
            firm.id("office", HQ),
        )
        await conn.execute(
            "UPDATE work_items SET due_on = $3 WHERE tenant_id = $1 AND engagement_id = $2 "
            "AND kind = 'assurance'",
            firm.tenant,
            engagement,
            template.due_on,
        )
        for seat, role in team:
            await conn.execute(
                "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                firm.tenant,
                engagement,
                seat_user(firm, seat),
                role,
            )
        return "engagement.created", "engagement", str(engagement)

    await _step(conn, firm, f"engagement:{a}", str(partner), engagement_row, counts)

    async def pbc_rows() -> tuple[str, str, str]:
        list_id = firm.id("pbc", a)
        await conn.execute(
            "INSERT INTO request_lists (id, tenant_id, engagement_id, created_at, kind, "
            "status, published_at, published_by) "
            "VALUES ($1, $2, $3, $4, 'pbc', 'published', $4, $5) "
            "ON CONFLICT DO NOTHING",
            list_id,
            firm.tenant,
            engagement,
            SETUP_AT,
            partner,
        )
        for position, area in enumerate(areas):
            await conn.execute(
                "INSERT INTO request_categories (id, tenant_id, request_list_id, name, "
                "position, family) VALUES ($1, $2, $3, $4, $5, 'audit_area') "
                "ON CONFLICT DO NOTHING",
                firm.id(f"category:{a}", area),
                firm.tenant,
                list_id,
                area,
                position,
            )
        for position, item in enumerate(items[: firm.shape.requests_per_audit], 1):
            await conn.execute(
                "INSERT INTO request_items (id, tenant_id, engagement_id, request_list_id, "
                "description, title, audit_area, category_id, status, created_by, created_at, "
                "client_visible, requested_at) VALUES ($1, $2, $3, $4, $5, $5, $6, $7, "
                "'requested', $8, $9, true, $9) ON CONFLICT DO NOTHING",
                firm.id(f"request:{a}", position),
                firm.tenant,
                engagement,
                list_id,
                item.description,
                item.audit_area,
                firm.id(f"category:{a}", item.audit_area),
                partner,
                SETUP_AT,
            )
        return "request_list.created", "request_list", str(list_id)

    await _step(conn, firm, f"pbc:{a}", str(partner), pbc_rows, counts)

    for p in range(firm.shape.portal_people_per_audit):

        async def portal_row(p: int = p) -> tuple[str, str, str]:
            user = firm.id(f"portal:{a}", p)
            await conn.execute(
                "INSERT INTO users (id, idp_issuer, idp_subject, email, display_name) "
                "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
                user,
                ISSUER,
                f"fleet-{firm.n:03d}-client-{a:02d}-{p}",
                f"client{a:02d}.{p}.firm{firm.n:03d}@{SINK}",
                f"Client Person {a + 1:02d}.{p + 1}, {firm.name}",
            )
            await conn.execute(
                "INSERT INTO memberships (tenant_id, user_id, status, kind) "
                "VALUES ($1, $2, 'active', 'client') ON CONFLICT DO NOTHING",
                firm.tenant,
                user,
            )
            await conn.execute(
                "INSERT INTO client_access_grants (id, tenant_id, user_id, role, scope_kind, "
                "scope_id, granted_by, status) VALUES ($1, $2, $3, $4, 'engagement', $5, $6, "
                "'active') ON CONFLICT DO NOTHING",
                firm.id(f"grant:{a}", p),
                firm.tenant,
                user,
                "owner" if p == 0 else "contributor",
                engagement,
                partner,
            )
            return "client_access.granted", "engagement", str(engagement)

        await _step(conn, firm, f"portal:{a}:{p}", str(partner), portal_row, counts)


async def _flags(conn: asyncpg.Connection, firm: Firm, counts: Counts) -> None:
    """Each flag on once: a flag already on is not set again (no second audit row)."""
    on = {
        str(r["flag"])
        for r in await tenant_rows(
            conn,
            firm.tenant,
            "SELECT flag FROM feature_flag_states WHERE tenant_id = $1 AND value = 'true'",
            firm.tenant,
        )
    }
    for name in FLEET_FLAGS:
        if name in on:
            counts.skipped += 1
            continue
        await set_flag(firm.tenant, name, "true", LOADER, "load profile (Q-03-T044)")
        counts.written += 1


# --- the run ------------------------------------------------------------------------------------

# x25 and x100 are perf-stack loads only (QD-6; security review, DEC-455): with `--staging` their
# database host must be the perf stack's own, whose instance Q-03-T036 names `abacus-perf-...`.
# x1 may also seed staging's shared database (one firm, the runbook's rehearsal).
PERF_HOST_PREFIX: Final = "abacus-perf"
PERF_ONLY: Final = frozenset({"x25", "x100"})


def perf_guard(dsn: str, profile: str, *, staging: bool) -> None:
    """Refuse x25 and x100 on any hosted database but the perf stack's."""
    if not staging or profile not in PERF_ONLY:
        return
    host = urlsplit(dsn).hostname or ""
    if not host.startswith(PERF_HOST_PREFIX):
        raise LoadRefused(
            f"{profile} loads only the perf stack's own database (a host starting "
            f"{PERF_HOST_PREFIX!r}), never staging's shared one"
        )


@dataclass(frozen=True)
class FleetResult:
    firms: int
    written: int
    skipped: int


async def load(
    dsn: str, profile: str, *, staging: bool = False, shape: FirmShape | None = None
) -> FleetResult:
    guard(dsn, staging=staging)
    perf_guard(dsn, profile, staging=staging)
    firms = plan(profile, shape)
    counts = Counts()
    conn = await connect_db(dsn)
    try:
        for firm in firms:
            synthetic = await tenant_value(
                conn, firm.tenant, "SELECT synthetic FROM firms WHERE tenant_id = $1", firm.tenant
            )
            if synthetic is False:
                raise LoadRefused(f"{firm.tenant} exists and is not synthetic")
        for firm in firms:
            await _firm(conn, firm, counts)
            await _seats(conn, firm, counts)
            await _clients(conn, firm, counts)
            await _audits(conn, firm, counts)
            await _flags(conn, firm, counts)
    finally:
        await conn.close()
    return FleetResult(len(firms), counts.written, counts.skipped)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load N synthetic Brightwater-size firms.")
    parser.add_argument("--profile", required=True, choices=sorted(PROFILES))
    parser.add_argument("--staging", action="store_true")
    args = parser.parse_args(argv)
    owner = settings().migrations_database_url
    dsn = (
        owner.get_secret_value()
        if args.staging and owner is not None
        else os.environ.get(SUPERUSER_ENV, DEFAULT_SUPERUSER)
    )
    try:
        result = asyncio.run(load(dsn, args.profile, staging=args.staging))
    except LoadRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1
    print(
        f"{args.profile}: {result.firms} firm(s), {result.written} write(s), "
        f"{result.skipped} already loaded"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
