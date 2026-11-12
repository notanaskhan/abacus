"""State residency and allocation (T-04-T39; T-04 §3.8 AC-8.1 to AC-8.6, §4.3; SPEC-649;
ADR-005, ADR-050; DEC-3124, DEC-4409). Amber.

Code states the facts, the options and the conflict; a person confirms (ADR-005):

- **Facts with citations.** From the return's sources, each kept with its citations and its
  source kind: the organizer's answers (main home, domicile), the deed and the co-op statement
  (the abodes), W-2 box 20 (the locality worked in) and a 1099's address block. A fact is
  insert-only (`residency_facts`); a later source adds a row, never edits one.
- **Options and conflict in code.** `OPTIONS` (full-year New York State and City; full-year State,
  part-year City; part-year State), each with the forms it adds (IT-360.1, IT-203). The
  recommendation and the conflict are `compute.individual.residency.residency_rules` over the
  statutory-day test and the main home (281 days with a New York City abode: full-year, no
  conflict; 150 days with Rhinebeck as the main home: a conflict for a person to resolve).
- **Status** (registry `residency_determination`): `review_point` until confirmed;
  `action_required` while the client has been asked and has not answered; `confirmed`.
- **Confirmation through SHL-10.** The residency proposal (the agent's `residency` mode,
  T-04-T38, or the reviewer's pick) is approved in SHL-10; its applier confirms the determination
  for the approving person when they hold `residency.confirm` on the return (the matrix's
  function condition), which the database requires (`residency_confirmed`: a confirmed row names
  its person and its proposal). `residency_determination.confirmed` then activates the IT-360.1 or
  IT-203 worksheet the option needs and flags the engine re-import.
- **Ask the client.** The determination's review point carries the client wording: the question
  and its options in template words only (`client_question`), sent by a reviewer through review's
  `issue.send_to_client`; the internal note never travels.
- **Allocation.** Income by jurisdiction, the IT-112-R other-state credit and the IT-225
  add-backs from the return's own fields, by code (`allocation_view`), and a deterministic xlsx
  (`kernel.safe_xlsx`). Feld 2025: 268,400 + 6,910 + 14,820 + 307,900 = 598,030; NY AGI 615,605;
  credit min(11,279, 15,920) = 11,279.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.safe_xlsx import Sheet, workbook
from abacus.kernel.uow import DomainEvent, OutboxEvent, Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import (
    AuthContext,
    authorise,
    engagement_resource,
    member_could,
    names_of,
)
from abacus.modules.review.api import issue_awaits_client
from abacus.modules.tax.compute.individual.residency import (
    ResidencyFacts,
    ResidencyOption,
    allocation,
    it112r,
    it225,
    residency_rules,
)

READ: Final = "residency.read"
CONFIRM: Final = "residency.confirm"
SCOPES: Final = ("T", "S", "J")
FactKey = Literal[
    "domicile", "second_residence", "days", "work_location", "voter_registration",
    "drivers_licenses", "trigger", "main_home_answer",
]  # fmt: skip
SourceKind = Literal["organizer_answer", "document", "engine", "human"]
Status = Literal["review_point", "action_required", "confirmed"]


@dataclass(frozen=True)
class Option:
    key: ResidencyOption
    label: str
    adds_forms: tuple[str, ...]  # the worksheets the option needs beyond IT-201


OPTIONS: Final[tuple[Option, ...]] = (
    Option("full_year_nys_nyc", "Full-year New York State and New York City", ()),
    Option(
        "full_year_nys_part_year_nyc",
        "Full-year New York State, part-year New York City",
        ("it360_1",),
    ),
    Option("part_year_nys", "Part-year New York State", ("it203",)),
)
_OPTION: Final = {o.key: o for o in OPTIONS}


class ResidencyNotFound(NotFound):
    def __init__(self) -> None:
        super().__init__("residency_determination")


class OptionUnknown(DomainInvalid):
    code = "residency_option_unknown"


class NotConfirmable(DomainConflict):
    code = "residency_not_confirmable"


class ConfirmNotPermitted(DomainForbidden):
    code = "level_not_permitted"


# --- the facts --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Source:
    """One cited source the facts come from: an organizer answer or a document's field."""

    kind: Literal["organizer", "deed", "coop_statement", "w2_box20", "1099_address"]
    citation_id: UUID
    value: Mapping[str, object]  # code's reading of the source (days, a locality, an address)


@dataclass(frozen=True)
class Fact:
    key: FactKey
    value: Mapping[str, object]  # `{t, ...}`: the fact's type and its parts (TRI)
    citation_ids: tuple[UUID, ...]
    source_kind: SourceKind


def facts_from_sources(sources: Sequence[Source]) -> list[Fact]:
    """The facts code states from the sources (module docstring), each with its citations.
    Sources of the same kind join one fact citing all of them; unknown parts are left out."""
    by_kind: dict[str, list[Source]] = {}
    for s in sources:
        by_kind.setdefault(s.kind, []).append(s)
    facts: list[Fact] = []

    def cites(kind: str) -> tuple[UUID, ...]:
        return tuple(dict.fromkeys(s.citation_id for s in by_kind.get(kind, ())))

    for s in by_kind.get("organizer", ()):
        if "nyc_days" in s.value:
            facts.append(
                Fact(
                    "days",
                    {"t": "days", "nyc": int(str(s.value["nyc_days"]))},
                    (s.citation_id,),
                    "organizer_answer",
                )
            )
        if "main_home" in s.value:
            facts.append(
                Fact(
                    "main_home_answer",
                    {"t": "place", "place": str(s.value["main_home"])},
                    (s.citation_id,),
                    "organizer_answer",
                )
            )
        if "domicile" in s.value:
            facts.append(
                Fact(
                    "domicile",
                    {"t": "place", "place": str(s.value["domicile"])},
                    (s.citation_id,),
                    "organizer_answer",
                )
            )
    for kind, label in (("coop_statement", "nyc_abode"), ("deed", "second_residence")):
        if kind in by_kind:
            places = sorted({str(s.value.get("place", "")) for s in by_kind[kind]} - {""})
            facts.append(
                Fact(
                    "second_residence" if kind == "deed" else "domicile",
                    {"t": label, "places": places},
                    cites(kind),
                    "document",
                )
            )
    if "w2_box20" in by_kind:
        localities = sorted({str(s.value.get("locality", "")) for s in by_kind["w2_box20"]} - {""})
        facts.append(
            Fact(
                "work_location",
                {"t": "localities", "localities": localities},
                cites("w2_box20"),
                "document",
            )
        )
    if "1099_address" in by_kind:
        places = sorted({str(s.value.get("place", "")) for s in by_kind["1099_address"]} - {""})
        facts.append(
            Fact(
                "trigger", {"t": "addresses", "places": places}, cites("1099_address"), "document"
            )
        )
    return facts


def residency_inputs(facts: Sequence[Fact]) -> ResidencyFacts:
    """The rules' inputs from the facts: New York City days, an abode there, and whether the
    organizer names a main home outside the City."""
    days = next((int(str(f.value.get("nyc", 0))) for f in facts if f.key == "days"), 0)
    abode = any(f.value.get("t") == "nyc_abode" and f.value.get("places") for f in facts)
    home = next((str(f.value.get("place", "")) for f in facts if f.key == "main_home_answer"), "")
    outside = bool(home) and "new york city" not in home.lower() and "nyc" not in home.lower()
    return ResidencyFacts(nyc_days=days, has_nyc_abode=abode, main_home_outside_nyc=outside)


def client_question(recommended: ResidencyOption) -> tuple[str, str]:
    """(title, client wording): the template words of the question and its options, the
    recommended one first; no internal note and no figure travels."""
    ordered = [_OPTION[recommended], *(o for o in OPTIONS if o.key != recommended)]
    lines = "\n".join(f"- {o.label}" for o in ordered)
    return (
        "Confirm your New York residency for the year",
        "Please tell us which of these describes where you lived during the year:\n" + lines,
    )


def status_of(confirmed: bool, asked_client: bool) -> Status:
    if confirmed:
        return "confirmed"
    return "action_required" if asked_client else "review_point"


# --- the store --------------------------------------------------------------------------------

_FIND = text(
    "SELECT id, engagement_id, scope, proposed_option, status, conflict, confirmed_by, "
    "confirmed_at, proposal_id, issue_id, version_no FROM residency_determinations "
    "WHERE tax_return_id = :r AND scope = :s"
)
_OPEN = text(
    "INSERT INTO residency_determinations (tenant_id, engagement_id, tax_return_id, scope, "
    "jurisdictions, options, proposed_option, status, conflict) VALUES (:t, :e, :r, :s, :j, "
    "CAST(:o AS jsonb), :p, 'proposed', :c) ON CONFLICT (tax_return_id, scope) DO NOTHING "
    "RETURNING id"
)
_FACT = text(
    "INSERT INTO residency_facts (tenant_id, engagement_id, tax_return_id, determination_id, "
    "fact_key, value, citation_ids, source_kind, added_by_kind) VALUES (:t, :e, :r, :d, :k, "
    "CAST(:v AS jsonb), :c, :s, :by)"
)
_FACTS = text(
    "SELECT fact_key, value, citation_ids, source_kind FROM residency_facts "
    "WHERE determination_id = :d ORDER BY created_at, id"
)
_LINK_ISSUE = text(
    "UPDATE residency_determinations SET issue_id = :i, version_no = version_no + 1, "
    "updated_at = clock_timestamp() WHERE id = :d"
)


_FACT_CITATIONS = text(
    "SELECT DISTINCT unnest(citation_ids) FROM residency_facts WHERE determination_id = :d"
)


async def fact_citations(tenant: TenantContext, determination_id: UUID) -> tuple[UUID, ...]:
    """The verified citations behind a determination's facts (code recorded them when it opened
    the determination), for the residency proposal's row: SHL-10 approves only a cited change."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_FACT_CITATIONS, {"d": determination_id})).scalars().all()
    return tuple(sorted(cast(UUID, r) for r in rows))


@dataclass(frozen=True)
class Determination:
    id: UUID
    engagement_id: UUID
    scope: str
    proposed_option: ResidencyOption | None
    status: str
    conflict: bool
    confirmed_by: UUID | None
    confirmed_at: datetime | None
    proposal_id: UUID | None
    issue_id: UUID | None
    version_no: int


def _row(r: object) -> Determination:
    g = cast(Mapping[str, object], r._mapping)  # type: ignore[attr-defined]  # a Row, typed object
    return Determination(
        cast(UUID, g["id"]),
        cast(UUID, g["engagement_id"]),
        str(g["scope"]),
        cast(ResidencyOption | None, g["proposed_option"]),
        str(g["status"]),
        bool(g["conflict"]),
        cast(UUID | None, g["confirmed_by"]),
        cast(datetime | None, g["confirmed_at"]),
        cast(UUID | None, g["proposal_id"]),
        cast(UUID | None, g["issue_id"]),
        int(cast(int, g["version_no"])),
    )


async def _authorised(ctx: AuthContext, return_id: UUID, action: str) -> UUID:
    engagement = await work_item_engagement(ctx.tenant, return_id)
    if engagement is None or ctx.client:
        raise NotFound("tax_return")  # INV-4: no portal principal reads residency
    ref = await get_ref(ctx, engagement)  # a wall answers 404
    await authorise(ctx, action, ref.resource())
    return engagement


async def determination(
    tenant: TenantContext, return_id: UUID, scope: str = "T"
) -> Determination | None:
    async with tenant_session(tenant) as session:
        found = (await session.execute(_FIND, {"r": return_id, "s": scope})).first()
    return _row(found) if found is not None else None


async def open_residency(
    tx: UnitOfWork,
    ctx: AuthContext,
    return_id: UUID,
    sources: Sequence[Source],
    tax_year: int,
    *,
    scope: str = "T",
) -> UUID:
    """The return's determination for `scope` with the facts code states from `sources` and
    code's recommendation and conflict, in the caller's unit of work (idempotent on the return
    and scope: a second call adds the new sources' facts only). Authorised `residency.read` and
    the caller's own writes are its facts (`added_by_kind` from the session)."""
    if scope not in SCOPES:
        raise DomainInvalid(facts={"field": "scope"})
    engagement = await _authorised(ctx, return_id, READ)
    facts = facts_from_sources(sources)
    call = residency_rules(residency_inputs(facts), tax_year)
    options = {o.key: {"label": o.label, "adds_forms": list(o.adds_forms)} for o in OPTIONS}
    opened = await tx.session.scalar(
        _OPEN,
        {
            "t": ctx.tenant_id,
            "e": engagement,
            "r": return_id,
            "s": scope,
            "j": ["NY", "NYC"],
            "o": json.dumps(options, sort_keys=True),
            "p": call.recommended,
            "c": call.conflict,
        },
    )
    determination_id = cast(UUID | None, opened)
    if determination_id is None:
        found = (await tx.session.execute(_FIND, {"r": return_id, "s": scope})).one()
        determination_id = cast(UUID, found.id)
    by = ctx.tenant.actor_kind if ctx.tenant.actor_kind in ("human", "agent") else "system"
    for f in facts:
        await tx.session.execute(
            _FACT,
            {
                "t": ctx.tenant_id,
                "e": engagement,
                "r": return_id,
                "d": determination_id,
                "k": f.key,
                "v": json.dumps(dict(f.value), sort_keys=True, default=str),
                "c": list(f.citation_ids),
                "s": f.source_kind,
                "by": by,
            },
        )
    tx.record(
        "residency_determination.opened",
        target=Target("residency_determination", determination_id),
        after=Ref(facts=len(facts), conflict=int(call.conflict)),
        scope=Scope(engagement_id=engagement),
    )
    return determination_id


async def link_review_point(tx: UnitOfWork, determination_id: UUID, issue_id: UUID) -> None:
    """The review point raised for the determination (the issue the client question rides)."""
    await tx.session.execute(_LINK_ISSUE, {"i": issue_id, "d": determination_id})


# --- the read --------------------------------------------------------------------------------


@dataclass(frozen=True)
class OptionView:
    key: str
    label: str
    recommended: bool
    adds_forms: tuple[str, ...]


@dataclass(frozen=True)
class FactView:
    key: str
    value: Mapping[str, object]
    citation_ids: tuple[UUID, ...]
    source_kind: str


@dataclass(frozen=True)
class ResidencyView:
    determination_id: UUID
    status: Status
    conflict: bool
    facts: tuple[FactView, ...]
    options: tuple[OptionView, ...]
    confirmed_by_name: str | None
    confirmed_at: datetime | None
    issue_id: UUID | None
    version: int
    tallies: Mapping[str, int] = field(default_factory=dict[str, int])


async def residency_view(ctx: AuthContext, return_id: UUID, scope: str = "T") -> ResidencyView:
    """TXI-03's residency pane: facts with citations, options with the recommendation, status,
    banner facts and tallies (facts, cited facts, options)."""
    await _authorised(ctx, return_id, READ)
    found = await determination(ctx.tenant, return_id, scope)
    if found is None:
        raise ResidencyNotFound
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_FACTS, {"d": found.id})).all()
    asked = await issue_awaits_client(ctx.tenant, found.issue_id) if found.issue_id else False
    names: dict[UUID, str] = await names_of([found.confirmed_by]) if found.confirmed_by else {}
    facts = tuple(
        FactView(
            str(r.fact_key),
            cast(Mapping[str, object], r.value),
            tuple(cast(list[UUID], r.citation_ids or [])),
            str(r.source_kind),
        )
        for r in rows
    )
    options = tuple(
        OptionView(o.key, o.label, o.key == found.proposed_option, o.adds_forms) for o in OPTIONS
    )
    return ResidencyView(
        determination_id=found.id,
        status=status_of(found.status == "confirmed", asked),
        conflict=found.conflict,
        facts=facts,
        options=options,
        confirmed_by_name=names.get(found.confirmed_by) if found.confirmed_by else None,
        confirmed_at=found.confirmed_at,
        issue_id=found.issue_id,
        version=found.version_no,
        tallies={
            "facts": len(facts),
            "cited": sum(1 for f in facts if f.citation_ids),
            "options": len(options),
        },
    )


# --- confirmation (the SHL-10 applier's) ------------------------------------------------------


class ResidencyConfirmed(DomainEvent):
    """A person confirmed a return's residency (AC-8.3, AC-8.6): the worksheets the option needs
    are activated and the engine re-import is flagged (identifiers and codes only)."""

    event_type: ClassVar[str] = "residency_determination.confirmed"

    determination_id: Annotated[UUID, classified("internal")]
    tax_return_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    option: Annotated[str, classified("internal")]


_CONFIRM = text(
    "UPDATE residency_determinations SET status = 'confirmed', proposed_option = :o, "
    "confirmed_by = :by, confirmed_at = clock_timestamp(), proposal_id = :p, "
    "version_no = version_no + 1, updated_at = clock_timestamp() "
    "WHERE id = :d AND status <> 'confirmed' RETURNING tax_return_id, engagement_id"
)


class _AlreadyConfirmed(Exception):
    """An approval delivered twice: the determination is confirmed already."""


async def confirm_approved(
    tenant: TenantContext,
    proposal_id: UUID,
    approver: UUID | None,
    determination_id: UUID,
    option: str,
) -> bool:
    """The approved residency proposal confirms its determination for the person who approved
    it, when they hold `residency.confirm` on the return (403 `level_not_permitted` otherwise);
    the database binds a confirmed row to its person and proposal. False when already confirmed
    (an approval delivered twice changes nothing)."""
    if option not in _OPTION:
        raise OptionUnknown(facts={"option": option})
    if approver is None:
        raise ConfirmNotPermitted(facts={"proposal_id": str(proposal_id)})
    system = TenantContext(tenant.tenant_id, "system", f"proposal:{proposal_id}")
    async with tenant_session(system) as session:
        scope = (
            await session.execute(
                text(
                    "SELECT engagement_id, tax_return_id FROM residency_determinations "
                    "WHERE id = :d"
                ),
                {"d": determination_id},
            )
        ).first()
    if scope is None:
        raise ResidencyNotFound
    resource = replace(
        await engagement_resource(system, cast(UUID, scope.engagement_id)),
        work_item_id=cast(UUID, scope.tax_return_id),
    )
    if not await member_could(tenant.tenant_id, approver, CONFIRM, resource):
        raise ConfirmNotPermitted(facts={"proposal_id": str(proposal_id)})
    try:
        async with uow(system) as tx:
            done = (
                await tx.session.execute(
                    _CONFIRM,
                    {"o": option, "by": approver, "p": proposal_id, "d": determination_id},
                )
            ).first()
            if done is None:
                raise _AlreadyConfirmed  # nothing changed: roll back, no audit event
            tx.record(
                "residency_determination.confirmed",
                target=Target("residency_determination", determination_id),
                after=Ref(by=approver, proposal=proposal_id),  # the option is on the row
                scope=Scope(engagement_id=cast(UUID, done.engagement_id)),
            )
            tx.emit(
                ResidencyConfirmed(
                    determination_id=determination_id,
                    tax_return_id=cast(UUID, done.tax_return_id),
                    engagement_id=cast(UUID, done.engagement_id),
                    option=option,
                )
            )
    except _AlreadyConfirmed:
        return False
    return True


_ACTIVATE = text(
    "UPDATE return_worksheets SET active = true, version_no = version_no + 1, "
    "updated_at = clock_timestamp() WHERE tax_return_id = :r AND key = ANY(:keys) "
    "AND NOT active RETURNING key"
)


async def on_residency_confirmed(event: OutboxEvent) -> None:
    """`ResidencyConfirmedConsumer` (T-04 §4.5): the option's worksheets (IT-360.1, IT-203) are
    activated where the return holds them, and `tax_return.engine_reimport_needed` is recorded
    so the sync chip reads "Out of sync" until the next export. Idempotent: an active worksheet
    is left as it is."""
    payload = event.payload
    option = _OPTION.get(cast(ResidencyOption, str(payload.get("option"))))
    if option is None:
        return
    return_id = UUID(str(payload["tax_return_id"]))
    engagement = UUID(str(payload["engagement_id"]))
    system = TenantContext(event.tenant_id, "system", "residency_confirmed")
    async with uow(system) as tx:
        activated = (
            await tx.session.execute(_ACTIVATE, {"r": return_id, "keys": list(option.adds_forms)})
        ).all()
        tx.record(
            "tax_return.engine_reimport_needed",
            target=Target("tax_return", return_id),
            after=Ref(worksheets=len(activated)),  # the cause is the confirmation (the event)
            scope=Scope(engagement_id=engagement),
        )


# --- the allocation ----------------------------------------------------------------------------

# Where the allocation's inputs sit on the return: (worksheet key, field key). Form structure,
# not firm content: the IT-201 and IT-112-R lines the computation reads.
ALLOCATION_FIELDS: Final[Mapping[str, tuple[str, str]]] = {
    "wages": ("it201", "it201_l1"),
    "interest": ("it201", "it201_l2"),
    "dividends": ("it201", "it201_l3"),
    "rental_k1": ("it201", "it201_l11"),
    "ny_addition_l20": ("it201", "ny_addition_it201_l20"),
    "it225_ptet": ("it225", "it225_ptet_addback"),
    "it225_other_state": ("it225", "it225_other_state_addback"),
    "other_state_tax": ("it112r", "it112r_other_state_tax"),
    "ny_tax": ("it112r", "it112r_ny_tax"),
    "other_state_income": ("it112r", "it112r_other_state_income"),
}
_FIELDS = text(
    "SELECT w.key AS sheet, f.field_key, f.value FROM return_fields f "
    "JOIN return_worksheets w ON w.id = f.worksheet_id WHERE w.tax_return_id = :r AND w.active"
)


@dataclass(frozen=True)
class AllocationLine:
    jurisdiction: str
    label: str
    amount: Decimal | None
    derivation: str | None


@dataclass(frozen=True)
class AllocationView:
    lines: tuple[AllocationLine, ...]
    federal_total: Decimal | None
    ny_agi: Decimal | None
    credit: Decimal | None
    credit_limit: Decimal | None
    addbacks: Decimal | None
    missing: tuple[str, ...]


def _amount(value: object) -> Decimal | None:
    if isinstance(value, Mapping):
        raw = cast(Mapping[str, object], value).get("v")
        return None if raw is None else Decimal(str(raw))
    return None if value is None else Decimal(str(value))


def allocate_from(found: Mapping[str, Decimal]) -> AllocationView:
    """The allocation, credit and add-backs from the inputs found (pure; module docstring). An
    input not on the return is named in `missing` and its dependants read None."""
    missing = tuple(k for k in ALLOCATION_FIELDS if k not in found)
    parts = ("wages", "interest", "dividends", "rental_k1")
    federal = (
        allocation([found[p] for p in parts]).total if all(p in found for p in parts) else None
    )
    addback_keys = ("it225_ptet", "it225_other_state")
    addbacks = (
        it225([found[k] for k in addback_keys]).total
        if all(k in found for k in addback_keys)
        else None
    )
    ny_agi = (
        federal + found.get("ny_addition_l20", Decimal(0)) + addbacks
        if federal is not None and addbacks is not None
        else None
    )
    credit = limit = None
    keys = ("other_state_tax", "ny_tax", "other_state_income")
    if ny_agi is not None and ny_agi > 0 and all(k in found for k in keys):
        result = it112r(
            found["other_state_tax"], found["ny_tax"], found["other_state_income"], ny_agi
        )
        credit, limit = result.credit, result.limit
    lines = (
        AllocationLine("NY", "Federal amounts", federal, "wages + interest + dividends + Sch E"),
        AllocationLine("NY", "IT-225 additions", addbacks, "PTET + other-state add-back"),
        AllocationLine("NY", "NY AGI", ny_agi, "federal + IT-201 line 20 + IT-225"),
        AllocationLine(
            "NY",
            "IT-112-R credit",
            credit,
            "lesser of the other state's tax and NY tax x other-state income / NY AGI",
        ),
    )
    return AllocationView(lines, federal, ny_agi, credit, limit, addbacks, missing)


async def allocation_view(ctx: AuthContext, return_id: UUID) -> AllocationView:
    """TXI-03's allocation pane from the return's active worksheets' fields (code's sums)."""
    await _authorised(ctx, return_id, READ)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_FIELDS, {"r": return_id})).all()
    at = {(str(r.sheet), str(r.field_key)): r.value for r in rows}
    found: dict[str, Decimal] = {}
    for name, where in ALLOCATION_FIELDS.items():
        value = _amount(at.get(where))
        if value is not None:
            found[name] = value
    return allocate_from(found)


def allocation_xlsx(view: AllocationView) -> bytes:
    """The allocation as a deterministic workbook (no $; numbers as numbers; ADR-042)."""
    rows: list[list[str | Decimal | None]] = [["Jurisdiction", "Line", "Amount", "Derivation"]]
    rows.extend([ln.jurisdiction, ln.label, ln.amount, ln.derivation] for ln in view.lines)
    return workbook([Sheet("State allocation", rows)])


__all__ = [
    "ALLOCATION_FIELDS",
    "OPTIONS",
    "AllocationView",
    "ConfirmNotPermitted",
    "Fact",
    "OptionUnknown",
    "ResidencyConfirmed",
    "ResidencyView",
    "Source",
    "allocate_from",
    "allocation_view",
    "allocation_xlsx",
    "client_question",
    "confirm_approved",
    "determination",
    "facts_from_sources",
    "link_review_point",
    "on_residency_confirmed",
    "open_residency",
    "residency_inputs",
    "residency_view",
    "status_of",
]
