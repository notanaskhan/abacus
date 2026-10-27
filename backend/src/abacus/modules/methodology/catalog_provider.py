"""Methodology's own catalog providers (K-01-T03; KNW-01; DEC-571): methodology versions and PBC
templates.

A template with a `family` (EBP, FS, SSARS) is Methodology; one without is a PBC template
(Templates). Cards, by the counting rule (AC1.4):
- every `published` version is a Published card and every `superseded` one a Superseded card
  ("Kept for engagements archived under it");
- a template with neither has one Draft card: its newest `draft`, `parsing` or `needs_review`
  version, shown only to people who manage or approve content (AC1.6);
- a draft under a published card is not a card: it is a review-queue row; `discarded` is nothing.

Methodology content is firm-wide (no engagement, so no wall applies to it); its usage count is
the engagements module's, over `visible()` (INV-3). Firm content stays in the database: nothing
here is a constant (rule 16).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import func, select

from abacus.kernel.db import tenant_session
from abacus.modules.methodology.catalog import (
    CatalogItem,
    CatalogProvider,
    ChangeEntry,
    ReviewItem,
    Viewer,
    register_catalog_provider,
)
from abacus.modules.methodology.models import (
    MethodologyArea,
    MethodologyRequestItem,
    MethodologyTemplate,
    MethodologyVersion,
    MethodologyVersionEvent,
    MethodologyVersionState,
    Program,
    ProgramStep,
)

USAGE_TYPE: Final = "methodology_version"
_FAMILY: Final = {"ebp": "EBP", "fs": "FS", "ssars": "SSARS"}
_PENDING: Final = frozenset({"draft", "parsing", "needs_review"})
_SHOWN: Final = frozenset({"published", "superseded"})
_EVENT_KINDS: Final = frozenset(
    {
        "legacy_backfilled",
        "imported",
        "published",
        "draft_created",
        "submitted",
        "approved",
        "superseded",
        "discarded",
        "standards_mapped",
        "exported",
    }
)


def _category(family: str | None) -> str:
    return "methodology" if family is not None else "pbc_templates"


def _route(category: str, version_id: UUID, status: str) -> str:
    """KNW-03 (first program) for a published methodology, KNW-02 for one in review; KNW-05 for
    a PBC template. Planned targets are the frontend's to hide (AC1.8)."""
    if category == "pbc_templates":
        return f"/knowledge/templates/{version_id}"
    if status in _SHOWN:
        return f"/knowledge/methodology/{version_id}/programs"
    return f"/knowledge/methodology/{version_id}"


async def _rows(
    viewer: Viewer,
) -> Sequence[tuple[MethodologyTemplate, MethodologyVersion, MethodologyVersionState]]:
    async with tenant_session(viewer.ctx.tenant) as session:
        found = await session.execute(
            select(MethodologyTemplate, MethodologyVersion, MethodologyVersionState)
            .join(MethodologyVersion, MethodologyVersion.template_id == MethodologyTemplate.id)
            .join(
                MethodologyVersionState,
                MethodologyVersionState.version_id == MethodologyVersion.id,
            )
            .order_by(MethodologyTemplate.name, MethodologyVersion.version)
        )
        return [(t, v, s) for t, v, s in found.tuples().all()]


async def _details(
    viewer: Viewer, version_ids: Sequence[UUID]
) -> tuple[dict[UUID, int], dict[UUID, tuple[str, ...]]]:
    """Request counts, and area and program names per version (the subtitle and what search
    also finds)."""
    if not version_ids:
        return {}, {}
    async with tenant_session(viewer.ctx.tenant) as session:
        counts = dict(
            (
                await session.execute(
                    select(MethodologyRequestItem.version_id, func.count())
                    .where(MethodologyRequestItem.version_id.in_(list(version_ids)))
                    .group_by(MethodologyRequestItem.version_id)
                )
            )
            .tuples()
            .all()
        )
        areas: dict[UUID, list[str]] = {}
        for version_id, name in (
            await session.execute(
                select(MethodologyArea.version_id, MethodologyArea.name)
                .where(MethodologyArea.version_id.in_(list(version_ids)))
                .order_by(MethodologyArea.version_id, MethodologyArea.position)
            )
        ).tuples():
            areas.setdefault(version_id, []).append(name)
        for version_id, name in (
            await session.execute(
                select(Program.version_id, Program.name)
                .where(Program.version_id.in_(list(version_ids)))
                .order_by(Program.version_id, Program.position)
            )
        ).tuples():
            areas.setdefault(version_id, []).append(name)
    return {k: int(v) for k, v in counts.items()}, {k: tuple(v) for k, v in areas.items()}


def _subtitle(family: str | None, requests: int) -> str:
    counted = f"{requests} request" + ("" if requests == 1 else "s")
    return f"{_FAMILY[family]} · {counted}" if family in _FAMILY else counted


async def _items(viewer: Viewer, category: str) -> list[CatalogItem]:
    rows = [r for r in await _rows(viewer) if _category(r[0].family) == category]
    chosen: list[tuple[MethodologyTemplate, MethodologyVersion, MethodologyVersionState, str]] = []
    by_template: dict[
        UUID, list[tuple[MethodologyTemplate, MethodologyVersion, MethodologyVersionState]]
    ] = {}
    for row in rows:
        by_template.setdefault(row[0].id, []).append(row)
    for versions in by_template.values():
        shown = [r for r in versions if r[2].status in _SHOWN]
        if shown:
            chosen += [(t, v, s, s.status) for t, v, s in shown]
            continue
        pending = [r for r in versions if r[2].status in _PENDING]
        if pending and viewer.sees_drafts:
            t, v, s = max(pending, key=lambda r: r[1].version)
            chosen.append((t, v, s, "draft"))
    requests, areas = await _details(viewer, [v.id for _t, v, _s, _c in chosen])
    return [
        CatalogItem(
            id=v.id,
            category=category,
            title=t.name,
            subtitle=_subtitle(t.family, requests.get(v.id, 0)),
            status=card,
            version_label=v.label,
            effective_from=s.effective_from if card != "draft" else None,
            owner_user_id=s.approved_by or v.imported_by,
            updated_at=s.updated_at,
            route=_route(category, v.id, s.status),
            usage=(USAGE_TYPE, v.id) if card != "draft" else None,
            keywords=areas.get(v.id, ()),
        )
        for t, v, s, card in chosen
    ]


async def _flags_open(viewer: Viewer, version_ids: Sequence[UUID]) -> dict[UUID, int]:
    """Steps with a parse flag nobody resolved yet, per version (KNW-02's flags)."""
    if not version_ids:
        return {}
    async with tenant_session(viewer.ctx.tenant) as session:
        rows = await session.execute(
            select(ProgramStep.version_id, func.count())
            .where(
                ProgramStep.version_id.in_(list(version_ids)),
                ProgramStep.parse_flag.is_not(None),
                ProgramStep.flag_resolution.is_(None),
            )
            .group_by(ProgramStep.version_id)
        )
        return {v: int(n) for v, n in rows.tuples().all()}


async def _queue(viewer: Viewer, category: str) -> list[ReviewItem]:
    """Versions in review the viewer may approve, and the viewer's own drafts and imports in
    progress, including drafts under a published card (AC1.4)."""
    me = viewer.ctx.user_id
    waiting = [
        (t, v, s)
        for t, v, s in await _rows(viewer)
        if _category(t.family) == category
        and s.status in _PENDING
        and ((s.status == "needs_review" and viewer.approves) or v.imported_by == me)
    ]
    flags = await _flags_open(viewer, [v.id for _t, v, _s in waiting])
    return [
        ReviewItem(
            category=category,
            object_id=v.id,
            title=t.name,
            version_label=v.label,
            status=s.status,
            submitted_by=v.imported_by,
            submitted_at=v.created_at,
            flags_open=flags.get(v.id, 0),
            route=_route(category, v.id, s.status),
        )
        for t, v, s in waiting
    ]


def _facts(raw: object) -> dict[str, str | int | bool | None]:
    """Codes, ids and counts only: anything else in an event's facts is left out."""
    if not isinstance(raw, dict):
        return {}
    kept: dict[str, str | int | bool | None] = {}
    for key, value in raw.items():  # pyright: ignore[reportUnknownVariableType]
        if isinstance(key, str) and (value is None or isinstance(value, str | int | bool)):
            kept[key] = value if not isinstance(value, str) else value[:80]
    return kept


async def _changes(viewer: Viewer, category: str) -> list[ChangeEntry]:
    """The version events of this category's versions; a reader who can't see drafts sees only
    the events of versions that are published or superseded now."""
    async with tenant_session(viewer.ctx.tenant) as session:
        found = (
            (
                await session.execute(
                    select(
                        MethodologyVersionEvent,
                        MethodologyTemplate.name,
                        MethodologyTemplate.family,
                        MethodologyVersion.label,
                        MethodologyVersionState.status,
                    )
                    .join(
                        MethodologyVersion,
                        MethodologyVersion.id == MethodologyVersionEvent.version_id,
                    )
                    .join(
                        MethodologyTemplate,
                        MethodologyTemplate.id == MethodologyVersion.template_id,
                    )
                    .join(
                        MethodologyVersionState,
                        MethodologyVersionState.version_id == MethodologyVersion.id,
                    )
                    .order_by(MethodologyVersionEvent.at, MethodologyVersionEvent.seq)
                )
            )
            .tuples()
            .all()
        )
    return [
        ChangeEntry(
            id=e.id,
            at=e.at,
            seq=e.seq,
            category=category,
            object_id=e.version_id,
            title=f"{name} · {label}",
            kind=e.kind,
            actor_kind=e.actor_kind,
            actor_user_id=e.actor_user_id,
            on_behalf_of_user_id=e.on_behalf_of_user_id,
            facts=_facts(e.facts),
        )
        for e, name, family, label, status in found
        if _category(family) == category
        and e.kind in _EVENT_KINDS
        and (viewer.sees_drafts or status in _SHOWN)
    ]


async def methodology_items(viewer: Viewer) -> list[CatalogItem]:
    return await _items(viewer, "methodology")


async def methodology_queue(viewer: Viewer) -> list[ReviewItem]:
    return await _queue(viewer, "methodology")


async def methodology_changes(viewer: Viewer) -> list[ChangeEntry]:
    return await _changes(viewer, "methodology")


async def template_items(viewer: Viewer) -> list[CatalogItem]:
    return await _items(viewer, "pbc_templates")


async def template_queue(viewer: Viewer) -> list[ReviewItem]:
    return await _queue(viewer, "pbc_templates")


async def template_changes(viewer: Viewer) -> list[ChangeEntry]:
    return await _changes(viewer, "pbc_templates")


def register_methodology_providers() -> None:
    register_catalog_provider(
        "methodology", CatalogProvider(methodology_items, methodology_queue, methodology_changes)
    )
    register_catalog_provider(
        "pbc_templates", CatalogProvider(template_items, template_queue, template_changes)
    )


__all__ = ["USAGE_TYPE", "register_methodology_providers"]
