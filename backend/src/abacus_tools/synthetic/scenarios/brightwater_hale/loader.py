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
(`--slice binders`) and bootstrapped the same way; see DEC-146. Granite Peak's agent-drafted SURL
request (Sep 24, so from the 2026-10-01 snapshot) is bootstrapped too, with the agent's audit row
on behalf of its firm owner: no service writes a drafted request outside a procedure session.

The `portal_pbc` slice (R-01-T11: Dana Kowalski's client titles on AUD-03's rows) is opt-in
(`--slice portal_pbc`, which brings `binders` and `portal`) and goes through `requests.api` as
Marcus Delaney; see DEC-348 and the slice's gaps in TASK-1221.

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

The `email_templates` slice (R-01-T22: Brightwater Hale's six email templates, POR-20's versions
and the Reminder's v4 draft, behind the editor flag) is opt-in (`--slice email_templates`) and goes
through `communications.api`'s editor service as Grace Holloway; see DEC-451.

`--slice` adds slices to the default `audit_core`. The `shell` slice (P-01-T07: the training
sandbox and Grace's membership in it, job titles, Hannah's default office and notification
preferences) has no service yet either and is bootstrapped the same way. Its columns arrive with
P-01-T03 and P-01-T04, so the loader checks the schema first and refuses the whole load
(`SchemaPending`) rather than replaying part of it.

Refuses: `environment = production`; outside `--staging`, any database URL that is not loopback;
with `--staging`, an environment other than staging, a firm that is not synthetic, or a staging
deploy in flight (F-04.16, F-04.17).

With `--staging`, each firm the timeline creates gets its tenant key before anything else is
written for it: the loader starts (or attaches to) the firm's `TenantKeyWorkflow` and waits for
the verified key (DEC-1012), since staging seals every write with the firm's own KMS key.
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
from contextlib import asynccontextmanager, contextmanager, suppress
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Final, Literal, cast
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg
from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from sqlalchemy import text
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel.clock import frozen, system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.dispatch import dispatch
from abacus.kernel.temporal import temporal_client
from abacus.kernel.uow import Target, uow
from abacus.modules.assurance.api import (
    import_grouping_csv,
    publish_grouping_version,
    record_phase,
    update_profile,
)
from abacus.modules.communications.api import (
    Inbound,
    TemplateContent,
    add_attachment,
    email_template_state,
    publish_email_template,
    record_inbound_message,
    save_email_template_draft,
)
from abacus.modules.connections.api import seed_synthetic_connection
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
    conclude_independence,
    create_draft,
    decide_acceptance,
    designate_contact,
    remove_from_team,
    send_to_partner,
    start_acceptance,
    team_approval,
    update_answers,
)
from abacus.modules.evidence.api import (
    HoldScope,
    NewItem,
    PolicyChange,
    Provenance,
    add_version,
    legal_hold_activate,
    legal_hold_apply_batch,
    place_hold,
    set_policy,
    stage_content,
)
from abacus.modules.identity.api import (
    AuthContext,
    MemberProfile,
    provision_setting,
    set_demo_clock,
    set_member_profile,
)
from abacus.modules.methodology.api import (
    EngagementType,
    create_standard,
    import_standard_workbook,
    import_template,
    publish_standard,
    standard_by_key,
    standard_workbook,
)
from abacus.modules.methodology.api import (
    approve_version as approve_methodology_version,
)
from abacus.modules.methodology.api import (
    version_state as methodology_version_state,
)
from abacus.modules.organisations.api import (
    ClientRecordChange,
    NewClient,
    RoleAsked,
    activate_contact,
    clear_conflict_result,
    client_with_entity,
    create_client,
    create_contact,
    run_conflict_check,
    set_client_record,
)
from abacus.modules.platform.api import (
    IncidentFacts,
    TenantKeyInput,
    TenantKeyWorkflow,
    enrol_pilot,
    record_incident,
    tenant_key_workflow_id,
)
from abacus.modules.portal.api import (
    BrandingSlots,
    activate_portal_host,
    add_portal_host,
    set_branding,
)
from abacus.modules.reporting.api import (
    TemplateImportIn,
    import_template_bundle,
    publish_template,
)
from abacus.modules.requests.api import (
    ItemPatch,
    attach_organizer,
    create_questionnaire,
    draft_question,
    fulfil_by_upload,
    import_questionnaire_template,
    latest_version_of,
    move_after_review,
    publish_questionnaire_template,
    questionnaire_templates,
    save_portal_answer,
    send_question,
    update_item,
)
from abacus.modules.review.api import STATEMENTS as SIGN_OFF_STATEMENTS
from abacus.modules.review.api import sign_target
from abacus.modules.sampling.api import (
    ApproveIn,
    ParametersIn,
    PopulationIn,
    SampleSetIn,
    TieComparisonIn,
    TieIn,
    UploadSourceIn,
    VersionIn,
    create_population,
    create_sample_set,
    record_tie,
    sample_set_view,
)
from abacus.modules.sampling.api import approve as approve_sample
from abacus.modules.sampling.api import draw as draw_sample
from abacus.modules.tax.api import import_engine_file, share_k1_internal
from abacus_tools import deploy_lock
from abacus_tools.db_connect import connect as connect_db
from abacus_tools.fakes.identity import ISSUER
from abacus_tools.flags import set_flag
from abacus_tools.local.db_guard import violations
from abacus_tools.synthetic.documents import positioned_pdf
from abacus_tools.synthetic.scenarios.brightwater_hale import sampling_content
from abacus_tools.synthetic.scenarios.brightwater_hale.acceptance import (
    CONTACTS,
    THORNBURY_ANSWERS,
    THORNBURY_FLAGS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.acceptance import (
    DRAFTS as ACCEPTANCE_DRAFTS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.acceptance import (
    NEEDS as ACCEPTANCE_NEEDS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.acceptance import (
    SLICE as ACCEPTANCE_SLICE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import (
    AUDITS,
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
    SURL_DRAFT,
    SURL_FILES,
    SURL_UPLOADED_BY,
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
from abacus_tools.synthetic.scenarios.brightwater_hale.connections import (
    NEEDS as CONNECTIONS_NEEDS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.connections import (
    SLICE as CONNECTIONS_SLICE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.consents_7216 import NEEDS as CONSENTS_NEEDS
from abacus_tools.synthetic.scenarios.brightwater_hale.consents_7216 import ROW_BY_LABEL
from abacus_tools.synthetic.scenarios.brightwater_hale.consents_7216 import SLICE as CONSENTS_SLICE
from abacus_tools.synthetic.scenarios.brightwater_hale.ebp import FILES as EBP_FILES
from abacus_tools.synthetic.scenarios.brightwater_hale.ebp import NEEDS as EBP_NEEDS
from abacus_tools.synthetic.scenarios.brightwater_hale.ebp import SLICE as EBP_SLICE
from abacus_tools.synthetic.scenarios.brightwater_hale.email_templates import (
    SLICE as EMAIL_TEMPLATES_SLICE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT as _CT
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import snapshot
from abacus_tools.synthetic.scenarios.brightwater_hale.firm_inbox import (
    NEEDS as FIRM_INBOX_NEEDS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.firm_inbox import (
    SLICE as FIRM_INBOX_SLICE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.firm_inbox import (
    TRIAGER as INBOX_TRIAGER,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.firm_people import (
    SERVICE_LINE_OF_TEAM,
    Level,
    TeamName,
    Template,
    access_ends_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.intake import (
    DRAFTS as INTAKE_DRAFTS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.intake import (
    MERIDIAN_ANSWERS,
    MERIDIAN_FLAGS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.intake import NEEDS as INTAKE_NEEDS
from abacus_tools.synthetic.scenarios.brightwater_hale.intake import SLICE as INTAKE_SLICE
from abacus_tools.synthetic.scenarios.brightwater_hale.methodology import (
    NEEDS as METHODOLOGY_NEEDS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.methodology import (
    SLICE as METHODOLOGY_SLICE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.methodology import (
    spec_of as methodology_spec,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.methodology import (
    workbook as methodology_workbook,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.people import (
    FIRM_ROLES,
    SEATS,
    Seat,
    email_of,
    slug_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.pilot import NEEDS as PILOT_NEEDS
from abacus_tools.synthetic.scenarios.brightwater_hale.pilot import SLICE as PILOT_SLICE
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
from abacus_tools.synthetic.scenarios.brightwater_hale.portal_pbc import (
    BINDER_NAME,
    CLIENT_FILE_BY_KEY,
    DELEGATION_BY_ORG,
    FELD_1095C_REQUEST,
    FELD_RETURN,
    KEYSTONE,
    RETURNED_SLICE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.portal_pbc import (
    NEEDS as PORTAL_PBC_NEEDS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.portal_pbc import (
    SLICE as PORTAL_PBC_SLICE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.report_templates import (
    NEEDS as REPORT_TEMPLATES_NEEDS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.report_templates import (
    SLICE as REPORT_TEMPLATES_SLICE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.report_templates import (
    bundle as report_template_bundle,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.sampling_slice import (
    NEEDS as SAMPLING_NEEDS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.sampling_slice import (
    SET_PURPOSE as SAMPLING_SET_PURPOSE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.sampling_slice import (
    SET_TITLE as SAMPLING_SET_TITLE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.sampling_slice import (
    SLICE as SAMPLING_SLICE,
)
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
from abacus_tools.synthetic.scenarios.brightwater_hale.signatures import BY_KEY as ENVELOPE_BY_KEY
from abacus_tools.synthetic.scenarios.brightwater_hale.signatures import (
    ERSD_BODY,
    KOWAL_FAILURES,
    HubEnvelope,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.signatures import NEEDS as SIGNATURES_NEEDS
from abacus_tools.synthetic.scenarios.brightwater_hale.signatures import (
    NUMBERS as ENVELOPE_NUMBERS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.signatures import SLICE as SIGNATURES_SLICE
from abacus_tools.synthetic.scenarios.brightwater_hale.signatures import at as _at
from abacus_tools.synthetic.scenarios.brightwater_hale.standards import (
    BH_TAX_02_CLIENTS,
    payload_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.standards import NEEDS as STANDARDS_NEEDS
from abacus_tools.synthetic.scenarios.brightwater_hale.standards import SLICE as STANDARDS_SLICE
from abacus_tools.synthetic.scenarios.brightwater_hale.standards import (
    spec_of as standard_spec,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_board import BOARD_BY_LABEL
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_board import NEEDS as TAX_BOARD_NEEDS
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_board import SLICE as TAX_BOARD_SLICE
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_content import (
    ANSWERED_BY,
    ORGANIZER,
    ORGANIZER_NAME,
    K1Set,
    ask_of,
    contact_email,
    organizer_csv,
    set_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_content import (
    NEEDS as TAX_CONTENT_NEEDS,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_content import (
    SLICE as TAX_CONTENT_SLICE,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_content import (
    Recipient as K1Recipient,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SUPERUSER_ENV: Final = "ABACUS_LOCAL_SUPERUSER_DSN"
DEFAULT_SUPERUSER: Final = "postgresql://postgres:postgres@127.0.0.1:55432/abacus"
LOOPBACK: Final = frozenset({"127.0.0.1", "localhost", "::1"})
LOADER: Final = "scenario-loader"
SETTLE_SECONDS: Final = 120.0
# DEC-1012: how long a staging load waits for a firm's tenant key (create, replicate, verify).
KEY_SECONDS: Final = 600.0
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
    # I-01-T13: HOME-01 lite on synthetic firms (GET /v1/home and the C13 gate list and counts).
    "home.dashboard",
    "review.grammar_api",
    "review.approve_agent_output",  # P-04-T46 (DEC-1385): SHL-10 approval on synthetic firms
    "engagements.roll_forward_v2",  # P-07-T55: ENG-13 v2 on synthetic firms
    # N-02-T17: record mode (SIG-01, the import, the portal reads) on synthetic firms from S15.
    "signatures.envelopes",
    # N-01-T23: INB-01, INB-02 and FIL-01 live on Brightwater Hale (staging and local).
    "inbox.firm_intake",
    "files.browser",
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


class KeyTimeout(RuntimeError):
    """A firm's tenant key was not verified within the wait (staging, DEC-1012)."""


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
# The scenario drafts by key: wave 2's (acceptance) and wave 3's (intake, P-07-T50).
DRAFTS: Final = {**ACCEPTANCE_DRAFTS, **INTAKE_DRAFTS}
# A prepared acceptance record's answers and human-authored flags, by draft.
PREPARED: Final = {
    "thornbury": (THORNBURY_ANSWERS, THORNBURY_FLAGS),
    "meridian": (MERIDIAN_ANSWERS, MERIDIAN_FLAGS),
}


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
    """The deploy-staging run in progress, if any (working agreement: no load during a build).
    From a laptop, GitHub's run list; inside the staging VPC (the ops task, no gh), the SSM deploy
    lock every deploy takes first (`abacus_tools.deploy_lock`, DEC-1005)."""
    gh = shutil.which("gh")
    if gh is None:
        try:
            lock = deploy_lock.held("staging")
        except Exception as error:  # no credentials or no SSM: refuse rather than guess
            raise LoadRefused("cannot tell whether a staging deploy is in flight") from error
        return None if lock is None else f"deploy lock held by {lock.holder} ({lock.run_ref})"
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


async def tenant_row(
    conn: asyncpg.Connection, tenant: UUID, sql: str, *args: object
) -> asyncpg.Record | None:
    """One row read as `tenant` (`as_tenant`)."""
    async with as_tenant(conn, tenant):
        return await conn.fetchrow(sql, *args)


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
    on_behalf_of: UUID | None = None,
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
            ("app.on_behalf_of", str(on_behalf_of) if on_behalf_of is not None else ""),
        ):
            await conn.execute("SELECT set_config($1, $2, true)", name, value)
        action, target_type, target_id = await write()
        await conn.execute(
            "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, "
            "target_id, trace_id, on_behalf_of_user_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            tenant,
            actor_kind,
            actor_id,
            action,
            target_type,
            target_id,
            trace,
            on_behalf_of,
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
    found = await tenant_value(
        conn, TENANT, "SELECT id FROM clients WHERE tenant_id = $1 AND name = $2", TENANT, name
    )
    if found is None:
        raise LookupError(f"no client {name!r}")
    return cast(UUID, found)


async def _entity_id(conn: asyncpg.Connection, client: UUID, name: str) -> UUID:
    found = await tenant_value(
        conn,
        TENANT,
        "SELECT id FROM client_entities WHERE tenant_id = $1 AND client_id = $2 AND name = $3",
        TENANT,
        client,
        name,
    )
    if found is None:
        raise LookupError(f"no entity {name!r}")
    return cast(UUID, found)


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


async def _return_board_set(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """T-02-T11: one return's board state (status, level, extension, sync, due dates) and its
    preparer and reviewer, on the engagement's team."""
    row = BOARD_BY_LABEL[str(event.data["return"])]
    ret = RETURN_BY_LABEL[row.label]
    engagement = UUID(ENGAGEMENT_BY_LABEL[ret.engagement].id)
    item = UUID(row.work_item_id)
    synced_at = (
        datetime.strptime(f"{row.sync.day} 2026 17:00", "%b %d %Y %H:%M").replace(tzinfo=_CT)
        if row.sync.day is not None
        else None
    )

    async def write() -> tuple[str, str, str]:
        updated = await conn.execute(
            "UPDATE tax_returns SET status = $3, review_level = $4, extended = $5, "
            "sync_status = $6, last_synced_at = $7, original_due_on = $8, extended_due_on = $9 "
            "WHERE tenant_id = $1 AND work_item_id = $2",
            TENANT,
            item,
            row.status,
            row.review_level,
            row.extended,
            row.sync.code,
            synced_at,
            row.original_due,
            row.extended_due if row.extended else None,
        )
        if updated != "UPDATE 1":
            raise RuntimeError(f"no tax return for {row.label}: load the binders slice first")
        for initials, function, role in (
            (row.preparer, "preparer", "staff"),
            (row.reviewer, "detail_reviewer", "reviewer"),
        ):
            user = user_id_of(_SEATS[initials])
            await conn.execute(
                "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                TENANT,
                engagement,
                user,
                role,
            )
            await conn.execute(
                "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, "
                "user_id, function, assigned_by) SELECT $1, $2, $3, $4, $5, $4 WHERE NOT EXISTS "
                "(SELECT 1 FROM work_item_assignments WHERE tenant_id = $1 AND work_item_id = $2 "
                "AND function = $5 AND removed_at IS NULL)",
                TENANT,
                item,
                engagement,
                user,
                function,
            )
        return "tax_return.board_set", "work_item", str(item)

    await _bootstrap(conn, event, write)


# T-01-T23 (DEC-1366): ADM-05's 218 consents, bootstrapped as record mode writes them (T-01-T10's
# capture is the person's path; the scenario has no envelopes to complete). No consent text is
# stored: a synthetic template version and its hash stand in, as a recorded consent carries them.
_CONSENT_TERMS: Final = "synthetic-terms"
_SIGNER_NAMES: Final = {
    "Calloway Family Trust": ("Eleanor Calloway, trustee",),
    "Ridgeline Property Partners, LP": ("Owen Calder, for Ridgeline GP LLC",),
    "Copperleaf Coffee Roasters, Inc.": ("Tess Moreno, CEO",),
}


def _signer_names(client: str, count: int) -> tuple[str, ...]:
    """ "Morgan & Kai Ferris" → "Morgan Ferris", "Kai Ferris"; a single person as named."""
    if client in _SIGNER_NAMES:
        return _SIGNER_NAMES[client][:count]
    if " & " in client and count == 2:
        first, rest = client.split(" & ", 1)
        given, _space, family = rest.rpartition(" ")
        return (f"{first} {family}", f"{given} {family}")
    return (client,) * count


def _ct(day: date | None) -> datetime | None:
    return None if day is None else datetime(day.year, day.month, day.day, 10, 0, tzinfo=_CT)


async def _consent_recorded(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    row = ROW_BY_LABEL[str(event.data["row"])]
    client = await _client_id(conn, row.client)
    entity = await _entity_id(conn, client, row.entity)
    creator = user_id_of(_SEATS["GH"])

    async def write() -> tuple[str, str, str]:
        set_id = None
        if len(row.purposes) > 1:
            set_id = UUID(row.set_id)
            await conn.execute(
                "INSERT INTO consent_sets (id, tenant_id, client_id, filing_unit_entity_id, "
                "kind, tax_years, created_by) VALUES ($1, $2, $3, $4, 'use_ai_disclosure', $5, "
                "$6) ON CONFLICT DO NOTHING",
                set_id,
                TENANT,
                client,
                entity,
                list(row.tax_years),
                creator,
            )
        names = _signer_names(row.client, len(row.signers))
        contacts = [UUID(stable_id(f"contact:consent:{row.client}:{n}")) for n in names]
        for contact, name in zip(contacts, names, strict=True):
            await conn.execute(
                "INSERT INTO contacts (id, tenant_id, client_id, display_name, contact_kind, "
                "created_at) VALUES ($1, $2, $3, $4, 'client_person', $5) "
                "ON CONFLICT DO NOTHING",
                contact,
                TENANT,
                client,
                name,
                event.at,
            )
        for purpose in row.purposes:
            consent = UUID(row.consent_id(purpose))
            await conn.execute(
                "INSERT INTO consents (id, tenant_id, client_id, client_entity_id, "
                "consent_set_id, purpose, tax_years, recipients, provider_terms_version, "
                "template_version_id, text_sha256, source, status, requested_at, signed_at, "
                "expires_at, declined_at, revoked_at, created_by) VALUES ($1, $2, $3, $4, $5, "
                "$6, $7, $8::jsonb, $9, $10, $11, 'record', $12, $13, $14, $15, $16, $17, $18) "
                "ON CONFLICT DO NOTHING",
                consent,
                TENANT,
                client,
                entity,
                set_id,
                purpose,
                list(row.tax_years),
                json.dumps([row.recipient]),
                _CONSENT_TERMS,
                UUID(stable_id(f"consent-template:{purpose}:v2")),
                hashlib.sha256(f"synthetic consent template {purpose} v2".encode()).digest(),
                row.status,
                _ct(row.signed_on) or _ct(row.declined_on) or event.at,
                _ct(row.signed_on) if row.status in ("signed", "revoked") else None,
                _ct(row.expires_on),
                _ct(row.declined_on),
                _ct(row.revoked_on),
                creator,
            )
            for index, (signer, contact) in enumerate(zip(row.signers, contacts, strict=True)):
                done = (
                    signer.signed_on if row.status in ("signed", "revoked", "requested") else None
                )
                await conn.execute(
                    "INSERT INTO consent_signers (id, tenant_id, consent_id, contact_id, "
                    "signer_role, required, signed_at, method) VALUES ($1, $2, $3, $4, $5, true, "
                    "$6, $7) ON CONFLICT DO NOTHING",
                    UUID(stable_id(f"consent-signer:{row.label}:{purpose}:{index}")),
                    TENANT,
                    consent,
                    contact,
                    signer.role,
                    _ct(done),
                    "record" if done else None,
                )
        return "consent.recorded", "client", str(client)

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


async def _request_drafted(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """An agent-drafted request (SHL-14 f): a Draft, Owners only, with its run and the
    fingerprint of the wording it was drafted with. No service writes a drafted request outside
    a procedure session's run, so it is bootstrapped with the audit row the run would write: the
    agent, for the firm owner whose procedure session it ran in."""
    draft = SURL_DRAFT
    pbc = _PBC[draft.list_key]
    engagement = engagement_id_of(BY_LABEL[pbc.engagement])
    owner = user_id_of(_SEATS[draft.owner])
    item = UUID(draft.id)

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO request_items (id, tenant_id, engagement_id, request_list_id, "
            "description, title, audit_area, category_id, status, created_by, created_at, "
            "client_visible, client_assignee_user_id, firm_owner_user_id, due_on, period_start, "
            "period_end, drafted_by_run_id, drafted_wording_source, drafted_wording_fingerprint) "
            "VALUES ($1, $2, $3, $4, $5, $5, $6, $7, 'draft', $8, $9, false, $10, $8, $11, $12, "
            "$13, $14, 'template', $15) ON CONFLICT DO NOTHING",
            item,
            TENANT,
            engagement,
            UUID(pbc.id),
            draft.title,
            draft.category,
            UUID(pbc.category_id(draft.category)),
            owner,
            event.at,
            UUID(_PORTAL[draft.assignee].id),
            draft.due_on,
            draft.period[0],
            draft.period[1],
            UUID(draft.run_id),
            hashlib.sha256(draft.title.encode()).hexdigest(),
        )
        return "request_item.created", "request_item", str(item)

    await bootstrap_write(
        conn,
        tenant=TENANT,
        actor_kind="agent",
        actor_id=draft.run_id,
        at=event.at,
        trace=trace_hex(event),
        write=write,
        on_behalf_of=owner,
    )


# --- the portal slice (P-08-T14; DEC-213) --------------------------------------------------------
# Branding and the host have services (`portal.api`), called in a unit of work under Grace
# Holloway. Client users, memberships and grants have none a loader can call (granting wants a
# signed-in person with fresh MFA, and a client-wide grant the firm's administrator), so they are
# bootstrapped like `_portal_user_added`, with the `granted` history row the service writes. The
# invitation is bootstrapped too: `create_invitation` would mint a token and email it.

SLICE_NEEDS: Final[dict[str, tuple[str, ...]]] = {
    PORTAL_SLICE: PORTAL_NEEDS,
    PORTAL_PBC_SLICE: PORTAL_PBC_NEEDS,
    RETURNED_SLICE: PORTAL_PBC_NEEDS,  # POR-03 g's alternate path (DEC-471)
    COMPLIANCE_SLICE: COMPLIANCE_NEEDS,
    METHODOLOGY_SLICE: METHODOLOGY_NEEDS,  # K-01-T10: Grace imports, Margaret approves
    EBP_SLICE: EBP_NEEDS,  # A-05-T07: Dana's EBP source documents on Northwind
    SAMPLING_SLICE: SAMPLING_NEEDS,  # A-03-T16: Table 2, BH FS groupings, Northwind's sample
    REPORT_TEMPLATES_SLICE: REPORT_TEMPLATES_NEEDS,  # P-11-T13: Grace imports, Margaret publishes
    CONNECTIONS_SLICE: CONNECTIONS_NEEDS,  # A-02-T27: Copperleaf's POR-16a connections
    ACCEPTANCE_SLICE: ACCEPTANCE_NEEDS,
    INTAKE_SLICE: INTAKE_NEEDS,  # P-07-T50: wave 3 (drafts, the open Harborline hit, Meridian)
    FIRM_INBOX_SLICE: FIRM_INBOX_NEEDS,  # N-01-T11: docs@ rows 1-17 and the Intake team
    EMAIL_TEMPLATES_SLICE: (),  # R-01-T22: Grace's firm admin role is audit_core's
    TAX_BOARD_SLICE: TAX_BOARD_NEEDS,  # T-02-T11: the board sets the binders' returns
    CONSENTS_SLICE: CONSENTS_NEEDS,  # T-01-T23: the sets name the tax engagements' entities
    STANDARDS_SLICE: STANDARDS_NEEDS,  # K-02-T18: Margaret creates; each owner publishes
    SIGNATURES_SLICE: SIGNATURES_NEEDS,  # N-02-T36: SIG-01 at E0 over the tax clients
    TAX_CONTENT_SLICE: TAX_CONTENT_NEEDS,  # T-02-T23: K-1 sets, the organizer, questions
    PILOT_SLICE: PILOT_NEEDS,  # TASK-2470: PF-X1's enrolments name the Feld return and Northwind
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
        engagement = await tenant_value(
            conn,
            TENANT,
            "SELECT engagement_id FROM work_items WHERE tenant_id = $1 AND id = $2",
            TENANT,
            item,
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
        client = await tenant_value(
            conn,
            TENANT,
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


# --- the portal PBC slice (R-01-T11; DEC-348, DEC-471) ------------------------------------------
# Titles go through `requests.api` as Marcus Delaney, with MFA just verified. DEC-471 fills what
# no service writes for a loader: a received row's title, the list's name, delegations without a
# grant, Claire's file in the Feld Inbox (the client-data gate refuses it: no Feld acceptance) and
# Kevin Osei's return (ADR-005: `evidence.decide` only serves a request). Each is bootstrapped
# with the audit row its service writes; files go through `evidence.api` (`stage_content`,
# `add_version`) in a unit of work as the person who sent them.
_PDF: Final = "application/pdf"
_XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _item_retitled(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    pbc = _PBC[str(event.data["list"])]
    engagement = engagement_id_of(BY_LABEL[pbc.engagement])
    item = UUID(pbc.request_id(int(cast(int, event.data["position"]))))
    title = str(event.data["title"])
    status = await tenant_value(
        conn,
        TENANT,
        "SELECT status FROM request_items WHERE tenant_id = $1 AND id = $2",
        TENANT,
        item,
    )
    if status != "received":
        ctx = await _staff_context(conn, event)
        await update_item(ctx, engagement, item, ItemPatch({"title": title}))
        return

    async def write() -> tuple[str, str, str]:  # DEC-471: a received request is not editable
        await conn.execute(
            "UPDATE request_items SET title = $3 WHERE tenant_id = $1 AND id = $2",
            TENANT,
            item,
            title,
        )
        return "request_item.updated", "request_item", str(item)

    await _bootstrap(conn, event, write)


async def _list_named(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    pbc = _PBC[str(event.data["list"])]
    list_id = UUID(pbc.id)

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "UPDATE request_lists SET name = $3 WHERE tenant_id = $1 AND id = $2",
            TENANT,
            list_id,
            BINDER_NAME,
        )
        return "request_list.updated", "request_list", str(list_id)

    await _bootstrap(conn, event, write)


async def _items_delegated(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """One organisation's delegated requests, without a grant (nobody has signed in yet)."""
    pbc = _PBC[str(event.data["list"])]
    engagement = engagement_id_of(BY_LABEL[pbc.engagement])
    delegation = DELEGATION_BY_ORG[str(event.data["org"])]
    contact = UUID(delegation.contact_id)
    by = user_id_of(_SEATS[event.actor])

    async def write() -> tuple[str, str, str]:
        if delegation.org != KEYSTONE:  # Keystone's is Sam Ortiz's contact (`portal`)
            client = await tenant_value(
                conn,
                TENANT,
                "SELECT client_id FROM engagements WHERE tenant_id = $1 AND id = $2",
                TENANT,
                engagement,
            )
            await conn.execute(
                "INSERT INTO contacts (id, tenant_id, client_id, display_name, "
                "organisation_name, contact_kind, created_at) VALUES ($1, $2, $3, $4, $4, "
                "'third_party', $5) ON CONFLICT DO NOTHING",
                contact,
                TENANT,
                client,
                delegation.org,
                event.at,
            )
        for position in delegation.positions:
            await conn.execute(
                "INSERT INTO request_delegations (id, tenant_id, request_item_id, contact_id, "
                "granted_by, granted_at) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING",
                UUID(stable_id(f"delegation:{pbc.key}:{position}")),
                TENANT,
                UUID(pbc.request_id(position)),
                contact,
                by,
                event.at,
            )
        return "request_item.delegated", "contact", str(contact)

    await _bootstrap(conn, event, write)


def _feld_engagement() -> UUID:
    ret = next(r for r in RETURN_BY_LABEL.values() if r.client == "Jonah & Claire Feld")
    return UUID(ENGAGEMENT_BY_LABEL[ret.engagement].id)


def _feld_request(title: str) -> UUID:
    binder = BINDER_BY_LABEL["jonah-and-claire-feld:1"]
    position = next(n for n, r in enumerate(binder.requests, 1) if r.title == title)
    return UUID(binder.request_id(position))


async def _inbox_file_added(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Claire's email in the Feld Inbox, waiting to be filed (POR-03 c; DEC-471)."""
    found = CLIENT_FILE_BY_KEY[str(event.data["file"])]
    sender = UUID(PERSON_BY_NAME[found.sender].id)
    content = found.content()
    stored = await stage_content(TENANT, content)
    file_id = UUID(stable_id(f"inbox-file:{found.key}"))

    async def write() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO inbox_files (id, tenant_id, engagement_id, file_name, media_type, "
            "size_bytes, fingerprint, storage_key, storage_version_id, uploaded_by, "
            "uploaded_by_staff, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, "
            "false, $11) ON CONFLICT DO NOTHING",
            file_id,
            TENANT,
            _feld_engagement(),
            found.file_name,
            _PDF,
            len(content),
            stored.fingerprint,
            stored.key,
            stored.version_id,
            sender,
            event.at,
        )
        return "inbox_file.added", "inbox_file", str(file_id)

    await bootstrap_write(
        conn,
        tenant=TENANT,
        actor_kind="human",
        actor_id=str(sender),
        at=event.at,
        trace=trace_hex(event),
        write=write,
    )


async def _client_file_uploaded(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    """Claire's portal upload to a Feld request (POR-03 g; DEC-471), through `evidence.api`."""
    found = CLIENT_FILE_BY_KEY[str(event.data["file"])]
    sender = UUID(PERSON_BY_NAME[found.sender].id)
    item = _feld_request(str(event.data["request"]))
    stored = await stage_content(TENANT, found.content())
    async with uow(TenantContext(TENANT, "human", str(sender))) as tx:
        version = await add_version(
            tx,
            engagement_id=_feld_engagement(),
            item=NewItem(title=found.file_name),
            stored=stored,
            media_type=_PDF,
            provenance=Provenance(source="client_upload", method="uploaded"),
            requested_by=sender,
        )
        await fulfil_by_upload(tx, request_item_id=item, evidence_version_id=version.id)


async def _file_returned(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    """Kevin Osei's send-back of Claire's file (POR-03 g; DEC-471): the decision row as
    `evidence.decide` writes it, then the request moves to returned."""
    returned = FELD_RETURN
    item = _feld_request(FELD_1095C_REQUEST)
    engagement = _feld_engagement()
    kevin = user_id_of(_SEATS[returned.by])
    tenant = TenantContext(TENANT, "human", str(kevin))
    version = await latest_version_of(tenant, item)
    if version is None:
        raise LookupError("no upload to return")
    decision = UUID(stable_id(f"review-decision:{returned.file}"))
    async with uow(tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO review_decisions (id, tenant_id, engagement_id, "
                "evidence_version_id, request_item_id, decision, reason_code, note, "
                "corrects_proposal, actor_kind, actor_id, decision_seq, prior_item_statuses) "
                "VALUES (:id, :tenant, :engagement, :version, :item, 'send_back', :reason, "
                ":note, false, 'human', :actor, 1, CAST(:prior AS jsonb))"
            ),
            {
                "id": decision,
                "tenant": TENANT,
                "engagement": engagement,
                "version": version,
                "item": item,
                "reason": returned.reason_code,
                "note": returned.note,
                "actor": str(kevin),
                "prior": json.dumps({str(item): "uploaded"}),
            },
        )
        await move_after_review(tx, item, "returned")
        tx.record("review_decision.created", target=Target("review_decision", decision))


async def _engagement_files_uploaded(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """The SURL request's 31 files on the Granite Peak engagement, from Luis Ferrante (DEC-471),
    through `evidence.api` in one unit of work."""
    luis = UUID(_PORTAL[SURL_UPLOADED_BY].id)
    pbc = _PBC[SURL_DRAFT.list_key]
    engagement = engagement_id_of(BY_LABEL[pbc.engagement])
    staged = [(f.file_name, await stage_content(TENANT, f.content())) for f in SURL_FILES]
    async with uow(TenantContext(TENANT, "human", str(luis))) as tx:
        for name, stored in staged:
            await add_version(
                tx,
                engagement_id=engagement,
                item=NewItem(title=name),
                stored=stored,
                media_type=_PDF,
                provenance=Provenance(source="client_upload", method="uploaded"),
                requested_by=luis,
            )


async def _ebp_documents_uploaded(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    """A-05-T07: Northwind's EBP source documents (the adoption agreements, the 2024 amendment,
    the 2025 SPD, the census, the HR sample, the PayGrid register and the W-3) from Dana
    Kowalski, the plan administrator, through `evidence.api` in one unit of work."""
    dana = UUID(_PORTAL["Dana Kowalski"].id)
    engagement = engagement_id_of(BY_LABEL["A1"])
    staged = [(f, await stage_content(TENANT, f.content())) for f in EBP_FILES]
    async with uow(TenantContext(TENANT, "human", str(dana))) as tx:
        for file, stored in staged:
            await add_version(
                tx,
                engagement_id=engagement,
                item=NewItem(title=file.file_name),
                stored=stored,
                media_type=file.media_type,
                provenance=Provenance(source="client_upload", method="uploaded"),
                requested_by=dana,
            )


# --- the sampling slice (A-03-T16 part two; DEC-1767) --------------------------------------------
# Through the services as the people the design names: Margaret imports and publishes BH FS
# groupings v1; Dana uploads the census versions; Marcus builds each population, records its ties,
# creates the Participants set and draws with the scenario seeds (inline: the loader has no
# worker); Marcus prepares Version 2 and Hannah approves it, once Ana Cruz's confirmation meets
# Northwind's G2 (DEC-1767).

_SAMPLING_TIES: Final = {"register": sampling_content.REGISTER, "w3": sampling_content.W3}


async def _northwind_work_item(conn: asyncpg.Connection) -> tuple[UUID, UUID]:
    engagement = engagement_id_of(BY_LABEL["A1"])
    item = await tenant_value(
        conn,
        TENANT,
        "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
        engagement,
    )
    if item is None:
        raise LookupError("Northwind's assurance work item is audit_core's and is missing")
    return engagement, cast(UUID, item)


async def _grouping_set_imported(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    await import_grouping_csv(
        await _staff_context(conn, event),
        sampling_content.GROUPING_SET_KEY,
        sampling_content.GROUPING_SET_NAME,
        sampling_content.grouping_set_csv(),
    )


async def _grouping_set_published(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    version = await tenant_value(
        conn,
        TENANT,
        "SELECT v.id FROM grouping_set_versions v JOIN grouping_sets s "
        "ON s.id = v.grouping_set_id WHERE s.key = $1 ORDER BY v.version DESC LIMIT 1",
        sampling_content.GROUPING_SET_KEY,
    )
    await publish_grouping_version(
        await _staff_context(conn, event),
        cast(UUID, version),
        effective_from=event.at.astimezone(_CT).date(),
    )


async def _sampling_census_uploaded(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Dana Kowalski uploads the census: a new item for v1, its next version for v2."""
    census = int(cast(int, event.data["census"]))
    rows = sampling_content.census_v1() if census == 1 else sampling_content.census()
    dana = UUID(_PORTAL["Dana Kowalski"].id)
    engagement = (await _northwind_work_item(conn))[0]
    existing = await tenant_value(
        conn,
        TENANT,
        "SELECT id FROM evidence_items WHERE engagement_id = $1 AND title = $2",
        engagement,
        sampling_content.CENSUS_FILE,
    )
    stored = await stage_content(TENANT, sampling_content.census_xlsx(rows))
    async with uow(TenantContext(TENANT, "human", str(dana))) as tx:
        await add_version(
            tx,
            engagement_id=engagement,
            item=cast(UUID, existing) if existing else NewItem(title=sampling_content.CENSUS_FILE),
            stored=stored,
            media_type=_XLSX,
            provenance=Provenance(source="client_upload", method="uploaded"),
            requested_by=dana,
        )


async def _census_version(conn: asyncpg.Connection, census: int) -> UUID:
    engagement = (await _northwind_work_item(conn))[0]
    found = await tenant_value(
        conn,
        TENANT,
        "SELECT v.id FROM evidence_versions v JOIN evidence_items i ON i.id = v.evidence_item_id "
        "WHERE i.engagement_id = $1 AND i.title = $2 AND v.version_no = $3",
        engagement,
        sampling_content.CENSUS_FILE,
        census,
    )
    if found is None:
        raise LookupError(f"census v{census} has not been uploaded")
    return cast(UUID, found)


async def _population_of(conn: asyncpg.Connection, census: int) -> UUID:
    """The work item's populations in the order they were built: census v1's, then v2's."""
    item = (await _northwind_work_item(conn))[1]
    rows = await tenant_rows(
        conn,
        TENANT,
        "SELECT id FROM sample_populations WHERE work_item_id = $1 ORDER BY created_at, id",
        item,
    )
    return cast(UUID, rows[census - 1]["id"])


async def _participants_set(conn: asyncpg.Connection) -> UUID:
    item = (await _northwind_work_item(conn))[1]
    found = await tenant_value(
        conn,
        TENANT,
        "SELECT id FROM sample_sets WHERE work_item_id = $1 AND title = $2",
        item,
        SAMPLING_SET_TITLE,
    )
    return cast(UUID, found)


async def _population_built(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    census = int(cast(int, event.data["census"]))
    item = (await _northwind_work_item(conn))[1]
    await create_population(
        await _staff_context(conn, event),
        item,
        PopulationIn(
            source=UploadSourceIn(
                evidence_version_id=await _census_version(conn, census),
                column_map=dict(sampling_content.COLUMN_MAP),
            ),
            sampling_unit=sampling_content.SAMPLING_UNIT,
            deviation_definition=sampling_content.DEVIATION,
        ),
    )


async def _sampling_tie_recorded(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    census = int(cast(int, event.data["census"]))
    label, comparisons = _SAMPLING_TIES[str(event.data["tie"])]
    await record_tie(
        await _staff_context(conn, event),
        await _population_of(conn, census),
        TieIn(
            label=label,
            comparisons=[
                TieComparisonIn(label=name, amount=amount) for name, amount in comparisons
            ],
        ),
    )


async def _sample_set_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    item = (await _northwind_work_item(conn))[1]
    await create_sample_set(
        await _staff_context(conn, event),
        item,
        SampleSetIn(title=SAMPLING_SET_TITLE, purpose=SAMPLING_SET_PURPOSE),
    )


async def _sample_version_drawn(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Moderate RMM, 10 % tolerable, 0 % expected, 90 % confidence: Table 2 gives 25."""
    census = int(cast(int, event.data["census"]))
    await draw_sample(
        await _staff_context(conn, event),
        await _participants_set(conn),
        VersionIn(
            population_id=await _population_of(conn, census),
            method="attribute_nonstatistical",
            parameters=ParametersIn(
                rmm="moderate",
                tolerable_rate=Decimal("0.10"),
                expected_rate=Decimal("0"),
                confidence=Decimal("0.90"),
            ),
        ),
        scenario_seed=int(cast(int, event.data["seed"])),
    )


async def _sampling_independence_concluded(
    conn: asyncpg.Connection, _: Scenario, event: Event
) -> None:
    """Margaret concludes Northwind's independence once every team member has confirmed (G2)."""
    await conclude_independence(
        await _staff_context(conn, event), _a(event), option="independent", safeguards=None
    )


async def _sampling_contact_designated(
    conn: asyncpg.Connection, _: Scenario, event: Event
) -> None:
    """Margaret names the client's contact in the designation (Dana Kowalski, SKE designee)."""
    engagement = _a(event)
    contact = await tenant_value(
        conn,
        TENANT,
        "SELECT c.id FROM contacts c JOIN engagements e ON e.client_id = c.client_id "
        "WHERE e.id = $1 AND c.display_name = $2",
        engagement,
        str(event.data["contact"]),
    )
    if contact is None:
        raise LookupError(f"{event.data['contact']} is not a contact of the engagement's client")
    await designate_contact(
        await _staff_context(conn, event), engagement, cast(UUID, contact), "ske_designee"
    )


async def _sample_version_prepared(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Marcus signs L1 on the version he drew, on the content hash he sees (AUD-11 a)."""
    ctx = await _staff_context(conn, event)
    sample_set = await _participants_set(conn)
    view = await sample_set_view(ctx, sample_set, int(cast(int, event.data["version"])))
    version_id = await tenant_value(
        conn,
        TENANT,
        "SELECT id FROM sample_set_versions WHERE sample_set_id = $1 AND version_no = $2",
        sample_set,
        view.version_no,
    )
    await sign_target(
        ctx,
        "sample_set_version",
        cast(UUID, version_id),
        1,
        f"sha256:{view.content_hash}",
        SIGN_OFF_STATEMENTS[1].version,
    )


async def _sample_version_approved(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Hannah approves (L2), never the preparer; the earlier version is superseded."""
    ctx = await _staff_context(conn, event)
    sample_set = await _participants_set(conn)
    version = int(cast(int, event.data["version"]))
    view = await sample_set_view(ctx, sample_set, version)
    await approve_sample(ctx, sample_set, version, ApproveIn(seen_hash=str(view.content_hash)))


# --- service-backed events ---------------------------------------------------------------------


# The scenario's client kinds (CLI-01's words) in the record's vocabulary (organisations, 0082).
ClientKind = Literal["household", "business", "plan_sponsor", "nonprofit", "trust_family"]
CLIENT_KINDS: Final[dict[str, ClientKind]] = {
    "individual": "household",
    "household": "household",
    "business": "business",
    "partnership": "business",
    "exempt_org": "nonprofit",
    "trust": "trust_family",
    "estate": "trust_family",
    "plan": "plan_sponsor",
}
_AUDIT_ENTITIES: Final = frozenset(a.entity for a in AUDITS if a.entity is not None)


async def _client_created(_: asyncpg.Connection, scenario: Scenario, event: Event) -> None:
    """Through `organisations.api` under the relationship partner, as a person would. A client a
    holdout keeps in an earlier form (P-07-T50) is the scenario's, not the full roster's."""
    kept = {c.name: c for c in scenario.clients}
    client: Client = kept.get(str(event.client)) or _CLIENTS[str(event.client)]
    kind, actor = _actor(event)
    # F-04-T31: the ids the fixtures use (`client:<slug>` and `entityIdOf` in the TS seed), so the
    # exported fixtures and the TS seed name the same client.
    ids = NewClient(
        UUID(stable_id(f"client:{client.slug}")),
        UUID(entity_id_of(client.slug, client.entities[0])),
    )
    async with uow(TenantContext(TENANT, kind, actor)) as tx:  # type: ignore[arg-type]  # "human" or "system"
        await create_client(tx, TENANT, client.name, client.entities[0], ids=ids)
        # TASK-393 (F-04-T29): the record's facts as clients.json gives them; attest is derived
        # from the client's engagements (DEC-128), never set.
        await set_client_record(
            tx,
            ids.client_id,
            ClientRecordChange(
                kind=CLIENT_KINDS[client.kind],
                primary_office_id=office_id_of(client.office),
                relationship_partner_id=user_id_of(_SEATS[client.partner]),
                portal_status=client.portal,
            ),
        )
        # Further entities, except the plan entities the audit slice adds with their audits.
        for entity in client.entities[1:]:
            if entity in _AUDIT_ENTITIES:
                continue
            await client_with_entity(
                tx,
                TENANT,
                ids.client_id,
                None,
                entity,
                new_entity_id=UUID(entity_id_of(client.slug, entity)),
            )


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
        found = await tenant_row(
            conn,
            TENANT,
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
    # As the tenant: the owner role does not bypass row-level security on staging (DEC-455).
    async with as_tenant(conn, TENANT):
        role = await conn.fetchval(
            "SELECT firm_role FROM memberships WHERE tenant_id = $1 AND user_id = $2", TENANT, user
        )
    return AuthContext(
        TenantContext(TENANT, "human", str(user)), user, UUID(int=0), role, system_now()
    )


async def _email_template_draft(conn: asyncpg.Connection, event: Event) -> AuthContext:
    """R-01-T22: Grace saves the template's handoff copy as the draft, through the editor."""
    ctx = await _staff_context(conn, event)
    key = str(event.data["key"])
    content = TemplateContent.from_json(cast(dict[str, object], event.data["content"]))
    state = await email_template_state(ctx, key)
    expected = state.draft.draft_version if state.draft is not None else 0
    await save_email_template_draft(ctx, key, content, expected)
    return ctx


async def _email_template_draft_saved(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    await _email_template_draft(conn, event)


async def _email_template_published(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    ctx = await _email_template_draft(conn, event)
    await publish_email_template(ctx, str(event.data["key"]), source="handoff_seed")


async def _flag_set(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    await set_flag(TENANT, str(event.data["flag"]), "true", LOADER, "Brightwater Hale scenario")


async def _methodology_imported(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """K-01-T10: the version's workbook through `methodology.api`, as a firm admin imports it."""
    data = event.data
    spec = methodology_spec(str(data["family"]), int(cast(int, data["number"])))
    await import_template(
        await _staff_context(conn, event),
        spec.name,
        methodology_workbook(spec),
        engagement_types=(cast(EngagementType, spec.engagement_type),),
        family=cast(Literal["ebp", "fs", "ssars"], spec.family),
    )


async def _methodology_approved(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """K-01-T10: the QM owner approves what she reviewed, with its effective date (K-01-T06)."""
    data = event.data
    version_id = await tenant_value(
        conn,
        TENANT,
        "SELECT v.id FROM methodology_versions v JOIN methodology_templates t "
        "ON t.id = v.template_id WHERE t.name = $1 AND v.version = $2",
        str(data["name"]),
        int(cast(int, data["number"])),
    )
    ctx = await _staff_context(conn, event)
    state = await methodology_version_state(ctx, cast(UUID, version_id))
    await approve_methodology_version(
        ctx,
        cast(UUID, version_id),
        effective_from=date.fromisoformat(str(data["effective_from"])),
        checklist_hash=state.checklist_hash,
        row_version=state.row_version,
    )


async def _pilot_enrolled(_: asyncpg.Connection, __: Scenario, event: Event) -> None:
    """TASK-2470 (DEC-1530): PF-X1's enrolment through `make pilot-enrol`'s service, in shadow."""
    data = event.data
    target = str(data["target"])
    item = (
        _return_item(target)
        if data["kind"] == "return"
        else await _assurance_work_item(BY_LABEL[target])
    )
    await enrol_pilot(
        TenantContext(TENANT, "system", LOADER),
        item,
        date.fromisoformat(str(data["window_start"])),
        date.fromisoformat(str(data["window_end"])),
        int(str(data["baseline_days"])),
        UUID(str(data["operator"])),
    )


async def _standard_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """K-02-T18: Margaret creates the standard and names its owner (`firm_standard.create`)."""
    data = event.data
    await create_standard(
        await _staff_context(conn, event),
        key=str(data["key"]),
        name=str(data["name"]),
        kind=str(data["kind"]),
        owner_id=user_id_of(_SEATS[str(data["owner"])]),
    )


async def _standard_payload(conn: asyncpg.Connection, key: str, version: int) -> dict[str, object]:
    """The version's payload; BH-TAX-02 names its clients and Daniel Reyes by id here."""
    if key != "bh-tax-02":
        return payload_of(standard_spec(key), version)
    signer = user_id_of(_SEATS["DR"])
    applies: list[dict[str, object]] = []
    for name in BH_TAX_02_CLIENTS:
        client = await tenant_value(
            conn, TENANT, "SELECT id FROM clients WHERE tenant_id = $1 AND name = $2", TENANT, name
        )
        if client is None:
            raise LookupError(f"BH-TAX-02 names {name}, which the scenario has not created")
        applies.append({"client_id": str(client), "approver_user_id": str(signer)})
    return {
        "kind": "return_approval_policy",
        "code": "BH-TAX-02",
        "rule": "signing_partner_final_approval",
        "applies_to": applies,
        "export_condition": "after_final_approval",
    }


async def _standard_imported(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """K-02-T18: the version's workbook through the import endpoint's path, as a draft."""
    data = event.data
    key = str(data["key"])
    ctx = await _staff_context(conn, event)
    standard = await standard_by_key(ctx, key)
    payload = await _standard_payload(conn, key, int(cast(int, data["version"])))
    await import_standard_workbook(
        ctx, standard.id, standard_workbook(standard.kind, standard.name, payload)
    )


async def _standard_published(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """K-02-T18: the owner publishes the draft, effective the day they publish it."""
    data = event.data
    ctx = await _staff_context(conn, event)
    standard = await standard_by_key(ctx, str(data["key"]))
    await publish_standard(
        ctx,
        standard.id,
        effective_from=event.at.astimezone(_CT).date(),
        change_summary=f"Version {int(cast(int, data['version']))}",
    )


async def _report_template_imported(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """P-11-T13: the bundle through C11's import, as a firm admin imports it (a draft version)."""
    body = TemplateImportIn.model_validate(report_template_bundle(str(event.data["name"])))
    report = await import_template_bundle(await _staff_context(conn, event), body, dry_run=False)
    if not report.ok:
        raise RuntimeError(f"template {body.name} refused: {report.errors}")


async def _report_template_published(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """P-11-T13: the partner publishes the version Grace imported (fresh MFA, four eyes)."""
    row = await tenant_row(
        conn,
        TENANT,
        "SELECT t.id, v.version_no FROM report_templates t JOIN report_template_versions v "
        "ON v.template_id = t.id WHERE t.name = $1 ORDER BY v.version_no DESC LIMIT 1",
        str(event.data["name"]),
    )
    if row is None:
        raise RuntimeError(f"template {event.data['name']} was not imported")
    await publish_template(
        await _staff_context(conn, event), cast(UUID, row["id"]), int(row["version_no"])
    )


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


async def _connection_seeded(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """A-02-T27: one of Copperleaf's connections at its POR-16a state (fake providers only)."""
    data = event.data
    client = await _client_id(conn, str(event.client))
    last_sync = data["last_sync_at"]
    await seed_synthetic_connection(
        TENANT,
        client_entity_id=await _entity_id(conn, client, str(data["entity"])),
        provider=str(data["provider"]),
        category=str(data["category"]),
        display_label=str(data["label"]),
        status=str(data["status"]),
        reason=None if data["reason"] is None else str(data["reason"]),
        connected_by_user_id=UUID(stable_id(f"user:{slug_of(str(data['connected_by']))}")),
        connected_at=datetime.fromisoformat(str(data["connected_at"])),
        last_sync_at=None if last_sync is None else datetime.fromisoformat(str(last_sync)),
    )


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


# --- the firm_inbox slice (N-01-T11; DEC-836) ----------------------------------------------------
# The Intake team is a bootstrap write (no team service is exported); every docs@ message goes
# through the intake service as the transport would deliver it, every file through
# `add_attachment` (scanned, stored write-once). W0's ignored file is a bootstrap status write
# (no ignore service before N-01-T15); W0's filed files wait for a filing service (DEC-836).


async def _intake_team_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    name = str(event.data["name"])
    members = [user_id_of(_SEATS[str(i)]) for i in cast(list[str], event.data["members"])]

    async def write() -> tuple[str, str, str]:
        team = team_id_of(name)
        await conn.execute(
            "INSERT INTO teams (id, tenant_id, name, kind) VALUES ($1, $2, $3, 'intake') "
            "ON CONFLICT DO NOTHING",
            team,
            TENANT,
            name,
        )
        for user in members:
            await conn.execute(
                "INSERT INTO team_rosters (tenant_id, team_id, user_id) SELECT $1, $2, $3 "
                "WHERE NOT EXISTS (SELECT 1 FROM team_rosters WHERE tenant_id = $1 "
                "AND team_id = $2 AND user_id = $3)",
                TENANT,
                team,
                user,
            )
        return "team.created", "team", str(team)

    await _bootstrap(conn, event, write)


def _synthetic_file(name: str) -> bytes:
    """A small synthetic PDF per file name (no real document is ever loaded)."""
    return f"%PDF-1.4\n% Brightwater Hale scenario file: {name}\n%%EOF\n".encode()


async def _inbound_email_recorded(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    data = event.data
    client = data["client"]
    tenant = TenantContext(TENANT, "system", "transport:docs@")
    recorded = await record_inbound_message(
        tenant,
        Inbound(
            channel="email",
            sender_display=str(data["sender"]),
            subject=str(data["subject"]),
            received_at=datetime.fromisoformat(str(data["received_at"])),
            body=None if data["body"] is None else str(data["body"]),
            sender_address=str(data["sender"]),
            internet_message_id=str(data["internet_message_id"]),
            in_reply_to=None if data["in_reply_to"] is None else str(data["in_reply_to"]),
            client_id=None if client is None else await _client_id(conn, str(client)),
            # A named client is a staff match, so it names who matched (Grace, DEC-836).
            logged_by=None if client is None else user_id_of(_SEATS[INBOX_TRIAGER]),
            received_via="email",
            source_display="docs@",
        ),
    )
    for attachment in cast(list[dict[str, str]], data["attachments"]):
        if attachment["state"] == "filed":
            continue  # DEC-836: a filed row needs its evidence version (N-01-T15's filing)
        received = await add_attachment(
            tenant,
            recorded.message_id,
            file_name=attachment["name"],
            content=_synthetic_file(attachment["name"]),
        )
        if attachment["state"] == "ignored":

            async def ignore(found: UUID = received.attachment_id) -> tuple[str, str, str]:
                await conn.execute(
                    "UPDATE inbox_attachments SET status = 'ignored' WHERE id = $1", found
                )
                return "inbox_attachment.ignored", "inbox_attachment", str(found)

            await _bootstrap(conn, event, ignore)


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
    row = await tenant_row(
        conn,
        TENANT,
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
        entity = cast(
            UUID | None,
            await tenant_value(
                conn,
                TENANT,
                "SELECT client_entity_id FROM engagements WHERE tenant_id = $1 AND id = $2",
                TENANT,
                prior,
            ),
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
        step=str(payload.get("step", "team_independence")),  # P-07-T50: ENG-03 a, d at step 1
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
    if data["clear"] is None:  # P-07-T50: CLI-06 h's hit, left for a person's assessment
        return
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
    documents; the fee section is answered, not a manual check: DEC-412); CLI-07 f's for Meridian
    (P-07-T50)."""
    ctx = await _staff_context(conn, event)
    engagement = await _prospect(conn, event)
    rating = str(event.data["risk_rating"])
    answers, flags = PREPARED[str(event.data["draft"])]
    for n, (section, summary) in enumerate(answers):
        await update_answers(
            ctx,
            engagement,
            section,
            seen_version=0,
            values={"summary": summary},
            complete=True,
            risk_rating=rating if n == 0 else None,
        )
    for severity, title, body in flags:
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


# --- N-02-T36 (`--slice signatures`): the ERSD disclosure, then SIG-01's envelopes at E0 ---------


async def _disclosure_imported(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    async def write() -> tuple[str, str, str]:
        disclosure = UUID(stable_id("esign-disclosure:v1"))
        await conn.execute(
            "INSERT INTO esign_disclosures (id, tenant_id, version_no, body, body_sha256, "
            "imported_by, imported_at) VALUES ($1, $2, 1, $3, $4, $5, $6) "
            "ON CONFLICT (id) DO NOTHING",
            disclosure,
            TENANT,
            ERSD_BODY,
            hashlib.sha256(ERSD_BODY.encode()).hexdigest(),
            user_id_of(_SEATS["GH"]),
            event.at,
        )
        return "esign_disclosure.imported", "esign_disclosure", str(disclosure)

    await _bootstrap(conn, event, write)


def _identity(e: HubEnvelope, firm: bool) -> str:
    if firm:
        return "firm_sso"
    return "kba" if e.policy_family == "efile_authorization" else "email_code"


async def _envelope_signer(
    conn: asyncpg.Connection, e: HubEnvelope, client: UUID, envelope: UUID, n: int
) -> UUID:
    s = e.signers[n]
    signer = UUID(stable_id(f"envelope-signer:{e.key}:{n}"))
    contact: UUID | None = None
    user: UUID | None = None
    if s.firm:
        user = user_id_of(_SEATS[s.name])
    else:
        contact = UUID(stable_id(f"contact:envelope:{e.scenario_client}:{s.name}"))
        await conn.execute(
            "INSERT INTO contacts (id, tenant_id, client_id, display_name, contact_kind) "
            "VALUES ($1, $2, $3, $4, 'client_person') ON CONFLICT (id) DO NOTHING",
            contact,
            TENANT,
            client,
            s.name,
        )
    status = "signed" if s.signed else "verification_failed" if s.kba_locked else "pending"
    first_view = _at(e.viewed, 10) if n == 0 else None
    await conn.execute(
        'INSERT INTO envelope_signers (id, tenant_id, envelope_id, "order", routing_group, '
        "party_kind, contact_id, user_id, role, identity_method, status, kba_failures, "
        "viewed_at, signed_at, signature_method) VALUES ($1, $2, $3, $4, $4, $5, $6, $7, $8, "
        "$9, $10, $11, $12, $13, $14) ON CONFLICT (id) DO NOTHING",
        signer,
        TENANT,
        envelope,
        n + 1,
        "user" if s.firm else "contact",
        contact,
        user,
        "countersigner" if s.firm else "signer",
        _identity(e, s.firm),
        status,
        3 if s.kba_locked else 0,
        _at(s.signed_on, 10) or first_view,
        _at(s.signed_on, 11),
        "provider_adopted" if s.signed else None,
    )
    return signer


async def _envelope_event(
    conn: asyncpg.Connection,
    envelope: UUID,
    kind: str,
    when: datetime,
    source: str,
    signer: UUID | None = None,
) -> None:
    await conn.execute(
        "INSERT INTO envelope_events (id, tenant_id, envelope_id, signer_id, kind, source, "
        "occurred_at) VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO NOTHING",
        UUID(stable_id(f"envelope-event:{envelope}:{kind}:{signer}:{when.isoformat()}")),
        TENANT,
        envelope,
        signer,
        kind,
        source,
        when,
    )


async def _envelope_timeline(
    conn: asyncpg.Connection, e: HubEnvelope, envelope: UUID, signers: list[UUID]
) -> None:
    """The envelope's events as the provider and the firm would have written them."""
    sent = _at(e.sent)
    if sent is not None:
        await _envelope_event(conn, envelope, "envelope.sent", sent, "firm")
    viewed = _at(e.viewed, 10)
    if viewed is not None and signers:
        await _envelope_event(
            conn, envelope, "signer.viewed", viewed, "provider_webhook", signers[0]
        )
    for n, s in enumerate(e.signers):
        signed = _at(s.signed_on, 11)
        if signed is not None:
            await _envelope_event(
                conn, envelope, "signer.signed", signed, "provider_webhook", signers[n]
            )
        if s.kba_locked:  # Irene Kowal, Sun Sep 13, 8:06 to 8:14 PM
            for failed in KOWAL_FAILURES:
                await _envelope_event(
                    conn,
                    envelope,
                    "signer.verification_failed",
                    failed,
                    "provider_webhook",
                    signers[n],
                )
    completed = _at(e.completed, 12)
    if completed is not None:
        await _envelope_event(conn, envelope, "envelope.completed", completed, "provider_webhook")
    expired = _at(e.expired, 23, 59)
    if expired is not None:
        await _envelope_event(conn, envelope, "envelope.expired", expired, "system")


async def _envelope_recorded(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    e = ENVELOPE_BY_KEY[str(event.data["key"])]
    client = await _client_id(conn, e.scenario_client)
    # The client's engagement, where it has one (visible() reads an envelope through it).
    engagement = await tenant_value(
        conn,
        TENANT,
        "SELECT id FROM engagements WHERE tenant_id = $1 AND client_id = $2 "
        "ORDER BY created_at, id LIMIT 1",
        TENANT,
        client,
    )
    grace = user_id_of(_SEATS["GH"])
    envelope = UUID(e.id)

    async def write() -> tuple[str, str, str]:
        number = ENVELOPE_NUMBERS[e.key]
        agent = e.drafted_by == "agent"
        sent_at = _at(e.sent)
        await conn.execute(
            "INSERT INTO envelopes (id, tenant_id, number, purpose, form_code, policy_family, "
            "client_id, title, provider, status, signer_order, due_on, expires_at, "
            "drafted_by_kind, drafted_by, drafted_via_run_id, sent_by, sent_at, completed_at, "
            "created_at, updated_at, engagement_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, "
            "'fake', $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $19, $20) "
            "ON CONFLICT (id) DO NOTHING",
            envelope,
            TENANT,
            number,
            e.stored_purpose,
            e.form_code,
            e.policy_family,
            client,
            e.title,
            e.status,
            "parallel" if e.policy_family == "efile_authorization" else "sequential",
            e.due,
            _at(e.expired, 23, 59),
            "agent" if agent else "human",
            None if agent else grace,
            UUID(stable_id(f"agent-run:{e.key}")) if agent else None,
            None if sent_at is None else grace,
            sent_at,
            _at(e.completed, 12),
            event.at,
            engagement,
        )
        signers = [
            await _envelope_signer(conn, e, client, envelope, n) for n in range(len(e.signers))
        ]
        await _envelope_timeline(conn, e, envelope, signers)
        return "envelope.recorded", "envelope", str(envelope)

    await _bootstrap(conn, event, write)


Handler = Callable[[asyncpg.Connection, Scenario, Event], Awaitable[None]]

# --- T-02-T23 (`--slice tax_content`): K-1 sets and POR-05's questions -----------------------


def _return_item(client: str) -> UUID:
    """The client's 2025 return (its first part)."""
    found = next((r for r in RETURN_BY_LABEL.values() if r.client == client), None)
    if found is None:
        raise LookupError(f"no 2025 return for {client!r}")
    return UUID(found.id)


def _recipient(event: Event) -> tuple[K1Set, K1Recipient]:
    k1_set = set_of(str(event.data["client"]))
    ref = str(event.data["ref"])
    return k1_set, next(r for r in k1_set.recipients if r.ref == ref)


def _k1_pdf(k1_set: K1Set, recipient: K1Recipient) -> bytes:
    lines = [
        f"Schedule K-1 (Form {k1_set.form.upper()}) 2025",
        k1_set.client,
        f"Recipient: {recipient.name}",
        *(f"Box {b.code} {b.description} {b.amount}" for b in recipient.boxes),
    ]
    return positioned_pdf([[(50.0, 740.0 - 14 * i, line) for i, line in enumerate(lines)]])


async def _k1_contact_created(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """A recipient's delivery contact on the issuing client, named as TXP-12 names it."""
    k1_set, recipient = _recipient(event)
    client = await _client_id(conn, k1_set.client)
    await create_contact(
        await _staff_context(conn, event),
        client,
        name=recipient.contact,
        party_kind="person",
        email=contact_email(recipient.contact),
        phone=None,
        roles=[],
    )


async def _contact_of(conn: asyncpg.Connection, client: str, name: str) -> UUID:
    found = await tenant_value(
        conn,
        TENANT,
        "SELECT c.id FROM contacts c JOIN clients k ON k.id = c.client_id "
        "WHERE c.tenant_id = $1 AND k.name = $2 AND c.display_name = $3",
        TENANT,
        client,
        name,
    )
    if found is None:
        raise LookupError(f"no contact {name!r} on {client!r}")
    return cast(UUID, found)


async def _k1_portal_person_added(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """POR-13's people: a client user whose contact is active, as an accepted invitation leaves
    it (`organisations.activate_contact`), so a release grants them `k1_recipient` at once."""
    name = str(event.data["contact"])
    contact = await _contact_of(conn, str(event.data["client"]), name)
    user = UUID(stable_id(f"user:k1:{name}"))
    async with as_tenant(conn, TENANT):
        await conn.execute(
            "INSERT INTO users (id, idp_issuer, idp_subject, email, display_name) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            user,
            ISSUER,
            f"scenario-k1-{stable_id(name)}",
            contact_email(name),
            name,
        )
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id, status, kind) "
            "VALUES ($1, $2, 'active', 'client') ON CONFLICT DO NOTHING",
            TENANT,
            user,
        )
    async with uow(TenantContext(TENANT, "system", LOADER)) as tx:
        await activate_contact(tx, contact, user)


async def _engine_pdf_imported(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """The engine's K-1 PDF through the bridge (`pdfs`), a person's upload."""
    k1_set, recipient = _recipient(event)
    await import_engine_file(
        await _staff_context(conn, event),
        _return_item(k1_set.client),
        "pdfs",
        k1_set.pdf_name(recipient),
        _k1_pdf(k1_set, recipient),
    )


async def _k1_set_imported(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """The K-1 set through the bridge's `k1_set` import (T-02-T20); each delivery contact named."""
    k1_set = set_of(str(event.data["client"]))
    ctx = await _staff_context(conn, event)
    item = _return_item(k1_set.client)
    await import_engine_file(
        ctx,
        item,
        "k1_set",
        f"{k1_set.engine_return_id.replace(':', '_')}_k1_set.json",
        k1_set.manifest(),
    )
    for recipient in k1_set.recipients:
        contact = await _contact_of(conn, k1_set.client, recipient.contact)
        # No route names a recipient's contact before a release (TXP-12's picker is T-02-T25):
        # the loader links the contact it created, the one the release delivers to.
        async with as_tenant(conn, TENANT):
            await conn.execute(
                "UPDATE k1_recipients SET contact_id = $3 WHERE tenant_id = $1 "
                "AND work_item_id = $2 AND engine_ref = $4 AND contact_id IS NULL",
                TENANT,
                item,
                contact,
                recipient.ref,
            )


async def _k1_shared(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Samuel shares a partner's draft with their own 1040 (DEC-88), as TXP-12's share does."""
    k1_set = set_of(str(event.data["client"]))
    item = _return_item(k1_set.client)
    package = await tenant_value(
        conn,
        TENANT,
        "SELECT p.id FROM k1_packages p JOIN k1_recipients r ON r.id = p.recipient_id "
        "WHERE p.tenant_id = $1 AND p.work_item_id = $2 AND r.engine_ref = $3 "
        "AND p.status = 'draft' ORDER BY p.version_no DESC LIMIT 1",
        TENANT,
        item,
        str(event.data["ref"]),
    )
    if package is None:
        raise LookupError(f"no draft K-1 for {event.data['ref']}")
    # The sharer is the issuing return's manager reviewer: team membership and functions are
    # scenario structure, seeded as the tax board seeds its preparer and reviewer
    # (`k1_package.share_internal` is a manager's or partner's, with one of its functions).
    ret = next(r for r in RETURN_BY_LABEL.values() if r.client == k1_set.client)
    async with as_tenant(conn, TENANT):
        await conn.execute(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, 'manager') ON CONFLICT (tenant_id, engagement_id, user_id) "
            "DO UPDATE SET role = 'manager'",  # the board seeded him as the reviewer
            TENANT,
            UUID(ENGAGEMENT_BY_LABEL[ret.engagement].id),
            user_id_of(_SEATS[event.actor]),
        )
        await conn.execute(
            "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, "
            "user_id, function, assigned_by) SELECT $1, $2, $3, $4, 'manager_reviewer', $4 "
            "WHERE NOT EXISTS (SELECT 1 FROM work_item_assignments WHERE tenant_id = $1 "
            "AND work_item_id = $2 AND function = 'manager_reviewer' AND removed_at IS NULL)",
            TENANT,
            item,
            UUID(ENGAGEMENT_BY_LABEL[ret.engagement].id),
            user_id_of(_SEATS[event.actor]),
        )
    await share_k1_internal(
        await _staff_context(conn, event),
        item,
        [cast(UUID, package)],
        [_return_item(str(event.data["target"]))],
    )


async def _organizer_imported(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Grace imports the firm's organizer template (T-02-T16's CSV), a draft version."""
    await import_questionnaire_template(
        await _staff_context(conn, event), ORGANIZER_NAME, organizer_csv(), "csv", dry_run=False
    )


async def _organizer_template(ctx: AuthContext) -> tuple[UUID, int]:
    """The organizer template and the version to publish (its draft, else the current one)."""
    found = next(t for t in await questionnaire_templates(ctx) if t.name == ORGANIZER_NAME)
    return found.id, int(found.draft_version or found.current_version or 1)


async def _organizer_published(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Daniel Reyes publishes it (`questionnaire_template.publish`, fresh second factor)."""
    ctx = await _staff_context(conn, event)
    template, version = await _organizer_template(ctx)
    await publish_questionnaire_template(ctx, template, version)


async def _binder_of(conn: asyncpg.Connection, item: UUID) -> UUID:
    found = await tenant_value(
        conn,
        TENANT,
        "SELECT id FROM request_lists WHERE tenant_id = $1 AND work_item_id = $2 "
        "ORDER BY created_at DESC LIMIT 1",
        TENANT,
        item,
    )
    if found is None:
        raise LookupError(f"no binder on {item}")
    return cast(UUID, found)


async def _organizer_attached(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Kevin attaches the published organizer to the Feld 2025 Binder."""
    ctx = await _staff_context(conn, event)
    template, _version = await _organizer_template(ctx)
    version_id = await tenant_value(
        conn,
        TENANT,
        "SELECT id FROM questionnaire_template_versions WHERE tenant_id = $1 "
        "AND template_id = $2 AND published_at IS NOT NULL ORDER BY version DESC LIMIT 1",
        TENANT,
        template,
    )
    if version_id is None:
        raise LookupError("the organizer is not published")
    binder = await _binder_of(conn, _return_item(str(event.data["client"])))
    await attach_organizer(ctx, binder, cast(UUID, version_id), None)


async def _portal_context(conn: asyncpg.Connection, name: str) -> AuthContext:
    """A portal person signed in with their second step (the portal's MFA floor)."""
    person = PERSON_BY_NAME[name]
    user = UUID(person.id)
    async with as_tenant(conn, TENANT):
        membership = await conn.fetchval(
            "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2", TENANT, user
        )
    return AuthContext(
        TenantContext(TENANT, "human", str(user)),
        user,
        cast(UUID, membership),
        None,
        system_now(),
        client=True,
        portal_second_step=True,
    )


async def _organizer_answered(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """Claire Feld answers one organizer question in the portal (POR-05: 22 of 24)."""
    question = next(q for q in ORGANIZER if q.key == str(event.data["key"]))
    feld = _return_item("Jonah & Claire Feld")
    row = await tenant_row(
        conn,
        TENANT,
        "SELECT x.id, x.questionnaire_id FROM questions x JOIN questionnaires q "
        "ON q.id = x.questionnaire_id WHERE q.tenant_id = $1 AND q.work_item_id = $2 "
        "AND q.kind = 'organizer' AND x.client_wording = $3",
        TENANT,
        feld,
        question.wording,
    )
    if row is None:
        raise LookupError(f"no organizer question {question.key}")
    await save_portal_answer(
        await _portal_context(conn, str(event.data.get("person", ANSWERED_BY))),
        cast(UUID, row["questionnaire_id"]),
        cast(UUID, row["id"]),
        question.answer,
        1,
    )


async def _audit_item(conn: asyncpg.Connection, client: str) -> UUID:
    audit = next(a for a in AUDITS if a.client == client)
    found = await tenant_value(
        conn,
        TENANT,
        "SELECT id FROM work_items WHERE tenant_id = $1 AND engagement_id = $2 "
        "ORDER BY created_at LIMIT 1",
        TENANT,
        engagement_id_of(audit),
    )
    if found is None:
        raise LookupError(f"no audit work item for {client!r}")
    return cast(UUID, found)


async def _questions_sent(conn: asyncpg.Connection, _: Scenario, event: Event) -> None:
    """A person's team questions or inquiry: created, each question drafted, then sent."""
    ask = ask_of(str(event.data["label"]))
    ctx = await _staff_context(conn, event)
    item = (
        _return_item(ask.client) if ask.work == "return" else await _audit_item(conn, ask.client)
    )
    addressee = (
        await _contact_of(conn, ask.client, ask.addressee) if ask.addressee is not None else None
    )
    made = await create_questionnaire(
        ctx,
        kind=ask.kind,
        work_item_id=item,
        title=ask.title,
        addressed_to_contact_id=addressee,
        due_on=date.fromisoformat(ask.due) if ask.due is not None else None,
    )
    for wording, help_text in ask.questions:
        drafted = await draft_question(
            ctx,
            made.id,
            section=ask.title,
            type_="yes_no" if ask.work == "return" else "long_text",
            client_wording=wording,
            help_text=help_text or None,
            linked_request_item_id=None,
        )
        await send_question(ctx, drafted.id)


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
    # T-02-T11 (`--slice tax_board`, after `binders`): each return's board state and people.
    "tax.return_board_set": _return_board_set,
    "organisations.consent_recorded": _consent_recorded,
    # N-02-T36 (`--slice signatures`): the ERSD disclosure, then SIG-01's envelopes.
    "signatures.disclosure_imported": _disclosure_imported,
    "signatures.envelope_recorded": _envelope_recorded,
    "engagements.close_engagement_created": _close_engagement_created,
    "requests.binder_created": _binder_created,
    # P-06-T08 remainder: Granite Peak's agent-drafted SURL request, after its PBC list.
    "requests.request_drafted": _request_drafted,
    "evidence.engagement_files_uploaded": _engagement_files_uploaded,
    "evidence.ebp_documents_uploaded": _ebp_documents_uploaded,  # A-05-T07
    # A-03-T16 part two (DEC-1767): the sampling slice.
    "ledger.grouping_set_imported": _grouping_set_imported,
    "ledger.grouping_set_published": _grouping_set_published,
    "evidence.sampling_census_uploaded": _sampling_census_uploaded,
    "sampling.population_built": _population_built,
    "sampling.tie_recorded": _sampling_tie_recorded,
    "sampling.sample_set_created": _sample_set_created,
    "sampling.version_drawn": _sample_version_drawn,
    "engagements.independence_concluded": _sampling_independence_concluded,
    "engagements.contact_designated": _sampling_contact_designated,
    "sampling.version_prepared": _sample_version_prepared,
    "sampling.version_approved": _sample_version_approved,
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
    # A-02-T27 (`--slice connections`): Copperleaf's POR-16a connections.
    "connections.connection_seeded": _connection_seeded,
    "organisations.intake_team_created": _intake_team_created,  # N-01-T11
    "communications.inbound_email_recorded": _inbound_email_recorded,  # N-01-T11
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
    # R-01-T22 (`--slice email_templates`): the editor flag (above), then versions, then drafts.
    "communications.email_template_published": _email_template_published,
    "communications.email_template_draft_saved": _email_template_draft_saved,
    # R-01-T11 (`--slice portal_pbc`): Dana's titles and binder name (DEC-348), the delegations,
    # Claire's 9:12 AM email; `--slice portal_pbc_returned`: the 2024 upload and its return.
    "requests.item_retitled": _item_retitled,
    "requests.list_named": _list_named,
    "requests.items_delegated": _items_delegated,
    "evidence.inbox_file_added": _inbox_file_added,
    "evidence.client_file_uploaded": _client_file_uploaded,
    "evidence.file_returned": _file_returned,
    # K-01-T10 (`--slice methodology`): each version imported, then approved in label order.
    "methodology.version_imported": _methodology_imported,
    "methodology.version_approved": _methodology_approved,
    "standards.created": _standard_created,  # K-02-T18
    "platform.pilot_enrolled": _pilot_enrolled,  # TASK-2470
    "standards.version_imported": _standard_imported,
    "standards.version_published": _standard_published,
    "reporting.template_imported": _report_template_imported,
    "reporting.template_published": _report_template_published,
    # T-02-T23 (`--slice tax_content`): contacts and portal people, the engine's PDFs, then each
    # K-1 set and the shares; the organizer imported, published, attached and answered; asks.
    "tax.k1_contact_created": _k1_contact_created,
    "tax.k1_portal_person_added": _k1_portal_person_added,
    "tax.engine_pdf_imported": _engine_pdf_imported,
    "tax.k1_set_imported": _k1_set_imported,
    "tax.k1_shared": _k1_shared,
    "requests.organizer_imported": _organizer_imported,
    "requests.organizer_published": _organizer_published,
    "requests.organizer_attached": _organizer_attached,
    "requests.organizer_answered": _organizer_answered,
    "requests.questions_sent": _questions_sent,
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


# The events that bootstrap a firm row: on staging each firm needs its tenant key next (DEC-1012).
FIRM_KINDS: Final = frozenset({"identity.firm_created", "identity.sandbox_firm_created"})


async def ensure_tenant_key(tenant: UUID, *, timeout: float = KEY_SECONDS) -> str:
    """DEC-1012: start (or attach to) the firm's `TenantKeyWorkflow` and wait for its verified key.

    Provisioning starts that workflow (Q-01-T27); the loader bootstraps the firm without
    provisioning, so on staging, where every sealed write needs the firm's KMS key, it asks for
    the key itself. A run that already completed is not started again: its result is the key."""
    workflow_id = tenant_key_workflow_id(str(tenant))
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            TenantKeyWorkflow,
            TenantKeyInput(str(tenant), LOADER),
            id=workflow_id,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
    handle = (await temporal_client()).get_workflow_handle(workflow_id)
    try:
        return str(await asyncio.wait_for(handle.result(), timeout))
    except TimeoutError:
        raise KeyTimeout(f"the tenant key was not verified within {timeout:.0f}s") from None


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
            else:
                with frozen(event.at), _traced(event):
                    await handler(conn, scenario, event)
                replayed += 1
                if wait:
                    await settle(conn)
            # A firm loaded by an earlier run may still lack its key, so this runs either way.
            if staging and event.kind in FIRM_KINDS:
                await ensure_tenant_key(tenant_of(event))
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
    except (LoadRefused, SchemaPending, KeyTimeout) as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1
    print(
        f"Brightwater Hale {SCENARIO_VERSION} at {args.snapshot}: "
        f"{result.replayed} event(s) replayed, {result.skipped} already loaded"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
