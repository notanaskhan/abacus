"""The composed engagement letter (N-02-T32; N-02 §3.11, §4.2; ENG-04; C11; DEC-1458).

A letter is composed from a firm template version (P-11 `report_template_versions`, imported
through KNW-03: database content) and the engagement's facts. Each edit in Draft is a new
insert-only version in `engagement_letter_versions` (0560): its clause states, the person's
variable overrides and plain-text section overrides, the fee terms, and the C11 draft it rendered.
The version it replaces moves to `superseded`; a partner-approved letter edited this way returns
to Draft with its approval left on the old version (stale), as N-02-T33 builds on.

- Variables come from facts (client name and signer, engagement partner, the G1 date, the
  approver of record and SKE designee per DEC-63, the §103(a)(3)(C) election on EBP audits, the
  AI-use disclosure default, the letter date). One that does not apply reads "—" with its reason
  and is not offered to the renderer, so a template that declares it refuses with
  `missing_variable` rather than printing a blank.
- Fees are typed lines, installments as shares and third-party fees. Code computes the total,
  each installment (the last takes the rounding remainder) and the wording; a third party's fee
  is shown and never added (ADR-050). Fee and billing variables cannot be overridden.
- The C11 kind `engagement_letter` resolves variables through `_provider`, which answers what this
  module resolved for the same owner in the current call (C11's provider receives no unit of
  work; DEC-1458). Approvals are N-02-T33's: until then the kind's approval provider answers
  None, so no final render of a letter happens.
- Sent and signed letters, and recorded-mode letters, take no edit (409).
"""

from __future__ import annotations

import re
from collections.abc import Generator, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel._statuses import LetterStatus
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.acceptance_tables import g1_decision
from abacus.modules.engagements.contacts import attest_of, designations_of
from abacus.modules.engagements.letter_contract import (
    ComposerLetterOut,
    InstallmentOut,
    LetterClause,
    LetterDraftIn,
    LetterFeesIn,
    LetterFeesOut,
    LetterheadOut,
    LetterSignerOut,
    LetterVariable,
    ThirdPartyFeeOut,
)
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.service import get_ref, lock_ref
from abacus.modules.identity.api import (
    AuthContext,
    allowed_actions,
    authorise,
    engagement_team,
    firm_name,
)
from abacus.modules.methodology.api import ReportTemplateParts, report_template_parts
from abacus.modules.organisations.api import client_names, signer_contacts
from abacus.modules.reporting import api as c11
from abacus.modules.reporting.api import DocBlock

KIND: Final = "engagement_letter"
OWNER: Final = "engagement_letter"
READ: Final = "letter.read"
DRAFT: Final = "letter.draft"
EDITABLE: Final = frozenset({"draft", "partner_approved"})
# Computed by code from the fee terms: never a person's text (ADR-050).
COMPUTED: Final = ("fee.", "billing.", "third_party_fee.")
_KEY = re.compile(r"^[a-z][a-z0-9_.]{0,79}$")
_SECTION = re.compile(r"^[a-z0-9_-]{1,64}$")
_MARKUP = re.compile(r"<\s*[a-zA-Z/!?]")
DASH: Final = "—"


class LetterLocked(DomainConflict):
    """The letter was sent or signed, or is a recorded letter: it takes no edit."""

    code = "letter_locked"


class LetterStale(DomainConflict):
    """`If-Match` names another version than the current one."""

    code = "stale_version"


class FeesDoNotFoot(DomainInvalid):
    """The installments' shares do not add to 100% of the fee."""

    code = "fees_do_not_foot"


class ComputedVariable(DomainInvalid):
    """A fee or billing variable was given as text: code computes those."""

    code = "computed_variable"


class UnknownLetterPart(DomainInvalid):
    """A clause, variable or section the template version does not have, or a template version
    that is not a letter's."""

    code = "unknown_letter_part"


class MarkupNotAllowed(DomainInvalid):
    """Overrides are plain text (no rich text until P-59)."""

    code = "markup_not_allowed"


# --- money, computed by code ----------------------------------------------------------------


def money(cents: int) -> str:
    """`$18,500`, or `$18,500.50` when there are cents."""
    dollars, rest = divmod(cents, 100)
    return f"${dollars:,}" if rest == 0 else f"${dollars:,}.{rest:02d}"


def compute_fees(fees: LetterFeesIn) -> LetterFeesOut:
    """The total of the lines; each installment's share of it, the last taking the rounding
    remainder; third-party fees beside it, never added. Shares must add to 100%."""
    total = sum(line.amount_cents for line in fees.lines)
    installments: list[InstallmentOut] = []
    if fees.installments:
        if sum(i.share_bp for i in fees.installments) != 10_000:
            raise FeesDoNotFoot(facts={"shares_bp": sum(i.share_bp for i in fees.installments)})
        amounts = [total * i.share_bp // 10_000 for i in fees.installments]
        amounts[-1] += total - sum(amounts)
        installments = [
            InstallmentOut(label=i.label, share_bp=i.share_bp, amount_cents=a)
            for i, a in zip(fees.installments, amounts, strict=True)
        ]
    return LetterFeesOut(
        basis=fees.basis,
        lines=list(fees.lines),
        total_cents=total,
        installments=installments,
        third_party=[
            ThirdPartyFeeOut(payee=t.payee, estimated_cents=t.estimated_cents)
            for t in fees.third_party
        ],
    )


def _share(bp: int) -> str:
    whole, rest = divmod(bp, 100)
    return f"{whole}%" if rest == 0 else f"{whole}.{rest:02d}%".rstrip("0")


def fee_variables(fees: LetterFeesOut) -> dict[str, str]:
    """The fee and billing wording the template prints, from the computed fee."""
    out = {
        "fee.total": money(fees.total_cents),
        "fee.summary": f"{money(fees.total_cents)} {fees.basis}",
        "fee.breakdown": "; ".join(f"{money(x.amount_cents)} {x.label}" for x in fees.lines),
    }
    if fees.installments:
        out["billing.terms"] = " · ".join(
            f"{_share(i.share_bp)} {i.label}" for i in fees.installments
        )
        out["billing.schedule"] = " · ".join(
            f"{money(i.amount_cents)} {i.label}" for i in fees.installments
        )
        # N-02-T34: each amount on its own, for the template's own prose around it.
        for n, i in enumerate(fees.installments, start=1):
            out[f"billing.installment_{n}"] = money(i.amount_cents)
    if fees.third_party:
        out["third_party_fee.summary"] = " · ".join(
            f"Est. {money(t.estimated_cents)} · billed by {t.payee}" for t in fees.third_party
        )
        for n, t in enumerate(fees.third_party, start=1):
            out[f"third_party_fee.estimate_{n}"] = money(t.estimated_cents)
    return out


# --- facts --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Fact:
    key: str
    value: str | None
    reason: str | None = None


def _long_date(day: date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


async def letter_facts(
    ctx: AuthContext, session: AsyncSession, engagement: Engagement
) -> list[Fact]:
    """The engagement facts a letter prints, read in the caller's session."""
    facts: list[Fact] = []
    names = await client_names(session, [engagement.client_entity_id])
    found = names.get(engagement.client_entity_id)
    facts.append(Fact("client.name", found.client_entity_name if found else None))
    designations = await designations_of(session, engagement.id)
    by_kind: dict[str, UUID] = {}
    for d in designations:
        by_kind.setdefault(d.designation, d.contact_id)
    named = await signer_contacts(ctx.tenant, list(by_kind.values()))

    def contact(kind: str) -> str | None:
        found = named.get(by_kind[kind]) if kind in by_kind else None
        if found is None:
            return None
        return found.display_name if not found.title else f"{found.display_name} · {found.title}"

    facts.append(Fact("client.signer", contact("signing_officer")))
    team = await engagement_team(ctx, engagement.id)
    partner = next((m.display_name for m in team if m.role == "engagement_partner"), None)
    facts.append(Fact("firm.signer", f"{partner}, Partner" if partner else None))
    cas = engagement.service_line == "cas"
    attest = bool(await attest_of(ctx.tenant, engagement.id))
    facts.append(
        Fact("approver_of_record", contact("approver_of_record"))
        if cas
        else Fact("approver_of_record", None, "cas_only")
    )
    facts.append(
        Fact("ske_designee", contact("ske_designee"))
        if attest
        else Fact("ske_designee", None, "attest_only")
    )
    election = await session.scalar(
        text(
            "SELECT bool_or(limited_scope_103a3c) FROM assurance_work_items "
            "WHERE engagement_id = :e AND ebp_plan_kind IS NOT NULL"
        ),
        {"e": engagement.id},
    )
    facts.append(
        Fact("ebp.limited_scope_election", None, "ebp_only")
        if election is None
        else Fact(
            "ebp.limited_scope_election",
            "Plan administrator elects (certification required)" if election else "No election",
        )
    )
    # ADM-04's firm default is not built: the disclosure clause is on by default (DEC-1458).
    facts.append(Fact("ai_use.disclosure", "on"))
    decision = await g1_decision(session, engagement.id)
    if decision is not None and decision.accepted:
        facts.append(Fact("acceptance.decided_on", _long_date(decision.decided_at.date())))
    facts.append(Fact("letter.date", _long_date(await clock.today(ctx.tenant))))
    return [
        f if f.value is not None or f.reason else Fact(f.key, None, "not_designated")
        for f in facts
    ]


# --- the C11 kind -------------------------------------------------------------------------

_resolving: ContextVar[Mapping[UUID, Mapping[str, str]] | None] = ContextVar(
    "abacus_letter_variables", default=None
)


async def _provider(owner: c11.OwnerRef, scope: c11.RenderScope) -> Mapping[str, str]:
    """What this module resolved for the owner in the current call; nothing otherwise, so every
    declared key refuses with `missing_variable` (never a blank)."""
    current = _resolving.get()
    return {} if current is None or owner.type != OWNER else current.get(owner.id, {})


async def _approval(ref: c11.ApprovalRef) -> tuple[UUID, str] | None:
    """N-02-T33 resolves a partner's approval; until then no letter renders final."""
    return None


def ensure_kind() -> None:
    """Register `engagement_letter` with C11 once per process."""
    try:
        c11.document_kind(KIND)
    except c11.UnknownDocumentKind:
        c11.register_document_kind(
            c11.DocumentKind(
                kind=KIND,
                layout="letter",
                variables_provider=_provider,
                approval_provider=_approval,
                retention_record_type="engagement_letter",
                formats=("pdf", "docx"),
            )
        )


@contextmanager
def _resolved(owner: UUID, values: Mapping[str, str]) -> Generator[None]:
    token = _resolving.set({owner: dict(values)})
    try:
        yield
    finally:
        _resolving.reset(token)


# --- the template ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClauseDef:
    clause_id: str
    title: str
    default_enabled: bool
    non_standard: bool


def _walk(blocks: list[object]) -> Iterator[Mapping[str, object]]:
    for block in blocks:
        if isinstance(block, dict):
            item = cast(Mapping[str, object], block)
            yield item
            for child in ("blocks", "children", "items"):
                nested = item.get(child)
                if isinstance(nested, list):
                    yield from _walk(cast(list[object], nested))


def clause_defs(parts: ReportTemplateParts) -> list[ClauseDef]:
    flagged = {
        str(b["clause_id"])
        for b in _walk(parts.body)
        if b.get("type") == "clause" and b.get("non_standard") is True
    }
    out: list[ClauseDef] = []
    for raw in parts.clauses:
        if isinstance(raw, dict):
            c = cast(Mapping[str, object], raw)
            cid = str(c.get("clause_id", ""))
            out.append(
                ClauseDef(
                    cid,
                    str(c.get("title", cid)),
                    bool(c.get("default_enabled", True)),
                    cid in flagged,
                )
            )
    return out


def section_ids(parts: ReportTemplateParts) -> frozenset[str]:
    return frozenset(
        str(b["id"])
        for b in _walk(parts.body)
        if b.get("type") == "section" and isinstance(b.get("id"), str)
    )


def clause_views(defs: list[ClauseDef], states: Mapping[str, str]) -> list[LetterClause]:
    views: list[LetterClause] = []
    for d in defs:
        state = states.get(d.clause_id, "on" if d.default_enabled else "off")
        on = state != "off"
        views.append(
            LetterClause(
                key=d.clause_id,
                title=d.title,
                state="off" if not on else ("required" if state == "required" else "on"),
                non_standard=d.non_standard,
            )
        )
    return views


def redline_count(
    defs: list[ClauseDef], clauses: list[LetterClause], sections: Mapping[str, object]
) -> int:
    """ENG-04's redline: the template's non-standard clauses, each clause switched from its
    default, and each section a person overrode (a clause both non-standard and off counts
    twice: "a clause toggle off adds it to the redline count")."""
    default = {d.clause_id: d.default_enabled for d in defs}
    flagged = sum(1 for c in clauses if c.non_standard)
    changed = sum(1 for c in clauses if (c.state != "off") != default.get(c.key, True))
    return flagged + changed + len(sections)


async def _letterhead(tenant_id: UUID) -> LetterheadOut:
    """The firm's name over the paper; the address waits for ADM's firm profile."""
    return LetterheadOut(firm=await firm_name(tenant_id))


def signers_of(variables: list[LetterVariable]) -> list[LetterSignerOut]:
    """The client signer, then the firm's countersignature (N-02 §3.11); a missing one is left
    out. Who has signed comes from the envelope (N-02-T33)."""
    values = {v.key: v.value for v in variables}
    out: list[LetterSignerOut] = []
    client, firm = values.get("client.signer"), values.get("firm.signer")
    if client:
        out.append(LetterSignerOut(order=1, name=client.split(" · ")[0], role="client"))
    if firm:
        out.append(LetterSignerOut(order=len(out) + 1, name=firm.split(",")[0], role="firm"))
    return out


_PAPER: Final = TypeAdapter(list[DocBlock])


# --- reads ----------------------------------------------------------------------------------


_LETTER = text("SELECT mode, current_version_id FROM engagement_letters WHERE engagement_id = :e")
_LETTER_FOR_UPDATE = text(
    "SELECT mode, current_version_id FROM engagement_letters WHERE engagement_id = :e FOR UPDATE"
)


@dataclass(frozen=True)
class _Current:
    mode: str
    version: Mapping[str, object] | None


async def _current(session: AsyncSession, engagement_id: UUID, *, lock: bool = False) -> _Current:
    row = (
        await session.execute(
            _LETTER_FOR_UPDATE if lock else _LETTER,
            {"e": engagement_id},
        )
    ).one_or_none()
    if row is None:
        return _Current("composed", None)
    if row.mode != "composed" or row.current_version_id is None:
        return _Current(str(row.mode), None)
    version = (
        (
            await session.execute(
                text("SELECT * FROM engagement_letter_versions WHERE id = :v"),
                {"v": row.current_version_id},
            )
        )
        .mappings()
        .one()
    )
    return _Current("composed", cast(Mapping[str, object], version))


Source = Literal["facts", "override", "computed"]


def _labels(parts: ReportTemplateParts | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in parts.variables if parts is not None else ():
        if isinstance(raw, dict):
            item = cast(Mapping[str, object], raw)
            key, label = item.get("key"), item.get("label")
            if isinstance(key, str) and isinstance(label, str):
                out[key] = label
    return out


def _variables_view(
    facts: list[Fact],
    stored: Mapping[str, object] | None,
    overrides: Mapping[str, object],
    *,
    computed: Mapping[str, str] | None = None,
    labels: Mapping[str, str] | None = None,
) -> list[LetterVariable]:
    """Facts first (an override wins), then the computed fee wording, then the template's other
    declared values, each with the template's label where it has one."""
    named = labels or {}
    out: list[LetterVariable] = []
    seen: set[str] = set()

    def add(key: str, value: str | None, source: Source, reason: str | None = None) -> None:
        seen.add(key)
        out.append(
            LetterVariable(
                key=key, value=value, source=source, reason=reason, label=named.get(key)
            )
        )

    for f in facts:
        if f.key in overrides:
            add(f.key, str(overrides[f.key]), "override")
        else:
            add(f.key, f.value, "facts", f.reason)
    for key, value in (computed or {}).items():
        if key not in seen:
            add(key, value, "computed")
    for key, value in (stored or {}).items():
        if key not in seen:
            add(key, str(value), "override" if key in overrides else "facts")
    return out


async def _engagement(session: AsyncSession, engagement_id: UUID) -> Engagement:
    found = await session.get(Engagement, engagement_id)
    if found is None:
        raise NotFound("engagement")
    return found


async def _view(
    ctx: AuthContext, session: AsyncSession, engagement: Engagement, current: _Current
) -> ComposerLetterOut:
    facts = await letter_facts(ctx, session, engagement)
    version = current.version
    approved_name: str | None = None
    template: tuple[str, int, list[object]] | None = None
    if version is None:
        clauses: list[LetterClause] = []
        variables = _variables_view(facts, None, {})
        fees = None
        redline = 0
    else:
        parts = await report_template_parts(session, cast(UUID, version["template_version_id"]))
        defs = clause_defs(parts) if parts is not None else []
        clauses = clause_views(defs, cast(Mapping[str, str], version["clause_states"]))
        stored = cast(Mapping[str, object], version["variables"])
        overrides = cast(Mapping[str, object], version["fee_terms"]).get("overrides", {})
        terms = cast(Mapping[str, object], version["fee_terms"]).get("terms")
        fees = compute_fees(LetterFeesIn.model_validate(terms)) if terms else None
        variables = _variables_view(
            facts,
            stored,
            cast(Mapping[str, object], overrides),
            computed=fee_variables(fees) if fees is not None else None,
            labels=_labels(parts),
        )
        sections = cast(Mapping[str, object], version["section_overrides"])
        redline = redline_count(defs, clauses, sections)
        if parts is not None:
            template = (parts.template_name, parts.version_no, parts.body)
        if version["approved_by"] is not None:
            team = await engagement_team(ctx, engagement.id)
            approved_name = next(
                (m.display_name for m in team if m.user_id == version["approved_by"]), None
            )
    status = LetterStatus.DRAFT if version is None else LetterStatus(str(version["status"]))
    return ComposerLetterOut(
        engagement_id=engagement.id,
        mode="composed" if current.mode == "composed" else "recorded",
        status=status,
        version_no=None if version is None else cast(int, version["version_no"]),
        template_version_id=None
        if version is None
        else cast(UUID, version["template_version_id"]),
        clauses=clauses,
        variables=variables,
        fees=fees,
        redline_count=redline,
        generated_document_id=(
            None if version is None else cast(UUID, version["generated_document_id"])
        ),
        approved_by_name=approved_name,
        approved_at=None if version is None else cast(datetime | None, version["approved_at"]),
        approval_content_hash=(
            None if version is None else cast(str | None, version["approval_content_hash"])
        ),
        envelope_id=None if version is None else cast(UUID | None, version["envelope_id"]),
        allowed_actions=[],
        version=0 if version is None else cast(int, version["version_no"]),
        template_name=None if template is None else template[0],
        template_version_no=None if template is None else template[1],
        paper=_PAPER.validate_python(template[2]) if template is not None else [],
        signers=signers_of(variables),
        letterhead=await _letterhead(ctx.tenant_id),
    )


async def composed_letter(ctx: AuthContext, engagement_id: UUID) -> ComposerLetterOut:
    """`GET …/letter/composer`: the ENG-04 projection."""
    if ctx.client:
        raise NotFound("letter")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, READ, ref.resource())
    async with tenant_session(ctx.tenant) as session:
        engagement = await _engagement(session, engagement_id)
        view = await _view(ctx, session, engagement, await _current(session, engagement_id))
    actions = await allowed_actions(ctx, ref.resource(), (READ, DRAFT))
    editable = view.mode == "composed" and view.status in EDITABLE
    return view.model_copy(
        update={"allowed_actions": [a for a in actions if a == READ or editable]}
    )


# --- the draft ------------------------------------------------------------------------------


def _check_draft(
    parts: ReportTemplateParts, defs: list[ClauseDef], body: LetterDraftIn
) -> dict[str, str]:
    if parts.layout_key != "letter":
        raise UnknownLetterPart(facts={"part": "template", "layout": parts.layout_key})
    known = {d.clause_id: d for d in defs}
    for clause_id in body.clause_states:
        if clause_id not in known:
            raise UnknownLetterPart(facts={"part": "clause", "id": clause_id[:64]})
    declared = set(parts.variable_keys)
    for key in body.variables:
        if not _KEY.fullmatch(key):
            raise UnknownLetterPart(facts={"part": "variable"})
        if key.startswith(COMPUTED):
            raise ComputedVariable(facts={"key": key})
        if key not in declared:
            raise UnknownLetterPart(facts={"part": "variable", "key": key})
    sections = section_ids(parts)
    for section_id, words in body.section_overrides.items():
        if not _SECTION.fullmatch(section_id) or section_id not in sections:
            raise UnknownLetterPart(facts={"part": "section"})
        if _MARKUP.search(words):
            raise MarkupNotAllowed(facts={"section": section_id})
    for key, words in body.variables.items():
        if _MARKUP.search(words):
            raise MarkupNotAllowed(facts={"key": key})
    states = {d.clause_id: "on" if d.default_enabled else "off" for d in defs}
    states.update(body.clause_states)
    return states


async def draft_letter(
    ctx: AuthContext, engagement_id: UUID, body: LetterDraftIn, if_match: str
) -> ComposerLetterOut:
    """`PUT …/letter/composer`: a new draft version from the template, the facts and the
    person's edits, rendered as a C11 draft in the same unit of work."""
    if ctx.client:
        raise NotFound("letter")
    ensure_kind()
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, DRAFT, ref.resource())
        engagement = await _engagement(tx.session, engagement_id)
        current = await _current(tx.session, engagement_id, lock=True)
        if current.mode != "composed":
            raise LetterLocked(facts={"engagement_id": str(engagement_id), "mode": current.mode})
        prior = current.version
        if prior is not None and str(prior["status"]) not in EDITABLE:
            raise LetterLocked(
                facts={"engagement_id": str(engagement_id), "status": str(prior["status"])}
            )
        at = 0 if prior is None else cast(int, prior["version_no"])
        if if_match.strip('"') != str(at):
            raise LetterStale(facts={"version": at})
        parts = await report_template_parts(tx.session, body.template_version_id)
        if parts is None:
            raise UnknownLetterPart(facts={"part": "template"})
        defs = clause_defs(parts)
        states = _check_draft(parts, defs, body)
        fees = compute_fees(body.fees)
        facts = await letter_facts(ctx, tx.session, engagement)
        values = {f.key: f.value for f in facts if f.value is not None}
        values.update(body.variables)
        values.update(fee_variables(fees))
        owner = engagement_id
        with _resolved(owner, values):
            ticket = await c11.render(
                tx,
                c11.RenderRequest(
                    kind=KIND,
                    owner_ref=c11.OwnerRef(OWNER, owner),
                    scope=c11.RenderScope(client_id=engagement.client_id, engagement_id=owner),
                    template_version_id=body.template_version_id,
                    requested_by=c11.Requester("human", user_id=ctx.user_id),
                    formats=("pdf", "docx"),
                    clause_states=tuple(
                        c11.ClauseState(k, v != "off") for k, v in sorted(states.items())
                    ),
                    section_overrides=tuple(
                        c11.SectionOverride(
                            k,
                            tuple(p.strip() for p in v.split("\n\n") if p.strip()),
                            ctx.user_id,
                        )
                        for k, v in sorted(body.section_overrides.items())
                    ),
                ),
            )
        declared = set(parts.variable_keys)
        stored = {k: v for k, v in values.items() if k in declared}
        version_id = uuid4()
        await tx.session.execute(
            text(
                "INSERT INTO engagement_letter_versions (id, tenant_id, engagement_id, "
                "version_no, kind, template_version_id, clause_states, variables, "
                "section_overrides, fee_terms, generated_document_id, content_hash, status, "
                "created_by, created_by_kind) VALUES (:id, :t, :e, :n, 'original', :tv, "
                "CAST(:cs AS jsonb), CAST(:vars AS jsonb), CAST(:so AS jsonb), "
                "CAST(:ft AS jsonb), :doc, :hash, 'draft', :by, 'human')"
            ),
            {
                "id": version_id,
                "t": ctx.tenant_id,
                "e": engagement_id,
                "n": at + 1,
                "tv": body.template_version_id,
                "cs": _json(states),
                "vars": _json(stored),
                "so": _json(dict(body.section_overrides)),
                "ft": _json(
                    {"terms": body.fees.model_dump(mode="json"), "overrides": body.variables}
                ),
                "doc": ticket.generated_document_id,
                "hash": ticket.content_hash,
                "by": ctx.user_id,
            },
        )
        if prior is not None:
            await tx.session.execute(
                text("UPDATE engagement_letter_versions SET status = 'superseded' WHERE id = :v"),
                {"v": prior["id"]},
            )
        await tx.session.execute(
            text(
                "INSERT INTO engagement_letters (tenant_id, engagement_id, status, recorded_by, "
                "recorded_by_user_id, mode, current_version_id) VALUES (:t, :e, 'not_started', "
                ":by, :uid, 'composed', :v) ON CONFLICT (tenant_id, engagement_id) DO UPDATE "
                "SET current_version_id = EXCLUDED.current_version_id"
            ),
            {
                "t": ctx.tenant_id,
                "e": engagement_id,
                "by": str(ctx.user_id),
                "uid": ctx.user_id,
                "v": version_id,
            },
        )
        tx.record(
            "letter.drafted",
            target=Target("engagement", engagement_id),
            after=Ref(
                version_no=at + 1,
                generated_document_id=ticket.generated_document_id,
                returned_to_draft=int(prior is not None and prior["status"] == "partner_approved"),
            ),
        )
    return await composed_letter(ctx, engagement_id)


def _json(value: object) -> str:
    import json

    return json.dumps(value, sort_keys=True, ensure_ascii=False)


__all__ = [
    "ComputedVariable",
    "FeesDoNotFoot",
    "LetterLocked",
    "LetterStale",
    "MarkupNotAllowed",
    "UnknownLetterPart",
    "composed_letter",
    "compute_fees",
    "draft_letter",
    "ensure_kind",
    "fee_variables",
    "money",
]
