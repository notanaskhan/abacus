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
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.assurance.governance_room import SECTIONS_FINGERPRINT
from abacus.modules.engagements.api import assurance_item, get_ref
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, grant_tcwg_member
from abacus.modules.methodology.api import published_body
from abacus.modules.organisations.api import contact_facts, signer_contacts

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
            "content_hash, created_by, template_version_id) VALUES (:t, :e, :wi, :c, :no, :s, "
            "CAST(:refs AS jsonb), :h, :by, :tv) RETURNING id"
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
) -> str:
    """Compose again from today's facts; a person's edited sections keep their text. The letter
    keeps the template its current version was composed from (DEC-3027)."""
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
    return send_id


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
    async with uow(ctx.tenant) as tx:
        for body_id in dict.fromkeys(body_ids):
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
