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

The `binders` slice (P-06-T08: the 241 TY2025 binders on 224 return work items over 214 tax
engagements, Copperleaf's close intake, and the client people binders name) is opt-in
(`--slice binders`) and bootstrapped the same way; see DEC-146.

The `portal` slice (P-08-T14: Brightwater Hale's portal branding and host, the portal people and
their grants, Sam Ortiz's pending invitation) is opt-in (`--slice portal`, which brings `binders`
with it; `make seed-staging` passes it). Branding and the host go through `portal.api`; the host is
`brightwaterhale.<portal_base_domain>` from settings, left out on a laptop without that setting and
refused on `--staging` without it. People, grants and the invitation are bootstrapped; see DEC-213.

The `people` slice (G-01-T06: the seat total, the four teams and each seat holder's template,
level, title, team, service line and seasonal end) is opt-in (`--slice people`). The seats and
profiles go through identity's services in a unit of work; teams are bootstrapped like offices
until G-01-T08 gives them a service.

The `compliance` slice (Q-02-T39: FIL-02a's retention policies, FIL-02b's two holds taken to
Active, INC-2026-005, and the two rollout flags they sit behind) is opt-in (`--slice compliance`,
which brings `people`) and goes through `evidence.api` and `platform.api` as the people the
handoff names, with fresh MFA at the event's time; see the section comment and DEC-363.

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
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Final, Literal, cast
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg
from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

from abacus.kernel.clock import frozen, system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.assurance.api import record_phase, update_profile
from abacus.modules.engagements.api import (
    NewCondition,
    acceptance_record,
    add_flag,
    add_to_team,
    answer_independence,
    approve_team,
    assign_eqr,
    assurance_item,
    assurance_item_id,
    change_team_role,
    create_draft,
    decide_acceptance,
    remove_from_team,
    send_to_partner,
    start_acceptance,
    team_approval,
    update_answers,
)
from abacus.modules.evidence.api import (
    HoldScope,
    PolicyChange,
    legal_hold_activate,
    legal_hold_apply_batch,
    place_hold,
    set_policy,
)
from abacus.modules.identity.api import (
    AuthContext,
    MemberProfile,
    provision_setting,
    set_demo_clock,
    set_member_profile,
)
from abacus.modules.organisations.api import (
    NewClient,
    RoleAsked,
    clear_conflict_result,
    client_with_entity,
    create_client,
    create_contact,
    run_conflict_check,
)
from abacus.modules.platform.api import IncidentFacts, record_incident
from abacus.modules.portal.api import (
    BrandingSlots,
    activate_portal_host,
    add_portal_host,
    set_branding,
)
from abacus_tools.db_connect import connect as connect_db
from abacus_tools.fakes.identity import ISSUER
from abacus_tools.flags import set_flag
from abacus_tools.local.db_guard import violations
from abacus_tools.synthetic.scenarios.brightwater_hale.acceptance import (
    CONTACTS,
    DRAFTS,
    THORNBURY_ANSWERS,
    THORNBURY_FLAGS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.acceptance import (
    NEEDS as ACCEPTANCE_NEEDS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.acceptance import (
    SLICE as ACCEPTANCE_SLICE,
)
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
from abacus_tools.synthetic.scenarios.brightwater_hale.binders import (
    BINDER_BY_LABEL,
    CLOSE_DUE,
    CLOSE_PERIOD,
    CLOSE_PREPARER,
    COPPERLEAF,
    COPPERLEAF_CLOSE_ENGAGEMENT,
    COPPERLEAF_CLOSE_ITEM,
    ENGAGEMENT_BY_LABEL,
    RETURN_BY_LABEL,
    TAX_YEAR,
    Binder,
    person_email,
    person_id,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.clients import (
    Client,
    build_clients,
    entity_id_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.compliance import (
    NEEDS as COMPLIANCE_NEEDS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.compliance import (
    SLICE as COMPLIANCE_SLICE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import snapshot
from abacus_tools.synthetic.scenarios.brightwater_hale.firm_people import (
    SERVICE_LINE_OF_TEAM,
    Level,
    TeamName,
    Template,
    access_ends_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.people import (
    FIRM_ROLES,
    SEATS,
    Seat,
    email_of,
    slug_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.portal import (
    HOST_LABEL,
    INVITATION_BY_NAME,
    PERSON_BY_NAME,
    PortalPerson,
    delegated_requests,
    work_item_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.portal import NEEDS as PORTAL_NEEDS
from abacus_tools.synthetic.scenarios.brightwater_hale.portal import SLICE as PORTAL_SLICE
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
    "agents.client_data_optin",
    "audits.cockpit",  # A-01: "the local seed turns it on for Brightwater Hale"
)
OFFICE_ZONES: Final = {
    "Chicago": "America/Chicago",
    "Denver": "America/Denver",
    "New York": "America/New_York",
}
# G-01-T08 (AC7.1): ADM-03a's office codes; Chicago is the HQ.
OFFICE_CODES: Final = {"Chicago": "CHI", "Denver": "DEN", "New York": "NYC"}
HQ_OFFICE: Final = "Chicago"


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


@asynccontextmanager
async def as_tenant(conn: asyncpg.Connection, tenant: UUID) -> AsyncGenerator[None]:
    """A transaction that sees `tenant`'s rows. The owner role does not bypass row-level security
    (`migrations/bootstrap.sql`), so a read outside one sees nothing on a hosted database even
    where a laptop's superuser sees everything (security review, DEC-455)."""
    async with conn.transaction():
        await conn.execute("SELECT set_config($1, $2, true)", "app.tenant_id", str(tenant))
        yield


async def tenant_value(conn: asyncpg.Connection, tenant: UUID, sql: str, *args: object) -> object:
    """One value read as `tenant` (`as_tenant`)."""
    async with as_tenant(conn, tenant):
        return await conn.fetchval(sql, *args)


async def tenant_rows(
    conn: asyncpg.Connection, tenant: UUID, sql: str, *args: object
) -> list[asyncpg.Record]:
    """Rows read as `tenant` (`as_tenant`)."""
    async with as_tenant(conn, tenant):
        return list(await conn.fetch(sql, *args))


Write = Callable[[], Awaitable[tuple[str, str, str]]]


async def bootstrap_write(
    conn: asyncpg.Connection,
    *,
    tenant: UUID,
    actor_kind: str,
    actor_id: str,
    at: datetime,
    trace: str,
    write: Write,
) -> None:
    """One owner transaction carrying the tenant, actor and business time, ending with the audit
    row the missing service would have written (the scenario loader's and the load profiles'
    bootstrap, `synthetic.fleet`)."""
    async with conn.transaction():
        for name, value in (
            ("app.tenant_id", str(tenant)),
            ("app.actor_kind", actor_kind),
            ("app.actor_id", actor_id),
            ("app.now", at.isoformat()),
        ):
            await conn.execute("SELECT set_config($1, $2, true)", name, value)
        action, target_type, target_id = await write()
        await conn.execute(
            "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, "
            "target_id, trace_id) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            tenant,
            actor_kind,
            actor_id,
            action,
            target_type,
            target_id,
            trace,
        )


async def _bootstrap(conn: asyncpg.Connection, event: Event, write: Write) -> None:
    """The event's bootstrap write: its tenant, actor, business time and scenario trace."""
    kind, actor = _actor(event)
    await bootstrap_write(
        conn,
        tenant=tenant_of(event),
        actor_kind=kind,
        actor_id=actor,
        at=event.at,
        trace=trace_hex(event),
        write=write,
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
            "INSERT INTO offices (id, tenant_id, name, time_zone, code, is_hq) "
            "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING",
            office_id_of(name),
            TENANT,
            name,
            OFFICE_ZONES[name],
            OFFICE_CODES[name],
            name == HQ_OFFICE,
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
        # G-01-T06: one microsecond per ADM-02 row, so "in the order the firm added them" is the
        # screen's order (the business clock is frozen at the setup instant for all 46).
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id, status, kind, firm_role, office_id, "
            "initials, created_at) VALUES ($1, $2, 'active', 'staff', $3, $4, $5, $6) "
            "ON CONFLICT DO NOTHING",
            TENANT,
            user,
            FIRM_ROLES.get(seat.initials),
            office_id_of(seat.office),
            seat.initials,
            event.at + timedelta(microseconds=seat.n),
        )
        return "membership.created", "user", str(user)

    await _bootstrap(conn, event, write)


# --- the people slice (G-01-T06) --------------------------------------------------------------
# The seat total and each profile go through identity (`provision_setting`, `set_member_profile`)
# in a unit of work under the event's actor. Teams have no service until G-01-T08, so their rows
# are bootstrapped like offices.


def team_id_of(name: str) -> UUID:
    return UUID(stable_id(f"team:{name}"))


async def _seats_provisioned(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    kind, actor = _actor(event)
    async with uow(TenantContext(TENANT, kind, actor)) as tx:  # type: ignore[arg-type]  # "human" or "system"
        await provision_setting(
            tx, TENANT, "plan", "seats", int(str(event.data["seats"])), UUID(int=0)
        )


async def _team_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    name = str(event.data["name"])

    async def write() -> tuple[str, str, str]:
        line = SERVICE_LINE_OF_TEAM.get(cast(TeamName, name))
        # G-01-T08: a service line's team carries its line; Firm operations is a practice group.
        await conn.execute(
            "INSERT INTO teams (id, tenant_id, name, kind, service_line) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            team_id_of(name),
            TENANT,
            name,
            "practice_group" if line is None else "service_line",
            line,
        )
        return "team.created", "team", str(team_id_of(name))

    await _bootstrap(conn, event, write)


async def _member_profile_set(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    seat = _SEATS[str(event.data["initials"])]
    team = cast(TeamName, event.data["team"])
    line = SERVICE_LINE_OF_TEAM[team]
    profile = MemberProfile(
        role_template=cast(Template, event.data["template"]),
        level=cast(Level, event.data["level"]),
        title=str(event.data["title"]),
        service_lines=[] if line is None else [line],
        access_ends_on=access_ends_of(seat),
        team_ids=[team_id_of(team)],
    )
    kind, actor = _actor(event)
    async with uow(TenantContext(TENANT, kind, actor)) as tx:  # type: ignore[arg-type]  # "human" or "system"
        await set_member_profile(tx, TENANT, user_id_of(seat), profile)


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
    entity = str(event.data["entity"])
    # F-04-T31: the entity id the fixtures use (`entityIdOf` in the TS seed).
    entity_id = UUID(entity_id_of(_CLIENTS[str(event.client)].slug, entity))
    kind, actor = _actor(event)
    async with uow(TenantContext(TENANT, kind, actor)) as tx:  # type: ignore[arg-type]  # "human" or "system"
        await client_with_entity(tx, TENANT, client, None, entity, new_entity_id=entity_id)


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
            "delivered" if audit.status == "archived" else audit.status,
            creator,
            created,
            office,
        )
        # A-01-T07 (DEC-310): the phase is never written here; it moves through A-01's services
        # (`assurance.phase_*` events), and an archived engagement is archived after them.
        await conn.execute(
            "UPDATE work_items SET due_on = $3, office_id = $4, created_at = $5 "
            "WHERE tenant_id = $1 AND engagement_id = $2 AND kind = 'assurance'",
            TENANT,
            engagement,
            audit.due_on,
            office,
            created,
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


# --- the binders slice (P-06-T08; bootstrap writes) ----------------------------------------------
# The binder service creates Drafts for a signed-in person and moves them one step at a time
# (publish behind G3 and a 10-second Undo grant, mark-done by a client principal, close on a C1
# status event). The slice's binders stand at their E0 states, on return work items no tax
# service opens yet (T-02), so the loader writes them as the owner with their audit rows.

_FELD_TEAM: Final = (
    ("DR", "engagement_partner"),
    ("SI", "manager"),
    ("OB", "senior"),
    ("KO", "staff"),
)
_FELD_OPENED: Final = datetime(2026, 2, 2, 15, tzinfo=UTC)  # audits.ts: onDate("2026-02-02")
_FELD_DUE: Final = date(2026, 10, 15)


async def _client_person_added(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """A client's person a binder names ("Marked done by"): a client user, no grant yet."""
    name = str(event.data["person"])
    user = UUID(person_id(name))

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO users (id, idp_issuer, idp_subject, email, display_name) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            user,
            ISSUER,
            f"scenario-{slug_of(name).strip('-')}",
            person_email(name),
            name,
        )
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id, status, kind) "
            "VALUES ($1, $2, 'active', 'client') ON CONFLICT DO NOTHING",
            TENANT,
            user,
        )
        return "membership.created", "user", str(user)

    await _bootstrap(conn, event, write)


async def _engagement_row(
    conn: asyncpg.Connection,
    engagement: UUID,
    client_name: str,
    entity_name: str,
    *,
    name: str,
    type_: str,
    period: tuple[date, date],
    creator: UUID,
    created: datetime | None,
) -> tuple[UUID, UUID]:
    client = await _client_id(conn, client_name)
    entity = await _entity_id(conn, client, entity_name)
    await conn.execute(
        "INSERT INTO engagements (id, tenant_id, client_id, client_entity_id, name, type, "
        "fiscal_period_start, fiscal_period_end, status, created_by, created_at, office_id) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active', $9, coalesce($10, abacus_now()), "
        "$11) ON CONFLICT DO NOTHING",
        engagement,
        TENANT,
        client,
        entity,
        name,
        type_,
        period[0],
        period[1],
        creator,
        created,
        office_id_of(_CLIENTS[client_name].office),
    )
    return client, entity


async def _tax_engagement_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """A TY2025 tax engagement with its return work items (`tax_return`, with the subtype)."""
    found = ENGAGEMENT_BY_LABEL[str(event.data["engagement"])]
    returns = [RETURN_BY_LABEL[label] for label in found.returns]
    engagement = UUID(found.id)
    creator = user_id_of(_SEATS[found.partner])
    feld = found.label == "jonah-and-claire-feld"

    async def write() -> tuple[str, str, str]:
        client, entity = await _engagement_row(
            conn,
            engagement,
            found.client,
            found.entity,
            name=found.name(returns[0]),
            type_="tax_compliance",
            period=returns[0].period,
            creator=creator,
            created=_FELD_OPENED if feld else None,
        )
        for ret in returns:
            await conn.execute(
                "INSERT INTO work_items (id, tenant_id, engagement_id, client_id, "
                "client_entity_id, kind, name, period_start, period_end, office_id, due_on, "
                "created_by) VALUES ($1, $2, $3, $4, $5, 'tax_return', $6, $7, $8, $9, $10, $11) "
                "ON CONFLICT DO NOTHING",
                UUID(ret.id),
                TENANT,
                engagement,
                client,
                entity,
                ret.name,
                ret.period[0],
                ret.period[1],
                office_id_of(ret.office),
                _FELD_DUE if feld else None,
                creator,
            )
            await conn.execute(
                "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, "
                "client_entity_id, form, tax_year) VALUES ($1, $2, $3, $4, $5, $6) "
                "ON CONFLICT DO NOTHING",
                TENANT,
                UUID(ret.id),
                engagement,
                entity,
                ret.code,
                TAX_YEAR,
            )
        for initials, role in _FELD_TEAM if feld else ():
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


async def _close_engagement_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Copperleaf's 2026 Close and its August close (CLS-03: preparer RM, reviewer PR)."""
    engagement = UUID(COPPERLEAF_CLOSE_ENGAGEMENT)
    item = UUID(COPPERLEAF_CLOSE_ITEM)
    creator = user_id_of(_SEATS[event.actor])
    copperleaf = _CLIENTS[COPPERLEAF]

    async def write() -> tuple[str, str, str]:
        client, entity = await _engagement_row(
            conn,
            engagement,
            COPPERLEAF,
            copperleaf.entities[0],
            name="2026 Close",
            type_="cas_monthly_close",
            period=(date(2026, 1, 1), date(2026, 12, 31)),
            creator=creator,
            created=None,
        )
        await conn.execute(
            "INSERT INTO work_items (id, tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, period_start, period_end, office_id, due_on, created_by) VALUES ($1, $2, "
            "$3, $4, $5, 'close', 'August 2026 Close', $6, $7, $8, $9, $10) "
            "ON CONFLICT DO NOTHING",
            item,
            TENANT,
            engagement,
            client,
            entity,
            date(2026, 8, 1),
            date(2026, 8, 31),
            office_id_of(copperleaf.office),
            CLOSE_DUE,
            creator,
        )
        await conn.execute(
            "INSERT INTO closes (tenant_id, work_item_id, engagement_id, period) "
            "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
            TENANT,
            item,
            engagement,
            CLOSE_PERIOD,
        )
        for initials, role in ((event.actor, "engagement_partner"), (CLOSE_PREPARER, "senior")):
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


def _binder_home(binder: Binder) -> tuple[UUID, UUID]:
    """(engagement, work item) the binder hangs on."""
    if binder.kind == "close_intake":
        return UUID(COPPERLEAF_CLOSE_ENGAGEMENT), UUID(COPPERLEAF_CLOSE_ITEM)
    ret = RETURN_BY_LABEL[binder.ret]
    return UUID(ENGAGEMENT_BY_LABEL[ret.engagement].id), UUID(ret.id)


async def _binder_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """A binder at its E0 state, its categories and requests, and its activity projection."""
    binder = BINDER_BY_LABEL[str(event.data["binder"])]
    engagement, item = _binder_home(binder)
    actor = user_id_of(_SEATS[event.actor])
    named = binder.named
    done = named.marked_done if named is not None else None
    published = binder.published
    binder_id = UUID(binder.id)

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO request_lists (id, tenant_id, engagement_id, work_item_id, name, kind, "
            "part, status, published_at, published_by, marked_done_at, marked_done_by, "
            "closed_at, created_from) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, "
            "$12, $13, $14) ON CONFLICT DO NOTHING",
            binder_id,
            TENANT,
            engagement,
            item,
            binder.name,
            binder.kind,
            binder.part,
            binder.status,
            published[1] if published is not None else None,
            user_id_of(_SEATS[published[0]]) if published is not None else None,
            done[1] if done is not None else None,
            UUID(person_id(done[0])) if done is not None else None,
            named.closed_at if named is not None else None,
            binder.created_from,
        )
        for position, (name, glyph) in enumerate(binder.categories):
            await conn.execute(
                "INSERT INTO request_categories (id, tenant_id, request_list_id, name, "
                "position, glyph, family) VALUES ($1, $2, $3, $4, $5, $6, $7) "
                "ON CONFLICT DO NOTHING",
                UUID(binder.category_id(name)),
                TENANT,
                binder_id,
                name,
                position,
                glyph,
                binder.family,
            )
        for position, request in enumerate(binder.requests, 1):
            incorporated = request.incorporation == "incorporated"
            await conn.execute(
                "INSERT INTO request_items (id, tenant_id, engagement_id, request_list_id, "
                "description, title, audit_area, category_id, status, kind, created_by, "
                "created_at, client_visible, due_on, requested_at, incorporation_state, "
                "incorporated_by, incorporated_at) VALUES ($1, $2, $3, $4, $5, $5, $6, $7, $8, "
                "$9, $10, $11, true, $12, $11, $13, $14, $15) ON CONFLICT DO NOTHING",
                UUID(binder.request_id(position)),
                TENANT,
                engagement,
                binder_id,
                request.title,
                request.category,
                UUID(binder.category_id(request.category)),
                request.status,
                request.kind,
                actor,
                request.created,
                request.due_on,
                request.incorporation,
                actor if incorporated else None,
                request.received if incorporated else None,
            )
        open_count = sum(1 for r in binder.requests if r.status != "received")
        await conn.execute(
            "INSERT INTO binder_activity (tenant_id, binder_id, work_item_id, status, "
            "open_count, last_client_activity_at) VALUES ($1, $2, $3, $4, $5, $6) "
            "ON CONFLICT DO NOTHING",
            TENANT,
            binder_id,
            item,
            binder.status,
            open_count,
            named.last_activity if named is not None else None,
        )
        return "binder.created", "binder", str(binder_id)

    await _bootstrap(conn, event, write)


# --- the portal slice (P-08-T14; DEC-213) --------------------------------------------------------
# Branding and the host have services (`portal.api`), called in a unit of work under Grace
# Holloway. Client users, memberships and grants have none a loader can call (granting wants a
# signed-in person with fresh MFA, and a client-wide grant the firm's administrator), so they are
# bootstrapped like `_portal_user_added`, with the `granted` history row the service writes. The
# invitation is bootstrapped too: `create_invitation` would mint a token and email it.

SLICE_NEEDS: Final[dict[str, tuple[str, ...]]] = {
    PORTAL_SLICE: PORTAL_NEEDS,
    COMPLIANCE_SLICE: COMPLIANCE_NEEDS,
    ACCEPTANCE_SLICE: ACCEPTANCE_NEEDS,
}


def expand_slices(slices: tuple[str, ...]) -> tuple[str, ...]:
    """The slices with the ones they need first, each once, in the order asked."""
    out: list[str] = []
    for name in slices:
        for needed in (*SLICE_NEEDS.get(name, ()), name):
            if needed not in out:
                out.append(needed)
    return tuple(out)


def portal_host(label: str) -> str | None:
    """`<label>.<portal_base_domain>`, or None where the environment sets no portal domain."""
    domain = settings().portal_base_domain
    return None if domain is None else f"{label}.{domain}"


async def _branding_set(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    data = event.data
    kind, actor = _actor(event)
    slots = BrandingSlots(
        display_name=str(data["display_name"]),
        address_line=str(data["address_line"]),
        support_contact_name=str(data["support_contact_name"]),
        secured_footer=bool(data["secured_footer"]),
    )
    async with uow(TenantContext(TENANT, kind, actor)) as tx:  # type: ignore[arg-type]  # "human" or "system"
        await set_branding(tx, TENANT, slots, UUID(actor))


async def _host_added(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    """The firm's default host, active: provisioning's DNS and certificate are the edge's."""
    host = portal_host(str(event.data["label"]))
    if host is None:
        raise LoadRefused("the portal host needs portal_base_domain")
    kind, actor = _actor(event)
    async with uow(TenantContext(TENANT, kind, actor)) as tx:  # type: ignore[arg-type]  # "human" or "system"
        await add_portal_host(tx, TENANT, host, "default")
        await activate_portal_host(tx, TENANT, host)


async def _portal_scope(
    conn: asyncpg.Connection, person: PortalPerson
) -> tuple[UUID, tuple[str, str]]:
    """The grant's scope id and the audit target the grant service names (firm or engagement)."""
    if person.scope_kind == "work_item":
        item = UUID(work_item_of(person))
        engagement = await conn.fetchval(
            "SELECT engagement_id FROM work_items WHERE tenant_id = $1 AND id = $2", TENANT, item
        )
        if engagement is None:
            raise LookupError(f"no work item for {person.scope!r}")
        return item, ("engagement", str(engagement))
    client = await _client_id(conn, person.client)
    if person.scope_kind == "client":
        return client, ("firm", str(TENANT))
    return await _entity_id(conn, client, person.scope), ("firm", str(TENANT))


async def _portal_person_added(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """A portal person: their user, a client membership and their grant (F-03-T26)."""
    person = PERSON_BY_NAME[str(event.data["person"])]
    user = UUID(person.id)
    grant = UUID(person.grant_id)
    by = user_id_of(_SEATS[event.actor])

    async def write() -> tuple[str, str, str]:
        scope, (target_type, target_id) = await _portal_scope(conn, person)
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
        inserted = await conn.fetchval(
            "INSERT INTO client_access_grants (id, tenant_id, user_id, role, scope_kind, "
            "scope_id, granted_by, status, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7, "
            "'active', $8) ON CONFLICT DO NOTHING RETURNING id",
            grant,
            TENANT,
            user,
            person.role,
            person.scope_kind,
            scope,
            by,
            event.at,
        )
        if inserted is not None:
            await conn.execute(
                "INSERT INTO client_access_events (tenant_id, grant_id, event, by_user_id, at) "
                "VALUES ($1, $2, 'granted', $3, $4)",
                TENANT,
                grant,
                by,
                event.at,
            )
        return "client_access.granted", target_type, target_id

    await _bootstrap(conn, event, write)


async def _client_invitation_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """A pending invitation as the table holds it (no token: nothing is emailed), with its v2
    fields (P-08-T18): the invitee's third-party contact, the kind, terms and grant template."""
    invitation = INVITATION_BY_NAME[str(event.data["invitee"])]
    engagement = engagement_id_of(BY_LABEL[invitation.engagement])
    by = user_id_of(_SEATS[event.actor])
    invitation_id = UUID(invitation.id)
    contact_id = UUID(invitation.contact_id)
    template = {
        "role": invitation.grant_role,
        "scope_kind": "request_item",
        "scope_ids": list(delegated_requests(invitation)),
    }

    async def write() -> tuple[str, str, str]:
        client = await conn.fetchval(
            "SELECT client_id FROM engagements WHERE tenant_id = $1 AND id = $2",
            TENANT,
            engagement,
        )
        await conn.execute(
            "INSERT INTO contacts (id, tenant_id, client_id, display_name, email, title, "
            "organisation_name, contact_kind, portal_state, created_at) VALUES ($1, $2, $3, $4, "
            "$5, $6, $7, 'third_party', 'invited', $8) ON CONFLICT DO NOTHING",
            contact_id,
            TENANT,
            client,
            invitation.name,
            invitation.email,
            invitation.title,
            invitation.org,
            event.at,
        )
        await conn.execute(
            "INSERT INTO client_invitations (id, tenant_id, engagement_id, email, role, "
            "invited_by, created_at, expires_at, kind, contact_id, grant_template, "
            "terms_version) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12) "
            "ON CONFLICT DO NOTHING",
            invitation_id,
            TENANT,
            engagement,
            invitation.email,
            invitation.role,
            by,
            event.at,
            event.at + timedelta(days=invitation.days),
            invitation.kind,
            contact_id,
            json.dumps(template),
            invitation.terms_version,
        )
        return "client_invitation.created", "client_invitation", str(invitation_id)

    await _bootstrap(conn, event, write)


# --- service-backed events ---------------------------------------------------------------------


async def _client_created(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    """Through `organisations.api` under the relationship partner, as a person would."""
    client: Client = _CLIENTS[str(event.client)]
    kind, actor = _actor(event)
    # F-04-T31: the ids the fixtures use (`client:<slug>` and `entityIdOf` in the TS seed), so the
    # exported fixtures and the TS seed name the same client.
    ids = NewClient(
        UUID(stable_id(f"client:{client.slug}")),
        UUID(entity_id_of(client.slug, client.entities[0])),
    )
    async with uow(TenantContext(TENANT, kind, actor)) as tx:  # type: ignore[arg-type]  # "human" or "system"
        await create_client(tx, TENANT, client.name, client.entities[0], ids=ids)


# --- A-01-T07: the assurance slice through A-01's services (DEC-310) ----------------------------


def _partner_context(audit: Audit, at: datetime) -> AuthContext:
    """The engagement partner signed in, with MFA at the event's time."""
    seat = _SEATS[audit.ep]
    user = user_id_of(seat)
    return AuthContext(
        TenantContext(TENANT, "human", str(user)),
        user,
        UUID(int=0),
        FIRM_ROLES.get(seat.initials),
        at,
    )


async def _assurance_work_item(audit: Audit) -> UUID:
    found = await assurance_item_id(
        TenantContext(TENANT, "system", LOADER), engagement_id_of(audit)
    )
    if found is None:
        raise LookupError(f"no assurance work item on {audit.label}")
    return found


async def _profile_set(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    """The EBP label facts through PATCH profile's service, as the engagement partner."""
    audit = BY_LABEL[str(event.data["audit"])]
    ctx = _partner_context(audit, event.at)
    work_item = await _assurance_work_item(audit)
    item = await assurance_item(ctx.tenant, work_item)
    await update_profile(
        ctx,
        work_item,
        item.version,
        {
            "ebp_plan_kind": str(event.data["plan"]),
            "limited_scope_103a3c": bool(event.data["limited"]),
        },
    )


async def _independence_confirmed(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    """The engagement partner confirms their own independence (G2) before moving the phase."""
    audit = BY_LABEL[str(event.data["audit"])]
    ctx = _partner_context(audit, event.at)
    await answer_independence(ctx, engagement_id_of(audit), confirm=True, note=None)


async def _phase_recorded(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    """Record mode: the engagement partner records the next phase (SPEC-330 AC-9 to AC-12)."""
    audit = BY_LABEL[str(event.data["audit"])]
    ctx = _partner_context(audit, event.at)
    await record_phase(ctx, await _assurance_work_item(audit), str(event.data["to"]))


async def _phase_advanced(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Seed only (security review, DEC-310): a gate phase whose SPEC-314 facts (EQR concurrence,
    rep letter, release) the slice does not model. The derived event is written as the owner in
    the event's actor transaction with its audit row, like the other bootstrap writes; its
    insert trigger still binds the actor to the session, refuses a stale or backward move and
    moves the projection. No product path moves a phase without its gate met
    (`assurance.phase.advance_by_gate` computes it). A release keeps its own date."""
    audit = BY_LABEL[str(event.data["audit"])]
    engagement = engagement_id_of(audit)
    on = event.data.get("on")
    at = datetime.combine(date.fromisoformat(str(on)), event.at.timetz()) if on else event.at

    async def write() -> tuple[str, str, str]:
        found = await conn.fetchrow(
            "SELECT work_item_id, phase FROM assurance_work_items "
            "WHERE tenant_id = $1 AND engagement_id = $2",
            TENANT,
            engagement,
        )
        if found is None:
            raise LookupError(f"no assurance work item on {audit.label}")
        await conn.execute(
            "INSERT INTO assurance_phase_events (tenant_id, engagement_id, work_item_id, "
            "from_phase, to_phase, mode, gate_ref, actor_kind, actor_user_id) "
            "VALUES ($1, $2, $3, $4, $5, 'derived', $6, 'human', $7)",
            TENANT,
            engagement,
            found["work_item_id"],
            found["phase"],
            str(event.data["to"]),
            str(event.data["gate"]),
            user_id_of(_SEATS[audit.ep]),
        )
        return "assurance.phase_derived", "engagement", str(engagement)

    await _bootstrap(conn, replace(event, at=at), write)


async def _engagement_archived(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Juniper and Meridian archived outside Accrued: no record-mode archive service exists before
    A-01-T23, so the archive is written as the owner with its audit row (the phase stays
    Released, DEC-263)."""
    audit = BY_LABEL[str(event.data["audit"])]
    engagement = engagement_id_of(audit)

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "UPDATE engagements SET status = 'archived' WHERE tenant_id = $1 AND id = $2",
            TENANT,
            engagement,
        )
        await conn.execute(
            "UPDATE work_items SET status = 'archived' "
            "WHERE tenant_id = $1 AND engagement_id = $2 AND kind = 'assurance'",
            TENANT,
            engagement,
        )
        return "engagement.archived", "engagement", str(engagement)

    await _bootstrap(conn, event, write)


# --- the compliance slice (Q-02-T39; DEC-363) ----------------------------------------------------
# Each event goes through the owning module's service as the person the handoff names, signed in
# with a second factor at the event's time (the services need fresh MFA). A hold is then taken to
# Active by the same steps `LegalHoldApply` runs (repeat-safe), since the loader replays without
# a worker; a running relay starting the workflow too changes nothing.


# The services' own literals, restated: the loader reads them from the slice's event data.
StaffRole = Literal["engagement_partner", "manager", "senior", "staff", "reviewer", "specialist"]
Option = Literal["accept", "accept_with_conditions", "decline"]
ServiceLine = Literal["audit", "tax", "cas", "advisory", "any"]
Anchor = Literal[
    "upload",
    "report_release",
    "filing_date",
    "due_or_received_later",
    "relationship_end",
    "client_inactive",
    "message_date",
    "event_date",
    "period_end",
]
ReasonCode = Literal["irs_examination", "litigation", "regulatory_inquiry", "subpoena", "other"]
EventKind = Literal[
    "unauthorized_access",
    "credential_attack",
    "data_exposure",
    "lost_device",
    "vendor_incident",
    "other",
]


async def _staff_context(conn: asyncpg.Connection, event: Event) -> AuthContext:
    """The event's actor as a signed-in member, with the firm role their membership holds now and
    a second factor just verified (`authorise` checks its recency against the system clock, not
    the event's business time)."""
    user = user_id_of(_SEATS[event.actor])
    role = await conn.fetchval(
        "SELECT firm_role FROM memberships WHERE tenant_id = $1 AND user_id = $2", TENANT, user
    )
    return AuthContext(
        TenantContext(TENANT, "human", str(user)), user, UUID(int=0), role, system_now()
    )


async def _flag_set(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    await set_flag(TENANT, str(event.data["flag"]), "true", LOADER, "Brightwater Hale scenario")


async def _retention_policy_set(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    data = event.data
    change = PolicyChange(
        record_type=str(data["record_type"]),
        service_line=cast(ServiceLine, data["service_line"]),
        firm_years=Decimal(str(data["firm_years"])),
        clock_start_event=cast(Anchor, data["clock_start_event"]),
        lock=bool(data["lock"]),
    )
    await set_policy(await _staff_context(conn, event), change)


async def _legal_hold_placed(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    data = event.data
    client: Client = _CLIENTS[str(data["client"])]
    scope = HoldScope(
        "client_tax_year",
        client_id=UUID(stable_id(f"client:{client.slug}")),
        tax_year=int(cast(int, data["tax_year"])),
    )
    view = await place_hold(
        await _staff_context(conn, event),
        scope,
        cast(ReasonCode, data["reason_code"]),
        str(data["details"]),
        (),
    )
    while await legal_hold_apply_batch(TENANT, view.id) > 0:
        pass
    await legal_hold_activate(TENANT, view.id)


async def _incident_recorded(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    data = event.data
    consumers = data["consumers_affected"]
    unencrypted = data["unencrypted"]
    facts = IncidentFacts(
        title=str(data["title"]),
        event_kind=cast(EventKind, data["event_kind"]),
        discovered_at=datetime.fromisoformat(str(data["discovered_at"])),
        consumers_affected=None if consumers is None else int(cast(int, consumers)),
        unencrypted=None if unencrypted is None else bool(unencrypted),
    )
    await record_incident(await _staff_context(conn, event), facts)


# --- the acceptance slice (P-07-T40; DEC-412) ---------------------------------------------------
# Each act goes through the owning service as the person the handoff names, signed in with a
# fresh second factor (`_staff_context`). The questionnaire templates have no service (firm
# content waiting for its admin screen), so they are bootstrapped like `_portal_user_added`.


async def _questionnaire_template_added(
    conn: asyncpg.Connection, _: Scenario, event: Event
) -> None:
    data = event.data
    family = str(data["family"])
    template = UUID(stable_id(f"questionnaire-template:{family}"))
    sections = [
        {"code": code, "title": title}
        for code, title in cast(list[tuple[str, str]], data["sections"])
    ]
    by = user_id_of(_SEATS[event.actor])
    tenant = tenant_of(event)  # the tenant `_bootstrap` sets and audits (security review)

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO acceptance_questionnaire_templates (id, tenant_id, name, family, "
            "created_by) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            template,
            tenant,
            str(data["name"]),
            family,
            by,
        )
        await conn.execute(
            "INSERT INTO acceptance_questionnaire_template_versions (id, tenant_id, template_id, "
            "version_no, sections, created_by) VALUES ($1, $2, $3, 1, $4::jsonb, $5) "
            "ON CONFLICT DO NOTHING",
            UUID(stable_id(f"questionnaire-version:{family}:1")),
            tenant,
            template,
            json.dumps(sections),
            by,
        )
        return "acceptance_template.created", "acceptance_template", str(template)

    await _bootstrap(conn, event, write)


async def _contact_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    contact = CONTACTS[int(cast(int, event.data["index"]))]
    client = await _client_id(conn, contact.client)
    roles = (
        [RoleAsked(contact.role, "client", client, contact.title)]
        if contact.role is not None
        else []
    )
    await create_contact(
        await _staff_context(conn, event),
        client,
        name=contact.name,
        party_kind=contact.party_kind,
        email=contact.email,
        phone=None,
        roles=roles,
    )


def _a(event: Event) -> UUID:
    return engagement_id_of(BY_LABEL[str(event.data["audit"])])


def _member(event: Event, key: str = "member") -> UUID:
    return user_id_of(_SEATS[str(event.data[key])])


async def _member_hours_set(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    hours = Decimal(str(event.data["hours"]))
    await change_team_role(
        await _staff_context(conn, event), _a(event), _member(event), None, hours
    )


async def _member_removed(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    await remove_from_team(await _staff_context(conn, event), _a(event), _member(event))


async def _eqr_assigned(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    await assign_eqr(await _staff_context(conn, event), _a(event), _member(event, "eqr"))


async def _team_approved(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    ctx = await _staff_context(conn, event)
    seen = await team_approval(ctx, _a(event))
    await approve_team(ctx, _a(event), seen.member_set_hash)


async def _member_proposed(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    await add_to_team(
        await _staff_context(conn, event),
        _a(event),
        _member(event),
        cast(StaffRole, event.data["role"]),
        Decimal(str(event.data["hours"])),
    )


async def _member_independence_confirmed(
    conn: asyncpg.Connection, _: Scenario, event: Event
) -> None:
    """A team member, or the EQR, confirms their own independence (CLI-08a)."""
    await answer_independence(
        await _staff_context(conn, event), _a(event), confirm=True, note=None
    )


async def _draft_of(conn: asyncpg.Connection, event: Event) -> tuple[UUID, UUID | None]:
    """The scenario draft the event names (by its creator and name) and its prospect."""
    _, payload = DRAFTS[str(event.data["draft"])]
    row = await conn.fetchrow(
        "SELECT id, prospect_engagement_id FROM engagement_drafts WHERE tenant_id = $1 "
        "AND created_by = $2 AND payload->>'name' = $3 AND discarded_at IS NULL "
        "ORDER BY saved_at DESC LIMIT 1",
        TENANT,
        user_id_of(_SEATS[_draft_owner(event)]),
        str(payload["name"]),
    )
    if row is None:
        raise LookupError(f"no draft {event.data['draft']!r}")
    return row["id"], row["prospect_engagement_id"]


def _draft_owner(event: Event) -> str:
    """Who created the scenario draft (only they can read it or start its acceptance)."""
    _, payload = DRAFTS[str(event.data["draft"])]
    return str(payload["owner"])


async def _draft_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    client_name, payload = DRAFTS[str(event.data["draft"])]
    client = await _client_id(conn, client_name)
    prior_label = payload.get("prior_audit")
    if prior_label is not None:
        prior = engagement_id_of(BY_LABEL[str(prior_label)])
        entity = await conn.fetchval(
            "SELECT client_entity_id FROM engagements WHERE tenant_id = $1 AND id = $2",
            TENANT,
            prior,
        )
    else:
        prior, entity = None, await _entity_id(conn, client, client_name)
    team = [
        {"user_id": str(user_id_of(_SEATS[i])), "role": role}
        for i, role in cast(list[tuple[str, str]], payload["team"])
    ]
    body: dict[str, object] = {
        "name": payload["name"],
        "fiscal_period_start": payload["fiscal_period_start"],
        "fiscal_period_end": payload["fiscal_period_end"],
        "team": team,
    }
    if prior is not None:
        body["prior_engagement_id"] = str(prior)
    await create_draft(
        await _staff_context(conn, event),
        client_id=client,
        client_entity_id=entity,
        type_code=str(payload["type_code"]),
        step="team_independence",
        payload=body,
    )


async def _conflict_check_run(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """A check over the subject; each hit on the cleared name is assessed not adverse."""
    data = event.data
    ctx = await _staff_context(conn, event)
    if data["subject"] == "client":
        subject = await _client_id(conn, str(event.client))
    else:
        subject = (await _draft_of(conn, event))[0]
    names = [str(n) for n in cast(list[str], data["names"])]
    check = await run_conflict_check(
        ctx,
        subject_kind="client" if data["subject"] == "client" else "engagement_draft",
        subject_id=subject,
        names=names,
    )
    cleared = str(data["clear"])
    for result in check.results:
        if result.redacted or result.matched_name is None:
            continue
        if result.matched_name.casefold() == cleared.casefold():
            await clear_conflict_result(
                ctx, check.id, result.id, assessment="not_adverse", reason=str(data["reason"])
            )


async def _acceptance_started(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    draft = (await _draft_of(conn, event))[0]
    await start_acceptance(await _staff_context(conn, event), draft)


async def _prospect(conn: asyncpg.Connection, event: Event) -> UUID:
    _, prospect = await _draft_of(conn, event)
    if prospect is None:
        raise LookupError(f"draft {event.data['draft']!r} has no prospect yet")
    return prospect


async def _acceptance_prepared(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """CLI-07b: the preparer's answers, risk rating and three flags (sources wait for the intake
    documents; the fee section is answered, not a manual check: DEC-412)."""
    ctx = await _staff_context(conn, event)
    engagement = await _prospect(conn, event)
    rating = str(event.data["risk_rating"])
    for n, (section, summary) in enumerate(THORNBURY_ANSWERS):
        await update_answers(
            ctx,
            engagement,
            section,
            seen_version=0,
            values={"summary": summary},
            complete=True,
            risk_rating=rating if n == 0 else None,
        )
    for severity, title, body in THORNBURY_FLAGS:
        await add_flag(ctx, engagement, severity=severity, title=title, body=body, sources=())


async def _acceptance_sent(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    ctx = await _staff_context(conn, event)
    engagement = await _prospect(conn, event)
    record = await acceptance_record(ctx, engagement)
    await send_to_partner(ctx, engagement, record.version)


async def _acceptance_decided(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    data = event.data
    ctx = await _staff_context(conn, event)
    engagement = await _prospect(conn, event)
    record = await acceptance_record(ctx, engagement)
    owner = _member(event, "assignee")
    await decide_acceptance(
        ctx,
        engagement,
        option=cast(Option, data["option"]),
        rationale=str(data["rationale"]),
        conditions=[NewCondition(str(t), owner) for t in cast(list[str], data["conditions"])],
        seen_version=record.version,
    )


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
    # A-01-T07: profile facts, the partner's independence, phase moves, then the archive.
    "assurance.profile_set": _profile_set,
    "engagements.independence_confirmed": _independence_confirmed,
    "assurance.phase_recorded": _phase_recorded,
    "assurance.phase_advanced": _phase_advanced,
    "engagements.engagement_archived": _engagement_archived,
    # P-06-T08 (`--slice binders`): client people, tax and close engagements, then the binders.
    "identity.client_person_added": _client_person_added,
    "engagements.tax_engagement_created": _tax_engagement_created,
    "engagements.close_engagement_created": _close_engagement_created,
    "requests.binder_created": _binder_created,
    # P-08-T14 (`--slice portal`): branding before its host; people after the work items they name.
    "portal.branding_set": _branding_set,
    "portal.host_added": _host_added,
    "identity.portal_person_added": _portal_person_added,
    "identity.client_invitation_created": _client_invitation_created,
    # G-01-T06 (`--slice people`): seats, then teams, then each person's profile.
    "identity.seats_provisioned": _seats_provisioned,
    "organisations.team_created": _team_created,
    "identity.member_profile_set": _member_profile_set,
    # The shell slice, after audit_core: the sandbox firm before its offices and membership.
    "identity.sandbox_firm_created": _sandbox_firm_created,
    "organisations.sandbox_office_created": _sandbox_office_created,
    "identity.sandbox_membership_added": _sandbox_membership_added,
    "identity.job_title_set": _job_title_set,
    "identity.default_office_set": _default_office_set,
    "notifications.preference_set": _preference_set,
    # Q-02-T39 (`--slice compliance`): flags first, then policies, holds and the incident.
    "platform.flag_set": _flag_set,
    "evidence.retention_policy_set": _retention_policy_set,
    "evidence.legal_hold_placed": _legal_hold_placed,
    "platform.incident_recorded": _incident_recorded,
    # P-07-T40 (`--slice acceptance`): templates, Calloway's custodian, the Northwind team's
    # history, the conflict searches, independence, contacts, then Thornbury and Meridian.
    "engagements.questionnaire_template_added": _questionnaire_template_added,
    "organisations.contact_created": _contact_created,
    "engagements.member_hours_set": _member_hours_set,
    "engagements.member_removed": _member_removed,
    "engagements.eqr_assigned": _eqr_assigned,
    "engagements.team_approved": _team_approved,
    "engagements.draft_created": _draft_created,
    "organisations.conflict_check_run": _conflict_check_run,
    "engagements.member_independence_confirmed": _member_independence_confirmed,
    "engagements.acceptance_started": _acceptance_started,
    "engagements.acceptance_prepared": _acceptance_prepared,
    "engagements.acceptance_sent": _acceptance_sent,
    "engagements.acceptance_decided": _acceptance_decided,
    "engagements.member_proposed": _member_proposed,
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
    tenant = tenant_of(event)
    return bool(
        await tenant_value(
            conn,
            tenant,
            "SELECT EXISTS (SELECT 1 FROM audit_events WHERE tenant_id = $1 AND trace_id = $2)",
            tenant,
            trace_hex(event),
        )
    )


async def settle(conn: asyncpg.Connection, timeout: float = SETTLE_SECONDS) -> None:
    """The barrier: the tenant's outbox is empty (each async consequence has been handed on)."""
    deadline = system_now().timestamp() + timeout
    while await tenant_value(
        conn,
        TENANT,
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND published_at IS NULL",
        TENANT,
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
    slices = expand_slices(slices)
    host = portal_host(HOST_LABEL) if PORTAL_SLICE in slices else None
    if staging and PORTAL_SLICE in slices and host is None:
        raise LoadRefused("--slice portal on staging needs portal_base_domain for its host")
    scenario = build(at, holdouts, ("audit_core", *slices))
    replayed = skipped = 0
    conn = await connect_db(dsn)
    try:
        synthetic = await tenant_value(
            conn, TENANT, "SELECT synthetic FROM firms WHERE tenant_id = $1", TENANT
        )
        if synthetic is False:
            raise LoadRefused("the scenario firm exists and is not synthetic")
        await preflight(conn, scenario.events)
        # A laptop without a portal domain loads everything but the host.
        events = tuple(
            e for e in scenario.events if host is not None or e.kind != "portal.host_added"
        )
        for event in replay_order(events):
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
