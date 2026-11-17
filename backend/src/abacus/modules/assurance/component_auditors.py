"""Component auditors, instructions and deliverables (A-09-T27; A-09 §3.6; SPEC-658 F6; AUD-35 a
to g; DEC-5405; amber).

- **Auditors**: the other firm (organisation, city), its engagement-partner contact (a contact
  of kind `component_auditor`), the component it audits, and the evaluation facts a person
  records (questionnaire received, competence evaluated, independence confirmed, peer review).
- **Instructions** (DV-6, P-25 off): a deterministic merge of the firm's `component_instructions`
  letter template (C11 DB content: a heading starts a section, its paragraphs are its body) with
  code's facts: the component PM and the group's clearly-trivial threshold (nothing else of
  group materiality), and the required-communications dates (the component's milestones). A
  placeholder with no fact leaves its section **Needs input** ("{{group_risks}}" until the group
  risk assessment names the component's risks). Provenance "Drafted by <person> via Agent"
  (the deterministic run is on the person's behalf; no model). Edits are new versions.
- **Send** (a live person only; never the agent): every section complete, the recipient the
  auditor's contact; the letter renders through C11; the send waits 10 seconds for an Undo,
  then issues the `component_auditor` grant at `component` scope (an invitation carrying it when
  the contact has not signed in) and records `component_instructions.sent`.
- **Deliverables**: requested with a due date (each is also a milestone), received from the
  portal (A-09-T33), reviewed or returned by a person (Late and Returned are derived).
- **Make reference**: the engagement partner's decision card (SHL-11); deciding sets the flag.
- **Acknowledge**: the portal's (A-09-T33) call for the auditor's contact.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDConflictPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from abacus.kernel.classification import classified
    from abacus.kernel.db import TenantContext, tenant_session
    from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
    from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, UnitOfWork, uow
    from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise, names_of
    from abacus.modules.review.api import ComputedCard

FAMILY: Final = "component_instructions"
UNDO_SECONDS: Final = 10
MAKE_REFERENCE: Final = "make_reference"
_PLACEHOLDER: Final = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")
_I = classified("internal")


# --- events --------------------------------------------------------------------------------------


class ComponentInstructionsSent(DomainEvent):
    event_type: ClassVar[str] = "component_instructions.sent"

    instructions_id: Annotated[UUID, _I]
    component_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]


class ComponentInstructionsAcknowledged(DomainEvent):
    event_type: ClassVar[str] = "component_instructions.acknowledged"

    instructions_id: Annotated[UUID, _I]
    component_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]


class ComponentDeliverableEvent(DomainEvent):
    """`component_deliverable.requested|received|reviewed|returned` (identifiers only)."""

    event_type: ClassVar[str] = "component_deliverable.changed"

    deliverable_id: Annotated[UUID, _I]
    component_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    change: Annotated[str, _I]


# --- errors --------------------------------------------------------------------------------------


class TemplateMissing(DomainConflict):
    """The firm has no published `component_instructions` letter template (DB content)."""

    code = "instructions_template_missing"


class InstructionsIncomplete(DomainConflict):
    """A section still Needs input: Send instructions is disabled with this reason."""

    code = "instructions_needs_input"


class InstructionsStale(DomainConflict):
    code = "instructions_version_stale"


class RecipientInvalid(DomainInvalid):
    """The recipient must be the component auditor's engagement-partner contact."""

    code = "recipient_invalid"


class UndoWindowClosed(DomainConflict):
    code = "undo_window_closed"


class AlreadySent(DomainConflict):
    code = "instructions_already_sent"


class ComponentNotAudited(DomainInvalid):
    """The component is not this work item's, or a component auditor already covers it."""

    code = "component_invalid"


class DeliverableClosed(DomainConflict):
    code = "deliverable_not_open"


# --- views ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    number: int
    title: str
    body: str
    needs_input: bool


@dataclass(frozen=True)
class AuditorView:
    id: UUID
    organisation_name: str
    city: str | None
    component_id: UUID
    contact_name: str | None
    questionnaire_received_on: date | None
    competence_evaluated_at: datetime | None
    independence_confirmed_at: datetime | None
    peer_review_obtained_on: date | None
    make_reference: bool
    instructions_status: str | None


@dataclass(frozen=True)
class InstructionsView:
    id: UUID
    status: str
    version_id: UUID
    sections: tuple[Section, ...]
    provenance: str
    send_blocked_reason: str | None
    content_hash: str
    row_version: int


@dataclass(frozen=True)
class DeliverableView:
    id: UUID
    title: str
    due_on: date
    status: str  # expected · received · reviewed · late (derived) · returned (derived)
    days_late: int | None
    received_at: datetime | None
    reviewed_by_name: str | None
    return_reason: str | None


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _resource(ctx: AuthContext, engagement_id: UUID) -> Resource:
    from abacus.modules.engagements.api import get_ref

    return (await get_ref(ctx, engagement_id)).resource()


# --- the pure merge ------------------------------------------------------------------------------


def template_sections(blocks: Sequence[object] | None) -> list[tuple[str, list[str]]]:
    """A published letter's sections: each heading starts one; its paragraphs are its body."""
    sections: list[tuple[str, list[str]]] = []
    for raw in blocks or ():
        if not isinstance(raw, dict):
            continue
        block = cast("dict[str, object]", raw)
        if block.get("type") == "heading":
            sections.append((str(block.get("text", "")).strip(), []))
            continue
        if block.get("type") != "paragraph":
            continue
        words = "".join(
            str(cast("dict[str, object]", r).get("text", ""))
            for r in cast("list[object]", block.get("runs") or [])
            if isinstance(r, dict) and cast("dict[str, object]", r).get("type") == "text"
        ).strip()
        if not words:
            continue
        if not sections:
            sections.append(("", []))
        sections[-1][1].append(words)
    return sections


def merge(
    template: Sequence[tuple[str, Sequence[str]]], facts: Mapping[str, str]
) -> tuple[Section, ...]:
    """Each placeholder takes its fact; a section with a placeholder no fact answers keeps it
    and reads Needs input. Code never writes the letter's words."""
    out: list[Section] = []
    for n, (title, paragraphs) in enumerate(template, start=1):
        body = "\n\n".join(paragraphs)
        missing = False

        def fill(m: re.Match[str]) -> str:
            nonlocal missing
            value = facts.get(m.group(1))
            if value is None or value == "":
                missing = True
                return m.group(0)
            return value

        merged = _PLACEHOLDER.sub(fill, body)
        out.append(Section(n, title, merged, missing))
    return tuple(out)


def sections_hash(sections: Sequence[Section]) -> str:
    body = json.dumps(
        [[s.number, s.title, s.body, s.needs_input] for s in sections], sort_keys=True
    )
    return hashlib.sha256(body.encode()).hexdigest()


def money(value: Decimal) -> str:
    return f"{value:,.0f}"


def deliverable_status(
    status: str, due_on: date, returned: bool, today: date
) -> tuple[str, int | None]:
    """Late and Returned are derived, never stored: an expected deliverable past its due date
    is Late by the days since; a returned one waits again as Returned."""
    if status == "expected" and returned:
        return "returned", None
    if status == "expected" and today > due_on:
        return "late", (today - due_on).days
    return status, None


# --- SQL -----------------------------------------------------------------------------------------

_AUDITORS: Final = text(
    "SELECT a.id, a.organisation_name, a.city, a.component_id, a.ep_contact_id, "
    "a.questionnaire_received_on, a.competence_evaluated_at, a.independence_confirmed_at, "
    "a.peer_review_obtained_on, a.make_reference, i.status AS instructions_status "
    "FROM component_auditors a LEFT JOIN component_instructions i "
    "ON i.component_auditor_id = a.id WHERE a.work_item_id = :w ORDER BY a.created_at, a.id"
)
_AUDITOR: Final = text(
    "SELECT a.id, a.engagement_id, a.work_item_id, a.organisation_name, a.city, a.component_id, "
    "a.ep_contact_id, a.make_reference, a.row_version, a.created_by, c.component_pm, "
    "c.consolidation_entity_id FROM component_auditors a JOIN components c "
    "ON c.id = a.component_id WHERE a.id = :a"
)
_COMPONENT: Final = text(
    "SELECT id, work_item_id, engagement_id, performed_by FROM components WHERE id = :c"
)
_INSERT_AUDITOR: Final = text(
    "INSERT INTO component_auditors (tenant_id, engagement_id, work_item_id, organisation_name, "
    "city, component_id, ep_contact_id, created_by) VALUES (:t, :e, :w, :o, :city, :c, :ep, :by) "
    "RETURNING id"
)
_EVALUATE: Final = text(
    "UPDATE component_auditors SET questionnaire_received_on = coalesce(:q, "
    "questionnaire_received_on), competence_evaluated_by = CASE WHEN :comp THEN :by ELSE "
    "competence_evaluated_by END, competence_evaluated_at = CASE WHEN :comp THEN "
    "clock_timestamp() ELSE competence_evaluated_at END, independence_confirmed_at = CASE WHEN "
    ":ind THEN clock_timestamp() ELSE independence_confirmed_at END, peer_review_obtained_on = "
    "coalesce(:peer, peer_review_obtained_on), row_version = row_version + 1 WHERE id = :a "
    "RETURNING row_version"
)
_INSTRUCTIONS_OF: Final = text(
    "SELECT id, status, current_version_id, row_version FROM component_instructions "
    "WHERE component_auditor_id = :a"
)
_INSTRUCTIONS: Final = text(
    "SELECT i.id, i.engagement_id, i.work_item_id, i.component_auditor_id, i.status, "
    "i.current_version_id, i.row_version, v.sections, v.content_hash, v.created_by, "
    "v.created_at, v.version_no FROM component_instructions i JOIN "
    "component_instruction_versions v ON v.id = i.current_version_id WHERE i.id = :i"
)
_INSERT_INSTRUCTIONS: Final = text(
    "INSERT INTO component_instructions (tenant_id, engagement_id, work_item_id, "
    "component_auditor_id) VALUES (:t, :e, :w, :a) RETURNING id"
)
_INSERT_VERSION: Final = text(
    "INSERT INTO component_instruction_versions (tenant_id, engagement_id, work_item_id, "
    "instructions_id, version_no, sections, content_hash, created_by) VALUES (:t, :e, :w, :i, "
    "(SELECT coalesce(max(version_no), 0) + 1 FROM component_instruction_versions "
    "WHERE instructions_id = :i), CAST(:s AS jsonb), :h, :by) RETURNING id"
)
_POINT: Final = text(
    "UPDATE component_instructions SET current_version_id = :v, row_version = row_version + 1 "
    "WHERE id = :i AND status = 'draft' AND row_version = :rv RETURNING row_version"
)
_GROUP_CT: Final = text(
    "SELECT ct FROM materiality_versions WHERE work_item_id = :w AND scope = 'group' "
    "AND status IN ('decided', 'revised') ORDER BY version_no DESC LIMIT 1"
)
_MILESTONES: Final = text(
    "SELECT kind, label, due_on FROM component_milestones WHERE component_auditor_id = :a "
    "ORDER BY due_on, position"
)
_INSERT_SEND: Final = text(
    "INSERT INTO component_instruction_sends (tenant_id, engagement_id, work_item_id, "
    "instructions_id, version_id, recipient_contact_id, sent_by, content_hash, "
    "generated_document_id) VALUES (:t, :e, :w, :i, :v, :r, :by, :h, :doc) RETURNING id"
)
_SEND: Final = text(
    "SELECT s.id, s.instructions_id, s.version_id, s.recipient_contact_id, s.sent_by, "
    "s.created_at, s.completed_at, s.undone_at, i.engagement_id, i.work_item_id, "
    "i.component_auditor_id FROM component_instruction_sends s JOIN component_instructions i "
    "ON i.id = s.instructions_id WHERE s.id = :s"
)
_UNDO: Final = text(
    "UPDATE component_instruction_sends SET undone_at = clock_timestamp() WHERE id = :s "
    "AND sent_by = :by AND completed_at IS NULL AND undone_at IS NULL "
    "AND clock_timestamp() <= created_at + interval '10 seconds' RETURNING id"
)
_COMPLETE: Final = text(
    "UPDATE component_instruction_sends SET completed_at = clock_timestamp(), grant_id = :g "
    "WHERE id = :s AND completed_at IS NULL AND undone_at IS NULL "
    "AND clock_timestamp() >= created_at + interval '10 seconds' RETURNING id"
)
_MARK_SENT: Final = text(
    "UPDATE component_instructions SET status = 'sent', sent_by = :by, sent_at = "
    "clock_timestamp(), sent_actor_kind = 'human', row_version = row_version + 1 "
    "WHERE id = :i AND status = 'draft'"
)
_DELIVERABLES: Final = text(
    "SELECT id, title, due_on, status, received_at, reviewed_by, returned_at, return_reason "
    "FROM component_deliverables WHERE component_auditor_id = :a ORDER BY due_on, created_at"
)
_DELIVERABLE: Final = text(
    "SELECT d.id, d.engagement_id, d.work_item_id, d.component_auditor_id, d.status, "
    "d.row_version, a.component_id FROM component_deliverables d JOIN component_auditors a "
    "ON a.id = d.component_auditor_id WHERE d.id = :d"
)
_INSERT_DELIVERABLE: Final = text(
    "INSERT INTO component_deliverables (tenant_id, engagement_id, work_item_id, "
    "component_auditor_id, title, due_on) VALUES (:t, :e, :w, :a, :title, :due) RETURNING id"
)
_INSERT_MILESTONE: Final = text(
    "INSERT INTO component_milestones (tenant_id, engagement_id, work_item_id, "
    "component_auditor_id, kind, label, due_on, deliverable_id) VALUES (:t, :e, :w, :a, :k, "
    ":label, :due, :d)"
)
_REVIEW: Final = text(
    "UPDATE component_deliverables SET status = 'reviewed', reviewed_by = :by, reviewed_at = "
    "clock_timestamp(), reviewed_actor_kind = 'human', row_version = row_version + 1 "
    "WHERE id = :d AND status = 'received' RETURNING id"
)
_RETURN: Final = text(
    "UPDATE component_deliverables SET status = 'expected', returned_at = clock_timestamp(), "
    "return_reason = :why, received_at = NULL, evidence_item_id = NULL, "
    "row_version = row_version + 1 WHERE id = :d AND status = 'received' RETURNING id"
)
_RECEIVE: Final = text(
    "UPDATE component_deliverables SET status = 'received', received_at = clock_timestamp(), "
    "evidence_item_id = :item, returned_at = NULL, return_reason = NULL, "
    "row_version = row_version + 1 WHERE id = :d AND status = 'expected' RETURNING id"
)
_ACKNOWLEDGE: Final = text(
    "UPDATE component_instructions SET status = 'acknowledged', acknowledged_contact_id = :c, "
    "acknowledged_at = clock_timestamp(), row_version = row_version + 1 "
    "WHERE id = :i AND status = 'sent' RETURNING engagement_id"
)


async def _auditor(tenant: TenantContext, auditor_id: UUID) -> dict[str, object]:
    async with tenant_session(tenant) as session:
        found = (await session.execute(_AUDITOR, {"a": auditor_id})).mappings().first()
    if found is None:
        raise NotFound("component_auditor")
    return dict(found)


# --- auditors ------------------------------------------------------------------------------------


async def auditors(ctx: AuthContext, work_item_id: UUID) -> list[AuditorView]:
    """AUD-35's queue (the route authorised `component_auditor.read`)."""
    from abacus.modules.organisations.api import contact_facts

    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_AUDITORS, {"w": work_item_id})).mappings().all()
        contacts = [cast(UUID, r["ep_contact_id"]) for r in rows if r["ep_contact_id"]]
        facts = await contact_facts(session, contacts) if contacts else {}
    return [
        AuditorView(
            id=cast(UUID, r["id"]),
            organisation_name=str(r["organisation_name"]),
            city=cast(str | None, r["city"]),
            component_id=cast(UUID, r["component_id"]),
            contact_name=(
                facts[cast(UUID, r["ep_contact_id"])].display_name
                if r["ep_contact_id"] in facts
                else None
            ),
            questionnaire_received_on=cast(date | None, r["questionnaire_received_on"]),
            competence_evaluated_at=cast(datetime | None, r["competence_evaluated_at"]),
            independence_confirmed_at=cast(datetime | None, r["independence_confirmed_at"]),
            peer_review_obtained_on=cast(date | None, r["peer_review_obtained_on"]),
            make_reference=bool(r["make_reference"]),
            instructions_status=cast(str | None, r["instructions_status"]),
        )
        for r in rows
    ]


async def add_auditor(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    organisation_name: str,
    city: str | None,
    component_id: UUID,
    ep_contact_id: UUID | None,
) -> AuditorView:
    _person(ctx, "component_auditor.manage")
    async with tenant_session(ctx.tenant) as session:
        component = (await session.execute(_COMPONENT, {"c": component_id})).mappings().first()
    if component is None or component["work_item_id"] != work_item_id:
        raise ComponentNotAudited(facts={"field": "component_id"})
    engagement_id = cast(UUID, component["engagement_id"])
    async with uow(ctx.tenant) as tx:
        made = cast(
            UUID,
            await tx.session.scalar(
                _INSERT_AUDITOR,
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "o": organisation_name.strip(),
                    "city": (city or "").strip() or None,
                    "c": component_id,
                    "ep": ep_contact_id,
                    "by": ctx.user_id,
                },
            ),
        )
        tx.record(
            "component_auditor.added",
            target=Target("component_auditor", made),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return next(a for a in await auditors(ctx, work_item_id) if a.id == made)


async def evaluate(
    ctx: AuthContext,
    auditor_id: UUID,
    *,
    questionnaire_received_on: date | None,
    competence_evaluated: bool,
    independence_confirmed: bool,
    peer_review_obtained_on: date | None,
) -> AuditorView:
    """The evaluation facts a person records (AU-C 600 .A40 ff.): each stamp names who and when."""
    _person(ctx, "component_auditor.manage")
    row = await _auditor(ctx.tenant, auditor_id)
    await authorise(
        ctx, "component_auditor.manage", await _resource(ctx, cast(UUID, row["engagement_id"]))
    )
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _EVALUATE,
            {
                "q": questionnaire_received_on,
                "comp": competence_evaluated,
                "ind": independence_confirmed,
                "peer": peer_review_obtained_on,
                "by": ctx.user_id,
                "a": auditor_id,
            },
        )
        tx.record("component_auditor.evaluated", target=Target("component_auditor", auditor_id))
    return next(
        a for a in await auditors(ctx, cast(UUID, row["work_item_id"])) if a.id == auditor_id
    )


# --- instructions --------------------------------------------------------------------------------


async def _facts(tenant: TenantContext, row: Mapping[str, object]) -> dict[str, str]:
    """Code's facts for the merge: the component PM, the group's clearly-trivial threshold and
    the required-communications dates; nothing else of group materiality (AU-C 600)."""
    async with tenant_session(tenant) as session:
        ct = await session.scalar(_GROUP_CT, {"w": row["work_item_id"]})
        milestones = (await session.execute(_MILESTONES, {"a": row["id"]})).all()
    facts: dict[str, str] = {"component_auditor": str(row["organisation_name"])}
    if row["component_pm"] is not None:
        facts["component_pm"] = money(Decimal(str(row["component_pm"])))
    if ct is not None:
        facts["clearly_trivial_threshold"] = money(Decimal(str(ct)))
    if milestones:
        facts["required_communications"] = "\n".join(
            f"{(m.label or str(m.kind).replace('_', ' ').capitalize())}: "
            f"{cast(date, m.due_on):%b %-d, %Y}"
            for m in milestones
        )
    return facts


async def _view(ctx: AuthContext, instructions_id: UUID) -> InstructionsView:
    async with tenant_session(ctx.tenant) as session:
        r = (await session.execute(_INSTRUCTIONS, {"i": instructions_id})).mappings().first()
    if r is None:
        raise NotFound("component_instructions")
    raw = r["sections"]
    stored = cast("list[dict[str, object]]", json.loads(raw) if isinstance(raw, str) else raw)
    sections = tuple(
        Section(
            int(cast(int, s["number"])),
            str(s["title"]),
            str(s["body"]),
            bool(s["needs_input"]),
        )
        for s in stored
    )
    author = cast(UUID, r["created_by"])
    name = (await names_of([author])).get(author, "")
    at = cast(datetime, r["created_at"])
    blocked = next((s for s in sections if s.needs_input), None)
    return InstructionsView(
        id=instructions_id,
        status=str(r["status"]),
        version_id=cast(UUID, r["current_version_id"]),
        sections=sections,
        provenance=f"Drafted by {name} via Agent · {at:%-I:%M %p}",
        send_blocked_reason=(
            None
            if blocked is None
            else f"§{blocked.number} {blocked.title} needs input before you can send."
        ),
        content_hash=str(r["content_hash"]),
        row_version=int(cast(int, r["row_version"])),
    )


async def _insert_version(
    tx: UnitOfWork, ctx: AuthContext, row: Mapping[str, object], instructions_id: UUID,
    sections: Sequence[Section],
) -> UUID:  # fmt: skip
    return cast(
        UUID,
        await tx.session.scalar(
            _INSERT_VERSION,
            {
                "t": ctx.tenant_id,
                "e": row["engagement_id"],
                "w": row["work_item_id"],
                "i": instructions_id,
                "s": json.dumps(
                    [
                        {
                            "number": s.number,
                            "title": s.title,
                            "body": s.body,
                            "needs_input": s.needs_input,
                        }
                        for s in sections
                    ]
                ),
                "h": sections_hash(sections),
                "by": ctx.user_id,
            },
        ),
    )


async def draft_instructions(ctx: AuthContext, auditor_id: UUID) -> InstructionsView:
    """The deterministic draft run on the person's behalf (DV-6; no model): the firm's template
    merged with code's facts. A redraft of a draft is a new version; sent letters never change."""
    from abacus.modules.methodology.api import published_body, published_clauses

    _person(ctx, "component_instructions.draft")
    row = await _auditor(ctx.tenant, auditor_id)
    await authorise(
        ctx, "component_instructions.draft", await _resource(ctx, cast(UUID, row["engagement_id"]))
    )
    template = await published_clauses(ctx.tenant, FAMILY)
    blocks = (
        None if template is None else await published_body(ctx.tenant, FAMILY, template.version_id)
    )
    parsed = template_sections(blocks)
    if not parsed:
        raise TemplateMissing(facts={"family": FAMILY})
    sections = merge(parsed, await _facts(ctx.tenant, row))
    async with tenant_session(ctx.tenant) as session:
        existing = (await session.execute(_INSTRUCTIONS_OF, {"a": auditor_id})).mappings().first()
    async with uow(ctx.tenant) as tx:
        if existing is None:
            instructions_id = cast(
                UUID,
                await tx.session.scalar(
                    _INSERT_INSTRUCTIONS,
                    {
                        "t": ctx.tenant_id,
                        "e": row["engagement_id"],
                        "w": row["work_item_id"],
                        "a": auditor_id,
                    },
                ),
            )
            rv = 1
        else:
            if existing["status"] != "draft":
                raise AlreadySent(facts={"status": str(existing["status"])})
            instructions_id = cast(UUID, existing["id"])
            rv = int(cast(int, existing["row_version"]))
        version = await _insert_version(tx, ctx, row, instructions_id, sections)
        if await tx.session.scalar(_POINT, {"v": version, "i": instructions_id, "rv": rv}) is None:
            raise InstructionsStale(facts={"instructions": str(instructions_id)})
        tx.record(
            "component_instructions.drafted",
            target=Target("component_instructions", instructions_id),
            after=Ref(version=version, n=sum(1 for s in sections if s.needs_input)),
        )
    return await _view(ctx, instructions_id)


async def edit_section(
    ctx: AuthContext, instructions_id: UUID, *, number: int, body: str, seen_version: int
) -> InstructionsView:
    """A person's words for one section: a new version, the section no longer Needs input."""
    _person(ctx, "component_instructions.edit")
    current = await _view(ctx, instructions_id)
    if current.status != "draft":
        raise AlreadySent(facts={"status": current.status})
    if current.row_version != seen_version:
        raise InstructionsStale(facts={"row_version": current.row_version})
    async with tenant_session(ctx.tenant) as session:
        r = (await session.execute(_INSTRUCTIONS, {"i": instructions_id})).mappings().one()
    await authorise(
        ctx, "component_instructions.edit", await _resource(ctx, cast(UUID, r["engagement_id"]))
    )
    if number not in {s.number for s in current.sections}:
        raise NotFound("instructions_section")
    sections = tuple(
        replace(s, body=body.strip(), needs_input=False) if s.number == number else s
        for s in current.sections
    )
    async with uow(ctx.tenant) as tx:
        version = await _insert_version(tx, ctx, dict(r), instructions_id, sections)
        if (
            await tx.session.scalar(
                _POINT, {"v": version, "i": instructions_id, "rv": seen_version}
            )
            is None
        ):
            raise InstructionsStale(facts={"instructions": str(instructions_id)})
        tx.record(
            "component_instructions.edited",
            target=Target("component_instructions", instructions_id),
            after=Ref(version=version, position=number),
        )
    return await _view(ctx, instructions_id)


def instruction_blocks(sections: Sequence[Section]) -> list[object]:
    """The C11 body: each section's numbered heading, then its paragraphs (the firm's words)."""
    blocks: list[object] = []
    for s in sections:
        blocks.append({"type": "heading", "level": 2, "text": f"{s.number}. {s.title}".strip()})
        for para in (p.strip() for p in s.body.split("\n\n")):
            if para:
                blocks.append({"type": "paragraph", "runs": [{"type": "text", "text": para}]})
    return blocks


_sending: ContextVar[tuple[object, UUID] | None] = ContextVar("component_send", default=None)


async def letter_body(tenant: TenantContext, owner: object, _scope: object) -> list[object]:
    """C11's body provider: the owner version's sections."""
    from abacus.modules.reporting.api import OwnerRef

    if not isinstance(owner, OwnerRef) or owner.type != "component_instruction_version":
        return []
    async with tenant_session(tenant) as session:
        raw = await session.scalar(
            text("SELECT sections FROM component_instruction_versions WHERE id = :v"),
            {"v": owner.id},
        )
    if raw is None:
        raise NotFound("component_instruction_version")
    stored = cast("list[dict[str, object]]", json.loads(raw) if isinstance(raw, str) else raw)
    return instruction_blocks(
        [
            Section(int(cast(int, s["number"])), str(s["title"]), str(s["body"]), False)
            for s in stored
        ]
    )


async def send_approval(ref: object) -> tuple[UUID, str] | None:
    """C11's approval provider: only the send in flight, for the person sending it."""
    held = _sending.get()
    return None if held is None or held[0] != ref else (held[1], getattr(ref, "content_hash", ""))


async def _no_variables(*_: object) -> Mapping[str, str]:
    return {}


def register() -> None:
    """At import (assurance/api.py): the C11 kind, the EP's make-reference card and the gate."""
    from abacus.modules.reporting import api as c11
    from abacus.modules.review.api import DecisionKind, register_decision_kind

    try:
        c11.document_kind(FAMILY)
    except c11.UnknownDocumentKind:
        c11.register_document_kind(
            c11.DocumentKind(
                kind=FAMILY,
                layout="letter",
                variables_provider=_no_variables,
                approval_provider=send_approval,
                body_provider=letter_body,
                retention_record_type="audit_documentation",  # AU-C 230
                formats=("pdf",),
            )
        )
    register_decision_kind(
        DecisionKind(
            code=MAKE_REFERENCE,
            reserved_role="engagement_partner",
            options=_make_reference_card,
            questions={MAKE_REFERENCE: "Make reference to the component auditor"},
            apply=_apply_make_reference,
        )
    )


async def send_instructions(
    ctx: AuthContext, instructions_id: UUID, *, recipient_contact_id: UUID, version_id: UUID
) -> tuple[InstructionsView, UUID]:
    """A live person's send (never the agent): complete, the auditor's contact, the version on
    screen. The letter renders final now; the grant and invitation wait out the 10-second Undo."""
    from abacus.modules.engagements.api import get_ref
    from abacus.modules.reporting import api as c11

    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("component_instructions.send", "role")
    current = await _view(ctx, instructions_id)
    async with tenant_session(ctx.tenant) as session:
        r = (await session.execute(_INSTRUCTIONS, {"i": instructions_id})).mappings().one()
    engagement_id = cast(UUID, r["engagement_id"])
    await authorise(ctx, "component_instructions.send", await _resource(ctx, engagement_id))
    if current.status != "draft":
        raise AlreadySent(facts={"status": current.status})
    if current.version_id != version_id:
        raise InstructionsStale(facts={"version": str(version_id)})
    if current.send_blocked_reason is not None:
        raise InstructionsIncomplete(facts={"instructions": str(instructions_id)})
    auditor = await _auditor(ctx.tenant, cast(UUID, r["component_auditor_id"]))
    if auditor["ep_contact_id"] != recipient_contact_id:
        raise RecipientInvalid(facts={"field": "recipient_contact_id"})
    client_id = (await get_ref(ctx, engagement_id)).client_id
    who = c11.Requester("human", user_id=ctx.user_id)
    async with uow(ctx.tenant) as tx:
        ticket = await c11.render(
            tx,
            c11.RenderRequest(
                kind=FAMILY,
                owner_ref=c11.OwnerRef("component_instruction_version", version_id),
                scope=c11.RenderScope(
                    client_id=client_id,
                    engagement_id=engagement_id,
                    work_item_id=cast(UUID, r["work_item_id"]),
                ),
                template_version_id=None,
                requested_by=who,
                formats=("pdf",),
            ),
        )
        send_id = cast(
            UUID,
            await tx.session.scalar(
                _INSERT_SEND,
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": r["work_item_id"],
                    "i": instructions_id,
                    "v": version_id,
                    "r": recipient_contact_id,
                    "by": ctx.user_id,
                    "h": current.content_hash,
                    "doc": ticket.generated_document_id,
                },
            ),
        )
        ref = c11.ApprovalRef("component_instruction_send", send_id, ticket.content_hash)
        token = _sending.set((ref, ctx.user_id))
        try:
            await c11.render_final(tx, ticket.generated_document_id, ref, who)
        finally:
            _sending.reset(token)
        tx.record(
            "component_instructions.send_requested",
            target=Target("component_instructions", instructions_id),
            after=Ref(send=send_id),
        )
    from abacus.kernel.dispatch import dispatch

    await dispatch(
        InstructionsSendWorkflow,
        SendInput(str(ctx.tenant_id), str(send_id)),
        id=f"component_send:{ctx.tenant_id}:{send_id}",
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return current, send_id


async def undo_send(ctx: AuthContext, send_id: UUID) -> None:
    """The sender's Undo inside 10 seconds: nothing is sent, the letter stays a draft."""
    _person(ctx, "component_instructions.send")
    async with uow(ctx.tenant) as tx:
        done = await tx.session.scalar(_UNDO, {"s": send_id, "by": ctx.user_id})
        if done is None:
            raise UndoWindowClosed(facts={"send": str(send_id)})
        tx.record("component_instructions.send_undone", target=Target("component_send", send_id))


async def complete_send(tenant_id: UUID, send_id: UUID) -> str:
    """After the Undo window: the grant (and invitation), Sent, `component_instructions.sent`.
    An undone or already completed send does nothing."""
    from abacus.modules.identity.api import grant_component_auditor
    from abacus.modules.organisations.api import contact_facts, signer_contacts

    tenant = TenantContext(tenant_id, "system", f"component_send:{send_id}")
    async with tenant_session(tenant) as session:
        s = (await session.execute(_SEND, {"s": send_id})).mappings().first()
        if s is None or s["undone_at"] is not None or s["completed_at"] is not None:
            return "skipped"
        contact = cast(UUID, s["recipient_contact_id"])
        people = await contact_facts(session, [contact])
        auditor = (
            (await session.execute(_AUDITOR, {"a": s["component_auditor_id"]})).mappings().one()
        )
    person = people.get(contact)
    if person is None:
        return "recipient_missing"
    emails = await signer_contacts(tenant, [contact])
    async with uow(tenant) as tx:
        given = await grant_component_auditor(
            tx,
            tenant,
            engagement_id=cast(UUID, s["engagement_id"]),
            client_id=person.client_id,
            contact_id=contact,
            user_id=person.user_id,
            email=None if contact not in emails else emails[contact].email,
            component_id=cast(UUID, auditor["component_id"]),
            granted_by=cast(UUID, s["sent_by"]),
        )
        grant = given.grant_id  # None while the invitation carries a pending grant
        done = await tx.session.scalar(_COMPLETE, {"s": send_id, "g": grant})
        if done is None:
            return "window_open"
        await tx.session.execute(_MARK_SENT, {"i": s["instructions_id"], "by": s["sent_by"]})
        tx.record(
            "component_instructions.sent",
            target=Target("component_instructions", cast(UUID, s["instructions_id"])),
            after=Ref(send=send_id),
            scope=Scope(
                engagement_id=cast(UUID, s["engagement_id"]),
                work_item_id=cast(UUID, s["work_item_id"]),
            ),
        )
        tx.emit(
            ComponentInstructionsSent(
                instructions_id=cast(UUID, s["instructions_id"]),
                component_id=cast(UUID, auditor["component_id"]),
                engagement_id=cast(UUID, s["engagement_id"]),
            )
        )
    return "sent"


@dataclass(frozen=True)
class SendInput:
    tenant_id: str
    send_id: str


@activity.defn(name="assurance.component_instructions.complete_send")
async def complete_send_activity(p: SendInput) -> str:
    return await complete_send(UUID(p.tenant_id), UUID(p.send_id))


@workflow.defn(name="ComponentInstructionsSend")
class InstructionsSendWorkflow:
    """Wait out the Undo window, then complete the send once."""

    @workflow.run
    async def run(self, p: SendInput) -> str:
        await workflow.sleep(timedelta(seconds=UNDO_SECONDS + 1))
        return await workflow.execute_activity(
            "assurance.component_instructions.complete_send",
            p,
            result_type=str,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )


async def acknowledge(tenant: TenantContext, instructions_id: UUID, contact_id: UUID) -> None:
    """POR-23's acknowledge (A-09-T33 calls it for the auditor's own contact)."""
    async with uow(tenant) as tx:
        engagement = await tx.session.scalar(_ACKNOWLEDGE, {"i": instructions_id, "c": contact_id})
        if engagement is None:
            raise NotFound("component_instructions")
        component = await tx.session.scalar(
            text(
                "SELECT a.component_id FROM component_instructions i JOIN component_auditors a "
                "ON a.id = i.component_auditor_id WHERE i.id = :i"
            ),
            {"i": instructions_id},
        )
        tx.record(
            "component_instructions.acknowledged",
            target=Target("component_instructions", instructions_id),
        )
        tx.emit(
            ComponentInstructionsAcknowledged(
                instructions_id=instructions_id,
                component_id=cast(UUID, component),
                engagement_id=cast(UUID, engagement),
            )
        )


# --- make reference ------------------------------------------------------------------------------


def make_reference_question(auditor_id: UUID) -> str:
    return f"{MAKE_REFERENCE}.{auditor_id.hex}"


async def _make_reference_card(tenant: TenantContext, subject: object) -> ComputedCard:
    from abacus.modules.review.api import CardOption

    del tenant, subject
    return ComputedCard(
        options=(
            CardOption("make_reference", "Make reference to the component auditor's report"),
            CardOption("no_reference", "Do not make reference"),
        )
    )


async def raise_make_reference(ctx: AuthContext, auditor_id: UUID) -> UUID:
    from abacus.modules.review.api import raise_decision_card

    _person(ctx, "component_auditor.manage")
    row = await _auditor(ctx.tenant, auditor_id)
    return await raise_decision_card(
        ctx,
        engagement_id=cast(UUID, row["engagement_id"]),
        kind=MAKE_REFERENCE,
        question_key=make_reference_question(auditor_id),
        work_item_id=cast(UUID, row["work_item_id"]),
        raised_under="component_auditor.manage",
    )


async def _apply_make_reference(tx: UnitOfWork, ctx: AuthContext, decided: object) -> None:
    """The EP's decision sets the auditor's flag in the decider's own unit of work."""
    key = str(getattr(decided, "question_key", ""))
    if not key.startswith(f"{MAKE_REFERENCE}."):
        return
    auditor_id = UUID(hex=key.split(".", 1)[1])
    flag = getattr(decided, "option_key", "") == "make_reference"
    await tx.session.execute(
        text(
            "UPDATE component_auditors SET make_reference = :f, row_version = row_version + 1 "
            "WHERE id = :a"
        ),
        {"f": flag, "a": auditor_id},
    )
    tx.record(
        "component_auditor.make_reference_decided",
        target=Target("component_auditor", auditor_id),
        after=Ref(on=flag),
    )
    del ctx


# --- deliverables --------------------------------------------------------------------------------


async def deliverables(ctx: AuthContext, auditor_id: UUID) -> list[DeliverableView]:
    from abacus.kernel.clock import today

    row = await _auditor(ctx.tenant, auditor_id)
    await authorise(
        ctx, "component_deliverable.read", await _resource(ctx, cast(UUID, row["engagement_id"]))
    )
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_DELIVERABLES, {"a": auditor_id})).mappings().all()
    reviewers = [cast(UUID, r["reviewed_by"]) for r in rows if r["reviewed_by"]]
    names = await names_of(reviewers) if reviewers else {}
    now = await today(ctx.tenant)
    out: list[DeliverableView] = []
    for r in rows:
        status, late = deliverable_status(
            str(r["status"]), cast(date, r["due_on"]), r["returned_at"] is not None, now
        )
        out.append(
            DeliverableView(
                id=cast(UUID, r["id"]),
                title=str(r["title"]),
                due_on=cast(date, r["due_on"]),
                status=status,
                days_late=late,
                received_at=cast(datetime | None, r["received_at"]),
                reviewed_by_name=(
                    names.get(cast(UUID, r["reviewed_by"])) if r["reviewed_by"] else None
                ),
                return_reason=cast(str | None, r["return_reason"]),
            )
        )
    return out


async def request_deliverable(
    ctx: AuthContext, auditor_id: UUID, *, title: str, due_on: date
) -> DeliverableView:
    """A deliverable the component auditor owes (also a milestone on the tracker)."""
    _person(ctx, "component_deliverable.manage")
    row = await _auditor(ctx.tenant, auditor_id)
    engagement_id = cast(UUID, row["engagement_id"])
    await authorise(ctx, "component_deliverable.manage", await _resource(ctx, engagement_id))
    async with uow(ctx.tenant) as tx:
        made = cast(
            UUID,
            await tx.session.scalar(
                _INSERT_DELIVERABLE,
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": row["work_item_id"],
                    "a": auditor_id,
                    "title": title.strip(),
                    "due": due_on,
                },
            ),
        )
        await tx.session.execute(
            _INSERT_MILESTONE,
            {
                "t": ctx.tenant_id,
                "e": engagement_id,
                "w": row["work_item_id"],
                "a": auditor_id,
                "k": "other",
                "label": title.strip()[:200],
                "due": due_on,
                "d": made,
            },
        )
        tx.record("component_deliverable.requested", target=Target("component_deliverable", made))
        tx.emit(
            ComponentDeliverableEvent(
                deliverable_id=made,
                component_id=cast(UUID, row["component_id"]),
                engagement_id=engagement_id,
                change="requested",
            )
        )
    return next(d for d in await deliverables(ctx, auditor_id) if d.id == made)


async def _deliverable(tenant: TenantContext, deliverable_id: UUID) -> dict[str, object]:
    async with tenant_session(tenant) as session:
        r = (await session.execute(_DELIVERABLE, {"d": deliverable_id})).mappings().first()
    if r is None:
        raise NotFound("component_deliverable")
    return dict(r)


async def _decide(
    ctx: AuthContext, deliverable_id: UUID, sql: object, params: dict[str, object], change: str
) -> DeliverableView:
    _person(ctx, "component_deliverable.review")
    d = await _deliverable(ctx.tenant, deliverable_id)
    engagement_id = cast(UUID, d["engagement_id"])
    await authorise(ctx, "component_deliverable.review", await _resource(ctx, engagement_id))
    async with uow(ctx.tenant) as tx:
        if await tx.session.scalar(sql, {"d": deliverable_id, **params}) is None:  # type: ignore[arg-type] -- a text clause
            raise DeliverableClosed(facts={"status": str(d["status"])})
        tx.record(
            f"component_deliverable.{change}",
            target=Target("component_deliverable", deliverable_id),
        )
        tx.emit(
            ComponentDeliverableEvent(
                deliverable_id=deliverable_id,
                component_id=cast(UUID, d["component_id"]),
                engagement_id=engagement_id,
                change=change,
            )
        )
    auditor = cast(UUID, d["component_auditor_id"])
    return next(x for x in await deliverables(ctx, auditor) if x.id == deliverable_id)


async def review_deliverable(ctx: AuthContext, deliverable_id: UUID) -> DeliverableView:
    """A person's review of a received deliverable (never the agent; the CHECK holds it too)."""
    return await _decide(ctx, deliverable_id, _REVIEW, {"by": ctx.user_id}, "reviewed")


async def return_deliverable(
    ctx: AuthContext, deliverable_id: UUID, *, reason: str
) -> DeliverableView:
    """Returned with a person's note: the auditor uploads again (POR-23 e)."""
    return await _decide(ctx, deliverable_id, _RETURN, {"why": reason.strip()}, "returned")


async def receive_deliverable(
    tenant: TenantContext, deliverable_id: UUID, evidence_item_id: UUID
) -> None:
    """The portal's upload (A-09-T33) landed as an evidence version on this deliverable."""
    d = await _deliverable(tenant, deliverable_id)
    async with uow(tenant) as tx:
        if (
            await tx.session.scalar(_RECEIVE, {"d": deliverable_id, "item": evidence_item_id})
            is None
        ):
            raise DeliverableClosed(facts={"status": str(d["status"])})
        tx.record(
            "component_deliverable.received",
            target=Target("component_deliverable", deliverable_id),
        )
        tx.emit(
            ComponentDeliverableEvent(
                deliverable_id=deliverable_id,
                component_id=cast(UUID, d["component_id"]),
                engagement_id=cast(UUID, d["engagement_id"]),
                change="received",
            )
        )


WORKFLOWS: Final[dict[type, str]] = {InstructionsSendWorkflow: "interactive"}
ACTIVITIES: Final[tuple[object, ...]] = (complete_send_activity,)


# --- the shared Questions thread (component_thread) ----------------------------------------------


class ComponentThreadAnchors:
    """`component_thread`: one thread per component auditor (AUD-35 c, POR-23 b), shared with the
    auditor's portal room (A-09-T33's reader policy)."""

    locator_keys: frozenset[str] = frozenset()

    async def facts(self, ctx: AuthContext, anchor_id: UUID, locator: object) -> object | None:
        from abacus.modules.collaboration.api import AnchorFacts
        from abacus.modules.engagements.api import get_ref

        del locator
        async with tenant_session(ctx.tenant) as session:
            row = (await session.execute(_AUDITOR, {"a": anchor_id})).mappings().first()
        if row is None:
            return None
        ref = await get_ref(ctx, cast(UUID, row["engagement_id"]))
        return AnchorFacts(
            tenant_id=ctx.tenant_id,
            engagement_id=cast(UUID, row["engagement_id"]),
            client_id=ref.client_id,
            label=f"{row['organisation_name']} · Questions",
            archived=ref.archived,
            work_item_id=cast(UUID, row["work_item_id"]),
            client_visible=True,
        )


THREAD_KIND: Final = "component_thread"
THREAD_ANCHORS: Final = ComponentThreadAnchors()
