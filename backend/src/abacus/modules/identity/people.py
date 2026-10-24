"""People v2: ADM-02's list, person, attributes, roles, deactivation and invitations (G-01-T05;
G-01 sections 3.3 to 3.5; ADR P-10, DEC-21, DEC-35; DEC-285, DEC-286).

- **The list** is every staff membership and live invitation, in bands by level, with per-band
  `counts` over the filters (minus the band filter) and firm-wide `tallies`. Rows are ordered by
  band, then as the firm added them. Reading it is `firm.read_people` (firm admins, security
  admins, partners); nothing else gets a 404-free answer.
- **Templates.** A membership's template is stored (`role_template`, 0142); one with none (made
  before 0142 or by a fixture) reads the template its firm role and level imply.
- **Writes** are a live person's (INV-1; the matrix denies agent and system, and so does this
  module): attributes against the person's `version` (409 `stale_version`), a role change that
  moves the template, level and firm role together, the security role (security admins may hold
  only that), and deactivation with a reason. The definers keep the firm's last firm
  administrator and last security administrator (409 `last_admin`).
- **Seats** are the provisioned `plan.seats` (DEC-285): an invitation counts against them while
  pending, and one more than the total answers 409 `seats_full`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.listing import (
    Position,
    clamp_limit,
    decode_cursor,
    encode_cursor,
    query_hash,
)
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity import _role_templates as generated
from abacus.modules.identity import people_repository as repo
from abacus.modules.identity.authz import Forbidden, Resource, allowed_actions, authorise
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import (
    AccessChanged,
    MembershipDeactivated,
    StaffInvitationIssued,
)
from abacus.modules.identity.repository import (
    memberships_elsewhere,
    pending_staff_invitation_for,
    set_staff_invitation_status,
    set_staff_token_hash,
    user_contacts,
    walled_clients,
)
from abacus.modules.identity.settings_registry import active_wall_count, seat_total
from abacus.modules.identity.slots import firm_offices, member_teams, set_member_teams

Template = Literal[
    "partner",
    "manager",
    "tax_reviewer",
    "senior",
    "staff",
    "tax_preparer",
    "firm_admin",
    "it_security",
]
Level = Literal["partner", "manager", "senior", "staff", "seasonal", "admin"]
Band = Literal["partners", "managers", "seniors", "staff", "seasonal", "operations"]
Status = Literal["active", "invited", "deactivated"]
Cell = Literal["allow", "conditional", "delegated", "deny", "locked"]

TEMPLATES: Final[tuple[Template, ...]] = cast(tuple[Template, ...], tuple(generated.TEMPLATES))
BANDS: Final[tuple[Band, ...]] = (
    "partners",
    "managers",
    "seniors",
    "staff",
    "seasonal",
    "operations",
)
BAND_OF_LEVEL: Final[dict[str, Band]] = {
    "partner": "partners",
    "manager": "managers",
    "senior": "seniors",
    "staff": "staff",
    "seasonal": "seasonal",
    "admin": "operations",
}
INVITATION_DAYS: Final = 14  # DEC-35
SIGN_INS_SHOWN: Final = 3
_OVERSIGHT: Final = frozenset({"practice_leader", "quality_partner"})
# The templates a firm role implies when a membership has none stored (0142's back-fill).
_TEMPLATE_OF_FIRM_ROLE: Final[dict[str | None, Template]] = {
    "firm_admin": "firm_admin",
    "security_admin": "it_security",
}
_REASON_INDEX: Final = {"manual": 1, "access_ended": 2, "scim_deprovisioned": 3}
_ATTRIBUTES: Final = ("title", "office_id", "service_lines", "access_ends_on", "offshore")
_LIST = "firm_staff"


# --- errors (409 and 422; codes in docs/architecture/error-codes.yaml) ---------------------------


class SeatsFull(DomainConflict):
    """Every seat is held or invited (AC3.3); the facts carry `used` and `total`."""

    code = "seats_full"


# The email already belongs to an active member of the firm (AC3.5). No docstring: the error
# catalogue keeps the shared `already_member` summary.
class AlreadyMember(DomainConflict):
    code = "already_member"


class SeatsNotProvisioned(DomainConflict):
    """The firm's seats aren't provisioned yet, so nobody can be invited (DEC-285: fails closed
    for a real firm; a synthetic one without seats has no limit)."""

    code = "seats_not_provisioned"


class AccessEndsRequired(DomainInvalid):
    """A seasonal member needs the date their access ends (AC3.5)."""

    code = "access_ends_required"


class OffshoreAssignmentConflict(DomainConflict):
    """Offshore can't be turned on while the person is assigned to clients without an offshore
    consent (AC4.6); the facts carry the assignment count."""

    code = "offshore_assignment_conflict"


class FirmRoleHeld(DomainConflict):
    """The person holds another firm role; only a firm admin changes it (AC4.3)."""

    code = "firm_role_held"


class PersonInvalid(DomainInvalid):
    """An office or team that isn't the firm's, or a level the template doesn't allow."""

    code = "person_invalid"


class DeactivationReasonInvalid(DomainInvalid):
    """A person deactivates with `manual`; the other reasons are the system's."""

    code = "deactivation_reason_invalid"


# The firm keeps at least one firm admin and one security admin (AC4.3). No docstring: the
# catalogue keeps SPEC-024's `last_admin` summary.
class LastAdministrator(DomainConflict):
    code = "last_admin"


# The person changed since it was read: read again. No docstring: the error catalogue keeps the
# shared `stale_version` summary.
class StalePerson(DomainConflict):
    code = "stale_version"


# --- shapes ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class StaffRow:
    user_id: UUID | None
    invitation_id: UUID | None
    display_name: str
    email: str
    title: str | None
    role_template: Template
    level: Level
    band: Band
    status: Status
    office_id: UUID | None
    team_ids: list[UUID]
    service_lines: list[str]
    access_ends_on: date | None
    offshore: bool
    last_sign_in_at: datetime | None
    invitation_expires_on: date | None
    deactivated_on: date | None
    allowed_actions: list[str]
    firm_role: str | None = None
    invitation_expires_at: datetime | None = None
    invited_at: datetime | None = None


@dataclass(frozen=True)
class Tallies:
    seats_used: int
    seats_total: int | None
    seats_pending: int
    partners: int
    professionals: int
    operations: int
    sso_mfa: int
    signed_in_of: int
    walls_active: int | None
    seasonal: int
    seasonal_access_ends_on: date | None


@dataclass(frozen=True)
class StaffFilters:
    q: str | None = None
    role_template: Template | None = None
    office_id: UUID | None = None
    team_id: UUID | None = None
    status: Status | None = None
    band: Band | None = None
    cursor: str | None = None
    limit: int | None = None


@dataclass(frozen=True)
class StaffPage:
    items: list[StaffRow]
    total: int
    next_cursor: str | None
    counts: dict[str, int]
    tallies: Tallies


@dataclass(frozen=True)
class SignIn:
    at: datetime
    method: str
    mfa: bool


@dataclass(frozen=True)
class UserDetail:
    row: StaffRow
    firm_role: str | None
    wall_ids: list[UUID]
    assignment_count: int
    recent_sign_ins: list[SignIn]
    version: int


@dataclass(frozen=True)
class InviteTerms:
    email: str
    firm_role: str | None = None
    role_template: Template | None = None
    level: Level | None = None
    office_id: UUID | None = None
    team_ids: list[UUID] = field(default_factory=list[UUID])
    service_lines: list[str] = field(default_factory=list[str])
    access_ends_on: date | None = None
    offshore: bool = False
    display_name: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class GridRow:
    key: str
    actions: list[str]
    cells: dict[str, Cell]
    conditions: dict[str, str]
    source: Literal["matrix", "policy"]
    locked: bool = False


@dataclass(frozen=True)
class TemplateCount:
    key: Template
    levels: list[Level]
    member_count: int


@dataclass(frozen=True)
class RoleTemplates:
    templates: list[TemplateCount]
    grid: list[GridRow]


# --- templates and levels ------------------------------------------------------------------------


def template_of(role_template: str | None, firm_role: str | None, level: str | None) -> Template:
    """The stored template, or the one the firm role and level imply (0142's back-fill rule)."""
    if role_template in TEMPLATES:
        return role_template
    if firm_role in _TEMPLATE_OF_FIRM_ROLE:
        return _TEMPLATE_OF_FIRM_ROLE[firm_role]
    implied: dict[str | None, Template] = {
        "partner": "partner",
        "manager": "manager",
        "senior": "senior",
        "seasonal": "tax_preparer",
    }
    return implied.get(level, "staff")


def levels_of(template: Template) -> list[Level]:
    return cast(list[Level], list(cast(list[str], generated.TEMPLATES[template]["levels"])))


def level_of(template: Template, level: str | None) -> Level:
    """The stored level when the template allows it, else the template's first."""
    allowed = levels_of(template)
    return level if level in allowed else allowed[0]


def _firm_role_of(template: Template) -> str | None:
    return cast(str | None, generated.TEMPLATES[template]["firm_role"])


# --- reading -------------------------------------------------------------------------------------


async def _read_or_404(ctx: AuthContext) -> None:
    """ADR-024: someone who can't read people sees nothing, not "forbidden"."""
    try:
        await authorise(ctx, "firm.read_people", Resource.firm(ctx.tenant_id))
    except Forbidden:
        raise NotFound("staff_member") from None


def _human(ctx: AuthContext) -> None:
    """INV-1 behind the matrix: only a signed-in person changes people."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden("firm.manage_users", "role")


def _member_row(
    m: RowMapping,
    contacts: Mapping[UUID, tuple[str, str]],
    teams: Mapping[UUID, list[UUID]],
    sign_ins: Mapping[UUID, datetime],
    actions: list[str],
) -> StaffRow:
    user = cast(UUID, m["user_id"])
    template = template_of(m["role_template"], m["firm_role"], m["level"])
    level = level_of(template, m["level"])
    active = m["status"] == "active"
    name, email = contacts.get(user, ("", ""))
    revoked = cast(datetime | None, m["revoked_at"])
    return StaffRow(
        user_id=user,
        invitation_id=None,
        display_name=name,
        email=email,
        title=m["job_title"],
        role_template=template,
        level=level,
        band=BAND_OF_LEVEL[level],
        status="active" if active else "deactivated",
        office_id=m["office_id"],
        team_ids=list(teams.get(user, [])),
        service_lines=list(m["service_lines"] or []),
        access_ends_on=m["access_ends_on"],
        offshore=bool(m["offshore"]),
        last_sign_in_at=sign_ins.get(user),
        invitation_expires_on=None,
        deactivated_on=_deactivated_on(revoked, m["access_ends_on"], m["revoked_reason"]),
        allowed_actions=actions if active else [],
        firm_role=m["firm_role"],
    )


def _deactivated_on(at: datetime | None, ends: date | None, reason: str | None) -> date | None:
    """ADM-02e reads "Deactivated Oct 31": an access end is dated by the end date itself."""
    if at is None:
        return None
    if reason == "access_ended" and ends is not None:
        return ends
    return at.astimezone(clock.FIRM_ZONE).date()


def _invitation_row(i: RowMapping, actions: list[str]) -> StaffRow:
    template = template_of(i["role_template"], i["firm_role"], i["level"])
    level = level_of(template, i["level"])
    expires = cast(datetime, i["expires_at"])
    email = str(i["email"])
    return StaffRow(
        user_id=None,
        invitation_id=cast(UUID, i["id"]),
        display_name=str(i["display_name"] or email.split("@", 1)[0]),
        email=email,
        title=i["job_title"],
        role_template=template,
        level=level,
        band=BAND_OF_LEVEL[level],
        status="invited",
        office_id=i["office_id"],
        team_ids=list(i["team_ids"] or []),
        service_lines=list(i["service_lines"] or []),
        access_ends_on=i["access_ends_on"],
        offshore=bool(i["offshore"]),
        last_sign_in_at=None,
        invitation_expires_on=expires.astimezone(clock.FIRM_ZONE).date(),
        deactivated_on=None,
        allowed_actions=[a for a in actions if a == "firm.manage_users"],
        firm_role=i["firm_role"],
        invitation_expires_at=expires,
        invited_at=i["created_at"],
    )


async def _all_rows(ctx: AuthContext) -> list[StaffRow]:
    actions = sorted(
        await allowed_actions(
            ctx, Resource.firm(ctx.tenant_id), ("firm.manage_users", "security_role.assign")
        )
    )
    now = await clock.now(ctx.tenant)
    async with tenant_session(ctx.tenant) as session:
        members = await repo.staff_rows(session)
        pending = await repo.pending_invitations(session, now)
        sign_ins = await repo.last_sign_ins(session)
    users = [cast(UUID, m["user_id"]) for m in members]
    # DEC-286: a staff session names no firm; someone who belongs or belonged to another firm
    # shows no sign-ins here, so nothing of theirs elsewhere leaks.
    elsewhere = await memberships_elsewhere(ctx.tenant_id, users)
    sign_ins = {u: at for u, at in sign_ins.items() if u not in elsewhere}
    contacts = await user_contacts(users)
    teams = await member_teams(ctx.tenant, users)
    rows = [_member_row(m, contacts, teams, sign_ins, actions) for m in members]
    # An invitation for someone already a member (re-invited after deactivation) shows once.
    rows += [_invitation_row(i, actions) for i in pending]
    order = {band: n for n, band in enumerate(BANDS)}
    return [r for _, r in sorted(enumerate(rows), key=lambda p: (order[p[1].band], p[0]))]


def _matches(row: StaffRow, f: StaffFilters, *, band: bool = True) -> bool:
    if f.q:
        needle = f.q.casefold()
        if needle not in row.display_name.casefold() and needle not in row.email.casefold():
            return False
    return (
        (f.role_template is None or row.role_template == f.role_template)
        and (f.office_id is None or row.office_id == f.office_id)
        and (f.team_id is None or f.team_id in row.team_ids)
        and (f.status is None or row.status == f.status)
        and (not band or f.band is None or row.band == f.band)
    )


async def _tallies(ctx: AuthContext, rows: Sequence[StaffRow]) -> Tallies:
    active = [r for r in rows if r.status == "active"]
    pending = sum(r.status == "invited" for r in rows)
    seasonal = [r for r in active if r.level == "seasonal"]
    ends = sorted(r.access_ends_on for r in seasonal if r.access_ends_on is not None)
    partners = sum(r.level == "partner" for r in active)
    operations = sum(r.level == "admin" for r in active)
    return Tallies(
        seats_used=len(active) + pending,
        seats_total=await seat_total(ctx.tenant),
        seats_pending=pending,
        partners=partners,
        professionals=len(active) - partners - operations,
        operations=operations,
        # DEC-22: staff sign in only through SSO with MFA, so every active member counts.
        sso_mfa=len(active),
        signed_in_of=len(active),
        walls_active=await active_wall_count(ctx),
        seasonal=len(seasonal),
        seasonal_access_ends_on=ends[0] if ends else None,
    )


def _filters_hash(f: StaffFilters) -> str:
    return query_hash(
        q=f.q,
        role_template=f.role_template,
        office_id=f.office_id,
        team_id=f.team_id,
        status=f.status,
        band=f.band,
    )


async def staff_page(ctx: AuthContext, f: StaffFilters, *, legacy: bool = False) -> StaffPage:
    """AC3.1, AC3.2: the people list on the envelope, with band counts and tallies. `legacy`:
    SPEC-024's route, which keeps `firm.manage_users` (403, fresh MFA; DEC-286)."""
    if legacy:
        await _manage(ctx)
    else:
        await _read_or_404(ctx)
    rows = await _all_rows(ctx)
    unbanded = [r for r in rows if _matches(r, f, band=False)]
    counts = {band: sum(r.band == band for r in unbanded) for band in BANDS}
    matched = [r for r in unbanded if f.band is None or r.band == f.band]
    query = _filters_hash(f)
    start = 0
    if f.cursor is not None:
        start = int(
            decode_cursor(f.cursor, tenant_id=ctx.tenant_id, resource=_LIST, query=query).key or 0
        )
    limit = clamp_limit(f.limit)
    page = matched[start : start + limit]
    after = start + len(page)
    next_cursor = (
        encode_cursor(
            Position(after, str(page[-1].user_id or page[-1].invitation_id)),
            tenant_id=ctx.tenant_id,
            resource=_LIST,
            query=query,
        )
        if page and after < len(matched)
        else None
    )
    return StaffPage(page, len(matched), next_cursor, counts, await _tallies(ctx, rows))


async def _visible_walls(ctx: AuthContext, user_id: UUID) -> list[UUID]:
    """The person's walls, for a reader who may list walls, less any on a client the reader is
    walled from (DEC-43: a reader never learns of those)."""
    if "wall.list" not in await allowed_actions(ctx, Resource.firm(ctx.tenant_id), ("wall.list",)):
        return []
    hidden = await walled_clients(ctx.tenant, ctx.user_id)
    async with tenant_session(ctx.tenant) as session:
        walls = await session.execute(
            text(
                "SELECT id, client_id FROM ethical_walls WHERE user_id = :u "
                "AND status = 'active' ORDER BY created_at, id"
            ),
            {"u": user_id},
        )
        return [w.id for w in walls if w.client_id not in hidden]


async def staff_user(ctx: AuthContext, user_id: UUID) -> UserDetail:
    """AC4.1: ADM-02d's drawer."""
    await _read_or_404(ctx)
    row = next((r for r in await _all_rows(ctx) if r.user_id == user_id), None)
    if row is None:
        raise NotFound("staff_member")
    async with tenant_session(ctx.tenant) as session:
        member = await repo.staff_row(session, user_id)
        history = await repo.sign_in_history(session, user_id, SIGN_INS_SHOWN)
        assignments = await repo.assignment_count(session, user_id)
    if member is None:
        raise NotFound("staff_member")
    return UserDetail(
        row=row,
        firm_role=member["firm_role"],
        wall_ids=await _visible_walls(ctx, user_id),
        assignment_count=assignments,
        recent_sign_ins=[]
        if await memberships_elsewhere(ctx.tenant_id, [user_id])
        else [SignIn(h["signed_in_at"], str(h["provider"]), bool(h["mfa"])) for h in history],
        version=int(member["version"]),
    )


# --- writing -------------------------------------------------------------------------------------


async def _manage(ctx: AuthContext) -> None:
    await authorise(ctx, "firm.manage_users", Resource.firm(ctx.tenant_id))
    _human(ctx)


async def _check_office(ctx: AuthContext, office_id: UUID | None) -> None:
    if office_id is not None and office_id not in {o for o, _ in await firm_offices(ctx.tenant)}:
        raise PersonInvalid(facts={"field": "office_id"})


async def update_person(
    ctx: AuthContext, user_id: UUID, version: int, changes: Mapping[str, object]
) -> None:
    """AC4.6 and ADM-02d's fields: the attributes sent (a sent `null` clears), against the
    person's version; `team_ids` replaces their teams."""
    await _manage(ctx)
    async with uow(ctx.tenant) as tx:
        member = await repo.staff_row(tx.session, user_id)
        if member is None or member["status"] != "active":
            raise NotFound("staff_member")
        if int(member["version"]) != version:
            raise StalePerson(facts={"version": int(member["version"])})
        merged: dict[str, object] = {
            "job_title": member["job_title"],
            "office_id": member["office_id"],
            "service_lines": list(member["service_lines"] or []),
            "access_ends_on": member["access_ends_on"],
            "offshore": bool(member["offshore"]),
        }
        for name in _ATTRIBUTES:
            if name in changes:
                value = changes[name]
                merged["job_title" if name == "title" else name] = (
                    list(cast(list[str], value)) if name == "service_lines" and value else value
                )
        if merged["service_lines"] is None:
            merged["service_lines"] = []
        if merged["offshore"] is None:
            merged["offshore"] = False
        template = template_of(member["role_template"], member["firm_role"], member["level"])
        if level_of(template, member["level"]) == "seasonal" and merged["access_ends_on"] is None:
            raise AccessEndsRequired
        await _check_office(ctx, cast(UUID | None, merged["office_id"]))
        if merged["offshore"] and not member["offshore"]:
            # No offshore-disclosure consent provider is registered until T-01 (fail closed,
            # DEC-52): any assignment conflicts.
            held = await repo.assignment_count(tx.session, user_id)
            if held:
                raise OffshoreAssignmentConflict(facts={"assignments": held})
        if not await repo.update_attributes(tx.session, user_id, version, merged):
            raise StalePerson(facts={"version": version})
        if "team_ids" in changes:
            teams = list(cast(list[UUID], changes["team_ids"] or []))
            if not await set_member_teams(tx, ctx.tenant_id, user_id, teams):
                raise PersonInvalid(facts={"field": "team_ids"})
        changed = sorted(set(changes) & {*_ATTRIBUTES, "team_ids"})
        tx.record(
            "membership.attributes_changed",
            target=Target("user", user_id),
            after=Ref(version=version + 1, **dict.fromkeys(changed, 1)),
        )
        tx.emit(AccessChanged(user_id=user_id))


async def change_template(
    ctx: AuthContext,
    user_id: UUID,
    template: Template,
    level: Level | None = None,
    oversight: str | None = None,
) -> None:
    """AC4.2: the template, its level and the firm role it carries, in one unit of work; it
    applies on their next request. A partner may also hold a firm oversight role."""
    await _manage(ctx)
    if level is not None and level not in levels_of(template):
        raise PersonInvalid(facts={"field": "level"})
    async with uow(ctx.tenant) as tx:
        member = await repo.staff_row(tx.session, user_id)
        if member is None or member["status"] != "active":
            raise NotFound("staff_member")
        firm_role = _firm_role_of(template)
        if firm_role is None and template == "partner":
            firm_role = oversight if oversight in _OVERSIGHT else None
            if oversight is None and member["firm_role"] in _OVERSIGHT:
                firm_role = member["firm_role"]
        new_level = level or level_of(template, member["level"])
        if new_level == "seasonal" and member["access_ends_on"] is None:
            raise AccessEndsRequired
        if member["firm_role"] != firm_role:
            outcome = await repo.set_firm_role(tx.session, user_id, firm_role)
            if outcome == "last_admin":
                raise LastAdministrator(facts={"role": str(member["firm_role"])})
            if outcome != "ok":
                raise NotFound("staff_member")
            if member["firm_role"] == "firm_admin":  # no longer invites: their invitations end
                await revoke_invitations_of(tx, user_id, include_to=False)
        await repo.set_template(tx.session, user_id, template, new_level)
        tx.record(
            "membership.role_changed",
            target=Target("user", user_id),
            after=Ref(
                template=TEMPLATES.index(template) + 1,
                version=int(member["version"]) + 1,
            ),
        )
        tx.emit(AccessChanged(user_id=user_id))


async def set_security_role(ctx: AuthContext, user_id: UUID, security_admin: bool) -> None:
    """AC4.3: grant or remove `security_admin` only; someone holding another firm role keeps it
    (409 `firm_role_held`), and the last security admin stays (409 `last_admin`)."""
    await authorise(ctx, "security_role.assign", Resource.firm(ctx.tenant_id))
    _human(ctx)
    async with uow(ctx.tenant) as tx:
        member = await repo.staff_row(tx.session, user_id)
        if member is None or member["status"] != "active":
            raise NotFound("staff_member")
        current = member["firm_role"]
        if current not in (None, "security_admin"):
            raise FirmRoleHeld
        wanted = "security_admin" if security_admin else None
        if current != wanted:
            outcome = await repo.set_firm_role(tx.session, user_id, wanted)
            if outcome == "last_admin":
                raise LastAdministrator(facts={"role": "security_admin"})
            if outcome != "ok":
                raise NotFound("staff_member")
            # The template follows the firm role (an IT / Security template implies it).
            await repo.reconcile_template(tx.session, user_id)
            await repo.bump_version(tx.session, user_id)
        tx.record(
            "membership.security_role_changed",
            target=Target("user", user_id),
            after=Ref(security_admin=int(security_admin)),
        )
        tx.emit(AccessChanged(user_id=user_id))


async def deactivate(ctx: AuthContext, user_id: UUID, reason: str = "manual") -> None:
    """AC4.4: revoked with its reason, the seat freed, sessions ended; engagement roles stay as
    history and every sign-off stays attributed (memberships are never deleted)."""
    await _manage(ctx)
    if reason != "manual":
        raise DeactivationReasonInvalid
    elsewhere = await memberships_elsewhere(ctx.tenant_id, [user_id])
    async with uow(ctx.tenant) as tx:
        outcome = await repo.deactivate(
            tx.session, user_id, reason, None, end_sessions=not elsewhere.get(user_id, False)
        )
        if outcome == "not_found":
            raise NotFound("staff_member")
        if outcome == "last_admin":
            raise LastAdministrator(facts={"role": "firm_admin"})
        tx.record(
            "membership.deactivated",
            target=Target("user", user_id),
            after=Ref(reason=_REASON_INDEX[reason]),
        )
        await revoke_invitations_of(tx, user_id, include_to=True)
        tx.emit(MembershipDeactivated(user_id=user_id))
        tx.emit(AccessChanged(user_id=user_id))


async def revoke_invitations_of(tx: UnitOfWork, user_id: UUID, *, include_to: bool) -> None:
    """In the caller's unit of work: the pending invitations the person sent (they can no
    longer invite) and, with `include_to`, those sent to their own email (which would bring a
    deactivated member back), revoked with their tokens cleared and an audit row each."""
    email = None
    if include_to:
        email = (await user_contacts([user_id])).get(user_id, ("", ""))[1] or None
    for invitation in await repo.pending_invitations_of(tx.session, user_id, email):
        await set_staff_invitation_status(tx.session, invitation, "revoked")
        await set_staff_token_hash(tx.session, invitation, None)
        tx.record("staff_invitation.revoked", target=Target("staff_invitation", invitation))


async def check_seats_at_acceptance(session: AsyncSession, now: datetime) -> None:
    """Acceptance turns a held seat into a member's; if provisioning lowered the seats while the
    invitation waited, there may be none for it (DEC-285). Holds the firm's row."""
    await repo.lock_firm(session)
    total = await repo.stored_seats(session)
    used = await repo.seats_held(session, now)
    if total is not None and used > total:
        raise SeatsFull(facts={"used": used, "total": total})


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def invite(ctx: AuthContext, terms: InviteTerms) -> UUID:
    """AC3.3 to AC3.5: a single-use, 14-day invitation that counts against the seats while
    pending; a pending one for the same email is replaced."""
    await _manage(ctx)
    email = terms.email.strip()
    if not 3 <= len(email) <= 320 or "@" not in email:
        raise PersonInvalid(facts={"field": "email"})
    template = terms.role_template or template_of(None, terms.firm_role, terms.level)
    if terms.level is not None and terms.level not in levels_of(template):
        raise PersonInvalid(facts={"field": "level"})
    level = level_of(template, terms.level)
    if level == "seasonal" and terms.access_ends_on is None:
        raise AccessEndsRequired
    firm_role = _firm_role_of(template) or (
        terms.firm_role if template == "partner" and terms.firm_role in _OVERSIGHT else None
    )
    if terms.role_template is None:  # SPEC-024's invitation: the firm role as sent
        firm_role = terms.firm_role
    await _check_office(ctx, terms.office_id)
    rows = await _all_rows(ctx)
    if any(r.status == "active" and r.email.casefold() == email.casefold() for r in rows):
        raise AlreadyMember
    invitation_id = uuid4()
    now = await clock.now(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        # The seat check holds the firm's row (DEC-285): two invitations can't both take the
        # last seat.
        synthetic = await repo.lock_firm(tx.session)
        replaced = await pending_staff_invitation_for(tx.session, email)
        total = await repo.stored_seats(tx.session)
        if total is None and not synthetic:
            raise SeatsNotProvisioned
        used = await repo.seats_held(tx.session, now, but_email=email)
        if total is not None and used >= total:
            raise SeatsFull(facts={"used": used, "total": total})
        if replaced is not None:
            await set_staff_invitation_status(tx.session, replaced, "revoked")
            await set_staff_token_hash(tx.session, replaced, None)
            tx.record("staff_invitation.revoked", target=Target("staff_invitation", replaced))
        await repo.insert_invitation(
            tx.session,
            {
                "id": invitation_id,
                "tenant_id": ctx.tenant_id,
                "email": email,
                "firm_role": firm_role,
                "invited_by": ctx.user_id,
                "expires_at": now + timedelta(days=INVITATION_DAYS),
                # A SPEC-024 invitation (no template) leaves the membership as the definer does.
                "role_template": terms.role_template,
                "level": level if terms.role_template is not None else terms.level,
                "office_id": terms.office_id,
                "team_ids": list(dict.fromkeys(terms.team_ids)),
                "service_lines": list(dict.fromkeys(terms.service_lines)),
                "access_ends_on": terms.access_ends_on,
                "offshore": terms.offshore,
                "display_name": terms.display_name,
                "job_title": terms.title,
            },
        )
        tx.record(
            "staff_invitation.created",
            target=Target("staff_invitation", invitation_id),
            after=Ref(email=_digest(email.casefold()), template=TEMPLATES.index(template) + 1),
        )
        tx.emit(StaffInvitationIssued(invitation_id=invitation_id))
    return invitation_id


async def apply_invitation_terms(
    session: AsyncSession, invitation_id: UUID, user_id: UUID
) -> list[UUID]:
    """On acceptance (AC3.4), in the acceptance's unit of work: the membership takes the
    invitation's template, level, office, service lines, access end, offshore and title. Returns
    the invitation's teams for the caller to set."""
    terms = await repo.invitation_terms(session, invitation_id)
    if terms is None or terms["role_template"] is None:
        return []  # a SPEC-024 invitation: the membership keeps what the definer gave it
    await session.execute(
        text(
            "UPDATE memberships SET role_template = :t, level = :l, office_id = :o, "
            "service_lines = :s, access_ends_on = :e, offshore = :off, "
            "job_title = coalesce(:title, job_title) "
            "WHERE user_id = :u AND kind = 'staff'"
        ),
        {
            "t": terms["role_template"],
            "l": terms["level"],
            "o": terms["office_id"],
            "s": list(terms["service_lines"] or []),
            "e": terms["access_ends_on"],
            "off": bool(terms["offshore"]),
            "title": terms["job_title"],
            "u": user_id,
        },
    )
    return list(terms["team_ids"] or [])


# --- role templates and the grid (AC5.1 to AC5.3) -----------------------------------------------


def _source(actions: list[str]) -> Literal["matrix", "policy"]:
    from abacus.modules.identity.authz.matrix import RULES

    return "matrix" if actions and all(a in RULES for a in actions) else "policy"


async def role_templates(ctx: AuthContext) -> RoleTemplates:
    """Eight templates with their member counts, the sixteen-row grid and the locked agent row.
    Cells are the declared policy, narrowed by the firm's stricter-only overrides: a `deny`
    override on a row's action for every role a template may hold makes its cell `deny`."""
    await _read_or_404(ctx)
    rows = [r for r in await _all_rows(ctx) if r.status == "active"]
    templates = [
        TemplateCount(t, levels_of(t), sum(r.role_template == t for r in rows)) for t in TEMPLATES
    ]
    grid_rows = list(generated.GRID)
    actions = sorted({a for g in grid_rows for a in cast(list[str], g["actions"])})
    async with tenant_session(ctx.tenant) as session:
        denied = await repo.denied_overrides(session, actions)
    grid: list[GridRow] = []
    for g in grid_rows:
        row_actions = list(cast(list[str], g["actions"]))
        cells = dict(cast(dict[str, Cell], g["cells"]))
        for t in TEMPLATES:
            roles = cast(list[str], generated.TEMPLATES[t]["roles"])
            if cells[t] != "deny" and any(
                all((a, role) in denied for role in roles) for a in row_actions
            ):
                cells[t] = "deny"
        grid.append(
            GridRow(
                key=str(g["key"]),
                actions=row_actions,
                cells=cells,
                conditions=dict(cast(dict[str, str], g["conditions"])),
                source=_source(row_actions),
            )
        )
    grid.append(
        GridRow(
            key="accrued_agent",
            actions=sorted(
                {
                    a
                    for g in grid_rows
                    if g["key"] in generated.AGENT_NEVER
                    for a in cast(list[str], g["actions"])
                }
            ),
            cells=dict.fromkeys(TEMPLATES, cast(Cell, "locked")),
            conditions={},
            source="policy",
            locked=True,
        )
    )
    return RoleTemplates(templates, grid)


# --- provisioning and the scenario loader (G-01-T06) --------------------------------------------


@dataclass(frozen=True)
class MemberProfile:
    """What directory sync, provisioning or the scenario loader sets on a staff membership."""

    role_template: Template
    level: Level
    title: str | None = None
    service_lines: list[str] = field(default_factory=list[str])
    access_ends_on: date | None = None
    offshore: bool = False
    team_ids: list[UUID] = field(default_factory=list[UUID])


async def set_member_profile(
    tx: UnitOfWork, tenant_id: UUID, user_id: UUID, profile: MemberProfile
) -> None:
    """A staff member's template, level, firm role, title, service lines, access end, offshore
    and teams, in the caller's unit of work (no caller rights: provisioning and the loader own
    the unit of work and its actor), with its audit row. The definers still keep the last
    administrators."""
    if profile.level not in levels_of(profile.role_template):
        raise PersonInvalid(facts={"field": "level"})
    if profile.level == "seasonal" and profile.access_ends_on is None:
        raise AccessEndsRequired
    member = await repo.staff_row(tx.session, user_id)
    if member is None or member["status"] != "active":
        raise NotFound("staff_member")
    firm_role = _firm_role_of(profile.role_template)
    if firm_role is None:
        oversight = member["firm_role"] in _OVERSIGHT and profile.role_template == "partner"
        firm_role = member["firm_role"] if oversight else None
    if member["firm_role"] != firm_role:
        outcome = await repo.set_firm_role(tx.session, user_id, firm_role)
        if outcome == "last_admin":
            raise LastAdministrator(facts={"role": str(member["firm_role"])})
        if member["firm_role"] == "firm_admin":
            await revoke_invitations_of(tx, user_id, include_to=False)
    await repo.set_template(tx.session, user_id, profile.role_template, profile.level)
    await tx.session.execute(
        text(
            "UPDATE memberships SET job_title = :title, service_lines = :lines, "
            "access_ends_on = :ends, offshore = :offshore WHERE user_id = :u AND kind = 'staff'"
        ),
        {
            "title": profile.title,
            "lines": list(dict.fromkeys(profile.service_lines)),
            "ends": profile.access_ends_on,
            "offshore": profile.offshore,
            "u": user_id,
        },
    )
    if not await set_member_teams(tx, tenant_id, user_id, profile.team_ids):
        raise PersonInvalid(facts={"field": "team_ids"})
    tx.record(
        "membership.profile_set",
        target=Target("user", user_id),
        after=Ref(template=TEMPLATES.index(profile.role_template) + 1),
    )
    tx.emit(AccessChanged(user_id=user_id))
