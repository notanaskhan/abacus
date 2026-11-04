"""N-04-T12: the notice response, part 1 (NOT-03; N-04 §3 US-5; DEC-2240).

- **Draft.** From the firm's published `notice_response` template (database content, C11), with
  typed variables by code (notice code, tax year, the analysis's figures, the position) and the
  partner's approval reference. Provisional before the `notice_position` decision.
- **Versions.** Insert-only `notice_response_versions` of blocks with their provenance
  (`template` or `human`) and the edit diff; the response row carries the current version.
- **Edits.** `PUT` blocks and settings (enclosures, payment method label, signers, channel,
  follow-up days, owner) against `If-Match` (409 `stale_version`); a sent response is locked
  (409 `response_locked`). An edit is a new version, so any sign-off over the old hash goes stale.
- **Regenerate** refreshes template blocks only; a human block stays as written.
- **Reviewable** `notice_response`: its facts refuse sign-off with `decision_pending` (no decided
  position), `position_mismatch` (drafted for another position) or `explanation_required` (a
  Disagree response with no human explanation block).
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.methodology.api import (
    ReportTemplateVersionView as TemplateVersionView,
)
from abacus.modules.methodology.api import (
    report_template_version,
    report_templates_in_firm,
)
from abacus.modules.notices.service import notice
from abacus.modules.reporting.api import template_blocks
from abacus.modules.review.api import Reviewable, ReviewableFacts

JsonRow = dict[str, Any]  # Any: JSON columns as stored

FAMILY: Final = "notice_response"
TARGET: Final = "notice_response"


class TemplateMissing(DomainConflict):
    """The firm has no published notice-response template."""

    code = "template_missing"


class ResponseExists(DomainConflict):
    """The notice already has a response draft."""

    code = "response_exists"


class StaleVersion(DomainConflict):
    """The response moved on since `If-Match`."""

    code = "stale_version"


class ResponseLocked(DomainConflict):
    """A sent response does not change."""

    code = "response_locked"


@dataclass(frozen=True)
class Block:
    key: str
    origin: str  # template or human
    template_block_key: str | None
    text: str
    edited: bool


@dataclass(frozen=True)
class Response:
    id: UUID
    notice_id: UUID
    template_key: str
    position_source: str
    version_no: int
    content_hash: str
    blocks: tuple[Block, ...]
    settings: JsonRow
    row_version: int
    locked: bool


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "notice_response"
    return (slug if slug[0].isalpha() else f"t_{slug}")[:60]


def content_hash(
    blocks: Sequence[JsonRow],
) -> str:
    body = json.dumps(
        [(b["key"], b["text"]) for b in blocks], separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


async def _variables(ctx: AuthContext, notice_id: UUID) -> dict[str, str]:
    """Typed variables by code: never a model's text."""
    found = await notice(ctx, notice_id)
    async with tenant_session(ctx.tenant) as session:
        analysis = (
            await session.execute(
                text(
                    "SELECT rows FROM notice_analyses WHERE work_item_id = :w "
                    "AND status = 'ready' ORDER BY version DESC LIMIT 1"
                ),
                {"w": notice_id},
            )
        ).scalar()
    values = {
        "notice_code": found.notice_code or "",
        "tax_year": "" if found.tax_year is None else str(found.tax_year),
        "position": found.position or "",
    }
    for row in cast(
        list[JsonRow],
        analysis or [],
    ):
        values[f"{row['key']}.irs"] = row["irs"]
        values[f"{row['key']}.difference"] = row["difference"]
    return values


async def _template(
    ctx: AuthContext,
) -> tuple[UUID, str, list[tuple[str, str | None, str]], TemplateVersionView]:
    published = [t for t in await report_templates_in_firm(ctx, FAMILY) if t.current_version]
    if not published:
        raise TemplateMissing
    chosen = published[0]
    view = await report_template_version(ctx, chosen.id, chosen.current_version or 1)
    return view.version_id, _slug(chosen.name), [], view


async def _template_texts(
    ctx: AuthContext, notice_id: UUID, view: TemplateVersionView
) -> list[JsonRow]:
    values = await _variables(ctx, notice_id)
    return [
        {"key": block_id, "origin": "template", "template_block_key": block_id, "text": body}
        for block_id, _clause, body in template_blocks(
            layout_key=view.layout_key, body=view.body, clauses=view.clauses, values=values
        )
    ]


async def _insert_version(
    tx: UnitOfWork,
    ctx: AuthContext,
    response_id: UUID,
    blocks: list[JsonRow],
    before: str | None,
) -> tuple[UUID, int, str]:
    digest = content_hash(blocks)
    version_no = int(
        (
            await tx.session.execute(
                text(
                    "SELECT coalesce(max(version_no), 0) + 1 FROM notice_response_versions "
                    "WHERE response_id = :r"
                ),
                {"r": response_id},
            )
        ).scalar_one()
    )
    after_text = "\n".join(b["text"] for b in blocks)
    diff = (
        None
        if before is None
        else list(difflib.unified_diff(before.splitlines(), after_text.splitlines(), lineterm=""))
    )
    version_id = (
        await tx.session.execute(
            text(
                "INSERT INTO notice_response_versions (tenant_id, response_id, version_no, "
                "blocks, content_hash, edit_diff, created_by, created_actor_kind) VALUES (:t, :r, "
                ":n, CAST(:blocks AS jsonb), :h, CAST(:diff AS jsonb), :by, :kind) RETURNING id"
            ),
            {
                "t": ctx.tenant_id,
                "r": response_id,
                "n": version_no,
                "blocks": json.dumps(blocks),
                "h": digest,
                "diff": None if diff is None else json.dumps(diff),
                "by": ctx.user_id if ctx.tenant.actor_kind == "human" else None,
                "kind": "human" if ctx.tenant.actor_kind == "human" else "system",
            },
        )
    ).scalar_one()
    await tx.session.execute(
        text(
            "UPDATE notice_responses SET current_version_id = :v, row_version = row_version + 1, "
            "updated_at = clock_timestamp() WHERE id = :r"
        ),
        {"v": version_id, "r": response_id},
    )
    return UUID(str(version_id)), version_no, digest


async def draft(ctx: AuthContext, notice_id: UUID) -> Response:
    """From the firm's template for the notice; provisional until the position is decided."""
    found = await notice(ctx, notice_id)
    if await _row(ctx.tenant, found.id) is not None:
        raise ResponseExists
    version_id, key, _, view = await _template(ctx)
    blocks = await _template_texts(ctx, found.id, view)
    async with uow(ctx.tenant) as tx:
        response_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO notice_responses (tenant_id, work_item_id, template_key, "
                    "template_version_id, position_source) VALUES (:t, :w, :k, :tv, :ps) "
                    "RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "w": found.id,
                    "k": key,
                    "tv": version_id,
                    "ps": "decided" if found.decision_id else "provisional",
                },
            )
        ).scalar_one()
        await _insert_version(tx, ctx, UUID(str(response_id)), blocks, None)
        tx.record(
            "notice_response.drafted",
            target=Target("notice", found.id),
            after=Ref(template_version=version_id),
        )
    return await response(ctx, notice_id)


async def _row(tenant: TenantContext, notice_id: UUID) -> JsonRow | None:
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT r.*, v.version_no, v.blocks, v.content_hash "
                        "FROM notice_responses r LEFT JOIN notice_response_versions v "
                        "ON v.id = r.current_version_id "
                        "WHERE r.work_item_id = :w"
                    ),
                    {"w": notice_id},
                )
            )
            .mappings()
            .first()
        )
    return dict(row) if row else None


def _view(row: JsonRow) -> Response:
    blocks = tuple(
        Block(
            b["key"], b["origin"], b.get("template_block_key"), b["text"], b["origin"] == "human"
        )
        for b in cast(
            list[JsonRow],
            row["blocks"] or [],
        )
    )
    settings = {
        k: row[k]
        for k in ("enclosures", "payment", "signer_contact_ids", "channel", "follow_up_days")
    } | {"owner_user_id": row["owner_user_id"]}
    return Response(
        row["id"],
        row["work_item_id"],
        row["template_key"],
        row["position_source"],
        row["version_no"] or 1,
        row["content_hash"] or "",
        blocks,
        settings,
        row["row_version"],
        row["envelope_id"] is not None,
    )


async def response(ctx: AuthContext, notice_id: UUID) -> Response:
    found = await notice(ctx, notice_id)
    row = await _row(ctx.tenant, found.id)
    if row is None:
        raise NotFound("notice_response")
    return _view(row)


# The settings a person may edit on a draft response (`PUT …/response`).
_SETTABLE: Final = ("signer_contact_ids", "channel", "follow_up_days", "owner_user_id")


async def edit(
    ctx: AuthContext,
    notice_id: UUID,
    if_match: int,
    *,
    blocks: Sequence[tuple[str, str]],
    settings: JsonRow,
) -> Response:
    """Blocks and settings against If-Match; an edited block becomes the person's."""
    current = await response(ctx, notice_id)
    if current.locked:
        raise ResponseLocked
    if current.row_version != if_match:
        raise StaleVersion(facts={"current": current.row_version})
    edits = dict(blocks)
    merged = [
        {
            "key": b.key,
            "origin": "human" if b.key in edits else b.origin,
            "template_block_key": b.template_block_key,
            "text": edits.get(b.key, b.text),
        }
        for b in current.blocks
    ]
    async with uow(ctx.tenant) as tx:
        if edits:
            await _insert_version(
                tx, ctx, current.id, merged, "\n".join(b.text for b in current.blocks)
            )
        sets = {k: v for k, v in settings.items() if v is not None and k in _SETTABLE}
        if sets:
            # One fixed statement, bound parameters (SQL-001); an absent setting keeps its value.
            await tx.session.execute(
                text(
                    "UPDATE notice_responses SET "
                    "signer_contact_ids = COALESCE(CAST(:signer_contact_ids AS uuid[]), "
                    "signer_contact_ids), channel = COALESCE(CAST(:channel AS text), channel), "
                    "follow_up_days = COALESCE(CAST(:follow_up_days AS integer), follow_up_days), "
                    "owner_user_id = COALESCE(CAST(:owner_user_id AS uuid), owner_user_id), "
                    "row_version = row_version + 1, updated_at = clock_timestamp() WHERE id = :id"
                ),
                {**dict.fromkeys(_SETTABLE), **sets, "id": current.id},
            )
        tx.record(
            "notice_response.edited",
            target=Target("notice", current.notice_id),
            after=Ref(blocks=len(edits), settings=len(sets)),
        )
    return await response(ctx, notice_id)


async def regenerate(ctx: AuthContext, notice_id: UUID, if_match: int) -> Response:
    """Template blocks re-rendered from current figures; human blocks kept as written."""
    current = await response(ctx, notice_id)
    if current.locked:
        raise ResponseLocked
    if current.row_version != if_match:
        raise StaleVersion(facts={"current": current.row_version})
    _, _, _, view = await _template(ctx)
    fresh = {b["key"]: b for b in await _template_texts(ctx, notice_id, view)}
    merged = [
        {
            "key": b.key,
            "origin": b.origin,
            "template_block_key": b.template_block_key,
            "text": b.text if b.origin == "human" else fresh.get(b.key, {"text": b.text})["text"],
        }
        for b in current.blocks
    ]
    async with uow(ctx.tenant) as tx:
        await _insert_version(
            tx, ctx, current.id, merged, "\n".join(b.text for b in current.blocks)
        )
        tx.record(
            "notice_response.regenerated",
            target=Target("notice", current.notice_id),
            after=Ref(kept=sum(1 for b in current.blocks if b.origin == "human")),
        )
    return await response(ctx, notice_id)


def blocked_code(
    position: str | None, drafted_for: str | None, blocks: Sequence[Block]
) -> str | None:
    """The sign-off refusal, in order: decision, position, explanation."""
    if position is None:
        return "decision_pending"
    if drafted_for is not None and drafted_for != position:
        return "position_mismatch"
    if position == "disagree" and not any(b.origin == "human" for b in blocks):
        return "explanation_required"
    return None


async def reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT r.id, n.notice_code, v.content_hash FROM notice_responses r "
                    "JOIN notices n ON n.work_item_id = r.work_item_id "
                    "JOIN notice_response_versions v ON v.id = r.current_version_id "
                    "WHERE n.engagement_id = :e"
                ),
                {"e": engagement_id},
            )
        ).all()
    return [
        Reviewable(TARGET, rid, f"RESP-{code or 'notice'}", "Notice response", digest, True)
        for rid, code, digest in rows
    ]


async def facts(tenant: TenantContext, response_id: UUID) -> ReviewableFacts | None:
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT r.id, n.engagement_id, n.position, r.position_source, "
                        "v.version_no, v.blocks, v.content_hash FROM notice_responses r "
                        "JOIN notices n ON n.work_item_id = r.work_item_id "
                        "JOIN notice_response_versions v ON v.id = r.current_version_id "
                        "WHERE r.id = :r"
                    ),
                    {"r": response_id},
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        return None
    blocks = [
        Block(b["key"], b["origin"], b.get("template_block_key"), b["text"], False)
        for b in row["blocks"]
    ]
    drafted_for = row["position"] if row["position_source"] == "decided" else None
    return ReviewableFacts(
        target_type=TARGET,
        target_id=row["id"],
        engagement_id=row["engagement_id"],
        content_hash=row["content_hash"],
        version_no=row["version_no"],
        preparer_user_ids=frozenset(),
        blocked_code=blocked_code(row["position"], drafted_for, blocks),
    )


async def _gate_row(tenant: TenantContext, work_item_id: UUID) -> JsonRow | None:
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT n.position, r.id AS response_id, r.envelope_id FROM notices n "
                        "LEFT JOIN notice_responses r ON r.work_item_id = n.work_item_id "
                        "WHERE n.work_item_id = :w"
                    ),
                    {"w": work_item_id},
                )
            )
            .mappings()
            .first()
        )
    return dict(row) if row else None


async def position_decided(tenant: TenantContext, work_item_id: UUID) -> bool:
    """Gate kind `notice_position_decision`: the signer decided the position."""
    row = await _gate_row(tenant, work_item_id)
    return row is not None and row["position"] is not None


async def signoff_ready(tenant: TenantContext, work_item_id: UUID) -> bool:
    """Gate kind `notice_response_signoff`: a response exists and nothing refuses its sign-off."""
    row = await _gate_row(tenant, work_item_id)
    if row is None or row["response_id"] is None:
        return False
    found = await facts(tenant, row["response_id"])
    return found is not None and found.blocked_code is None


async def send_ready(tenant: TenantContext, work_item_id: UUID) -> bool:
    """Gate kind `notice_response_send`: the response went out for signature."""
    row = await _gate_row(tenant, work_item_id)
    return row is not None and row["envelope_id"] is not None
