"""ADM-08's tax-engine settings, live (T-01-T20; T-01 §3.7; DEC-1364). Red: what may leave the
firm for the engine is decided here.

- **Cells** are the file bridge's settings, stored as `integration_mappings` rows. The rules that
  keep a person's approval in the loop are locked on (stricter-only): export only after final
  approval, import only through an approval, and no status push (the bridge has no push). "Who
  may export" may narrow the matrix, never widen it (`reviewer_manager_signer` ⊃ `manager_signer`
  ⊃ `signer`). A locked cell answers 409 `setting_locked`; an unknown cell 422.
- **Mappings** (users, offices, workflow status) replace the kind's rows with the ones sent. Two
  Accrued statuses may not mirror onto one engine status: 409 `mapping_conflict` (and 0466's
  partial unique index). Every save carries the install's `version` (409 `stale_version`) and is
  audited (`integration.settings_updated`); the first save creates the file-bridge install.
- **Test** in file mode is a format check of the latest engine file, by the module that holds the
  files (`register_engine_file_check`; tax registers it): codes only, never the file's content.
- `engine_return_id` renders the return-ID template; T-01-T25's export uses it.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel._statuses import ReturnStatus
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Resource, allowed_actions, authorise
from abacus.modules.integrations.models import FirmIntegration, IntegrationMapping

ENGINE_KEY: Final = "cch_axcess_tax"
READ: Final = "integration.read"
CONFIGURE: Final = "integration.configure"
TEST: Final = "integration.test"
SUBJECT: Final = "firm_integration"
MappingKind = Literal["user", "office", "workflow_status"]
EXPORTERS: Final = ("reviewer_manager_signer", "manager_signer", "signer")  # widest first
TEMPLATE: Final = "{Tax year}{Type}:{Client code}:V{n}"


@dataclass(frozen=True)
class Cell:
    key: str
    kind: str
    source_key: str
    default: str
    lock_reason: str | None = None


CELLS: Final = (
    Cell("return_id_template", "return_id_template", "template", TEMPLATE),
    Cell("client_code_rule", "client_code_rule", "rule", "last_name_first_initial"),
    Cell("type_letter.1040", "type_letters", "1040", "I"),
    Cell("type_letter.1065", "type_letters", "1065", "P"),
    Cell("type_letter.1120", "type_letters", "1120", "C"),
    Cell("type_letter.1120S", "type_letters", "1120S", "S"),
    Cell("type_letter.1041", "type_letters", "1041", "F"),
    Cell(
        "export_after_final_approval",
        "export_rules",
        "export_after_final_approval",
        "true",
        "stricter_only",
    ),
    Cell(
        "import_requires_approval",
        "export_rules",
        "import_requires_approval",
        "true",
        "stricter_only",
    ),
    Cell("who_may_export", "export_rules", "who_may_export", EXPORTERS[0]),
    Cell("status_push", "export_rules", "status_push", "off", "file_mode_has_no_push"),
)
_BY_KEY: Final = {c.key: c for c in CELLS}
_CODE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}")
_RULES: Final = frozenset({"last_name_first_initial", "client_number", "entity_name"})


class SettingLocked(DomainConflict):
    """A stricter-only rule stays on (`facts.key`)."""

    code = "setting_locked"


class MappingConflict(DomainConflict):
    """Two Accrued statuses would mirror onto one engine status."""

    code = "mapping_conflict"


class SettingsStale(DomainConflict):
    code = "stale_version"


class SettingInvalid(DomainInvalid):
    code = "setting_invalid"


@dataclass(frozen=True)
class FormatCheck:
    ok: bool
    problems: tuple[str, ...]
    returns_read: int | None = None


EngineFileCheck = Callable[[TenantContext], Awaitable[FormatCheck]]
_CHECKS: list[EngineFileCheck] = []


LastEngineSync = Callable[[TenantContext], Awaitable[UUID | None]]
_LAST_SYNC: list[LastEngineSync] = []


def register_last_engine_sync(provider: LastEngineSync) -> None:
    """T-01-T51: the module that keeps the engine's sync events answers which return synced last
    (tax), so ADM-08's Last sync opens that return's TAX-09; integrations never reads tax."""
    _LAST_SYNC[:] = [provider]


async def last_engine_sync(tenant: TenantContext) -> UUID | None:
    """The return whose sync with the engine was the firm's latest, or None (nothing registered,
    or no sync yet). An identifier only: TAX-09 authorises the return when it opens."""
    return await _LAST_SYNC[0](tenant) if _LAST_SYNC else None


def register_engine_file_check(check: EngineFileCheck) -> None:
    """The module that holds the engine's files checks the latest one (tax, T-01-T19)."""
    if _CHECKS and _CHECKS[0] is not check:
        raise RuntimeError("an engine file check is already registered")
    if not _CHECKS:
        _CHECKS.append(check)


@dataclass(frozen=True)
class CellView:
    key: str
    value: str
    locked: bool
    lock_reason: str | None


@dataclass(frozen=True)
class MappingView:
    kind: str
    source_key: str
    target_value: str
    direction: str | None


@dataclass(frozen=True)
class SettingsView:
    key: str
    mode: Literal["file_bridge", "api"]
    enabled: bool
    cells: tuple[CellView, ...]
    mappings: tuple[MappingView, ...]
    version: int
    allowed_actions: tuple[str, ...]


def engine_return_id(
    template: str, *, tax_year: int, type_letter: str, client_code: str, version: int | None
) -> str:
    """`{Tax year}{Type}:{Client code}:V{n}` → `2025I:FeldJ:V3` (without a version, the return
    without its `:V{n}` part)."""
    out = template.replace("{Tax year}", str(tax_year)).replace("{Type}", type_letter)
    out = out.replace("{Client code}", client_code)
    if version is None:
        return out.removesuffix(":V{n}")
    return out.replace("{n}", str(version))


@dataclass(frozen=True)
class ExportSettings:
    """What T-01-T25's export reads of the firm's file-bridge install: whether it is on, the
    return-ID template, the client-code rule, each form's type letter and who may export."""

    enabled: bool
    return_id_template: str
    client_code_rule: str
    type_letters: Mapping[str, str]
    who_may_export: str


async def export_settings(tenant: TenantContext) -> ExportSettings:
    """The firm's engine export settings, for tax's export after it authorised the caller. With
    no install, or an install switched off, `enabled` is False (the per-firm kill switch)."""
    async with tenant_session(tenant) as session:
        install = await _install(session, ENGINE_KEY)
        rows = (
            list(
                (
                    await session.execute(
                        select(IntegrationMapping).where(
                            IntegrationMapping.firm_integration_id == install.id
                        )
                    )
                ).scalars()
            )
            if install
            else []
        )
    stored = {(r.kind, r.source_key): r.target_value for r in rows}

    def cell(key: str) -> str:
        c = _BY_KEY[key]
        return c.default if c.lock_reason else stored.get((c.kind, c.source_key), c.default)

    letters = {c.source_key: cell(c.key) for c in CELLS if c.kind == "type_letters"}
    return ExportSettings(
        enabled=install is not None and install.status == "connected",
        return_id_template=cell("return_id_template"),
        client_code_rule=cell("client_code_rule"),
        type_letters=letters,
        who_may_export=cell("who_may_export"),
    )


def _person(ctx: AuthContext) -> None:
    if ctx.client:
        raise NotFound("integration")


async def _install(
    session: AsyncSession, key: str, *, lock: bool = False
) -> FirmIntegration | None:
    stmt = select(FirmIntegration).where(
        FirmIntegration.catalog_key == key, FirmIntegration.status != "disconnected"
    )
    if lock:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def _view(ctx: AuthContext, session: AsyncSession, key: str) -> SettingsView:
    install = await _install(session, key)
    rows = (
        list(
            (
                await session.execute(
                    select(IntegrationMapping)
                    .where(IntegrationMapping.firm_integration_id == install.id)
                    .order_by(IntegrationMapping.kind, IntegrationMapping.source_key)
                )
            ).scalars()
        )
        if install
        else []
    )
    stored = {(r.kind, r.source_key): r.target_value for r in rows}
    cells = tuple(
        CellView(
            c.key,
            c.default if c.lock_reason else stored.get((c.kind, c.source_key), c.default),
            c.lock_reason is not None,
            c.lock_reason,
        )
        for c in CELLS
    )
    mappings = tuple(
        MappingView(r.kind, r.source_key, r.target_value, r.direction)
        for r in rows
        if r.kind in ("user", "office", "workflow_status")
    )
    may = await allowed_actions(ctx, Resource.firm(ctx.tenant_id), [CONFIGURE, TEST])
    return SettingsView(
        key,
        "api" if install is not None and install.mode == "token" else "file_bridge",
        install is not None,
        cells,
        mappings,
        install.version if install else 1,
        tuple(sorted(may)),
    )


async def settings_view(ctx: AuthContext, key: str) -> SettingsView:
    _person(ctx)
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    if key != ENGINE_KEY:
        raise NotFound("integration")
    async with tenant_session(ctx.tenant) as session:
        return await _view(ctx, session, key)


def _check_cell(cell: Cell, value: str) -> str:
    value = value.strip()
    if cell.lock_reason is not None:
        if value != cell.default:
            raise SettingLocked(facts={"key": cell.key})
        return value
    ok = {
        "return_id_template": "{Tax year}" in value
        and "{Client code}" in value
        and value.endswith(":V{n}")
        and len(value) <= 80,
        "client_code_rule": value in _RULES,
        "type_letters": len(value) == 1 and value.isalpha() and value.isupper(),
        "export_rules": value in EXPORTERS,
    }[cell.kind]
    if not ok:
        raise SettingInvalid(facts={"field": cell.key})
    return value


async def _save(
    ctx: AuthContext,
    key: str,
    seen_version: int,
    write: Callable[[AsyncSession, UUID], Awaitable[int]],
) -> SettingsView:
    """One save: the install at the version seen (created on the first save), the rows, the
    version bump and the audit, in one unit of work."""
    _person(ctx)
    await authorise(ctx, CONFIGURE, Resource.firm(ctx.tenant_id))
    if key != ENGINE_KEY:
        raise NotFound("integration")
    async with uow(ctx.tenant) as tx:
        install = await _install(tx.session, key, lock=True)
        if install is None:
            if seen_version != 1:
                raise SettingsStale(facts={"key": key})
            install_id = (
                await tx.session.execute(
                    insert(FirmIntegration)
                    .values(
                        tenant_id=ctx.tenant_id,
                        catalog_key=key,
                        status="connected",
                        mode="file_bridge",
                        created_by=ctx.user_id,
                    )
                    .returning(FirmIntegration.id)
                )
            ).scalar_one()
            version = 1
        else:
            if install.version != seen_version:
                raise SettingsStale(facts={"key": key})
            install_id, version = install.id, install.version
        changed = await write(tx.session, install_id)
        await tx.session.execute(
            update(FirmIntegration)
            .where(FirmIntegration.id == install_id)
            .values(version=version + 1)
        )
        tx.record(
            "integration.settings_updated",
            target=Target(SUBJECT, install_id),
            after=Ref(version=version + 1, rows=changed),
        )
        return await _view(ctx, tx.session, key)


async def _upsert(
    session: AsyncSession,
    ctx: AuthContext,
    install_id: UUID,
    kind: str,
    rows: Mapping[str, str],
    *,
    replace_all: bool,
) -> int:
    existing = {
        r.source_key: r
        for r in (
            await session.execute(
                select(IntegrationMapping).where(
                    IntegrationMapping.firm_integration_id == install_id,
                    IntegrationMapping.kind == kind,
                )
            )
        ).scalars()
    }
    changed = 0
    if replace_all:
        gone = [k for k in existing if k not in rows]
        if gone:
            await session.execute(
                delete(IntegrationMapping).where(
                    IntegrationMapping.firm_integration_id == install_id,
                    IntegrationMapping.kind == kind,
                    IntegrationMapping.source_key.in_(gone),
                )
            )
            changed += len(gone)
    for source, target in sorted(rows.items()):
        found = existing.get(source)
        if found is None:
            await session.execute(
                insert(IntegrationMapping).values(
                    tenant_id=ctx.tenant_id,
                    firm_integration_id=install_id,
                    kind=kind,
                    source_key=source,
                    target_value=target,
                    direction="one_way" if kind == "workflow_status" else None,
                    updated_by=ctx.user_id,
                )
            )
            changed += 1
        elif found.target_value != target:
            await session.execute(
                update(IntegrationMapping)
                .where(IntegrationMapping.id == found.id)
                .values(
                    target_value=target,
                    version=found.version + 1,
                    updated_by=ctx.user_id,
                    updated_at=func.abacus_now(),
                )
            )
            changed += 1
    return changed


async def save_cells(
    ctx: AuthContext, key: str, cells: Mapping[str, str], seen_version: int
) -> SettingsView:
    """ADM-08 a: the settings; locked cells stay as they are (409 if sent otherwise)."""
    checked: dict[tuple[str, str], str] = {}
    for name, value in cells.items():
        cell = _BY_KEY.get(name)
        if cell is None:
            raise SettingInvalid(facts={"field": name})
        checked[(cell.kind, cell.source_key)] = _check_cell(cell, value)
    writable = {k: v for k, v in checked.items() if _cell_of(k).lock_reason is None}

    async def write(session: AsyncSession, install_id: UUID) -> int:
        changed = 0
        for kind in sorted({k for k, _s in writable}):
            rows = {s: v for (k, s), v in writable.items() if k == kind}
            changed += await _upsert(session, ctx, install_id, kind, rows, replace_all=False)
        return changed

    return await _save(ctx, key, seen_version, write)


def _cell_of(kind_source: tuple[str, str]) -> Cell:
    return next(c for c in CELLS if (c.kind, c.source_key) == kind_source)


async def save_mapping(
    ctx: AuthContext, key: str, kind: MappingKind, rows: Mapping[str, str], seen_version: int
) -> SettingsView:
    """ADM-08 b, f: users, offices or the workflow-status mirror, replaced with the rows sent."""
    clean = {s.strip(): t.strip() for s, t in rows.items()}
    for source, target in clean.items():
        if not _CODE.fullmatch(target) or not source:
            raise SettingInvalid(facts={"field": kind})
        if kind in ("user", "office"):
            try:
                UUID(source)
            except ValueError:
                raise SettingInvalid(facts={"field": kind}) from None
        if kind == "workflow_status" and source not in {s.value for s in ReturnStatus}:
            raise SettingInvalid(facts={"field": kind})
    if kind == "workflow_status" and len(set(clean.values())) != len(clean):
        raise MappingConflict(facts={"kind": kind})

    async def write(session: AsyncSession, install_id: UUID) -> int:
        return await _upsert(session, ctx, install_id, kind, clean, replace_all=True)

    return await _save(ctx, key, seen_version, write)


async def format_check(ctx: AuthContext, key: str) -> FormatCheck:
    """ADM-08 d: the latest engine file, checked by its holder; codes only."""
    _person(ctx)
    await authorise(ctx, TEST, Resource.firm(ctx.tenant_id))
    if key != ENGINE_KEY:
        raise NotFound("integration")
    if not _CHECKS:
        return FormatCheck(False, ("no_engine_file",))
    try:
        return await _CHECKS[0](ctx.tenant)
    except Exception:  # the holder could not answer: a code, never its error text
        return FormatCheck(False, ("check_failed",))


__all__ = [
    "CELLS",
    "ENGINE_KEY",
    "EXPORTERS",
    "CellView",
    "FormatCheck",
    "MappingConflict",
    "MappingView",
    "SettingInvalid",
    "SettingLocked",
    "SettingsStale",
    "SettingsView",
    "engine_return_id",
    "format_check",
    "last_engine_sync",
    "register_engine_file_check",
    "register_last_engine_sync",
    "save_cells",
    "save_mapping",
    "settings_view",
]
