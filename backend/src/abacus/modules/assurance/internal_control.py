"""Internal control and the Exceptions sheet (A-04-T25; A-04 §3.6, §4.2; AUD-09; DEC-2206).

- **Processes** (`control_activities`): one per name on the audit work item, with design,
  implementation and reliance, edited against the version the person saw (409
  `version_conflict`); a walkthrough is an insert-only row with its evidence (AC6.6).
- **The Exceptions sheet** (`control_exceptions`): row 2 onward under header row 1; every cell
  is addressed `Exceptions!<col><row>` (the severity is column D: "Exceptions!D2") and carries
  its citations (AC6.2). A severity on a row is a **proposal** only (a senior's edit or the
  agent's suggestion); no path here stores a concluded severity, which is A-06's `deficiencies`
  record read through it (AC6.3, AC6.7, INV-1).
- **Routing** (AC6.4): "Send to Findings" and "Convert to misstatement" call the router A-06
  registered through `register_exception_route` inside this unit of work, so the finding and the
  row's `routed_ref` are written together; with no router registered they answer 503
  `route_not_available` (fail closed). A misstatement needs the row's amount (409 `no_amount`).
- **Request evidence**: a C5 request item drafted from the row (the requests module's own
  create, `request_item.create`); a person sends it.

The routes have authorised their action and the flags; every write is audited.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainUnavailable, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.assurance.events import ControlExceptionRecorded
from abacus.modules.engagements.api import assurance_item_id
from abacus.modules.identity.api import AuthContext

RouteKind = Literal["finding", "misstatement"]
Severity = Literal["deficiency", "significant_deficiency", "material_weakness"]
SHEET: Final = "Exceptions"
SEVERITY_COLUMN: Final = "D"
HEADER_ROW: Final = 1


class VersionConflict(DomainConflict):
    code = "version_conflict"


class NoAmount(DomainConflict):
    """Convert to misstatement needs the row's misstatement candidate amount."""

    code = "no_amount"


class AlreadyRouted(DomainConflict):
    code = "already_routed"


class RouteNotAvailable(DomainUnavailable):
    """No exception router is registered for this kind yet (A-06 registers it): fail closed."""

    code = "route_not_available"


@dataclass(frozen=True)
class Process:
    id: UUID
    process_name: str
    walkthrough_on: date | None
    design: str
    implementation: str
    reliance: str
    service_organization_id: UUID | None
    row_version: int


@dataclass(frozen=True)
class ControlException:
    id: UUID
    workpaper_id: UUID
    sheet_row: int
    matter: str
    description: str
    proposed_severity: str | None
    disposition: str
    coso_component: str | None  # None: an exception for resolution has none yet (0663)
    misstatement_candidate_amount: Decimal | None
    routed_kind: str | None
    routed_ref: UUID | None
    suggestion_id: UUID | None
    citation_ids: tuple[UUID, ...]

    @property
    def address(self) -> str:
        return f"{SHEET}!{SEVERITY_COLUMN}{self.sheet_row}"


@dataclass(frozen=True)
class ExceptionRow:
    """A row as the drafter or a person records it (A-04-T29 mode `ic` writes these)."""

    sheet_row: int
    matter: str
    description: str
    coso_component: str | None  # None: an exception for resolution has none yet (0663)
    proposed_severity: Severity | None = None
    misstatement_candidate_amount: Decimal | None = None
    suggestion_id: UUID | None = None
    citation_ids: tuple[UUID, ...] = field(default_factory=tuple[UUID, ...])


@dataclass(frozen=True)
class RouteRequest:
    """What the router gets: the row's facts (never a concluded severity)."""

    engagement_id: UUID
    work_item_id: UUID
    control_exception_id: UUID
    address: str
    matter: str
    description: str
    proposed_severity: str | None
    coso_component: str | None  # None: an exception for resolution has none yet (0663)
    amount: Decimal | None
    citation_ids: tuple[UUID, ...]
    requested_by: UUID


ExceptionRouter = Callable[[UnitOfWork, RouteRequest], Awaitable[UUID]]
_ROUTERS: dict[RouteKind, ExceptionRouter] = {}


def register_exception_route(kind: RouteKind, router: ExceptionRouter) -> None:
    """A-06 registers the finding and misstatement routers; one per kind."""
    if kind in _ROUTERS and _ROUTERS[kind] is not router:
        raise ValueError(f"exception route {kind!r} already registered")
    _ROUTERS[kind] = router


def exception_route_available(kind: RouteKind) -> bool:
    """AUD-09 hides the menu item while no router is registered."""
    return kind in _ROUTERS


async def _work_item(ctx: AuthContext, engagement_id: UUID) -> UUID:
    found = await assurance_item_id(ctx.tenant, engagement_id)
    if found is None:
        raise NotFound("control_activity")
    return found


# --- processes ----------------------------------------------------------------------------------

_PROCESSES = text(
    "SELECT a.id, a.process_name, a.design, a.implementation, a.reliance, "
    "a.service_organization_id, a.row_version, "
    "(SELECT max(w.performed_on) FROM walkthroughs w WHERE w.tenant_id = a.tenant_id "
    " AND w.control_activity_id = a.id) AS walkthrough_on "
    "FROM control_activities a WHERE a.work_item_id = :item ORDER BY lower(a.process_name)"
)


def _process(row: object) -> Process:
    r = cast(dict[str, object], row)
    return Process(
        id=cast(UUID, r["id"]),
        process_name=cast(str, r["process_name"]),
        walkthrough_on=cast(date | None, r["walkthrough_on"]),
        design=cast(str, r["design"]),
        implementation=cast(str, r["implementation"]),
        reliance=cast(str, r["reliance"]),
        service_organization_id=cast(UUID | None, r["service_organization_id"]),
        row_version=cast(int, r["row_version"]),
    )


async def processes(ctx: AuthContext, engagement_id: UUID) -> list[Process]:
    item = await _work_item(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_PROCESSES, {"item": item})).mappings().all()
    return [_process(dict(r)) for r in rows]


async def process(ctx: AuthContext, engagement_id: UUID, process_id: UUID) -> Process:
    for found in await processes(ctx, engagement_id):
        if found.id == process_id:
            return found
    raise NotFound("control_activity")


async def add_process(
    ctx: AuthContext, engagement_id: UUID, process_name: str, service_organization_id: UUID | None
) -> Process:
    """A process on the work item (the drafter's mode `ic` and AUD-09's add)."""
    item = await _work_item(ctx, engagement_id)
    async with uow(ctx.tenant) as tx:
        new_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO control_activities (tenant_id, engagement_id, work_item_id, "
                    "process_name, service_organization_id) VALUES (:t, :e, :i, :name, :org) "
                    "RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "i": item,
                    "name": process_name.strip(),
                    "org": service_organization_id,
                },
            )
        ).scalar_one()
        tx.record("control_activity.recorded", target=Target("control_activity", new_id))
    return await process(ctx, engagement_id, new_id)


async def edit_process(
    ctx: AuthContext,
    engagement_id: UUID,
    process_id: UUID,
    *,
    expected_version: int,
    design: str | None,
    implementation: str | None,
    reliance: str | None,
    walkthrough_on: date | None,
) -> Process:
    """Design, implementation, reliance or a walkthrough, against the version the person saw."""
    item = await _work_item(ctx, engagement_id)
    async with uow(ctx.tenant) as tx:
        moved = (
            await tx.session.execute(
                text(
                    "UPDATE control_activities SET design = coalesce(:design, design), "
                    "implementation = coalesce(:impl, implementation), "
                    "reliance = coalesce(:reliance, reliance), row_version = row_version + 1, "
                    "updated_at = clock_timestamp() "
                    "WHERE id = :id AND work_item_id = :item AND row_version = :v RETURNING id"
                ),
                {
                    "design": design,
                    "impl": implementation,
                    "reliance": reliance,
                    "id": process_id,
                    "item": item,
                    "v": expected_version,
                },
            )
        ).scalar_one_or_none()
        if moved is None:
            exists = await tx.session.scalar(
                text("SELECT 1 FROM control_activities WHERE id = :id AND work_item_id = :item"),
                {"id": process_id, "item": item},
            )
            if exists is None:
                raise NotFound("control_activity")
            raise VersionConflict
        if walkthrough_on is not None:
            await tx.session.execute(
                text(
                    "INSERT INTO walkthroughs (tenant_id, engagement_id, work_item_id, "
                    "control_activity_id, performed_on, performed_by_user_id) "
                    "VALUES (:t, :e, :i, :a, :on, :by)"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "i": item,
                    "a": process_id,
                    "on": walkthrough_on,
                    "by": ctx.user_id,
                },
            )
        tx.record(
            "control_activity.recorded",
            target=Target("control_activity", process_id),
            after=Ref(version=expected_version + 1),
        )
    return await process(ctx, engagement_id, process_id)


# --- the Exceptions sheet -----------------------------------------------------------------------

_EXCEPTIONS = text(
    "SELECT id, workpaper_id, sheet_row, matter, description, proposed_severity, disposition, "
    "coso_component, misstatement_candidate_amount, routed_kind, routed_ref, suggestion_id, "
    "citation_ids FROM control_exceptions WHERE work_item_id = :item "
    "ORDER BY workpaper_id, sheet_row"
)


def _exception(r: dict[str, object]) -> ControlException:
    return ControlException(
        id=cast(UUID, r["id"]),
        workpaper_id=cast(UUID, r["workpaper_id"]),
        sheet_row=cast(int, r["sheet_row"]),
        matter=cast(str, r["matter"]),
        description=cast(str, r["description"]),
        proposed_severity=cast(str | None, r["proposed_severity"]),
        disposition=cast(str, r["disposition"]),
        coso_component=cast(str | None, r["coso_component"]),
        misstatement_candidate_amount=cast(Decimal | None, r["misstatement_candidate_amount"]),
        routed_kind=cast(str | None, r["routed_kind"]),
        routed_ref=cast(UUID | None, r["routed_ref"]),
        suggestion_id=cast(UUID | None, r["suggestion_id"]),
        citation_ids=tuple(cast(Sequence[UUID], r["citation_ids"] or ())),
    )


async def exceptions(ctx: AuthContext, engagement_id: UUID) -> list[ControlException]:
    item = await _work_item(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_EXCEPTIONS, {"item": item})).mappings().all()
    return [_exception(dict(r)) for r in rows]


async def exception_at(ctx: AuthContext, engagement_id: UUID, sheet_row: int) -> ControlException:
    """The row of the audit's Exceptions sheet; `Exceptions!D2` resolves to row 2."""
    for found in await exceptions(ctx, engagement_id):
        if found.sheet_row == sheet_row:
            return found
    raise NotFound("control_exception")


async def record_exceptions(
    ctx: AuthContext,
    engagement_id: UUID,
    workpaper_id: UUID,
    rows: Sequence[ExceptionRow],
    *,
    by_agent: bool = False,
) -> list[ControlException]:
    """Record or replace sheet rows (a re-draft replaces the facts of rows not yet routed). An
    agent's severity is a suggestion (`proposed_by_kind` agent) and needs its `suggestion_id`."""
    item = await _work_item(ctx, engagement_id)
    kind = "agent" if by_agent else "human"
    async with uow(ctx.tenant) as tx:
        for row in rows:
            if row.sheet_row <= HEADER_ROW:
                raise ValueError("the header is row 1; exceptions start on row 2")
            if by_agent and row.proposed_severity is not None and row.suggestion_id is None:
                raise ValueError("an agent's severity is a suggestion and names it")
            found = (
                await tx.session.execute(
                    text(
                        "INSERT INTO control_exceptions (tenant_id, engagement_id, work_item_id, "
                        "workpaper_id, sheet_row, matter, description, proposed_severity, "
                        "proposed_by_kind, proposed_by_user_id, disposition, coso_component, "
                        "misstatement_candidate_amount, suggestion_id, citation_ids, "
                        "recorded_by_kind) VALUES (:t, :e, :i, :wp, :row, :matter, :desc, :sev, "
                        ":sev_kind, :sev_by, :disp, :coso, :amount, :sugg, :cites, :kind) "
                        "ON CONFLICT (tenant_id, workpaper_id, sheet_row) DO UPDATE SET "
                        "matter = EXCLUDED.matter, description = EXCLUDED.description, "
                        "coso_component = EXCLUDED.coso_component, "
                        "misstatement_candidate_amount = EXCLUDED.misstatement_candidate_amount, "
                        "citation_ids = EXCLUDED.citation_ids, "
                        "row_version = control_exceptions.row_version + 1, "
                        "updated_at = clock_timestamp() "
                        "WHERE control_exceptions.routed_ref IS NULL RETURNING id"
                    ),
                    {
                        "t": ctx.tenant_id,
                        "e": engagement_id,
                        "i": item,
                        "wp": workpaper_id,
                        "row": row.sheet_row,
                        "matter": row.matter,
                        "desc": row.description,
                        "sev": row.proposed_severity,
                        # 0657: a proposed severity names who proposed it in the same row.
                        "sev_kind": None if row.proposed_severity is None else kind,
                        "sev_by": None
                        if row.proposed_severity is None or by_agent
                        else ctx.user_id,
                        "disp": "proposed"
                        if row.proposed_severity
                        else "exception_for_resolution",
                        "coso": row.coso_component,
                        "amount": row.misstatement_candidate_amount,
                        "sugg": row.suggestion_id,
                        "cites": list(row.citation_ids),
                        "kind": kind,
                    },
                )
            ).scalar_one_or_none()
            if found is None:
                continue  # routed rows keep their facts
            tx.record(
                "control_exception.recorded",
                target=Target("control_exception", found),
                after=Ref(row=row.sheet_row),
            )
            tx.emit(
                ControlExceptionRecorded(
                    engagement_id=engagement_id,
                    workpaper_id=workpaper_id,
                    control_exception_id=found,
                    sheet_row=row.sheet_row,
                )
            )
    return [e for e in await exceptions(ctx, engagement_id) if e.workpaper_id == workpaper_id]


async def propose_severity(
    ctx: AuthContext, engagement_id: UUID, sheet_row: int, severity: Severity
) -> ControlException:
    """A senior's (or manager's, or the EP's) proposal; the disposition becomes `proposed`. It
    never concludes: the engagement partner concludes in Findings (AC6.3)."""
    row = await exception_at(ctx, engagement_id, sheet_row)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE control_exceptions SET proposed_severity = :sev, proposed_by_kind = "
                "'human', proposed_by_user_id = :by, disposition = 'proposed', "
                "row_version = row_version + 1, updated_at = clock_timestamp() WHERE id = :id"
            ),
            {"sev": severity, "by": ctx.user_id, "id": row.id},
        )
        tx.record(
            "control_exception.severity_proposed",
            target=Target("control_exception", row.id),
            after=Ref(row=sheet_row),
        )
    return await exception_at(ctx, engagement_id, sheet_row)


async def route_exception(
    ctx: AuthContext, engagement_id: UUID, sheet_row: int, kind: RouteKind
) -> tuple[RouteKind, UUID]:
    """Send to Findings or Convert to misstatement through A-06's router, in one unit of work."""
    router = _ROUTERS.get(kind)
    if router is None:
        raise RouteNotAvailable
    row = await exception_at(ctx, engagement_id, sheet_row)
    if row.routed_ref is not None:
        raise AlreadyRouted(facts={"routed_kind": row.routed_kind or ""})
    if kind == "misstatement" and row.misstatement_candidate_amount is None:
        raise NoAmount
    item = await _work_item(ctx, engagement_id)
    async with uow(ctx.tenant) as tx:
        ref = await router(
            tx,
            RouteRequest(
                engagement_id=engagement_id,
                work_item_id=item,
                control_exception_id=row.id,
                address=row.address,
                matter=row.matter,
                description=row.description,
                proposed_severity=row.proposed_severity,
                coso_component=row.coso_component,
                amount=row.misstatement_candidate_amount,
                citation_ids=row.citation_ids,
                requested_by=ctx.user_id,
            ),
        )
        moved = await tx.session.scalar(
            text(
                "UPDATE control_exceptions SET routed_kind = :kind, routed_ref = :ref, "
                "row_version = row_version + 1, updated_at = clock_timestamp() "
                "WHERE id = :id AND routed_ref IS NULL RETURNING id"
            ),
            {"kind": kind, "ref": ref, "id": row.id},
        )
        if moved is None:
            raise AlreadyRouted(facts={"routed_kind": kind})
        tx.record(
            "control_exception.routed",
            target=Target("control_exception", row.id),
            after=Ref(routed_ref=ref),
        )
    return kind, ref


async def request_evidence(
    ctx: AuthContext, engagement_id: UUID, sheet_row: int
) -> tuple[UUID, list[UUID]]:
    """A C5 request item drafted from the row (SHL-14 opens it prefilled); a person sends it."""
    from abacus.modules.requests.api import NewRequestItem, add_request_item

    row = await exception_at(ctx, engagement_id, sheet_row)
    item = await add_request_item(
        ctx,
        engagement_id,
        NewRequestItem(
            description=f"{row.matter}: {row.description}"[:2000],
            audit_area="internal_control",
        ),
    )
    return item.id, [item.id]


_AUDIT_OWNERS: Final = {
    "control_activity": text(
        "SELECT id, engagement_id FROM control_activities WHERE id = ANY(:ids)"
    ),
    "control_exception": text(
        "SELECT id, engagement_id FROM control_exceptions WHERE id = ANY(:ids)"
    ),
}
AUDIT_KINDS: Final = frozenset(_AUDIT_OWNERS)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """The trail places these rows on their engagement (SPEC-304; DEC-121)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(_AUDIT_OWNERS[kind], {"ids": list(ids)})
        return {found: owned for found, owned in rows}
