"""Governance communications (A-07-T26; A-07 F4; SPEC-644; AU-C 260, 265, 703; DEC-83, DEC-93,
DEC-3011). PROTECTED (amber).

AUD-22's service over A-07-T08's tables (0668):

- **Kinds**: `planning_260` and `completion_260` (AU-C 260), `sd_mw_265` (AU-C 265, combined with
  AU-C 703's reportable findings in one letter, so a `reportable_703` row never stands alone) and
  `management_letter`. One communication per kind and work item.
- **Sections** are composed by code from the engagement's facts: the risk register (significant
  risks), the findings and their concluded deficiencies, and the service organisations. Each
  section records what it was built from (`built_from`: risk codes, finding refs, service
  organisation ids) for AUD-22's "Built from" chips; it carries no amount (code computes, the
  letter words; ADR-050).
- **Regenerate** composes again with a section-level merge: a section a person edited keeps their
  text; every other section takes the new facts. Every compose or edit is a new insert-only version
  whose sections are sealed (`[{key, heading, body, built_from, human_edited}]`, fingerprint
  `assurance.governance_sections`, the one the room reads, R-02-T12).
- **Approval and send** are the engagement partner's: human-only, fresh MFA (the matrix's
  `mfa_recent` on `governance_comm.approve_send`), on the version they saw (`seen_hash`). Output
  checks refuse first: a planning letter mentioning materiality or carrying an amount, and any
  letter naming "SAS 114" (superseded by AU-C 260), answer 422 `letter_check_failed`. The send
  goes to the POR-15 governance room of the body (one `governance_communication_sends` row; the
  room's `tcwg` grant holders read it there, R-02-T12) or, where the room is off, to a SIG-02
  acknowledgement envelope (DEC-83; the envelope itself is C7's).
- **Due dates**: AU-C 265 is due 60 days after the report release (`due_rule = 'release+60'`);
  until the release it shows no date.
- **Acknowledgements** arrive through the room (`governance_room.record_acknowledgement`).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.config import settings
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import (
    DomainConflict,
    DomainForbidden,
    DomainInvalid,
    DomainRateLimited,
    NotFound,
    ServiceUnavailable,
)
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.assurance.governance_room import SECTIONS_FINGERPRINT
from abacus.modules.communications.api import RecipientRef, SendScope, send_templated
from abacus.modules.engagements.api import assurance_item, get_ref, work_item_titles
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    authorise,
    firm_name,
    grant_tcwg_member,
)
from abacus.modules.methodology.api import published_body
from abacus.modules.organisations.api import ContactFacts, contact_facts, signer_contacts

Kind = Literal["planning_260", "completion_260", "sd_mw_265", "management_letter"]
KINDS: Final[tuple[Kind, ...]] = (
    "planning_260",
    "completion_260",
    "sd_mw_265",
    "management_letter",
)
STANDARD: Final[dict[str, str]] = {
    "planning_260": "AU-C 260",
    "completion_260": "AU-C 260",
    "sd_mw_265": "AU-C 265 · 703",
    "management_letter": "Management letter",
}
REQUIRED: Final = frozenset({"planning_260", "completion_260"})
DUE_AFTER_RELEASE: Final = timedelta(days=60)
_AMOUNT: Final = re.compile(r"\$\s?\d|\d[\d,]*\.\d{2}\b|\b\d{1,3}(,\d{3})+\b")
_MATERIALITY: Final = re.compile(r"\bmateriality\b", re.IGNORECASE)
_SAS_114: Final = re.compile(r"\bSAS\s*114\b", re.IGNORECASE)


class KindExists(DomainConflict):
    code = "communication_exists"


class StaleCommunication(DomainConflict):
    code = "item_changed"


class NotApprovable(DomainConflict):
    code = "not_awaiting_approval"


class LetterCheckFailed(DomainInvalid):
    code = "letter_check_failed"


class AmountInLetter(DomainInvalid):
    code = "amount_in_letter"


# --- sections ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LetterPart:
    key: str
    heading: str
    body: str
    built_from: tuple[str, ...] = ()
    human_edited: bool = False


HEADINGS: Final[dict[str, tuple[tuple[str, str], ...]]] = {
    "planning_260": (
        ("responsibilities", "Our responsibilities"),
        ("scope_timing", "Planned scope and timing"),
        ("significant_risks", "Significant risks identified"),
        ("service_organizations", "Service organizations"),
    ),
    "completion_260": (
        ("significant_findings", "Significant findings"),
        ("difficulties", "Difficulties encountered"),
        ("uncorrected", "Uncorrected misstatements"),
        ("other_matters", "Other matters"),
    ),
    "sd_mw_265": (
        ("deficiencies", "Significant deficiencies and material weaknesses"),
        ("reportable_703", "Reportable findings"),
    ),
    "management_letter": (("observations", "Observations"),),
}


@dataclass(frozen=True)
class Facts:
    significant_risks: tuple[tuple[str, str], ...] = ()  # (code, area)
    service_organizations: tuple[tuple[UUID, str], ...] = ()
    deficiencies: tuple[tuple[str, str], ...] = ()  # (finding ref, severity)
    findings: tuple[str, ...] = ()


_RISKS = text(
    "SELECT code, area_label FROM risk_register_rows WHERE work_item_id = :wi AND rmm = 'high' "
    "ORDER BY code"
)
_SERVICE_ORGS = text(
    "SELECT id, name FROM service_organizations WHERE work_item_id = :wi ORDER BY name"
)
_DEFICIENCIES = text(
    "SELECT f.ref, d.severity_concluded FROM deficiencies d JOIN audit_findings f "
    "ON f.id = d.finding_id WHERE d.work_item_id = :wi "
    "AND d.severity_concluded IN ('significant_deficiency', 'material_weakness') ORDER BY f.ref"
)
_FINDINGS = text("SELECT ref FROM audit_findings WHERE work_item_id = :wi ORDER BY ref")


async def facts_of(tenant: TenantContext, work_item_id: UUID) -> Facts:
    async with tenant_session(tenant) as session:
        risks = (await session.execute(_RISKS, {"wi": work_item_id})).all()
        orgs = (await session.execute(_SERVICE_ORGS, {"wi": work_item_id})).all()
        defs = (await session.execute(_DEFICIENCIES, {"wi": work_item_id})).all()
        found = (await session.execute(_FINDINGS, {"wi": work_item_id})).all()
    return Facts(
        tuple((str(r.code), str(r.area_label)) for r in risks),
        tuple((cast(UUID, o.id), str(o.name)) for o in orgs),
        tuple((str(d.ref), str(d.severity_concluded)) for d in defs),
        tuple(str(f.ref) for f in found),
    )


_SEVERITY_WORD: Final = {
    "significant_deficiency": "a significant deficiency",
    "material_weakness": "a material weakness",
}


FIRM_TEMPLATE: Final = "firm_template"


def template_paragraphs(blocks: Sequence[object] | None) -> list[str]:
    """DEC-3027: a published `governance_letter` version's paragraphs, in order, read from its
    C11 blocks' text runs (the firm's words; code never writes them)."""
    out: list[str] = []
    for raw in blocks or ():
        if not isinstance(raw, dict):
            continue
        block = cast("dict[str, object]", raw)
        if block.get("type") != "paragraph":
            continue
        words = ""
        for run in cast("list[object]", block.get("runs") or []):
            if isinstance(run, dict):
                part = cast("dict[str, object]", run)
                if part.get("type") == "text":
                    words += str(part.get("text", ""))
        if words.strip():
            out.append(words.strip())
    return out


def compose(kind: Kind, facts: Facts, template: Sequence[str] = ()) -> list[LetterPart]:
    """The kind's sections from the facts; a section with no facts states none were found. A
    firm template's paragraphs open the letter as one section (DEC-3027)."""
    sections: list[LetterPart] = []
    if template:
        sections.append(LetterPart(FIRM_TEMPLATE, "", "\n\n".join(template), ("template",)))
    for key, heading in HEADINGS[kind]:
        built: tuple[str, ...] = ()
        lines: list[str] = []
        if key == "significant_risks":
            built = tuple(code for code, _ in facts.significant_risks)
            lines = [f"{area} ({code})" for code, area in facts.significant_risks]
        elif key == "service_organizations":
            built = tuple(str(i) for i, _ in facts.service_organizations)
            lines = [name for _, name in facts.service_organizations]
        elif key in ("deficiencies",):
            built = tuple(ref for ref, _ in facts.deficiencies)
            lines = [f"{ref}: {_SEVERITY_WORD[sev]}" for ref, sev in facts.deficiencies]
        elif key in ("significant_findings", "reportable_703", "observations"):
            built = facts.findings
            lines = list(facts.findings)
        body = "\n".join(f"- {line}" for line in lines) if lines else ""
        sections.append(LetterPart(key, heading, body, built))
    return sections


def merge(previous: Sequence[LetterPart], composed: Sequence[LetterPart]) -> list[LetterPart]:
    """Regenerate: a person's edited section keeps its text; every other takes the new facts."""
    edited = {s.key: s for s in previous if s.human_edited}
    return [edited.get(s.key, s) for s in composed]


def canonical(sections: Sequence[LetterPart]) -> tuple[bytes, str]:
    body = json.dumps(
        [
            {
                "key": s.key,
                "heading": s.heading,
                "body": s.body,
                "built_from": list(s.built_from),
                "human_edited": s.human_edited,
            }
            for s in sections
        ],
        sort_keys=True,
    ).encode()
    return body, hashlib.sha256(body).hexdigest()


def letter_checks(kind: str, sections: Sequence[LetterPart]) -> list[str]:
    """The output checks before a send: no materiality and no amount in a planning letter, and
    never the superseded "SAS 114"."""
    problems: list[str] = []
    text_all = "\n".join(f"{s.heading}\n{s.body}" for s in sections)
    if kind == "planning_260" and _MATERIALITY.search(text_all):
        problems.append("materiality_in_planning_letter")
    if kind == "planning_260" and _AMOUNT.search(text_all):
        problems.append("amount_in_planning_letter")
    if _SAS_114.search(text_all):
        problems.append("sas_114")
    return problems


def due_on(kind: str, released_at: datetime | None) -> date | None:
    """AU-C 265's letter is due 60 days after the report release; the others carry no rule."""
    if kind != "sd_mw_265" or released_at is None:
        return None
    return (released_at + DUE_AFTER_RELEASE).date()


# --- reads ---------------------------------------------------------------------------------------


async def _person(ctx: AuthContext, work_item_id: UUID, action: str) -> UUID:
    if ctx.client:
        raise NotFound("governance_communication")
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")
    item = await assurance_item(ctx.tenant, work_item_id)
    await authorise(ctx, action, (await get_ref(ctx, item.engagement_id)).resource())
    return item.engagement_id


@dataclass(frozen=True)
class Row:
    id: UUID
    kind: str
    standard: str
    status: str
    due_on: date | None
    overdue: bool
    sent_at: datetime | None
    acknowledged_at: datetime | None
    channel: str | None


_ROWS = text(
    "SELECT c.id, c.kind, c.standard, c.status, c.due_on, c.channel, "
    "(SELECT max(s.sent_at) FROM governance_communication_sends s JOIN "
    "governance_communication_versions v ON v.id = s.version_id WHERE v.communication_id = c.id) "
    "AS sent_at, (SELECT max(a.acknowledged_at) FROM governance_acknowledgements a "
    "WHERE a.communication_id = c.id) AS acknowledged_at FROM governance_communications c "
    "WHERE c.work_item_id = :wi AND c.kind <> 'reportable_703' ORDER BY c.kind"
)


async def rows(ctx: AuthContext, work_item_id: UUID, today: date) -> list[Row]:
    """AUD-22's rows; Overdue is derived from the due date, never stored."""
    await _person(ctx, work_item_id, "governance_comm.read")
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(_ROWS, {"wi": work_item_id})).all()
    return [
        Row(
            r.id, r.kind, r.standard or STANDARD.get(r.kind, ""), r.status, r.due_on,
            r.due_on is not None and r.due_on < today and r.status not in ("sent", "acknowledged"),
            r.sent_at, r.acknowledged_at, r.channel,
        )
        for r in found
    ]  # fmt: skip


@dataclass(frozen=True)
class Communication:
    id: UUID
    kind: str
    status: str
    version_no: int | None
    content_hash: str | None
    sections: tuple[LetterPart, ...] = field(default_factory=tuple)
    row_version: int = 1


_ONE = text(
    "SELECT c.id, c.kind, c.status, c.version, c.current_version_id, c.engagement_id, "
    "c.work_item_id, v.version_no, v.content_hash, v.sections_sealed "
    "FROM governance_communications c LEFT JOIN governance_communication_versions v "
    "ON v.id = c.current_version_id WHERE c.id = :id AND c.work_item_id = :wi"
)


def _sections(raw: object) -> tuple[LetterPart, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[LetterPart] = []
    for item in cast(list[object], raw):
        if isinstance(item, dict):
            e = cast(dict[str, object], item)
            out.append(
                LetterPart(
                    str(e.get("key", "")),
                    str(e.get("heading") or ""),
                    str(e.get("body", "")),
                    tuple(str(b) for b in cast(list[object], e.get("built_from") or [])),
                    bool(e.get("human_edited", False)),
                )
            )
    return tuple(out)


async def _read(tenant: TenantContext, work_item_id: UUID, communication_id: UUID) -> object:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_ONE, {"id": communication_id, "wi": work_item_id})).first()
    if row is None:
        raise NotFound("governance_communication")
    return row


async def _open(tenant: TenantContext, row: object) -> tuple[LetterPart, ...]:
    sealed = cast(bytes | None, getattr(row, "sections_sealed", None))
    if sealed is None:
        return ()
    return _sections(json.loads(await open_sealed(tenant.tenant_id, sealed, SECTIONS_FINGERPRINT)))


async def communication(
    ctx: AuthContext, work_item_id: UUID, communication_id: UUID
) -> Communication:
    await _person(ctx, work_item_id, "governance_comm.read")
    row = await _read(ctx.tenant, work_item_id, communication_id)
    return Communication(
        communication_id,
        str(row.kind),  # type: ignore[attr-defined] -- a raw SQL row's column
        str(row.status),  # type: ignore[attr-defined] -- a raw SQL row's column
        cast(int | None, row.version_no),  # type: ignore[attr-defined] -- a raw SQL row's column
        cast(str | None, row.content_hash),  # type: ignore[attr-defined] -- a raw SQL row's column
        await _open(ctx.tenant, row),
        int(row.version),  # type: ignore[attr-defined] -- a raw SQL row's column
    )


# --- writes --------------------------------------------------------------------------------------


async def create(
    ctx: AuthContext,
    work_item_id: UUID,
    kind: Kind,
    template_version_id: UUID | None = None,
) -> UUID:
    """A communication of `kind` (one per work item), composed at once as version 1, opening with
    the chosen published firm template when one is given (DEC-3027)."""
    engagement_id = await _person(ctx, work_item_id, "governance_comm.draft")
    if (
        template_version_id is not None
        and (await published_body(ctx.tenant, TEMPLATE_FAMILY, template_version_id)) is None
    ):
        raise NotFound("report_template_version")
    async with uow(ctx.tenant) as tx:
        exists = await tx.session.scalar(
            text(
                "SELECT id FROM governance_communications WHERE work_item_id = :wi AND kind = :k"
            ),
            {"wi": work_item_id, "k": kind},
        )
        if exists is not None:
            raise KindExists(facts={"kind": kind})
        communication_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO governance_communications (tenant_id, engagement_id, "
                    "work_item_id, kind, standard, due_rule, status) VALUES (:t, :e, :wi, :k, "
                    ":std, :rule, 'draft') RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "wi": work_item_id,
                    "k": kind,
                    "std": STANDARD[kind],
                    "rule": "release+60" if kind == "sd_mw_265" else None,
                },
            ),
        )
        tx.record(
            "governance_communication.created",
            target=Target("governance_communication", communication_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    await regenerate(ctx, work_item_id, communication_id, template_version_id=template_version_id)
    return communication_id


async def _new_version(
    tx: UnitOfWork,
    ctx: AuthContext,
    row: object,
    sections: Sequence[LetterPart],
    action: str,
    template_version_id: UUID | None = None,
    drafted_by_run_id: UUID | None = None,
) -> tuple[int, str]:
    body, digest = canonical(sections)
    sealed = await seal(ctx.tenant_id, body, SECTIONS_FINGERPRINT)
    refs = sorted({b for s in sections for b in s.built_from})
    communication_id = cast(UUID, row.id)  # type: ignore[attr-defined] -- a raw SQL row's column
    version_no = int(
        await tx.session.scalar(
            text(
                "SELECT coalesce(max(version_no), 0) + 1 FROM governance_communication_versions "
                "WHERE communication_id = :c"
            ),
            {"c": communication_id},
        )
        or 1
    )
    version_id = await tx.session.scalar(
        text(
            "INSERT INTO governance_communication_versions (tenant_id, engagement_id, "
            "work_item_id, communication_id, version_no, sections_sealed, section_refs, "
            "content_hash, created_by, template_version_id, drafted_by_run_id) VALUES (:t, :e, "
            ":wi, :c, :no, :s, CAST(:refs AS jsonb), :h, :by, :tv, :run) RETURNING id"
        ),
        {
            "t": ctx.tenant_id,
            "e": row.engagement_id,  # type: ignore[attr-defined] -- a raw SQL row's column
            "wi": row.work_item_id,  # type: ignore[attr-defined] -- a raw SQL row's column
            "c": communication_id,
            "no": version_no,
            "s": sealed,
            "refs": json.dumps(refs),
            "h": digest,
            "by": ctx.user_id,
            "tv": template_version_id,
            "run": drafted_by_run_id,
        },
    )
    await tx.session.execute(
        text(
            "UPDATE governance_communications SET current_version_id = :v, status = 'draft', "
            "version = version + 1, updated_at = clock_timestamp() WHERE id = :c"
        ),
        {"v": version_id, "c": communication_id},
    )
    tx.record(
        action,
        target=Target("governance_communication", communication_id),
        after=Ref(version_no=version_no, content_hash=digest),
        scope=Scope(
            engagement_id=row.engagement_id,  # type: ignore[attr-defined] -- a raw SQL row's column
            work_item_id=row.work_item_id,  # type: ignore[attr-defined] -- a raw SQL row's column
        ),
    )
    return version_no, digest


async def regenerate(
    ctx: AuthContext,
    work_item_id: UUID,
    communication_id: UUID,
    *,
    template_version_id: UUID | None = None,
    drafted_by_run_id: UUID | None = None,
) -> str:
    """Compose again from today's facts; a person's edited sections keep their text. The letter
    keeps the template its current version was composed from (DEC-3027). A regenerate the Agent
    ran names its run (`drafted_by_run_id`)."""
    await _person(ctx, work_item_id, "governance_comm.draft")
    row = await _read(ctx.tenant, work_item_id, communication_id)
    if str(row.status) in ("sent", "acknowledged"):  # type: ignore[attr-defined] -- a raw SQL row's column
        raise StaleCommunication(facts={"status": str(row.status)})  # type: ignore[attr-defined] -- a raw SQL row's column
    previous = await _open(ctx.tenant, row)
    if template_version_id is None:
        async with tenant_session(ctx.tenant) as session:
            template_version_id = cast(
                UUID | None, await session.scalar(_CURRENT_TEMPLATE, {"c": communication_id})
            )
    template = (
        template_paragraphs(await published_body(ctx.tenant, TEMPLATE_FAMILY, template_version_id))
        if template_version_id is not None
        else []
    )
    facts = await facts_of(ctx.tenant, work_item_id)
    composed = compose(cast(Kind, str(row.kind)), facts, template)  # type: ignore[attr-defined] -- a raw SQL row's column
    async with uow(ctx.tenant) as tx:
        _no, digest = await _new_version(
            tx,
            ctx,
            row,
            merge(previous, composed),
            "governance_communication.composed",
            template_version_id,
            drafted_by_run_id,
        )
    return digest


TEMPLATE_FAMILY: Final = "governance_letter"
_CURRENT_TEMPLATE = text(
    "SELECT v.template_version_id FROM governance_communications c "
    "JOIN governance_communication_versions v ON v.id = c.current_version_id WHERE c.id = :c"
)


async def edit_section(
    ctx: AuthContext,
    work_item_id: UUID,
    communication_id: UUID,
    key: str,
    body: str,
    seen_version: int,
) -> str:
    """A person's text for one section: a new version, the section marked human-edited."""
    await _person(ctx, work_item_id, "governance_comm.draft")
    if _AMOUNT.search(body):
        raise AmountInLetter
    row = await _read(ctx.tenant, work_item_id, communication_id)
    if int(row.version) != seen_version:  # type: ignore[attr-defined] -- a raw SQL row's column
        raise StaleCommunication(facts={"version": int(row.version)})  # type: ignore[attr-defined] -- a raw SQL row's column
    sections = list(await _open(ctx.tenant, row))
    if key not in {s.key for s in sections}:
        raise NotFound("governance_section")
    edited = [
        LetterPart(s.key, s.heading, body, s.built_from, True) if s.key == key else s
        for s in sections
    ]
    async with uow(ctx.tenant) as tx:
        _no, digest = await _new_version(
            tx, ctx, row, edited, "governance_communication.section_edited"
        )
    return digest


async def request_approval(ctx: AuthContext, work_item_id: UUID, communication_id: UUID) -> None:
    engagement_id = await _person(ctx, work_item_id, "governance_comm.request_approval")
    async with uow(ctx.tenant) as tx:
        moved = await tx.session.execute(
            text(
                "UPDATE governance_communications SET status = 'awaiting_ep_approval', "
                "version = version + 1, updated_at = clock_timestamp() WHERE id = :c "
                "AND work_item_id = :wi AND status = 'draft' AND current_version_id IS NOT NULL"
            ),
            {"c": communication_id, "wi": work_item_id},
        )
        if moved.rowcount != 1:  # type: ignore[attr-defined] -- a raw SQL row's column
            raise NotApprovable
        tx.record(
            "governance_communication.approval_requested",
            target=Target("governance_communication", communication_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


_RELEASED = text(
    "SELECT min(released_at) FROM report_releases WHERE work_item_id = :wi AND kind = 'original'"
)
_MEMBERS = text(
    "SELECT contact_id FROM governance_body_members WHERE body_id = :b AND ended_on IS NULL"
)
_IS_RECIPIENT = text(
    "SELECT 1 FROM governance_recipients WHERE work_item_id = :wi AND governance_body_id = :b"
)
_BODIES_OF_CLIENT = text(
    "SELECT id FROM governance_bodies WHERE id = ANY(:ids) AND client_id = :c"
)


async def approve_and_send(
    ctx: AuthContext,
    work_item_id: UUID,
    communication_id: UUID,
    *,
    governance_body_id: UUID,
    recipient_contact_ids: Sequence[UUID],
    channel: Literal["governance_room", "ack_envelope"],
    seen_hash: str,
) -> UUID:
    """The EP's approve-and-send (module docstring); the send row's id."""
    engagement_id = await _person(ctx, work_item_id, "governance_comm.approve_send")
    if ctx.mfa_at is None:
        raise Forbidden("governance_comm.approve_send", "condition")
    row = await _read(ctx.tenant, work_item_id, communication_id)
    if str(row.status) != "awaiting_ep_approval":  # type: ignore[attr-defined] -- a raw SQL row's column
        raise NotApprovable
    if row.content_hash != seen_hash:  # type: ignore[attr-defined] -- a raw SQL row's column
        raise StaleCommunication(facts={"seen_hash": seen_hash})
    sections = await _open(ctx.tenant, row)
    problems = letter_checks(str(row.kind), sections)  # type: ignore[attr-defined] -- a raw SQL row's column
    if problems:
        raise LetterCheckFailed(facts={"checks": ",".join(problems)})
    async with tenant_session(ctx.tenant) as session:
        # S32 partials review: the letter goes only to a body set as this work item's recipient
        # (which `set_recipients` keeps to the engagement's client); its members get room grants.
        if (
            await session.scalar(_IS_RECIPIENT, {"wi": work_item_id, "b": governance_body_id})
            is None
        ):
            raise LetterCheckFailed(facts={"checks": "body_not_a_recipient"})
        members = {
            r.contact_id
            for r in (await session.execute(_MEMBERS, {"b": governance_body_id})).all()
        }
        released = cast(datetime | None, await session.scalar(_RELEASED, {"wi": work_item_id}))
    if not members or not set(recipient_contact_ids) <= members:
        raise LetterCheckFailed(facts={"checks": "recipients_not_members"})
    # DEC-3026: each recipient gets the room's `tcwg` grant at send (a pending grant and an
    # invitation for a contact who has never signed in), all inside the send's unit of work.
    recipients = list(dict.fromkeys(recipient_contact_ids))
    async with tenant_session(ctx.tenant) as session:
        people = await contact_facts(session, recipients)
    emails = await signer_contacts(
        ctx.tenant,
        [c for c in recipients if (f := people.get(c)) is not None and f.user_id is None],
    )
    async with uow(ctx.tenant) as tx:
        send_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO governance_communication_sends (tenant_id, engagement_id, "
                    "work_item_id, version_id, sent_by, governance_body_id, "
                    "recipient_contact_ids, channel, mfa_verified_at, actor_kind, actor_id) "
                    "VALUES (:t, :e, :wi, :v, :by, :b, :r, :ch, :mfa, :ak, :aid) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "wi": work_item_id,
                    "v": row.current_version_id,  # type: ignore[attr-defined] -- a raw SQL row's column
                    "by": ctx.user_id,
                    "b": governance_body_id,
                    "r": list(recipient_contact_ids),
                    "ch": channel,
                    "mfa": ctx.mfa_at,
                    "ak": ctx.tenant.actor_kind,
                    "aid": ctx.tenant.actor_id,
                },
            ),
        )
        await tx.session.execute(
            text(
                "UPDATE governance_communications SET status = 'sent', channel = :ch, "
                "due_on = coalesce(:due, due_on), version = version + 1, "
                "updated_at = clock_timestamp() WHERE id = :c"
            ),
            {"ch": channel, "due": due_on(str(row.kind), released), "c": communication_id},  # type: ignore[attr-defined] -- a raw SQL row's column
        )
        invited = 0
        for contact in recipients:
            person = people.get(contact)
            if person is None:
                raise LetterCheckFailed(facts={"checks": "recipient_unknown"})
            found = emails.get(contact)
            given = await grant_tcwg_member(
                tx,
                ctx.tenant,
                engagement_id=engagement_id,
                client_id=person.client_id,
                contact_id=contact,
                user_id=person.user_id,
                email=None if found is None else found.email,
                governance_body_id=governance_body_id,
                granted_by=ctx.user_id,
            )
            invited += int(given.invitation_id is not None)
        tx.record(
            "governance_communication.sent",
            target=Target("governance_communication", communication_id),
            after=Ref(
                send=send_id,
                body=governance_body_id,
                seen_hash=seen_hash,
                recipients=len(recipients),
                invited=invited,
            ),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
        # TASK-6543 (DEC-3145): the letter becomes a final C11 document in the same transaction:
        # a draft of the approved version, then its final on that draft's hash, approved by this
        # send (the partner approved the version's content hash with a fresh second factor; the
        # draft is that version's deterministic rendering).
        await _render_final(
            tx,
            ctx,
            cast(UUID, row.current_version_id),  # type: ignore[attr-defined] -- a raw SQL row's column
            send_id,
            engagement_id,
            work_item_id,
        )
    if channel == "governance_room":
        await _letter_emails(ctx, engagement_id, work_item_id, send_id, recipients, people)
    else:
        await _draft_acknowledgement_envelope(ctx, communication_id, engagement_id, work_item_id)
    return send_id


# --- the letter as a C11 document (TASK-6543; DEC-3145) ------------------------------------------

LETTER_KIND: Final = "governance_letter"
VERSION_OWNER: Final = "governance_communication_version"
APPROVAL_KIND: Final = "governance_send"
_approving: ContextVar[tuple[object, UUID] | None] = ContextVar(
    "governance_letter_approving", default=None
)
_VERSION_SECTIONS = text(
    "SELECT v.sections_sealed, c.kind FROM governance_communication_versions v "
    "JOIN governance_communications c ON c.id = v.communication_id WHERE v.id = :v"
)


def letter_blocks(sections: Sequence[LetterPart]) -> list[object]:
    """The C11 body of a version: each section's heading, then a paragraph per paragraph of its
    text (blank lines split them). The words are the version's own; code only arranges them."""
    blocks: list[object] = []
    for part in sections:
        if part.heading:
            blocks.append({"type": "heading", "level": 2, "text": part.heading})
        for para in (p.strip() for p in part.body.split("\n\n")):
            if para:
                blocks.append({"type": "paragraph", "runs": [{"type": "text", "text": para}]})
    return blocks


async def letter_body(tenant: TenantContext, owner: object, _scope: object) -> list[object]:
    """C11's body provider for `governance_letter`: the owner version's sealed sections."""
    from abacus.modules.reporting.api import OwnerRef

    if not isinstance(owner, OwnerRef) or owner.type != VERSION_OWNER:
        return []
    async with tenant_session(tenant) as session:
        found = (await session.execute(_VERSION_SECTIONS, {"v": owner.id})).first()
    if found is None:
        raise NotFound("governance_communication_version")
    raw = await open_sealed(tenant.tenant_id, found.sections_sealed, SECTIONS_FINGERPRINT)
    return letter_blocks(_sections(json.loads(raw)))


async def send_approval(ref: object) -> tuple[UUID, str] | None:
    """C11's approval provider: only the send in flight, for the partner who is sending it."""
    held = _approving.get()
    return None if held is None or held[0] != ref else (held[1], getattr(ref, "content_hash", ""))


async def _render_final(
    tx: UnitOfWork,
    ctx: AuthContext,
    version_id: UUID,
    send_id: UUID,
    engagement_id: UUID,
    work_item_id: UUID,
) -> None:
    from abacus.modules.reporting import api as c11

    client_id = (await get_ref(ctx, engagement_id)).client_id
    who = c11.Requester("human", user_id=ctx.user_id)
    ticket = await c11.render(
        tx,
        c11.RenderRequest(
            kind=LETTER_KIND,
            owner_ref=c11.OwnerRef(VERSION_OWNER, version_id),
            scope=c11.RenderScope(
                client_id=client_id, engagement_id=engagement_id, work_item_id=work_item_id
            ),
            template_version_id=None,
            requested_by=who,
            formats=("pdf",),
        ),
    )
    ref = c11.ApprovalRef(APPROVAL_KIND, send_id, ticket.content_hash)
    token = _approving.set((ref, ctx.user_id))
    try:
        await c11.render_final(tx, ticket.generated_document_id, ref, who)
    finally:
        _approving.reset(token)


# --- the acknowledgement envelope (A-07-T19 / A-07-T26 remainder; DEC-3145) -------------------

_LATEST_SEND = text(
    "SELECT s.id, s.version_id, s.recipient_contact_ids, s.engagement_id, s.work_item_id, "
    "c.kind FROM governance_communication_sends s "
    "JOIN governance_communication_versions v ON v.id = s.version_id "
    "JOIN governance_communications c ON c.id = v.communication_id "
    "WHERE s.version_id = :v ORDER BY s.created_at DESC LIMIT 1"
)


async def _final_document(tenant: TenantContext, version_id: UUID) -> tuple[UUID, str]:
    from abacus.modules.reporting import api as c11

    document = await c11.document_of_owner(
        tenant, c11.OwnerRef(VERSION_OWNER, version_id), LETTER_KIND
    )
    latest = None if document is None else await c11.latest_document_version(tenant, document)
    if latest is None:
        raise NotFound("governance_letter_document")
    return latest


async def governance_draft(ctx: AuthContext, version_id: UUID) -> object:
    """C7's draft from a sent version: the final letter, the recipients as email-code signers,
    each in their own routing group (any order), purpose `governance_letter` (general family)."""
    from abacus.modules.signatures.api import SourceDocument, SourceDraft, SourceSigner

    async with tenant_session(ctx.tenant) as session:
        sent = (await session.execute(_LATEST_SEND, {"v": version_id})).first()
    if sent is None:
        raise NotFound("governance_communication_send")
    await _person(ctx, cast(UUID, sent.work_item_id), "governance_comm.read")
    version, content_hash = await _final_document(ctx.tenant, version_id)
    client_id = (await get_ref(ctx, cast(UUID, sent.engagement_id))).client_id
    return SourceDraft(
        purpose=LETTER_KIND,
        policy_family="general",
        client_id=client_id,
        title=f"{STANDARD.get(str(sent.kind), 'Governance')} acknowledgement",
        documents=(
            SourceDocument(
                sha256=content_hash,
                generated_document_version_id=version,
                source_ref=f"governance_letter:{version_id}",
            ),
        ),
        signers=tuple(
            SourceSigner(identity_method="email_code", contact_id=contact, routing_group=1)
            for contact in cast("list[UUID]", sent.recipient_contact_ids)
        ),
        engagement_id=cast(UUID, sent.engagement_id),
        work_item_id=cast(UUID, sent.work_item_id),
        signer_order="parallel",
    )


async def governance_documents(ctx: AuthContext, version_id: UUID) -> Sequence[object]:
    return list(cast("Any", await governance_draft(ctx, version_id)).documents)


async def governance_signers(ctx: AuthContext, version_id: UUID) -> Sequence[object]:
    return list(cast("Any", await governance_draft(ctx, version_id)).signers)


async def _draft_acknowledgement_envelope(
    ctx: AuthContext, communication_id: UUID, engagement_id: UUID, work_item_id: UUID
) -> None:
    """The ack_envelope channel: a SIG-02 draft the partner (or a person) then sends from C7."""
    from abacus.modules.signatures.api import create_draft

    async with tenant_session(ctx.tenant) as session:
        version_id = cast(
            UUID,
            await session.scalar(
                text("SELECT current_version_id FROM governance_communications WHERE id = :c"),
                {"c": communication_id},
            ),
        )
    try:
        envelope_id = await create_draft(ctx, LETTER_KIND, version_id)
    except (DomainConflict, DomainInvalid, DomainForbidden, NotFound, Forbidden) as refused:
        # The send stands (the room and grants are the record); the envelope is drafted from
        # SIG-02 once the firm can (e-signatures on, the partner holding `envelope.draft`).
        _log.warning(
            "governance_letter.envelope_not_drafted",
            communication_id=str(communication_id),
            reason=type(refused).__name__,
        )
        return
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE governance_communications SET envelope_id = :e, version = version + 1, "
                "updated_at = clock_timestamp() WHERE id = :c"
            ),
            {"e": envelope_id, "c": communication_id},
        )
        tx.record(
            "governance_communication.envelope_drafted",
            target=Target("governance_communication", communication_id),
            after=Ref(envelope=envelope_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


# R-02-T14 (AC-36; DF-40; DEC-3140): each room recipient hears of the letter by the firm's
# `governance_letter_sent` email (database words; no amount, no letter text). A template the firm
# has not published blocks that email (recorded `blocked`, logged) and never undoes the send; the
# letter still waits in the room. The envelope channel's own email is C7's.
_GOVERNANCE_LETTER_SENT: Final = "governance_letter_sent"
_log = get_logger(__name__)


async def _letter_emails(
    ctx: AuthContext,
    engagement_id: UUID,
    work_item_id: UUID,
    send_id: UUID,
    recipients: Sequence[UUID],
    people: Mapping[UUID, ContactFacts],
) -> None:
    variables = {
        "firm_name": await firm_name(ctx.tenant_id),
        "work_item": (await work_item_titles(ctx.tenant, [work_item_id])).get(work_item_id, ""),
        "portal_link": f"{settings().app_base_url.rstrip('/')}/portal",
    }
    for contact in recipients:
        person = people.get(contact)
        if person is None:
            continue
        recipient = (
            RecipientRef("user", person.user_id)
            if person.user_id is not None
            else RecipientRef("contact", contact)
        )
        try:
            sent = await send_templated(
                ctx,
                _GOVERNANCE_LETTER_SENT,
                recipient,
                {**variables, "client_first_name": person.display_name.split(" ")[0] or "there"},
                scope=SendScope(engagement_id=engagement_id),
                idempotency_key=f"{_GOVERNANCE_LETTER_SENT}:{send_id}:{contact}",
                authority="governance_comm.approve_send",
            )
        except (
            Forbidden,
            NotFound,
            DomainInvalid,
            DomainConflict,
            DomainForbidden,
            DomainRateLimited,
            ServiceUnavailable,
        ) as refused:
            # The send has committed: an email refusal is logged, never a failed approve-and-send
            # (end-pass security review).
            _log.warning(
                "governance_letter.email_refused", send_id=send_id, error=type(refused).__name__
            )
            continue
        if sent.status == "blocked":
            _log.info(
                "governance_letter.email_blocked", send_id=send_id, reason=sent.blocked_reason
            )


# --- recipients ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Recipient:
    governance_body_id: UUID
    body_name: str
    member_count: int
    ack_required: bool


_RECIPIENTS = text(
    "SELECT r.governance_body_id, b.name, r.ack_required, (SELECT count(*) FROM "
    "governance_body_members m WHERE m.body_id = b.id AND m.ended_on IS NULL) AS members "
    "FROM governance_recipients r JOIN governance_bodies b ON b.id = r.governance_body_id "
    "WHERE r.work_item_id = :wi ORDER BY b.name"
)


async def recipients(ctx: AuthContext, work_item_id: UUID) -> list[Recipient]:
    await _person(ctx, work_item_id, "governance_comm.read")
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(_RECIPIENTS, {"wi": work_item_id})).all()
    return [
        Recipient(r.governance_body_id, str(r.name), int(r.members), bool(r.ack_required))
        for r in found
    ]


async def set_recipients(
    ctx: AuthContext, work_item_id: UUID, body_ids: Sequence[UUID]
) -> list[Recipient]:
    """The TCWG bodies the engagement's letters go to (DEC-93); acknowledgement required."""
    engagement_id = await _person(ctx, work_item_id, "governance_comm.manage_recipients")
    # S32 partials review: a body is a recipient only for its own client's engagement.
    client_id = (await get_ref(ctx, engagement_id)).client_id
    wanted = list(dict.fromkeys(body_ids))
    async with tenant_session(ctx.tenant) as session:
        owned = {
            r.id
            for r in (
                await session.execute(_BODIES_OF_CLIENT, {"ids": wanted, "c": client_id})
            ).all()
        }
    if set(wanted) - owned:
        raise LetterCheckFailed(facts={"checks": "body_not_the_clients"})
    async with uow(ctx.tenant) as tx:
        for body_id in wanted:
            await tx.session.execute(
                text(
                    "INSERT INTO governance_recipients (tenant_id, engagement_id, work_item_id, "
                    "governance_body_id, ack_required) VALUES (:t, :e, :wi, :b, true) "
                    "ON CONFLICT (tenant_id, work_item_id, governance_body_id) DO NOTHING"
                ),
                {"t": ctx.tenant_id, "e": engagement_id, "wi": work_item_id, "b": body_id},
            )
        tx.record(
            "governance_recipients.set",
            target=Target("work_item", work_item_id),
            after=Ref(bodies=len(set(body_ids))),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return await recipients(ctx, work_item_id)
