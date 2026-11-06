"""A-06-T25: the statements' note templates as firm content (AGENTS 16; A-06 §4; DEC-2389).

A firm imports its notes as CSV (`number, title, body, line_keys`), parsed in the isolated child
because the file is hostile content. `line_keys` names the FS lines that carry the note's
reference, semicolon-separated; a body may name a line's figure as `{{line.key}}`, which code fills
at draft time. A dry run lists the problems and writes nothing. A person publishes a version with
fresh MFA (the matrix), and a published version never changes. Problems are codes with where they
are, never the cell's text. No note wording lives in code or a migration.
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

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.methodology.disclosure_checklists import (
    ChecklistPublished,
    Imported,
    Published,
)

MAX_BYTES: Final = 2 * 1024 * 1024
MAX_NOTES: Final = 200
_LINE_KEY: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}")
_FIRST_NOTE: Final = 1
_LAST_NOTE: Final = 999
SUBJECT: Final = "statement_note_template"


class NoteTemplateRefused(DomainInvalid):
    code = "note_template_invalid"


@dataclass(frozen=True)
class PublishedNotes:
    version_id: UUID
    notes: tuple[dict[str, object], ...]


def parse_notes(content: bytes) -> tuple[list[dict[str, object]], list[str]]:
    """The notes in number order and every problem found (run in the isolated child)."""
    if len(content) > MAX_BYTES:
        return [], ["too_large"]
    try:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    except (UnicodeDecodeError, csv.Error):
        return [], ["not_csv"]
    if not rows:
        return [], ["empty"]
    if len(rows) > MAX_NOTES:
        return [], ["too_many_notes"]
    notes: list[dict[str, object]] = []
    problems: list[str] = []
    seen: set[int] = set()
    for n, row in enumerate(rows, start=2):
        raw = (row.get("number") or "").strip()
        number = int(raw) if raw.isdecimal() else 0
        title = (row.get("title") or "").strip()
        body = (row.get("body") or "").strip()
        keys = [k.strip() for k in (row.get("line_keys") or "").split(";") if k.strip()]
        if not _FIRST_NOTE <= number <= _LAST_NOTE:
            problems.append(f"row {n}: number")
        elif number in seen:
            problems.append(f"row {n}: duplicate_number")
        if not title or len(title) > 200:
            problems.append(f"row {n}: title")
        if len(body) > 20000:
            problems.append(f"row {n}: body")
        if not all(_LINE_KEY.fullmatch(k) for k in keys):
            problems.append(f"row {n}: line_keys")
        seen.add(number)
        notes.append({"number": number, "title": title, "body": body, "line_keys": keys})
    return sorted(notes, key=lambda note: int(str(note["number"]))), problems


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound(SUBJECT)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def import_notes(
    ctx: AuthContext, name: str, framework_key: str, content: bytes, *, dry_run: bool
) -> Imported:
    _person(ctx, f"{SUBJECT}.import")
    try:
        notes, problems = await asyncio.to_thread(run_isolated, parse_notes, content)
    except IsolationFailed:
        raise NoteTemplateRefused(facts={"problems": 1}) from None
    if problems or dry_run:
        return Imported(None, None, dry_run, tuple(problems))
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"{SUBJECT}:{framework_key}:{name}"},
        )
        template_id = await tx.session.scalar(
            text("SELECT id FROM statement_note_templates WHERE framework_key = :f AND name = :n"),
            {"f": framework_key, "n": name},
        )
        if template_id is None:
            template_id = await tx.session.scalar(
                text(
                    "INSERT INTO statement_note_templates (tenant_id, framework_key, name, "
                    "created_by) VALUES (:t, :f, :n, :by) RETURNING id"
                ),
                {"t": ctx.tenant_id, "f": framework_key, "n": name, "by": ctx.user_id},
            )
        version = await tx.session.scalar(
            text(
                "SELECT coalesce(max(version), 0) + 1 FROM statement_note_template_versions "
                "WHERE template_id = :t"
            ),
            {"t": template_id},
        )
        await tx.session.execute(
            text(
                "INSERT INTO statement_note_template_versions (tenant_id, template_id, version, "
                "notes, source_file_sha256, imported_by) VALUES (:tenant, :t, :v, "
                "CAST(:notes AS jsonb), :sha, :by)"
            ),
            {
                "tenant": ctx.tenant_id,
                "t": template_id,
                "v": version,
                "notes": json.dumps(notes),
                "sha": hashlib.sha256(content).hexdigest(),
                "by": ctx.user_id,
            },
        )
        tx.record(
            "statement_note_template.imported",
            target=Target(SUBJECT, template_id),
            after=Ref(version=int(version or 0), notes=len(notes)),
        )
    return Imported(template_id, int(version or 0), False, ())


async def publish_notes(ctx: AuthContext, template_id: UUID, version: int) -> Published:
    _person(ctx, f"{SUBJECT}.publish")
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                text(
                    "SELECT id, status FROM statement_note_template_versions "
                    "WHERE template_id = :t AND version = :v FOR UPDATE"
                ),
                {"t": template_id, "v": version},
            )
        ).first()
        if row is None:
            raise NotFound("statement_note_template_version")
        if row.status == "published":
            raise ChecklistPublished(facts={"version": version})
        published_at = await tx.session.scalar(
            text(
                "UPDATE statement_note_template_versions SET status = 'published', "
                "published_by = :by, published_at = clock_timestamp() WHERE id = :id "
                "RETURNING published_at"
            ),
            {"by": ctx.user_id, "id": row.id},
        )
        tx.record(
            "statement_note_template.published",
            target=Target(SUBJECT, template_id),
            after=Ref(version=version),
        )
    return Published(template_id, version, "published", published_at)


async def published_notes(tenant: TenantContext, framework_key: str) -> PublishedNotes | None:
    """The framework's most recently published notes; None when the firm has published none."""
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT v.id, v.notes FROM statement_note_template_versions v "
                    "JOIN statement_note_templates t ON t.id = v.template_id "
                    "WHERE t.framework_key = :f AND v.status = 'published' "
                    "ORDER BY v.published_at DESC, v.id LIMIT 1"
                ),
                {"f": framework_key},
            )
        ).first()
    return None if row is None else PublishedNotes(row.id, tuple(row.notes))


__all__ = [
    "MAX_BYTES",
    "NoteTemplateRefused",
    "PublishedNotes",
    "import_notes",
    "parse_notes",
    "publish_notes",
    "published_notes",
]
