"""The report builder (A-07-T27; A-07 F5; SPEC-644; AU-C 700, 705, 706, 720, 703; P-11 C11;
DEC-3012). PROTECTED (amber).

AUD-23 over A-07-T08's `audit_reports` and insert-only `audit_report_versions` (0668):

- **Choices are structured, never free text**, and each is validated where it is made:
  - `opinion_form` (`unmodified`, `qualified`, `adverse`, `disclaimer`) and `modification_basis`
    are the engagement partner's: any value but `unmodified` needs the EP's decided SHL-11 card
    (`opinion`, reserved to the engagement partner) whose option is that form, or it
    answers 409 `decision_required`. An agent or any non-person is refused here as well as by the
    matrix (`report.draft` is agent-deny for the opinion), at every layer (INV-1).
  - `going_concern` (the emphasis paragraph) is locked by AUD-19's going-concern decision: on when
    code finds the concluded doubt, and no one can switch it off (`locked_by`).
  - `erisa_supplemental_schedules` (ERISA-SUPP) and `other_information` (AU-C 720, OM-OTHER) are
    toggles with their reason code.
- **Assembly is server-side**: the published C11 `audit_report` template (or `review_report`,
  `compilation_report`) gives the paragraph blocks; the choices switch blocks on or off by their
  clause id, each recorded with its reason code. The composer never sees the wording: C11 holds
  it and renders it (ADR-320).
- **Versions** are insert-only; a choice that changes anything is a new version with its content
  hash. The word diff between two versions goes through C11 compare (P-11).
- **Draft renders** go through C11's DOCX writer with the DRAFT mark and the signature
  placeholder; the same version renders byte-identically. A render of a version that is no longer
  current is Out of date (AUD-23 j).

The EP's approval is an L4 sign-off on the report version (P-04's sign-off grammar; SHL-12),
recorded by review against the `audit_report_version` target this module registers.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.assurance.rep_letters import going_concern_doubt
from abacus.modules.engagements.api import (
    assurance_item,
    engagement_hold_facts,
    engagement_type_of,
    get_ref,
)
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.methodology.api import published_body, published_clauses
from abacus.modules.review.api import decided_cards, raise_decision_card

OpinionForm = Literal["unmodified", "qualified", "adverse", "disclaimer"]
OPINION_FORMS: Final[tuple[OpinionForm, ...]] = (
    "unmodified",
    "qualified",
    "adverse",
    "disclaimer",
)
ReportKind = Literal["audit", "review", "compilation"]
FAMILY: Final[dict[ReportKind, str]] = {
    "audit": "audit_report",
    "review": "review_report",
    "compilation": "compilation_report",
}
# A-07-T41 (DEC-3302): the report's kind follows the engagement type (AUD-23 e/f: an AR-C 90
# review or an AR-C 80 compilation uses its own template and title); every other attest type is
# an audit report.
KIND_OF_TYPE: Final[dict[str, ReportKind]] = {"review": "review", "compilation": "compilation"}
# The C3 card's question key, as `a07_registrations` registers the `opinion` kind (DEC-3028).
OPINION_KIND: Final = "opinion"
OPINION_CARD: Final = "opinion"
# The structured choices and who may set them.
PARTNER_FIELDS: Final = frozenset({"opinion_form", "modification_basis"})
TOGGLES: Final[dict[str, str]] = {
    "erisa_supplemental_schedules": "ERISA-SUPP",
    "other_information": "OM-OTHER",
}
LOCKED: Final[dict[str, str]] = {"going_concern": "AUD-19 going concern"}
FIELDS: Final = PARTNER_FIELDS | frozenset(TOGGLES) | frozenset(LOCKED)
_BASIS: Final = frozenset({"material_misstatement", "scope_limitation"})


class DecisionRequired(DomainConflict):
    """A modified opinion with no decided EP card for that form (AC: 409 `decision_required`)."""

    code = "decision_required"


class ChoiceLocked(DomainConflict):
    code = "choice_locked"


class ChoiceInvalid(DomainInvalid):
    code = "choice_invalid"


class StaleReport(DomainConflict):
    code = "item_changed"


class NoReportTemplate(DomainConflict):
    code = "template_missing"


class ReportNotDraft(DomainConflict):
    """The report date and city change only while the report is a draft (A-07-T41)."""

    code = "report_not_draft"


@dataclass(frozen=True)
class Choice:
    field: str
    value: str | bool | None
    locked_by: str | None = None
    decision_card_id: UUID | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class Paragraph:
    block_id: str
    included: bool
    reason_code: str | None = None


def default_choices() -> dict[str, Choice]:
    return {
        "opinion_form": Choice("opinion_form", "unmodified"),
        "modification_basis": Choice("modification_basis", None),
        "going_concern": Choice("going_concern", False, LOCKED["going_concern"]),
        "erisa_supplemental_schedules": Choice("erisa_supplemental_schedules", False),
        "other_information": Choice("other_information", False),
    }


def paragraphs(
    clauses: Sequence[tuple[str, bool]], choices: Mapping[str, Choice]
) -> list[Paragraph]:
    """Each template clause on or off from the choices: an `opinion_<form>` or `basis_<form>`
    clause follows the opinion form; `eom_going_concern`, `erisa_supplemental` and
    `other_information` follow their choices with their reason codes; any other clause keeps its
    default, so the firm's own clause is never dropped."""
    form = str(choices["opinion_form"].value or "unmodified")
    out: list[Paragraph] = []
    for clause_id, default in clauses:
        if clause_id.startswith(("opinion_", "basis_")):
            out.append(Paragraph(clause_id, clause_id.endswith(f"_{form}")))
        elif clause_id == "eom_going_concern":
            out.append(Paragraph(clause_id, bool(choices["going_concern"].value), "EOM-GC"))
        elif clause_id == "erisa_supplemental":
            on = bool(choices["erisa_supplemental_schedules"].value)
            out.append(Paragraph(clause_id, on, "ERISA-SUPP"))
        elif clause_id == "other_information":
            out.append(Paragraph(clause_id, bool(choices["other_information"].value), "OM-OTHER"))
        else:
            out.append(Paragraph(clause_id, default))
    return out


def canonical(
    template_version_id: UUID, choices: Mapping[str, Choice], paras: Sequence[Paragraph]
) -> tuple[dict[str, object], list[dict[str, object]], str]:
    choice_json: dict[str, object] = {
        k: {
            "value": c.value,
            "locked_by": c.locked_by,
            "decision_card_id": None if c.decision_card_id is None else str(c.decision_card_id),
            "reason_code": c.reason_code,
        }
        for k, c in sorted(choices.items())
    }
    para_json: list[dict[str, object]] = [
        {"block_id": p.block_id, "included": p.included, "reason_code": p.reason_code}
        for p in paras
    ]
    body = json.dumps(
        {"template": str(template_version_id), "choices": choice_json, "paragraphs": para_json},
        sort_keys=True,
    )
    return choice_json, para_json, hashlib.sha256(body.encode()).hexdigest()


def _choices(raw: object) -> dict[str, Choice]:
    out = default_choices()
    if isinstance(raw, dict):
        for key, entry in cast(dict[str, object], raw).items():
            if key in out and isinstance(entry, dict):
                e = cast(dict[str, object], entry)
                card = e.get("decision_card_id")
                out[key] = Choice(
                    key,
                    cast(str | bool | None, e.get("value")),
                    cast(str | None, e.get("locked_by")),
                    UUID(str(card)) if card else None,
                    cast(str | None, e.get("reason_code")),
                )
    return out


async def _person(ctx: AuthContext, work_item_id: UUID, action: str) -> UUID:
    if ctx.client:
        raise NotFound("audit_report")
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")
    item = await assurance_item(ctx.tenant, work_item_id)
    await authorise(ctx, action, (await get_ref(ctx, item.engagement_id)).resource())
    return item.engagement_id


async def validate(
    ctx: AuthContext,
    engagement_id: UUID,
    work_item_id: UUID,
    current: Mapping[str, Choice],
    field_name: str,
    value: str | bool | None,
    reason_code: str | None,
) -> Choice:
    """One choice, validated where it is made (module docstring)."""
    if field_name not in FIELDS:
        raise ChoiceInvalid(facts={"field": field_name})
    if field_name in LOCKED:
        raise ChoiceLocked(facts={"field": field_name, "locked_by": "AUD-19"})  # LOCKED names it
    if field_name in TOGGLES:
        if not isinstance(value, bool):
            raise ChoiceInvalid(facts={"field": field_name})
        return Choice(field_name, value, None, None, TOGGLES[field_name] if value else None)
    if ctx.tenant.actor_kind != "human":
        raise Forbidden("report.draft", "role")  # the opinion is a person's (INV-1)
    if field_name == "modification_basis":
        if value is not None and value not in _BASIS:
            raise ChoiceInvalid(facts={"field": field_name})
        return Choice(field_name, value, None, None, reason_code)
    if value not in OPINION_FORMS:
        raise ChoiceInvalid(facts={"field": field_name})
    if value == "unmodified":
        return Choice(field_name, value)
    card = next(
        (
            c
            for c in await decided_cards(ctx.tenant, engagement_id)
            if c.question_key == OPINION_CARD and c.option_key == value
        ),
        None,
    )
    if card is None:
        raise DecisionRequired(facts={"field": "opinion_form", "value": str(value)})
    del current, work_item_id
    return Choice(field_name, value, None, card.card_id, reason_code)


# --- reads and writes ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportState:
    report_id: UUID | None
    kind: ReportKind
    status: str
    version_no: int | None
    content_hash: str | None
    choices: dict[str, Choice]
    paragraphs: tuple[Paragraph, ...]
    template_version_id: UUID | None
    row_version: int
    created_at: datetime | None = None
    versions: tuple[tuple[int, str, datetime], ...] = field(default_factory=tuple)


_REPORT = text(
    "SELECT r.id, r.report_kind, r.status, r.version, r.template_id, v.version_no, "
    "v.content_hash, v.choices, v.paragraphs, v.created_at FROM audit_reports r "
    "LEFT JOIN audit_report_versions v ON v.id = r.current_version_id WHERE r.work_item_id = :wi"
)
_VERSIONS = text(
    "SELECT v.version_no, v.content_hash, v.created_at FROM audit_report_versions v "
    "JOIN audit_reports r ON r.id = v.report_id WHERE r.work_item_id = :wi ORDER BY v.version_no"
)


async def report_kind_of(tenant: TenantContext, work_item_id: UUID) -> ReportKind:
    item = await assurance_item(tenant, work_item_id)
    return KIND_OF_TYPE.get(await engagement_type_of(tenant, item.engagement_id) or "", "audit")


async def state(tenant: TenantContext, work_item_id: UUID) -> ReportState:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_REPORT, {"wi": work_item_id})).first()
        versions = (await session.execute(_VERSIONS, {"wi": work_item_id})).all()
    if row is None:
        kind = await report_kind_of(tenant, work_item_id)
        return ReportState(None, kind, "draft", None, None, default_choices(), (), None, 0)
    paras = tuple(
        Paragraph(str(p["block_id"]), bool(p["included"]), cast(str | None, p.get("reason_code")))
        for p in cast(list[dict[str, object]], row.paragraphs or [])
    )
    return ReportState(
        row.id,
        cast(ReportKind, row.report_kind),
        str(row.status),
        row.version_no,
        row.content_hash,
        _choices(row.choices),
        paras,
        row.template_id,
        int(row.version),
        row.created_at,
        tuple((int(v.version_no), str(v.content_hash), v.created_at) for v in versions),
    )


async def read(ctx: AuthContext, work_item_id: UUID) -> ReportState:
    await _person(ctx, work_item_id, "report.read")
    return await state(ctx.tenant, work_item_id)


async def set_choice(
    ctx: AuthContext,
    work_item_id: UUID,
    field_name: str,
    value: str | bool | None,
    reason_code: str | None,
    seen_version: int,
) -> ReportState:
    """A validated choice is a new version (insert-only); the paragraphs follow it."""
    engagement_id = await _person(ctx, work_item_id, "report.draft")
    current = await state(ctx.tenant, work_item_id)
    if current.report_id is not None and current.row_version != seen_version:
        raise StaleReport(facts={"version": current.row_version})
    choice = await validate(
        ctx, engagement_id, work_item_id, current.choices, field_name, value, reason_code
    )
    choices = {**current.choices, field_name: choice}
    if await going_concern_doubt(ctx.tenant, work_item_id):
        choices["going_concern"] = Choice("going_concern", True, LOCKED["going_concern"])
    family = FAMILY[current.kind]
    template = await published_clauses(ctx.tenant, family)
    if template is None:
        raise NoReportTemplate(facts={"family": family})
    paras = paragraphs(template.clauses, choices)
    choice_json, para_json, digest = canonical(template.version_id, choices, paras)
    async with uow(ctx.tenant) as tx:
        report_id = current.report_id
        if report_id is None:
            report_id = cast(
                UUID,
                await tx.session.scalar(
                    text(
                        "INSERT INTO audit_reports (tenant_id, engagement_id, work_item_id, "
                        "report_kind, template_id, status) VALUES (:t, :e, :wi, :kind, :tv, "
                        "'draft') RETURNING id"
                    ),
                    {"t": ctx.tenant_id, "e": engagement_id, "wi": work_item_id,
                     "kind": current.kind, "tv": template.version_id},
                ),
            )  # fmt: skip
        version_no = (current.version_no or 0) + 1
        version_id = await tx.session.scalar(
            text(
                "INSERT INTO audit_report_versions (tenant_id, engagement_id, work_item_id, "
                "report_id, version_no, choices, paragraphs, content_hash, created_by) VALUES "
                "(:t, :e, :wi, :r, :no, CAST(:c AS jsonb), CAST(:p AS jsonb), :h, :by) "
                "RETURNING id"
            ),
            {
                "t": ctx.tenant_id,
                "e": engagement_id,
                "wi": work_item_id,
                "r": report_id,
                "no": version_no,
                "c": json.dumps(choice_json),
                "p": json.dumps(para_json),
                "h": digest,
                "by": ctx.user_id,
            },
        )
        await tx.session.execute(
            text(
                "UPDATE audit_reports SET current_version_id = :v, template_id = :tv, "
                "status = 'draft', version = version + 1, updated_at = clock_timestamp() "
                "WHERE id = :r"
            ),
            {"v": version_id, "tv": template.version_id, "r": report_id},
        )
        tx.record(
            "audit_report.choice_set",
            target=Target("audit_report", report_id),
            after=Ref(version_no=version_no, content_hash=digest),  # the field is in the version
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return await state(ctx.tenant, work_item_id)


async def set_report_date(
    ctx: AuthContext, work_item_id: UUID, report_date: date, city: str, seen_version: int
) -> ReportState:
    """AUD-23's report date and city (A-07-T41; A-07 F5): the date G7's letter is dated as of
    and the release reads. A draft's fields only (409 `report_not_draft` once approved or
    released); a person's act (`report.draft`), never the agent's."""
    engagement_id = await _person(ctx, work_item_id, "report.draft")
    place = city.strip()
    if not place or len(place) > 120 or "\n" in place:
        raise DomainInvalid("city")
    current = await state(ctx.tenant, work_item_id)
    if current.report_id is None:
        raise NotFound("audit_report")
    if current.row_version != seen_version:
        raise StaleReport(facts={"version": current.row_version})
    if current.status != "draft":
        raise ReportNotDraft(facts={"status": current.status})
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE audit_reports SET report_date = :d, city = :c, version = version + 1, "
                "updated_at = clock_timestamp() WHERE id = :r AND version = :v"
            ),
            {"d": report_date, "c": place, "r": current.report_id, "v": seen_version},
        )
        tx.record(
            "audit_report.date_set",
            target=Target("audit_report", current.report_id),
            after=Ref(report_date=int(report_date.strftime("%Y%m%d"))),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return await state(ctx.tenant, work_item_id)


async def version_paragraphs(
    tenant: TenantContext, work_item_id: UUID, version_no: int
) -> list[Paragraph]:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT v.paragraphs FROM audit_report_versions v JOIN audit_reports r "
                    "ON r.id = v.report_id WHERE r.work_item_id = :wi AND v.version_no = :no"
                ),
                {"wi": work_item_id, "no": version_no},
            )
        ).first()
    if row is None:
        raise NotFound("audit_report_version")
    return [
        Paragraph(str(p["block_id"]), bool(p["included"]), cast(str | None, p.get("reason_code")))
        for p in cast(list[dict[str, object]], row.paragraphs or [])
    ]


def word_counts(before: Sequence[Paragraph], after: Sequence[Paragraph]) -> tuple[int, int]:
    """The blocks switched on and off between two versions (C11 compare words the paper)."""
    was = {p.block_id for p in before if p.included}
    now = {p.block_id for p in after if p.included}
    return len(now - was), len(was - now)


# --- the draft render (C11) ----------------------------------------------------------------------


async def draft_docx(ctx: AuthContext, work_item_id: UUID, version_no: int) -> tuple[bytes, bool]:
    """The version's DOCX through C11 (DRAFT mark, signature placeholder), and whether it is out
    of date (not the current version). The same version gives the same bytes."""
    from abacus.modules.reporting.api import RenderInput, render_docx

    await _person(ctx, work_item_id, "report.generate")
    current = await state(ctx.tenant, work_item_id)
    if current.template_version_id is None or current.version_no is None:
        raise NotFound("audit_report_version")
    if not any(v == version_no for v, _, _ in current.versions):
        raise NotFound("audit_report_version")
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT v.paragraphs, v.content_hash, v.created_at "
                    "FROM audit_report_versions v JOIN audit_reports r ON r.id = v.report_id "
                    "WHERE r.work_item_id = :wi "
                    "AND v.version_no = :no"
                ),
                {"wi": work_item_id, "no": version_no},
            )
        ).first()
    if row is None:
        raise NotFound("audit_report_version")
    blocks = await published_body(ctx.tenant, FAMILY[current.kind], current.template_version_id)
    if blocks is None:
        raise NoReportTemplate(facts={"family": FAMILY[current.kind]})
    states = {
        str(p["block_id"]): bool(p["included"])
        for p in cast(list[dict[str, object]], row.paragraphs or [])
    }
    out = render_docx(
        RenderInput(
            layout_key="report",
            blocks=blocks,
            values={"signature": "[Signature]"},
            title="Independent auditor's report",
            as_of=cast(datetime, row.created_at),
            mode="draft",
            content_hash=str(row.content_hash),
            clause_states=states,
        )
    )
    return out.docx, version_no != current.version_no


async def request_opinion_decision(ctx: AuthContext, work_item_id: UUID) -> UUID:
    """AUD-23 "Request decision" (DEC-3028): the `opinion` C3 card for the engagement partner,
    on the report's work item; its options are the four forms (computed, never a model's). The
    card answers 409 while `audits.report_release` is off (the kind's own check)."""
    engagement_id = await _person(ctx, work_item_id, "report.request_decision")
    return await raise_decision_card(
        ctx,
        engagement_id=engagement_id,
        kind=OPINION_KIND,
        question_key=OPINION_CARD,
        work_item_id=work_item_id,
        raised_under="report.request_decision",
    )


_VERSION_ID = text(
    "SELECT v.id, v.paragraphs FROM audit_report_versions v "
    "JOIN audit_reports r ON r.id = v.report_id WHERE r.work_item_id = :wi AND v.version_no = :no"
)


async def render_document(
    ctx: AuthContext,
    work_item_id: UUID,
    version_no: int,
    fmt: Literal["docx", "pdf"],
) -> UUID:
    """AUD-23 "Generate" (DEC-3028): a DRAFT render of one report version through C11's queue,
    as a generated document C11 owns (its versions, its Out of date when the source moves).
    Answers the generated document's id."""
    from abacus.modules.reporting import api as c11

    engagement_id = await _person(ctx, work_item_id, "report.generate")
    current = await state(ctx.tenant, work_item_id)
    if current.template_version_id is None:
        raise NotFound("audit_report_version")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_VERSION_ID, {"wi": work_item_id, "no": version_no})).first()
    if row is None:
        raise NotFound("audit_report_version")
    facts = await engagement_hold_facts(ctx.tenant, engagement_id)
    if facts is None:
        raise NotFound("engagement")
    clauses = tuple(
        c11.ClauseState(str(p["block_id"]), bool(p["included"]))
        for p in cast(list[dict[str, object]], row.paragraphs or [])
    )
    async with uow(ctx.tenant) as tx:
        ticket = await c11.render(
            tx,
            c11.RenderRequest(
                kind="audit_report",
                owner_ref=c11.OwnerRef("audit_report_version", cast(UUID, row.id)),
                scope=c11.RenderScope(
                    client_id=facts.client_id,
                    engagement_id=engagement_id,
                    work_item_id=work_item_id,
                ),
                template_version_id=current.template_version_id,
                requested_by=c11.Requester("human", user_id=ctx.user_id),
                formats=(fmt,),
                clause_states=clauses,
            ),
        )
    return ticket.generated_document_id
