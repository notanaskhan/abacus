"""The typed firm-settings registry and store (G-01-T04; G-01 sections 3.1, 3.2; DEC-170).

A key is accepted only when registered (`register_firm_setting`). Most keys live in the typed
store (`firm_settings`); a key another module owns names that owner's accessor, so its value has
one home (AC1.9): the portal's display name and footer write `portal_branding`, the firm's time
zone writes `firms.time_zone`. A section's keys save in one unit of work against the section's
version (409 `stale_version`), with one `firm_setting.updated` event naming the keys, never a
value.

At a glance is the rows other areas register (`register_settings_area`), each given 500 ms; a row
whose provider fails or is slow reads `unavailable` and delays nothing else (AC2.3).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.authz import Forbidden, Resource, allowed_actions, authorise
from abacus.modules.identity.context import AuthContext

Section = Literal["profile", "defaults", "plan"]
Value = str | int | bool | None
Kind = Literal["text", "int", "bool"]
GlanceTone = Literal["ok", "attention", "partial", "none"]
GLANCE_BUDGET: Final = 0.5
_TYPES: Final[dict[Kind, type]] = {"text": str, "int": int, "bool": bool}
_log = get_logger(__name__)

Read = Callable[[TenantContext], Awaitable[Value]]
Write = Callable[[UnitOfWork, UUID, Value, UUID], Awaitable[None]]  # (tx, tenant, value, by)


class UnknownSetting(DomainInvalid):
    """A key no module registered, or one that isn't editable."""

    code = "unknown_setting"


class SettingInvalid(DomainInvalid):
    """A value of the wrong kind, or too long."""

    code = "setting_invalid"


class DisplayNameRequired(DomainInvalid):
    """The name clients see in the portal can't be empty (AC1.3)."""

    code = "display_name_required"


# The section changed since it was read: read it again. No docstring: the error catalogue keeps
# the shared `stale_version` summary.
class StaleSection(DomainConflict):
    code = "stale_version"


@dataclass(frozen=True)
class SettingKey:
    section: Section
    key: str
    kind: Kind
    max_length: int = 200
    editable: bool = True
    required: bool = False
    read: Read | None = None  # an owner accessor; None: the typed store
    write: Write | None = None
    # A-01-T23: an enumerated text key accepts only these codes (`assurance_release_mode`).
    choices: tuple[str, ...] | None = None


_KEYS: dict[tuple[str, str], SettingKey] = {}


def register_firm_setting(setting: SettingKey) -> None:
    known = _KEYS.get((setting.section, setting.key))
    if known is not None and known != setting:
        raise ValueError(f"setting {setting.section}.{setting.key} is already registered")
    _KEYS[(setting.section, setting.key)] = setting


def section_keys(section: Section) -> list[SettingKey]:
    return sorted((k for k in _KEYS.values() if k.section == section), key=lambda k: k.key)


# --- At a glance ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class GlanceRow:
    key: str
    tone: GlanceTone
    facts: dict[str, int] = field(default_factory=dict[str, int])
    href: str | None = None
    unavailable: bool = False


GlanceProvider = Callable[[AuthContext], Awaitable[GlanceRow | None]]
_AREAS: dict[str, tuple[int, GlanceProvider]] = {}


def register_settings_area(key: str, order: int, provider: GlanceProvider) -> None:
    """An area's one-line status; None from the provider hides the row for that caller."""
    _AREAS[key] = (order, provider)


async def _glance(ctx: AuthContext, key: str, provider: GlanceProvider) -> GlanceRow | None:
    try:
        return await asyncio.wait_for(provider(ctx), timeout=GLANCE_BUDGET)
    except Exception as exc:  # any failure or timeout: this row only (AC2.3)
        _log.warning("settings.glance_unavailable", area=key, error=type(exc).__name__)
        return GlanceRow(key, "none", unavailable=True)


# --- reading -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SectionView:
    section: Section
    values: list[tuple[SettingKey, Value]]
    version: int
    read_only_reason: str | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class OverviewView:
    firm_name: str
    sections: list[tuple[str, bool]]  # (section, visible)
    at_a_glance: list[GlanceRow]
    as_of: datetime


_STORED = text("SELECT key, value FROM firm_settings WHERE section = :section")
_VERSION = text("SELECT version FROM firm_settings_sections WHERE section = :section")
_FIRM_NAME = text("SELECT name FROM firms LIMIT 1")


def _sees_plan(ctx: AuthContext) -> bool:
    """Plan & seats is absent for a security admin, not just hidden (AC1.7)."""
    return ctx.firm_role != "security_admin"


async def _read_or_404(ctx: AuthContext) -> None:
    """ADR-024: a caller who can't read settings sees nothing, not "forbidden" (AC1.8)."""
    try:
        await authorise(ctx, "firm.read_settings", Resource.firm(ctx.tenant_id))
    except Forbidden:
        raise NotFound("firm_settings") from None


async def read_section(ctx: AuthContext, section: Section) -> SectionView:
    await _read_or_404(ctx)
    if section == "plan" and not _sees_plan(ctx):
        raise NotFound("firm_settings")
    keys = section_keys(section)
    async with tenant_session(ctx.tenant) as session:
        stored = {  # jsonb arrives decoded
            str(k): v
            for k, v in (await session.execute(_STORED, {"section": section})).tuples().all()
        }
        version = (await session.execute(_VERSION, {"section": section})).scalar_one_or_none() or 1
    values: list[tuple[SettingKey, Value]] = []
    for k in keys:
        value = await k.read(ctx.tenant) if k.read is not None else stored.get(k.key)
        values.append((k, value))
    can_write = "firm.manage_settings" in await allowed_actions(
        ctx, Resource.firm(ctx.tenant_id), ("firm.manage_settings",)
    )
    return SectionView(
        section,
        values,
        int(version),
        None if can_write else "firm_admin_only",
        ["firm.manage_settings"] if can_write else [],
    )


async def overview(ctx: AuthContext) -> OverviewView:
    await _read_or_404(ctx)
    async with tenant_session(ctx.tenant) as session:
        name = str((await session.execute(_FIRM_NAME)).scalar_one())
    sections = [("profile", True), ("defaults", True), ("plan", _sees_plan(ctx))]
    ordered = sorted(_AREAS.items(), key=lambda item: (item[1][0], item[0]))
    rows = await asyncio.gather(*(_glance(ctx, key, p) for key, (_order, p) in ordered))
    return OverviewView(
        name, sections, [r for r in rows if r is not None], await clock.now(ctx.tenant)
    )


# --- writing -------------------------------------------------------------------------------------


def _checked(setting: SettingKey, value: Value) -> Value:
    if value is None:
        if setting.required:
            raise DisplayNameRequired if setting.key == "display_name" else SettingInvalid
        return None
    if not isinstance(value, _TYPES[setting.kind]) or (
        setting.kind == "int" and isinstance(value, bool)
    ):
        raise SettingInvalid
    if isinstance(value, str):
        value = value.strip()
        if not value:
            if setting.required:
                raise DisplayNameRequired if setting.key == "display_name" else SettingInvalid
            return None
        if len(value) > setting.max_length or "\n" in value:
            raise SettingInvalid
        if setting.choices is not None and value not in setting.choices:
            raise SettingInvalid
    return value


async def save_section(
    ctx: AuthContext, section: Section, version: int, values: Mapping[str, Value]
) -> None:
    """Fresh MFA (`firm.manage_settings`); every key registered and editable; one unit of
    work against the section's version."""
    await authorise(ctx, "firm.manage_settings", Resource.firm(ctx.tenant_id))
    if section == "plan" and not _sees_plan(ctx):
        raise NotFound("firm_settings")
    checked: dict[str, tuple[SettingKey, Value]] = {}
    for key, value in values.items():
        setting = _KEYS.get((section, key))
        if setting is None or not setting.editable:
            raise UnknownSetting(facts={"key": key[:64]})
        checked[key] = (setting, _checked(setting, value))
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO firm_settings_sections (tenant_id, section) "
                "VALUES (:tenant, :section) ON CONFLICT (tenant_id, section) DO NOTHING"
            ),
            {"tenant": ctx.tenant_id, "section": section},
        )
        current = (
            await tx.session.execute(
                text(
                    "SELECT version FROM firm_settings_sections WHERE section = :section "
                    "FOR UPDATE"
                ),
                {"section": section},
            )
        ).scalar_one()
        if int(current) != version:
            raise StaleSection(facts={"section": section})
        for key, (setting, value) in checked.items():
            if setting.write is not None:
                await setting.write(tx, ctx.tenant_id, value, ctx.user_id)
                continue
            await tx.session.execute(
                text(
                    "INSERT INTO firm_settings (tenant_id, section, key, value, updated_by) "
                    "VALUES (:tenant, :section, :key, CAST(:value AS jsonb), :by) "
                    "ON CONFLICT (tenant_id, section, key) DO UPDATE SET "
                    "value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, "
                    "updated_at = abacus_now()"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "section": section,
                    "key": key,
                    "value": json.dumps(value),  # a cleared key is JSON null
                    "by": ctx.user_id,
                },
            )
        bumped = int(
            (
                await tx.session.execute(
                    text(
                        "UPDATE firm_settings_sections SET version = version + 1, "
                        "updated_at = abacus_now() WHERE section = :section RETURNING version"
                    ),
                    {"section": section},
                )
            ).scalar_one()
        )
        tx.record(
            "firm_setting.updated",
            target=Target("firm", ctx.tenant_id),
            after=Ref(version=bumped, **dict.fromkeys(sorted(checked), 1)),
        )


async def stored_value(tenant: TenantContext, section: Section, key: str) -> Value:
    """A typed-store key's value for the firm's own reads (no caller rights: the caller already
    authorised what it shows), or None when unset."""
    async with tenant_session(tenant) as session:
        value = await session.scalar(
            text("SELECT value FROM firm_settings WHERE section = :section AND key = :key"),
            {"section": section, "key": key},
        )
    return value if isinstance(value, str | int | bool) else None


async def provision_setting(
    tx: UnitOfWork, tenant_id: UUID, section: Section, key: str, value: Value, by: UUID
) -> None:
    """Set a registered key that no route may write (`editable=False`: the seat total), for
    provisioning and the scenario loader, in their unit of work, with its audit row."""
    setting = _KEYS.get((section, key))
    if setting is None or setting.editable or setting.read is not None:
        raise UnknownSetting(facts={"key": key[:64]})
    checked = _checked(setting, value)
    await tx.session.execute(
        text(
            "INSERT INTO firm_settings (tenant_id, section, key, value, updated_by) "
            "VALUES (:tenant, :section, :key, CAST(:value AS jsonb), :by) "
            "ON CONFLICT (tenant_id, section, key) DO UPDATE SET "
            "value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, updated_at = abacus_now()"
        ),
        {
            "tenant": tenant_id,
            "section": section,
            "key": key,
            "value": json.dumps(checked),
            "by": by,
        },
    )
    tx.record("firm_setting.provisioned", target=Target("firm", tenant_id), after=Ref(**{key: 1}))


async def seat_total(tenant: TenantContext) -> int | None:
    """The firm's seats (`plan.seats`, provisioning's; DEC-285), or None when not set."""
    value = await stored_value(tenant, "plan", "seats")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


# --- identity's own keys and At a glance row ---------------------------------------------------


async def _time_zone(tenant: TenantContext) -> Value:
    async with tenant_session(tenant) as session:
        return str(await session.scalar(text("SELECT time_zone FROM firms")))


async def _set_time_zone(tx: UnitOfWork, _tenant: UUID, value: Value, _by: UUID) -> None:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    if not isinstance(value, str):
        raise SettingInvalid
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise SettingInvalid from None
    await tx.session.execute(text("UPDATE firms SET time_zone = :z"), {"z": value})


_PEOPLE = text(
    "SELECT (SELECT count(*) FROM memberships WHERE status = 'active' AND kind = 'staff'), "
    "(SELECT count(*) FROM staff_invitations WHERE status = 'pending'), "
    "(SELECT count(*) FROM memberships WHERE status = 'active' AND kind = 'staff' "
    "AND level = 'partner'), "
    "(SELECT count(*) FROM memberships WHERE status = 'active' AND kind = 'staff' "
    "AND (level = 'admin' OR role_template IN ('firm_admin', 'it_security')))"
)


async def _people(ctx: AuthContext) -> GlanceRow | None:
    """People: seat holders and pending invitations (AC2.1)."""
    async with tenant_session(ctx.tenant) as session:
        used, pending, partners, operations = (await session.execute(_PEOPLE)).one()
    # ADM-01 C's People line: partners and operations among the seat holders (G-01-T07).
    facts = {
        "used": int(used) + int(pending),
        "pending": int(pending),
        "partners": int(partners),
        "operations": int(operations),
    }
    total = await seat_total(ctx.tenant)
    if total is not None:
        facts["total"] = total
    return GlanceRow("people", "ok", facts, "/settings/people")


def register_identity_settings() -> None:
    for setting in (
        SettingKey("profile", "legal_name", "text"),
        SettingKey("profile", "website", "text", max_length=300),
        SettingKey("profile", "intake_mailbox", "text", max_length=254),
        SettingKey("profile", "seatless_staff_count", "int"),
        SettingKey(
            "profile", "time_zone", "text", max_length=64, read=_time_zone, write=_set_time_zone
        ),
        SettingKey("defaults", "week_starts_on", "text", max_length=16),
        SettingKey("plan", "billing_contact_user_id", "text", max_length=36),
        # G-01-T05 (DEC-285): the seat total; provisioning's, never a route's.
        SettingKey("plan", "seats", "int", editable=False),
    ):
        register_firm_setting(setting)
    register_settings_area("people", 10, _people)


async def active_wall_count(ctx: AuthContext) -> int | None:
    """The firm's active walls for At a glance, or None for a caller who can't list walls
    (AC2.4: shown only to `wall.list` holders, never a wrong count)."""
    if "wall.list" not in await allowed_actions(ctx, Resource.firm(ctx.tenant_id), ("wall.list",)):
        return None
    async with tenant_session(ctx.tenant) as session:
        return int(
            (
                await session.execute(
                    text("SELECT count(*) FROM ethical_walls WHERE status = 'active'")
                )
            ).scalar_one()
        )
