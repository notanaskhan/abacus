"""Engagement template drafts and their components (K-03-T17; TASK-9010; K-03 F2; KNW-06 a, b;
DEC-6016; amber).

- **Draft** (`create_draft`, `POST /v1/engagement-templates/{id}/versions`, `template.edit`, the
  quality owner): a new `draft` version based on a published one (409 `not_published` from a
  draft), the template's one draft (409 `draft_exists`; 0010's partial unique index holds it too),
  with every component of the base copied so the draft starts as the base reads.
- **Components** (`component`, `save_component`): one component kind's rows as a JSON body,
  `{"rows": […]}` (a nested kind carries its children: a sheet its `columns` and `views`, a column
  its `agent` definition; a form its `fields`); `program` is the version's methodology pin. A save
  replaces the kind's rows at the ETag the editor saw (`If-Match` the draft's `draft_etag`; 412
  `precondition_failed` when it moved), only on a draft (409 `not_draft`; 1010's trigger freezes a
  published version's components too), and writes one `template_version.component_changed` audit
  event naming the kind and the new ETag, as the person who saved.
- **Comments**: `template_version` is a comment anchor (C-29) for KNW-06's threads, registered
  by workpapers over `version_label` (methodology imports no host).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast
from uuid import UUID, uuid4

from sqlalchemy import Row, text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, DomainPreconditionFailed, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise

TARGET: Final = "template_version"


class DraftExists(DomainConflict):
    code = "draft_exists"


class NotDraft(DomainConflict):
    code = "not_draft"


class NotPublished(DomainConflict):
    code = "not_published"


class ComponentInvalid(DomainInvalid):
    code = "component_invalid"


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[str, ...]
    parent: str | None = None  # the column naming the parent row
    children: tuple[tuple[str, Table], ...] = ()  # (body key, child table)
    json_columns: frozenset[str] = frozenset()


_AGENT = Table(
    "template_agent_column_defs",
    ("instruction_doc", "output_type", "options", "runs_as_capability", "skill_key",
     "default_scope"),
    parent="sheet_column_id", json_columns=frozenset({"instruction_doc", "options"}),
)  # fmt: skip
_COLUMNS = Table(
    "template_sheet_columns",
    ("column_key", "name", "description", "type", "config", "required", "default_value",
     "validation", "client_visible", "classification", "classification_reason", "source_binding",
     "position"),
    parent="sheet_definition_id", children=(("agent", _AGENT),),
    json_columns=frozenset({"config", "default_value", "validation", "source_binding"}),
)  # fmt: skip
_VIEWS = Table(
    "template_sheet_views",
    ("view_key", "name", "filters", "sort", "visible_columns", "group_by", "position"),
    parent="sheet_definition_id",
    json_columns=frozenset({"filters", "sort"}),
)
KINDS: Final[dict[str, Table]] = {
    "sheets": Table(
        "template_sheet_definitions",
        ("sheet_key", "title", "step_key", "row_source", "sections", "position"),
        children=(("columns", _COLUMNS), ("views", _VIEWS)),
        json_columns=frozenset({"sections"}),
    ),
    "forms": Table(
        "template_forms",
        ("form_key", "title", "position"),
        children=(
            (
                "fields",
                Table(
                    "template_form_fields",
                    (
                        "field_key",
                        "label",
                        "type",
                        "config",
                        "required",
                        "classification",
                        "position",
                    ),
                    parent="form_id",
                    json_columns=frozenset({"config"}),
                ),
            ),
        ),
    ),
    "scoping_rules": Table(
        "scoping_rules",
        ("position", "label", "group_op", "conditions", "effect", "target_kind", "target_ref"),
        json_columns=frozenset({"conditions"}),
    ),
    "request_list": Table(
        "template_requests",
        (
            "request_key",
            "methodology_request_item_id",
            "step_key",
            "group_key",
            "title",
            "shown_by_rule_id",
            "position",
        ),
    ),
    "triggers": Table(
        "template_trigger_defaults",
        ("event", "capability_key", "target_ref", "condition_value", "enabled"),
        json_columns=frozenset({"condition_value"}),
    ),
    "report_templates": Table(
        "template_report_template_refs",
        ("report_template_id", "report_template_version_id", "role"),
    ),
    "skills": Table("template_skill_pins", ("skill_key", "skill_version_id")),
}


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


_VERSION: Final = text(
    "SELECT v.id, v.template_id, v.seq, v.label, v.status, v.draft_etag, "
    "v.methodology_version_id FROM template_versions v WHERE v.id = :v"
)


async def _version(ctx: AuthContext, version_id: UUID, action: str) -> Row[Any]:
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_VERSION, {"v": version_id})).first()
    if row is None:
        raise NotFound(TARGET)
    return row


def _bound(table: Table, column: str, value: object) -> object:
    """A reference column's text is a UUID (asyncpg binds a uuid, never a str)."""
    if column.endswith("_id") and isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            raise ComponentInvalid(facts={"table": table.name}) from None
    return value


# --- reading a component -------------------------------------------------------------------------


def _cell(table: Table, column: str, value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    return value


async def _rows(
    session: object, table: Table, where: str, value: object
) -> list[dict[str, object]]:
    from sqlalchemy.ext.asyncio import AsyncSession

    s = cast(AsyncSession, session)
    cols = ", ".join(("id", *table.columns))
    order = "position, id" if "position" in table.columns else "id"
    found = (
        await s.execute(
            text(f"SELECT {cols} FROM {table.name} WHERE {where} = :x ORDER BY {order}"),  # noqa: S608 -- fixed table and column names
            {"x": value},
        )
    ).mappings()
    out: list[dict[str, object]] = []
    for r in found:
        row = {c: _cell(table, c, r[c]) for c in table.columns}
        for key, child in table.children:
            kids = await _rows(s, child, cast(str, child.parent), r["id"])
            row[key] = kids[0] if key == "agent" else kids  # a column has at most one agent
            if key == "agent" and not kids:
                row[key] = None
        out.append(row)
    return out


async def component(
    ctx: AuthContext, version_id: UUID, kind: str
) -> tuple[int, dict[str, object]]:
    """The kind's body and the draft's ETag (`draft_etag`; a published version's stays put)."""
    row = await _version(ctx, version_id, "template.read")
    if kind == "program":
        return int(row.draft_etag), {
            "methodology_version_id": None
            if row.methodology_version_id is None
            else str(row.methodology_version_id)
        }
    table = KINDS.get(kind)
    if table is None:
        raise NotFound("component")
    async with tenant_session(ctx.tenant) as session:
        rows = await _rows(session, table, "template_version_id", version_id)
    return int(row.draft_etag), {"rows": rows}


# --- writing a component -------------------------------------------------------------------------


def _checked(table: Table, raw: object) -> list[dict[str, object]]:
    if not isinstance(raw, list) or len(cast(list[object], raw)) > 500:
        raise ComponentInvalid(facts={"table": table.name})
    out: list[dict[str, object]] = []
    allowed = set(table.columns) | {k for k, _ in table.children}
    for item in cast(list[object], raw):
        if not isinstance(item, dict):
            raise ComponentInvalid(facts={"table": table.name})
        row = cast(dict[str, object], item)
        unknown = sorted(set(row) - allowed)
        if unknown:
            raise ComponentInvalid(facts={"table": table.name, "unknown": len(unknown)})
        out.append(row)
    return out


async def _insert(
    tx: UnitOfWork,
    ctx: AuthContext,
    table: Table,
    version_id: UUID,
    rows: Sequence[Mapping[str, object]],
    parent_id: UUID | None = None,
) -> int:
    written = 0
    for row in rows:
        new_id = uuid4()
        values: dict[str, object] = {"id": new_id, "t": ctx.tenant_id, "v": version_id}
        cols = ["id", "tenant_id", "template_version_id"]
        params = [":id", ":t", ":v"]
        if table.parent is not None:
            cols.append(table.parent)
            params.append(":parent")
            values["parent"] = parent_id
        for c in table.columns:
            if c not in row:
                continue
            cols.append(c)
            if c in table.json_columns:
                params.append(f"CAST(:{c} AS jsonb)")
                values[c] = json.dumps(row[c])
            else:
                params.append(f":{c}")
                values[c] = _bound(table, c, row[c])
        await tx.session.execute(
            text(f"INSERT INTO {table.name} ({', '.join(cols)}) VALUES ({', '.join(params)})"),  # noqa: S608 -- fixed names; values are bound
            values,
        )
        written += 1
        for key, child in table.children:
            kids = row.get(key)
            if key == "agent":
                kids = [] if kids is None else [kids]
            written += await _insert(
                tx, ctx, child, version_id, _checked(child, kids or []), new_id
            )
    return written


async def _clear(tx: UnitOfWork, table: Table, version_id: UUID) -> None:
    for _key, child in table.children:  # children first (their foreign keys)
        await _clear(tx, child, version_id)
    await tx.session.execute(
        text(f"DELETE FROM {table.name} WHERE template_version_id = :v"),  # noqa: S608 -- a fixed name
        {"v": version_id},
    )


_BUMP: Final = text(
    "UPDATE template_versions SET draft_etag = draft_etag + 1 WHERE id = :v AND status = 'draft' "
    "AND draft_etag = :seen RETURNING draft_etag"
)
_PIN: Final = text(
    "UPDATE template_versions SET methodology_version_id = CAST(:m AS uuid), "
    "draft_etag = draft_etag + 1 WHERE id = :v AND status = 'draft' AND draft_etag = :seen "
    "RETURNING draft_etag"
)


def etag_of(if_match: str) -> int:
    raw = if_match.strip().removeprefix("W/").strip('"')
    if not raw.isdigit():
        raise DomainPreconditionFailed(facts={"etag": 0})
    return int(raw)


async def save_component(
    ctx: AuthContext, version_id: UUID, kind: str, body: Mapping[str, object], if_match: str
) -> tuple[int, dict[str, object]]:
    _human(ctx, "template.edit")
    row = await _version(ctx, version_id, "template.edit")
    if row.status != "draft":
        raise NotDraft(facts={"status": str(row.status)})
    seen = etag_of(if_match)
    if seen != int(row.draft_etag):
        raise DomainPreconditionFailed(facts={"etag": int(row.draft_etag)})
    async with uow(ctx.tenant) as tx:
        if kind == "program":
            pin = body.get("methodology_version_id")
            etag = await tx.session.scalar(_PIN, {"m": pin, "v": version_id, "seen": seen})
            written = 1
        else:
            table = KINDS.get(kind)
            if table is None:
                raise NotFound("component")
            rows = _checked(table, body.get("rows"))
            etag = await tx.session.scalar(_BUMP, {"v": version_id, "seen": seen})
            if etag is not None:
                await _clear(tx, table, version_id)
                written = await _insert(tx, ctx, table, version_id, rows)
            else:
                written = 0
        if etag is None:  # another save landed between the read and the write
            raise DomainPreconditionFailed(facts={"etag": int(row.draft_etag) + 1})
        tx.record(
            "template_version.component_changed",
            target=Target(TARGET, version_id),
            after=Ref(kind_rows=written, etag=int(etag)),
        )
    return await component(ctx, version_id, kind)


# --- a new draft ---------------------------------------------------------------------------------

_DRAFT_OF: Final = text(
    "SELECT id FROM template_versions WHERE template_id = :t AND status = 'draft'"
)
_NEXT_SEQ: Final = text(
    "SELECT coalesce(max(seq), 0) + 1 FROM template_versions WHERE template_id = :t"
)
_NEW: Final = text(
    "INSERT INTO template_versions (id, tenant_id, template_id, seq, label, status, "
    "methodology_version_id, based_on_version_id, created_by) VALUES (:id, :tenant, :t, :seq, "
    ":label, 'draft', :m, :base, :by)"
)


def next_label(label: str, seq: int) -> str:
    """ "FS v5" based on a published version answers "FS v6" (the trailing number moves)."""
    found = re.match(r"^(.*?)(\d+)\s*$", label)
    stem = found.group(1) if found else f"{label} v"
    return f"{stem}{seq}"[:40]


async def create_draft(ctx: AuthContext, template_id: UUID, from_version_id: UUID) -> UUID:
    _human(ctx, "template.edit")
    base = await _version(ctx, from_version_id, "template.edit")
    if base.template_id != template_id:
        raise NotFound(TARGET)
    if base.status != "published":
        raise NotPublished(facts={"status": str(base.status)})
    async with tenant_session(ctx.tenant) as session:
        if await session.scalar(_DRAFT_OF, {"t": template_id}) is not None:
            raise DraftExists(facts={"template": str(template_id)})
        seq = int(await session.scalar(_NEXT_SEQ, {"t": template_id}) or 1)
        copies = {
            kind: await _rows(session, table, "template_version_id", from_version_id)
            for kind, table in KINDS.items()
        }
    draft_id = uuid4()
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _NEW,
            {"id": draft_id, "tenant": ctx.tenant_id, "t": template_id, "seq": seq,
             "label": next_label(str(base.label), seq), "m": base.methodology_version_id,
             "base": from_version_id, "by": ctx.user_id},
        )  # fmt: skip
        for kind, table in KINDS.items():
            if kind == "request_list":  # a rule id points into the base: rules copy first
                continue
            await _insert(tx, ctx, table, draft_id, _strip_rule_refs(copies[kind]))
        await _insert(tx, ctx, KINDS["request_list"], draft_id,
                      _strip_rule_refs(copies["request_list"]))  # fmt: skip
        tx.record(
            "template_version.drafted",
            target=Target(TARGET, draft_id),
            after=Ref(template=template_id, based_on=from_version_id, seq=seq),
        )
    return draft_id


def _strip_rule_refs(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """A copied request's `shown_by_rule_id` named the base's rule; the draft's scoping rules
    are new rows (their ids differ), so the link is re-made by the rules editor (K-03-T18)."""
    return [{k: v for k, v in r.items() if k != "shown_by_rule_id"} for r in rows]


async def version_label(ctx: AuthContext, version_id: UUID) -> str | None:
    """A template version's label ("FS v6"), for the `template_version` comment anchor
    (workpapers registers it: methodology imports no host, DEC-6016); None when absent."""
    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(
            text("SELECT label FROM template_versions WHERE id = :v"), {"v": version_id}
        )
    return None if found is None else str(found)


__all__ = [
    "KINDS",
    "ComponentInvalid",
    "DraftExists",
    "NotDraft",
    "NotPublished",
    "component",
    "create_draft",
    "etag_of",
    "next_label",
    "save_component",
    "version_label",
]
