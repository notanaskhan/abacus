"""A-06-T28: disclosure checklist templates as firm content (AGENTS 16; A-06 §4; DEC-2330).

A firm imports its checklist as CSV (`key, section, text`), parsed in the isolated child because
the file is hostile content. A dry run lists the problems and writes nothing. A person publishes a
version with fresh MFA (the matrix), and a published version never changes. Problems are codes
with where they are, never the cell's text. No checklist wording lives in code or a migration.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden

MAX_BYTES: Final = 2 * 1024 * 1024
MAX_ITEMS: Final = 1000
_KEY: Final = re.compile(r"[a-z0-9][a-z0-9_.-]{0,79}")
SUBJECT: Final = "disclosure_checklist_template"


class ChecklistRefused(DomainInvalid):
    code = "checklist_invalid"


class ChecklistPublished(DomainConflict):
    """A published version never changes."""

    code = "version_published"


@dataclass(frozen=True)
class Imported:
    template_id: UUID | None
    version: int | None
    dry_run: bool
    problems: tuple[str, ...]


@dataclass(frozen=True)
class Published:
    template_id: UUID
    version: int
    status: str
    published_at: object


def parse_items(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    """The items in file order and every problem found (run in the isolated child)."""
    if len(content) > MAX_BYTES:
        return [], ["too_large"]
    try:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    except (UnicodeDecodeError, csv.Error):
        return [], ["not_csv"]
    if not rows:
        return [], ["empty"]
    if len(rows) > MAX_ITEMS:
        return [], ["too_many_items"]
    items: list[dict[str, str]] = []
    problems: list[str] = []
    seen: set[str] = set()
    for n, row in enumerate(rows, start=2):
        key = (row.get("key") or "").strip()
        wording = (row.get("text") or "").strip()
        section = (row.get("section") or "").strip()
        if not _KEY.fullmatch(key):
            problems.append(f"row {n}: key")
        elif key in seen:
            problems.append(f"row {n}: duplicate_key")
        if not wording or len(wording) > 2000:
            problems.append(f"row {n}: text")
        if len(section) > 120:
            problems.append(f"row {n}: section")
        seen.add(key)
        items.append({"key": key, "section": section, "text": wording})
    return items, problems


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound(SUBJECT)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def import_checklist(
    ctx: AuthContext, name: str, framework_key: str, content: bytes, *, dry_run: bool
) -> Imported:
    _person(ctx, f"{SUBJECT}.import")
    try:
        items, problems = await asyncio.to_thread(run_isolated, parse_items, content)
    except IsolationFailed:
        raise ChecklistRefused(facts={"problems": 1}) from None
    if problems or dry_run:
        return Imported(None, None, dry_run, tuple(problems))
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"{SUBJECT}:{framework_key}:{name}"},
        )
        template_id = (
            await tx.session.execute(
                text(
                    "SELECT id FROM disclosure_checklist_templates "
                    "WHERE framework_key = :f AND name = :n"
                ),
                {"f": framework_key, "n": name},
            )
        ).scalar_one_or_none()
        if template_id is None:
            template_id = (
                await tx.session.execute(
                    text(
                        "INSERT INTO disclosure_checklist_templates (tenant_id, framework_key, "
                        "name, created_by) VALUES (:t, :f, :n, :by) RETURNING id"
                    ),
                    {"t": ctx.tenant_id, "f": framework_key, "n": name, "by": ctx.user_id},
                )
            ).scalar_one()
        version = (
            await tx.session.execute(
                text(
                    "SELECT coalesce(max(version), 0) + 1 FROM "
                    "disclosure_checklist_template_versions WHERE template_id = :t"
                ),
                {"t": template_id},
            )
        ).scalar_one()
        await tx.session.execute(
            text(
                "INSERT INTO disclosure_checklist_template_versions (tenant_id, template_id, "
                "version, items, source_file_sha256, imported_by) VALUES (:tenant, :t, :v, "
                "CAST(:items AS jsonb), :sha, :by)"
            ),
            {
                "tenant": ctx.tenant_id,
                "t": template_id,
                "v": version,
                "items": json.dumps(items),
                "sha": hashlib.sha256(content).hexdigest(),
                "by": ctx.user_id,
            },
        )
        tx.record(
            "disclosure_checklist_template.imported",
            target=Target("disclosure_checklist_template", template_id),
            after=Ref(version=int(version), items=len(items)),
        )
    return Imported(template_id, int(version), False, ())


async def publish_checklist(ctx: AuthContext, template_id: UUID, version: int) -> Published:
    _person(ctx, f"{SUBJECT}.publish")
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                text(
                    "SELECT id, status FROM disclosure_checklist_template_versions "
                    "WHERE template_id = :t AND version = :v FOR UPDATE"
                ),
                {"t": template_id, "v": version},
            )
        ).first()
        if row is None:
            raise NotFound("disclosure_checklist_template_version")
        if row.status == "published":
            raise ChecklistPublished(facts={"version": version})
        published_at = (
            await tx.session.execute(
                text(
                    "UPDATE disclosure_checklist_template_versions SET status = 'published', "
                    "published_by = :by, published_at = clock_timestamp() WHERE id = :id "
                    "RETURNING published_at"
                ),
                {"by": ctx.user_id, "id": row.id},
            )
        ).scalar_one()
        tx.record(
            "disclosure_checklist_template.published",
            target=Target("disclosure_checklist_template", template_id),
            after=Ref(version=version),
        )
    return Published(template_id, version, "published", published_at)


__all__ = [
    "ChecklistPublished",
    "ChecklistRefused",
    "Imported",
    "Published",
    "import_checklist",
    "parse_items",
    "publish_checklist",
]
