"""Load the Brightwater Hale scenario into a database (F-04-T13; F-04.15 to F-04.18).

Run: python -m abacus_tools.synthetic.scenarios.brightwater_hale.loader [--snapshot E0]
         [--holdout fairhaven_ebp] [--slice shell] [--staging] [--no-settle]
     (`make seed-demo SNAPSHOT=E0`; `make seed-staging` passes --staging)

The timeline (`scenario.build`) is replayed in order. Each event runs inside
`kernel.clock.frozen(event.at)` under a trace whose id derives from
`scenario:<SCENARIO_VERSION>:<event_id>` (`trace_hex`: `audit_events.trace_id` holds 32 hex digits
since migration 0011, so the scenario trace is hashed into one). An event whose trace already has
an audit row is skipped, so a second run writes nothing. After each event the barrier waits for
the tenant's outbox to drain (`--no-settle` skips it where no relay runs). At the end the firm's
demo clock runs in `offset` mode from the snapshot instant (identity's `set_demo_clock`).

Events go through the owning module's `api.py` where a service exists (`client_created`:
`organisations.create_client`). The firm, its offices, people and memberships have no service
yet: tenant provisioning (Q-01) and directory sync own them. Until those exist, the loader writes
them as the database owner in a transaction that carries the event's actor, tenant and business
time, together with the audit row the service would have written. That's the same bootstrap
`seed_dev` uses.

The audit-core content (F-04-T20: the 27 audits, the Northwind and Granite Peak PBC lists, their
client people and the E0 firm settings) is bootstrapped the same way, except a plan entity, which
goes through `organisations.client_with_entity`; see the section comment and DEC-144.

`--slice` adds slices to the default `audit_core`. The `shell` slice (P-01-T07: the training
sandbox and Grace's membership in it, job titles, Hannah's default office and notification
preferences) has no service yet either and is bootstrapped the same way. Its columns arrive with
P-01-T03 and P-01-T04, so the loader checks the schema first and refuses the whole load
(`SchemaPending`) rather than replaying part of it.

Refuses: `environment = production`; outside `--staging`, any database URL that is not loopback;
with `--staging`, an environment other than staging, a firm that is not synthetic, or a staging
deploy in flight (F-04.16, F-04.17).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg
from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

from abacus.kernel.clock import frozen, system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.identity.api import AuthContext, set_demo_clock
from abacus.modules.organisations.api import client_with_entity, create_client
from abacus_tools.fakes.identity import ISSUER
from abacus_tools.flags import set_flag
from abacus_tools.local.db_guard import violations
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import (
    BY_LABEL,
    PBC_LISTS,
    PORTAL_USERS,
    Audit,
    team_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import (
    created_at as audit_created_at,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.clients import Client, build_clients
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import snapshot
from abacus_tools.synthetic.scenarios.brightwater_hale.people import (
    FIRM_ROLES,
    SEATS,
    Seat,
    email_of,
    slug_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import (
    FIRM_ID,
    SCENARIO_VERSION,
    Scenario,
    build,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.shell import (
    SANDBOX_FIRM_ID,
    SANDBOX_FIRM_NAME,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SUPERUSER_ENV: Final = "ABACUS_LOCAL_SUPERUSER_DSN"
DEFAULT_SUPERUSER: Final = "postgresql://postgres:postgres@127.0.0.1:55432/abacus"
LOOPBACK: Final = frozenset({"127.0.0.1", "localhost", "::1"})
LOADER: Final = "scenario-loader"
SETTLE_SECONDS: Final = 120.0
# The flags `seed_dev` turns on for the local firm (F-04 §1: rollout only, renewed Dec 14 to 18).
FLAGS_ON: Final = (
    "retrieval.auto",
    "engagement_agent.enabled",
    "ledger.import",
    "uploads.processing",
    "upload_review.enabled",
    "matching.enabled",
    "ledger.gl_import",
    "guidance.drafting",
)
OFFICE_ZONES: Final = {
    "Chicago": "America/Chicago",
    "Denver": "America/Denver",
    "New York": "America/New_York",
}


class LoadRefused(RuntimeError):
    """The loader will not run here (production, a hosted database, a real firm, a deploy)."""


class SettleTimeout(RuntimeError):
    """The tenant's outbox did not drain within the barrier's timeout."""


class SchemaPending(RuntimeError):
    """A slice's event needs a column or table that a later migration adds."""


def trace_hex(event: Event, version: str = SCENARIO_VERSION) -> str:
    """The 32-hex trace id that stands for `scenario:<version>:<event_id>`."""
    return hashlib.sha256(event.trace_id(version).encode()).hexdigest()[:32]


def user_id_of(seat: Seat) -> UUID:
    return UUID(stable_id(f"user:{slug_of(seat.name)}"))


def office_id_of(name: str) -> UUID:
    return UUID(stable_id(f"office:{name}"))


def sandbox_office_id_of(name: str) -> UUID:
    """Office ids are global keys, so the sandbox's copies need their own."""
    return UUID(stable_id(f"sandbox:office:{name}"))


TENANT: Final = UUID(FIRM_ID)
SANDBOX: Final = UUID(SANDBOX_FIRM_ID)
# Events written inside the training sandbox's tenant (their audit rows live there too).
SANDBOX_KINDS: Final = frozenset(
    {
        "identity.sandbox_firm_created",
        "organisations.sandbox_office_created",
        "identity.sandbox_membership_added",
    }
)


def tenant_of(event: Event) -> UUID:
    return SANDBOX if event.kind in SANDBOX_KINDS else TENANT


_SEATS: Final = {s.initials: s for s in SEATS}
_CLIENTS: Final = {c.name: c for c in build_clients()}


@contextmanager
def _traced(event: Event) -> Generator[None]:
    """Run under the event's trace, so the unit of work stamps its audit rows with it."""
    context = SpanContext(
        trace_id=int(trace_hex(event), 16),
        span_id=int(hashlib.sha256(event.id.encode()).hexdigest()[:16], 16) or 1,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    with trace.use_span(NonRecordingSpan(context), end_on_exit=False):
        yield


def _actor(event: Event) -> tuple[str, str]:
    if event.actor == "system":
        return "system", LOADER
    return "human", str(user_id_of(_SEATS[event.actor]))


# --- guards ------------------------------------------------------------------------------------


def guard(dsn: str, *, staging: bool) -> None:
    """F-04.16 and F-04.17: never production; laptops load loopback only; staging loads
    staging only, and never while a deploy is in flight."""
    environment = settings().environment
    if environment == "production":
        raise LoadRefused("the scenario loader never runs in production")
    if staging:
        if environment != "staging":
            raise LoadRefused(f"--staging needs environment=staging, not {environment}")
        running = deploy_in_flight()
        if running is not None:
            raise LoadRefused(f"a staging deploy is in flight: {running}")
        return
    if urlsplit(dsn).hostname not in LOOPBACK or violations():
        raise LoadRefused("make seed-demo loads a database on this machine only")


def deploy_in_flight() -> str | None:
    """The deploy-staging run in progress, if any (working agreement: no load during a build)."""
    gh = shutil.which("gh")
    if gh is None:
        raise LoadRefused("cannot tell whether a staging deploy is in flight: no gh")
    try:
        found = subprocess.run(
            [
                gh,
                "run",
                "list",
                "--workflow",
                "deploy-staging",
                "--status",
                "in_progress",
                "--json",
                "databaseId,displayTitle",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise LoadRefused("cannot tell whether a staging deploy is in flight") from error
    runs: list[dict[str, object]] = json.loads(found.stdout or "[]")
    if not runs:
        return None
    first = runs[0]
    return f"run {first.get('databaseId')} ({first.get('displayTitle')})"


# --- bootstrap writes (no owning service yet) -------------------------------------------------


async def _bootstrap(
    conn: asyncpg.Connection, event: Event, write: Callable[[], Awaitable[tuple[str, str, str]]]
) -> None:
    """One owner transaction carrying the event's tenant, actor and business time, ending with
    the audit row the missing service would have written."""
    kind, actor = _actor(event)
    tenant = tenant_of(event)
    async with conn.transaction():
        for name, value in (
            ("app.tenant_id", str(tenant)),
            ("app.actor_kind", kind),
            ("app.actor_id", actor),
            ("app.now", event.at.isoformat()),
        ):
            await conn.execute("SELECT set_config($1, $2, true)", name, value)
        action, target_type, target_id = await write()
        await conn.execute(
            "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, "
            "target_id, trace_id) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            tenant,
            kind,
            actor,
            action,
            target_type,
            target_id,
            trace_hex(event),
        )


async def _firm_created(conn: asyncpg.Connection, scenario: Scenario, event: Event) -> None:
    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO firms (tenant_id, name, synthetic, region, time_zone) "
            "VALUES ($1, $2, true, 'us', 'America/Chicago') ON CONFLICT DO NOTHING",
            TENANT,
            scenario.firm_name,
        )
        return "firm.created", "firm", str(TENANT)

    await _bootstrap(conn, event, write)


async def _office_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    name = event.label.removeprefix("office:")

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO offices (id, tenant_id, name, time_zone) VALUES ($1, $2, $3, $4) "
            "ON CONFLICT DO NOTHING",
            office_id_of(name),
            TENANT,
            name,
            OFFICE_ZONES[name],
        )
        return "office.created", "office", str(office_id_of(name))

    await _bootstrap(conn, event, write)


async def _staff_member_added(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    seat = _SEATS[str(event.data["initials"])]
    user = user_id_of(seat)

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO users (id, idp_issuer, idp_subject, email, display_name) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            user,
            ISSUER,
            f"scenario-{slug_of(seat.name)}",
            email_of(seat.name),
            seat.name,
        )
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id, status, kind, firm_role, office_id, "
            "initials) VALUES ($1, $2, 'active', 'staff', $3, $4, $5) ON CONFLICT DO NOTHING",
            TENANT,
            user,
            FIRM_ROLES.get(seat.initials),
            office_id_of(seat.office),
            seat.initials,
        )
        return "membership.created", "user", str(user)

    await _bootstrap(conn, event, write)


# --- the shell slice (P-01-T07; bootstrap writes until identity and notifications own them) ----


async def _sandbox_firm_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO firms (tenant_id, name, synthetic, region, time_zone, "
            "sandbox_of_firm_id) "
            "VALUES ($1, $2, true, 'us', 'America/Chicago', $3) ON CONFLICT DO NOTHING",
            SANDBOX,
            SANDBOX_FIRM_NAME,
            TENANT,
        )
        return "firm.created", "firm", str(SANDBOX)

    await _bootstrap(conn, event, write)


async def _sandbox_office_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    name = str(event.data["office"])

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO offices (id, tenant_id, name, time_zone) VALUES ($1, $2, $3, $4) "
            "ON CONFLICT DO NOTHING",
            sandbox_office_id_of(name),
            SANDBOX,
            name,
            OFFICE_ZONES[name],
        )
        return "office.created", "office", str(sandbox_office_id_of(name))

    await _bootstrap(conn, event, write)


async def _sandbox_membership_added(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    seat = _SEATS[str(event.data["initials"])]
    user = user_id_of(seat)

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id, status, kind, firm_role, office_id, "
            "initials) VALUES ($1, $2, 'active', 'staff', $3, $4, $5) ON CONFLICT DO NOTHING",
            SANDBOX,
            user,
            FIRM_ROLES.get(seat.initials),
            sandbox_office_id_of(str(event.data["office"])),
            seat.initials,
        )
        return "membership.created", "user", str(user)

    await _bootstrap(conn, event, write)


async def _job_title_set(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    user = user_id_of(_SEATS[str(event.data["initials"])])

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "UPDATE memberships SET job_title = $3 WHERE tenant_id = $1 AND user_id = $2",
            TENANT,
            user,
            str(event.data["job_title"]),
        )
        return "membership.updated", "user", str(user)

    await _bootstrap(conn, event, write)


async def _default_office_set(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """AC 2.1.3: the person sets it, so `user_preference.updated` names them."""
    user = user_id_of(_SEATS[str(event.data["initials"])])

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "UPDATE memberships SET default_office_filter_id = $3 "
            "WHERE tenant_id = $1 AND user_id = $2",
            TENANT,
            user,
            office_id_of(str(event.data["office"])),
        )
        return "user_preference.updated", "user", str(user)

    await _bootstrap(conn, event, write)


async def _preference_set(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """AC 4.1.1: one kind's two toggles; `notification_preference.changed` (C16 §7) names them."""
    user = user_id_of(_SEATS[str(event.data["initials"])])

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO notification_preferences (tenant_id, user_id, kind, in_app, email, "
            "updated_at) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (tenant_id, user_id, kind) "
            "DO UPDATE SET in_app = excluded.in_app, email = excluded.email, "
            "updated_at = excluded.updated_at",
            TENANT,
            user,
            str(event.data["kind"]),
            bool(event.data["in_app"]),
            bool(event.data["email"]),
            event.at,
        )
        return "notification_preference.changed", "user", str(user)

    await _bootstrap(conn, event, write)


# What each shell event needs from a later migration: (table, column or None, the task).
SCHEMA_NEEDS: Final[dict[str, tuple[str, str | None, str]]] = {
    "identity.sandbox_firm_created": ("firms", "sandbox_of_firm_id", "P-01-T04"),
    "identity.job_title_set": ("memberships", "job_title", "P-01-T04"),
    "identity.default_office_set": ("memberships", "default_office_filter_id", "P-01-T04"),
    "notifications.preference_set": ("notification_preferences", None, "P-01-T03"),
}


async def preflight(conn: asyncpg.Connection, events: tuple[Event, ...]) -> None:
    """Refuse before writing anything when an event's column or table is not there yet."""
    for kind in sorted({e.kind for e in events} & SCHEMA_NEEDS.keys()):
        table, column, task = SCHEMA_NEEDS[kind]
        found = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE "
            "table_schema = current_schema() AND table_name = $1 "
            "AND ($2::text IS NULL OR column_name = $2))",
            table,
            column,
        )
        if not found:
            where = table if column is None else f"{table}.{column}"
            raise SchemaPending(f"{kind} needs {where}, which arrives with {task}")


# --- the audit-core content (F-04-T20; bootstrap writes) ----------------------------------------
# The 25 shallow audits sit at phases (Fieldwork, In review, Released) that the engagements
# service reaches only through G1 to G3 records (acceptance, independence, the signed letter) and
# the release and archive gates, none of which this slice models. So, like the firm and its
# people, each engagement is written as the database owner at its stage, in one transaction with
# its team and the audit row `engagement.created` (`seed_dev`'s bootstrap). The PBC lists, the
# portal people's client memberships and grants and the firm setting are written the same way:
# the publish, grant and setting services all want a signed-in person with fresh MFA.

_PBC: Final = {p.key: p for p in PBC_LISTS}
_PORTAL: Final = {u.name: u for u in PORTAL_USERS}


async def _client_id(conn: asyncpg.Connection, name: str) -> UUID:
    found = await conn.fetchval(
        "SELECT id FROM clients WHERE tenant_id = $1 AND name = $2", TENANT, name
    )
    if found is None:
        raise LookupError(f"no client {name!r}")
    return found


async def _entity_id(conn: asyncpg.Connection, client: UUID, name: str) -> UUID:
    found = await conn.fetchval(
        "SELECT id FROM client_entities WHERE tenant_id = $1 AND client_id = $2 AND name = $3",
        TENANT,
        client,
        name,
    )
    if found is None:
        raise LookupError(f"no entity {name!r}")
    return found


def engagement_id_of(audit: Audit) -> UUID:
    return UUID(audit.id)


async def _client_entity_added(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Through `organisations.api` under the engagement partner: a plan entity of its sponsor."""
    client = await _client_id(conn, str(event.client))
    kind, actor = _actor(event)
    async with uow(TenantContext(TENANT, kind, actor)) as tx:  # type: ignore[arg-type]  # "human" or "system"
        await client_with_entity(tx, TENANT, client, None, str(event.data["entity"]))


async def _engagement_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    audit = BY_LABEL[str(event.data["audit"])]
    engagement = engagement_id_of(audit)
    creator = user_id_of(_SEATS[audit.ep])
    office = office_id_of(_CLIENTS[audit.client].office)
    created = audit_created_at(audit)

    async def write() -> tuple[str, str, str]:
        client = await _client_id(conn, audit.client)
        entity = await _entity_id(conn, client, audit.entity_name)
        # The insert trigger adds the primary engagement entity and, for an attest type, the
        # assurance work item at `planning`.
        await conn.execute(
            "INSERT INTO engagements (id, tenant_id, client_id, client_entity_id, name, type, "
            "fiscal_period_start, fiscal_period_end, status, created_by, created_at, office_id) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) ON CONFLICT DO NOTHING",
            engagement,
            TENANT,
            client,
            entity,
            audit.name,
            audit.type,
            audit.period[0],
            audit.period[1],
            audit.status,
            creator,
            created,
            office,
        )
        await conn.execute(
            "UPDATE work_items SET due_on = $3, office_id = $4, created_at = $5, "
            "status = CASE WHEN $6 THEN 'archived' ELSE status END "
            "WHERE tenant_id = $1 AND engagement_id = $2 AND kind = 'assurance'",
            TENANT,
            engagement,
            audit.due_on,
            office,
            created,
            audit.status == "archived",
        )
        await conn.execute(
            "UPDATE assurance_work_items SET phase = $3 "
            "WHERE tenant_id = $1 AND engagement_id = $2",
            TENANT,
            engagement,
            audit.phase,
        )
        for initials, role in team_of(audit):
            await conn.execute(
                "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                TENANT,
                engagement,
                user_id_of(_SEATS[initials]),
                role,
            )
        return "engagement.created", "engagement", str(engagement)

    await _bootstrap(conn, event, write)


async def _portal_user_added(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """A client person: their user, a client membership and an engagement-scoped grant."""
    person = _PORTAL[str(event.data["user"])]
    user = UUID(person.id)
    audit = BY_LABEL[person.engagement]

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO users (id, idp_issuer, idp_subject, email, display_name) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            user,
            ISSUER,
            f"scenario-{person.slug}",
            person.email,
            person.name,
        )
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id, status, kind) "
            "VALUES ($1, $2, 'active', 'client') ON CONFLICT DO NOTHING",
            TENANT,
            user,
        )
        await conn.execute(
            "INSERT INTO client_access_grants (id, tenant_id, user_id, role, scope_kind, "
            "scope_id, granted_by, status) VALUES ($1, $2, $3, $4, 'engagement', $5, $6, "
            "'active') ON CONFLICT DO NOTHING",
            UUID(stable_id(f"grant:{person.slug}:{person.engagement}")),
            TENANT,
            user,
            person.role,
            engagement_id_of(audit),
            user_id_of(_SEATS[audit.ep]),
        )
        return "client_access.granted", "engagement", str(engagement_id_of(audit))

    await _bootstrap(conn, event, write)


async def _pbc_list_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """A PBC list with its categories and requests, published when the firm has sent it."""
    pbc = _PBC[str(event.data["list"])]
    audit = BY_LABEL[pbc.engagement]
    engagement = engagement_id_of(audit)
    by = user_id_of(_SEATS[audit.ep])
    list_id = UUID(pbc.id)

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO request_lists (id, tenant_id, engagement_id, created_at, kind, status, "
            "published_at, published_by) VALUES ($1, $2, $3, $4, 'pbc', $5, $6, $7) "
            "ON CONFLICT DO NOTHING",
            list_id,
            TENANT,
            engagement,
            pbc.created,
            "published" if pbc.published else "draft",
            pbc.created if pbc.published else None,
            by if pbc.published else None,
        )
        for position, name in enumerate(pbc.categories()):
            await conn.execute(
                "INSERT INTO request_categories (id, tenant_id, request_list_id, name, "
                "position, family) VALUES ($1, $2, $3, $4, $5, 'audit_area') "
                "ON CONFLICT DO NOTHING",
                UUID(pbc.category_id(name)),
                TENANT,
                list_id,
                name,
                position,
            )
        for position, request in enumerate(pbc.requests, 1):
            assignee = request.assignee
            visible = request.status != "draft"
            await conn.execute(
                "INSERT INTO request_items (id, tenant_id, engagement_id, request_list_id, "
                "description, title, audit_area, category_id, status, created_by, created_at, "
                "client_visible, client_assignee_user_id, due_on, requested_at) VALUES ($1, $2, "
                "$3, $4, $5, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) ON CONFLICT DO NOTHING",
                UUID(pbc.request_id(position)),
                TENANT,
                engagement,
                list_id,
                request.title,
                request.category,
                UUID(pbc.category_id(request.category)),
                request.status,
                by,
                pbc.created,
                visible,
                UUID(assignee.id) if assignee is not None else None,
                request.due_on,
                pbc.created if visible else None,
            )
        return "request_list.created", "request_list", str(list_id)

    await _bootstrap(conn, event, write)


async def _firm_setting_set(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    user = user_id_of(_SEATS[event.actor])

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO firm_setting_values (tenant_id, key, value, set_by, set_at) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            TENANT,
            str(event.data["key"]),
            bool(event.data["value"]),
            user,
            event.at,
        )
        return "firm_setting.set", "firm", str(TENANT)

    await _bootstrap(conn, event, write)


# --- service-backed events ---------------------------------------------------------------------


async def _client_created(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    """Through `organisations.api` under the relationship partner, as a person would."""
    client: Client = _CLIENTS[str(event.client)]
    kind, actor = _actor(event)
    async with uow(TenantContext(TENANT, kind, actor)) as tx:  # type: ignore[arg-type]  # "human" or "system"
        await create_client(tx, TENANT, client.name, client.entities[0])


Handler = Callable[[asyncpg.Connection, Scenario, Event], Awaitable[None]]
HANDLERS: Final[dict[str, Handler]] = {
    "identity.firm_created": _firm_created,
    "organisations.office_created": _office_created,
    "identity.staff_member_added": _staff_member_added,
    "organisations.client_created": _client_created,
    # F-04-T20: plan entities, engagements, their client people, PBC lists, firm settings.
    "organisations.client_entity_added": _client_entity_added,
    "engagements.engagement_created": _engagement_created,
    "identity.portal_user_added": _portal_user_added,
    "requests.pbc_list_created": _pbc_list_created,
    "identity.firm_setting_set": _firm_setting_set,
    # The shell slice, after audit_core: the sandbox firm before its offices and membership.
    "identity.sandbox_firm_created": _sandbox_firm_created,
    "organisations.sandbox_office_created": _sandbox_office_created,
    "identity.sandbox_membership_added": _sandbox_membership_added,
    "identity.job_title_set": _job_title_set,
    "identity.default_office_set": _default_office_set,
    "notifications.preference_set": _preference_set,
}
# Within one instant the timeline orders by label; the loader orders by dependency first.
_ORDER: Final = {kind: n for n, kind in enumerate(HANDLERS)}


def replay_order(events: tuple[Event, ...]) -> list[Event]:
    return sorted(events, key=lambda e: (e.at, _ORDER.get(e.kind, len(_ORDER)), e.label))


# --- the run -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadResult:
    replayed: int
    skipped: int


async def _already_loaded(conn: asyncpg.Connection, event: Event) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM audit_events WHERE tenant_id = $1 AND trace_id = $2)",
            tenant_of(event),
            trace_hex(event),
        )
    )


async def settle(conn: asyncpg.Connection, timeout: float = SETTLE_SECONDS) -> None:
    """The barrier: the tenant's outbox is empty (each async consequence has been handed on)."""
    deadline = system_now().timestamp() + timeout
    while await conn.fetchval(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND published_at IS NULL", TENANT
    ):
        if system_now().timestamp() > deadline:
            raise SettleTimeout(f"the outbox did not drain within {timeout:.0f}s")
        await asyncio.sleep(0.25)


async def load(
    dsn: str,
    at: str = "E0",
    holdouts: tuple[str, ...] = (),
    *,
    slices: tuple[str, ...] = (),
    staging: bool = False,
    wait: bool = True,
) -> LoadResult:
    guard(dsn, staging=staging)
    scenario = build(at, holdouts, ("audit_core", *slices))
    replayed = skipped = 0
    conn = await asyncpg.connect(dsn)
    try:
        synthetic = await conn.fetchval("SELECT synthetic FROM firms WHERE tenant_id = $1", TENANT)
        if synthetic is False:
            raise LoadRefused("the scenario firm exists and is not synthetic")
        await preflight(conn, scenario.events)
        for event in replay_order(scenario.events):
            handler = HANDLERS.get(event.kind)
            if handler is None:
                raise NotImplementedError(f"no loader handler for {event.kind}")
            if await _already_loaded(conn, event):
                skipped += 1
                continue
            with frozen(event.at), _traced(event):
                await handler(conn, scenario, event)
            replayed += 1
            if wait:
                await settle(conn)
    finally:
        await conn.close()
    if replayed:
        await _finish(scenario.snapshot.at)
    return LoadResult(replayed, skipped)


async def _finish(anchor: datetime) -> None:
    """Flags on for the firm, then the clock runs from the snapshot (offset mode)."""
    for name in FLAGS_ON:
        await set_flag(TENANT, name, "true", LOADER, "Brightwater Hale scenario")
    admin = next(s for s in SEATS if FIRM_ROLES.get(s.initials) == "firm_admin")
    user = user_id_of(admin)
    ctx = AuthContext(
        TenantContext(TENANT, "human", str(user)), user, UUID(int=0), "firm_admin", system_now()
    )
    await set_demo_clock(ctx, "offset", anchor)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the Brightwater Hale scenario.")
    parser.add_argument("--snapshot", default="E0")
    parser.add_argument("--holdout", action="append", default=[])
    parser.add_argument("--slice", action="append", default=[], help="added to audit_core")
    parser.add_argument("--staging", action="store_true")
    parser.add_argument("--no-settle", action="store_true")
    args = parser.parse_args(argv)
    snapshot(args.snapshot)  # an unknown name fails before anything connects
    owner = settings().migrations_database_url
    dsn = (
        owner.get_secret_value()
        if args.staging and owner is not None
        else os.environ.get(SUPERUSER_ENV, DEFAULT_SUPERUSER)
    )
    try:
        result = asyncio.run(
            load(
                dsn,
                args.snapshot,
                tuple(args.holdout),
                slices=tuple(args.slice),
                staging=args.staging,
                wait=not args.no_settle,
            )
        )
    except (LoadRefused, SchemaPending) as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1
    print(
        f"Brightwater Hale {SCENARIO_VERSION} at {args.snapshot}: "
        f"{result.replayed} event(s) replayed, {result.skipped} already loaded"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
