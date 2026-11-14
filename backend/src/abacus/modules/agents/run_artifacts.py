"""Run artifacts and drill (W-02-T20; W-02 §3.8 AC-R1 to AC-R4, §4.3; `docs/contracts/
workbench-sessions.md`; ADR-050, DEC-43, DEC-61, DEC-87; DEC-4933). PROTECTED (agents, red).

- **Preview** (`run_content.read`): one sheet of the run's **stored** workbook, read from the
  stored bytes (fingerprint-checked) with openpyxl in read-only mode: values only, formulas never
  evaluated, nothing recomputed (WB-03 d2). Row 1 is the header; a trailing row whose only value
  is a definition ("Gather = Not started 2 + Gathering 8 · …") after a blank row is the footnote.
- **Download** (`run_artifact.download`): the stored bytes with their content type, and one
  `run_artifact.downloaded` audit event naming the artifact and its fingerprint (no content).
- **Drill** (`session.manage`, the session owner): a code-rendered table of one result group's
  records appended to the session as a `drill` item, with no model call. The group key's prefix
  names a source registered by the module that owns the records (`register_drill_source`; tax
  registers `status`, its returns under TAX-01's visibility). Rows are resolved under the viewer's
  `visible()` at read time; nothing walled is listed or counted.

Who may read: an engagement run, the action on its engagement (walls first, 404); a firm-level
run (a Workbench session's), only the person it ran for, with the action at firm level. Anyone
else reads 404 (no existence leak, DEC-43).
"""

from __future__ import annotations

import io
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final, Literal, cast
from uuid import UUID

from openpyxl import load_workbook
from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.api import read_run_artifact
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise

XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_PREVIEW_ROWS: Final = 500
CellKind = Literal["text", "number", "money", "percent", "date", "blank"]
_NUMBER: Final = re.compile(r"^-?\d+(\.\d+)?$")


class DrillGroupUnknown(DomainInvalid):
    """The group key names no registered source, or a group the source does not know."""

    code = "drill_group_unknown"


@dataclass(frozen=True)
class Cell:
    value: str
    kind: CellKind = "text"
    bold: bool = False


@dataclass(frozen=True)
class Preview:
    artifact_id: UUID
    file_name: str
    sheets: list[str]
    sheet: str
    columns: list[str]
    rows: list[list[Cell]]
    footnote: str | None
    sha256: str


@dataclass(frozen=True)
class DrillRow:
    ref_type: Literal["tax_return"]
    ref_id: UUID
    label: str
    detail: str | None
    href: str


@dataclass(frozen=True)
class Drill:
    item_id: UUID
    group_key: str
    title: str
    total: int
    rows: list[DrillRow]


# A drill source: (viewer, artifact name, group value) -> (group words, rows), under `visible()`.
DrillSource = Callable[[AuthContext, str, str], Awaitable[tuple[str, list[DrillRow]] | None]]
_SOURCES: dict[str, DrillSource] = {}


# The session item's writer: (viewer, session, key hash, payload) -> item id. Workbench owns the
# session tables and registers it (OWN-001); it answers the item already written under the key.
DrillWriter = Callable[[AuthContext, UUID, str, dict[str, object]], Awaitable[UUID]]
_WRITER: list[DrillWriter] = []


def register_drill_writer(writer: DrillWriter) -> None:
    _WRITER[:] = [writer]


def register_drill_source(prefix: str, source: DrillSource) -> None:
    """The owning module registers how a group of its records is listed (ADR-106 slot)."""
    if prefix in _SOURCES and _SOURCES[prefix] is not source:
        raise ValueError(f"drill source {prefix!r} is already registered")
    _SOURCES[prefix] = source


_ARTIFACT: Final = text(
    "SELECT a.id, a.run_id, a.name, a.size_bytes, a.storage_key, a.storage_version_id, a.sha256, "
    "r.engagement_id, r.initiator_user_id, r.session_id FROM run_artifacts a "
    "JOIN agent_runs r ON r.id = a.run_id WHERE a.id = :id"
)


async def _readable(ctx: AuthContext, artifact_id: UUID, action: str) -> object:
    """The artifact's row once the viewer may take `action` on its run (module docstring)."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise NotFound("run_artifact")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_ARTIFACT, {"id": artifact_id})).first()
    if row is None or row.storage_key is None:
        raise NotFound("run_artifact")
    if row.engagement_id is not None:
        ref = await get_ref(ctx, row.engagement_id)  # a wall answers 404
        try:
            await authorise(ctx, action, ref.resource())
        except Forbidden:
            raise NotFound("run_artifact") from None
        return row
    if row.initiator_user_id != ctx.user_id:
        raise NotFound("run_artifact")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    return row


async def _bytes(ctx: AuthContext, row: object) -> bytes:
    r = cast(_Row, row)
    return await read_run_artifact(
        ctx.tenant_id, str(r.storage_key), str(r.storage_version_id), str(r.sha256),
        int(r.size_bytes),
    )  # fmt: skip


class _Row:  # the shape `_ARTIFACT` answers (for the type checker only)
    id: UUID
    run_id: UUID
    name: str
    size_bytes: int
    storage_key: str
    storage_version_id: str
    sha256: str
    engagement_id: UUID | None
    initiator_user_id: UUID | None
    session_id: UUID | None


def _cell(value: object, bold: bool) -> Cell:
    if value is None or value == "":
        return Cell("", "blank", bold)
    if isinstance(value, bool):
        return Cell("TRUE" if value else "FALSE", "text", bold)
    if isinstance(value, int | float):
        return Cell(f"{value:,}" if isinstance(value, int) else str(value), "number", bold)
    shown = str(value)
    return Cell(shown, "number" if _NUMBER.match(shown) else "text", bold)


def preview_of(
    content: bytes, sheet: str | None
) -> tuple[list[str], str, list[str], list[list[Cell]], str | None]:
    """The stored workbook's tabs and one sheet's header, rows and footnote (values only)."""
    book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        names = list(book.sheetnames)
        chosen = sheet if sheet in names else names[0]
        rows = list(book[chosen].iter_rows(values_only=True))
    finally:
        book.close()
    if not rows:
        return names, chosen, [], [], None
    header = ["" if v is None else str(v) for v in rows[0]]
    body = [list(r) for r in rows[1 : MAX_PREVIEW_ROWS + 1]]
    footnote: str | None = None
    filled = [[v for v in r if v not in (None, "")] for r in body]
    if len(body) >= 2 and not filled[-2] and len(filled[-1]) == 1:
        footnote = str(filled[-1][0])
        body = body[:-2]
    out = [
        [_cell(v, bold=str(r[0] or "").startswith("Total")) for v in r] for r in body
    ]  # a total row reads bold, as built
    return names, chosen, header, out, footnote


async def preview(ctx: AuthContext, artifact_id: UUID, sheet: str | None) -> Preview:
    row = cast(_Row, await _readable(ctx, artifact_id, "run_content.read"))
    names, chosen, columns, rows, footnote = preview_of(await _bytes(ctx, row), sheet)
    return Preview(row.id, row.name, names, chosen, columns, rows, footnote, row.sha256)


async def download(ctx: AuthContext, artifact_id: UUID) -> tuple[str, bytes]:
    """The stored bytes and one audit event (AC-R3)."""
    row = cast(_Row, await _readable(ctx, artifact_id, "run_artifact.download"))
    content = await _bytes(ctx, row)
    async with uow(ctx.tenant) as tx:
        tx.record(
            "run_artifact.downloaded",
            target=Target("agent_run", row.run_id),
            after=Ref(artifact=row.id, sha256=row.sha256),
        )
    return row.name, content


def drill_title(words: str, total: int) -> str:
    return f"{words} {total}"


async def drill(
    ctx: AuthContext, session_id: UUID, artifact_id: UUID, group_key: str, key_hash: str
) -> Drill:
    """AC-R4: the group's records as a `drill` item (code's table, no model call)."""
    row = cast(_Row, await _readable(ctx, artifact_id, "run_content.read"))
    if row.session_id != session_id:
        raise NotFound("run_artifact")  # an artifact of another session is not drilled here
    prefix, _, value = group_key.partition(":")
    source = _SOURCES.get(prefix)
    found = None if source is None else await source(ctx, row.name, value)
    if found is None:
        raise DrillGroupUnknown(facts={"group_key": group_key})
    words, rows = found
    title = drill_title(words, len(rows))
    payload: dict[str, object] = {
        "v": 1,
        "artifact_id": str(artifact_id),
        "group_key": group_key,
        "title": title,
        "rows": [
            {"ref_type": r.ref_type, "ref_id": str(r.ref_id), "href": r.href} for r in rows
        ],  # names are resolved again at read time (DEC-61): the item keeps references only
    }
    if not _WRITER:
        raise NotFound("session")  # workbench is not mounted: there is no session to append to
    item_id = await _WRITER[0](ctx, session_id, key_hash, payload)
    return Drill(item_id, group_key, title, len(rows), rows)


def drill_sources() -> Sequence[str]:
    return sorted(_SOURCES)


__all__ = [
    "XLSX",
    "Cell",
    "Drill",
    "DrillGroupUnknown",
    "DrillRow",
    "DrillSource",
    "Preview",
    "download",
    "drill",
    "drill_sources",
    "drill_title",
    "preview",
    "preview_of",
    "register_drill_source",
]
