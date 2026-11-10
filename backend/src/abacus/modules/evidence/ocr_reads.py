"""C4 v1.1's reads and the retry (P-11-T27; P-11 F7, F8; DEC-2417). PROTECTED.

The boxes code read, a statement page's tables, the regions a field match lights, and a person's
"Read text again". Every read goes through `visible_version`, so a walled or other-firm version
answers 404. A TIN box returns its mask token and never a value (P-03's logged reveal stays the
only way). Retry runs the gate first: a refusal is answered, and nothing is queued. The routes have
authorised the action and the flag.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.db import tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.uow import Target, uow
from abacus.modules.evidence.events import OcrRefusal
from abacus.modules.evidence.ocr_gate import ROUTE, first_refusal, record_run
from abacus.modules.evidence.ocr_step import API, REFUSAL_WORDS, gate_facts
from abacus.modules.evidence.viewer import visible_version
from abacus.modules.evidence.workflow_types import UploadInput
from abacus.modules.evidence.workflows import UploadProcessing
from abacus.modules.identity.api import AuthContext, Forbidden

VERSION: Final = "version"
JsonRow = dict[str, Any]  # Any: rows from the database
_FIELDS = text(
    "SELECT DISTINCT ON (field_key) field_key, label, value_type, value_text, last4, page_no, "
    "bbox, confidence, low_confidence, extractor_kind, ocr_run_id, form_type, tax_year, "
    "form_map_version FROM extracted_fields WHERE evidence_version_id = :v "
    "AND (CAST(:form AS text) IS NULL OR form_type = :form) "
    "AND (CAST(:key AS text) IS NULL OR field_key = :key) "
    "ORDER BY field_key, created_at DESC"
)
_TABLES = text(
    "SELECT id, page_no, bbox FROM extracted_tables WHERE evidence_version_id = :v "
    "AND (CAST(:page AS integer) IS NULL OR page_no = :page) ORDER BY page_no, created_at"
)
_CELLS = text(
    "SELECT table_id, row_no, col_no, text, bbox, confidence FROM extracted_table_cells "
    "WHERE table_id = ANY(:tables) ORDER BY table_id, row_no, col_no"
)


@dataclass(frozen=True)
class ReadBox:
    field_key: str
    label: str
    value_type: str
    value_text: str | None
    mask_token: str | None
    page: int
    bbox: tuple[float, float, float, float]
    confidence: float
    low_confidence: bool
    extractor_kind: str
    match_id: str


@dataclass(frozen=True)
class ReadFields:
    form_type: str | None
    tax_year: int | None
    corrected: bool
    form_map_version: str | None
    items: tuple[ReadBox, ...]


@dataclass(frozen=True)
class ReadCell:
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float


@dataclass(frozen=True)
class ReadTable:
    table_id: UUID
    page: int
    bbox: tuple[float, float, float, float]
    rows: tuple[tuple[ReadCell, ...], ...]


def field_match_id(version_id: UUID, field_key: str) -> str:
    return f"ev:{version_id}#field:{field_key}"


def _box(raw: Sequence[object]) -> tuple[float, float, float, float]:
    x, y, w, h = (float(str(v)) for v in raw)
    return (x, y, w, h)


def _kind(extractor: str, ocr_run_id: UUID | None) -> str:
    """The stored extractor as the contract's words: a form map over the text layer or over OCR,
    or the key-value read."""
    if extractor != "form_map":
        return "key_value"
    return "text_layer_map" if ocr_run_id is None else "ocr_map"


async def extracted_fields(
    ctx: AuthContext, version_id: UUID, form: str | None, key: str | None
) -> ReadFields:
    version = await visible_version(ctx, version_id)
    async with tenant_session(ctx.tenant) as session:
        result = await session.execute(_FIELDS, {"v": version.id, "form": form, "key": key})
        rows = cast(Sequence[JsonRow], result.mappings().all())
    if not rows:
        return ReadFields(None, None, False, None, ())
    items: list[ReadBox] = []
    for r in rows:
        tin = r["value_type"] == "tin"
        items.append(
            ReadBox(
                field_key=r["field_key"],
                label=r["label"],
                value_type=r["value_type"],
                value_text=None if tin else r["value_text"],
                mask_token=f"•••-••-{r['last4']}" if tin and r["last4"] else None,
                page=r["page_no"],
                bbox=_box(r["bbox"]),
                confidence=float(r["confidence"]),
                low_confidence=bool(r["low_confidence"]),
                extractor_kind=_kind(r["extractor_kind"], r["ocr_run_id"]),
                match_id=field_match_id(version.id, r["field_key"]),
            )
        )
    first = rows[0]
    corrected = any(
        r["field_key"].endswith(".corrected") and r["value_text"] in ("true", "yes", "X")
        for r in rows
    )
    return ReadFields(
        first["form_type"], first["tax_year"], corrected, first["form_map_version"], tuple(items)
    )


async def field_regions(
    ctx: AuthContext, version_id: UUID, match_ids: Sequence[str]
) -> list[tuple[str, int, list[float], str]]:
    """Field matches on this version: `(match_id, page, rect, label)`. Others are ignored; a TIN's
    box lights with its label but no value. The read passes `visible_version` again."""
    prefix = f"ev:{version_id}#field:"
    wanted = {m.removeprefix(prefix) for m in match_ids if m.startswith(prefix)}
    if not wanted:
        return []
    found = await extracted_fields(ctx, version_id, None, None)
    return [
        (f.match_id, f.page, list(f.bbox), f.label) for f in found.items if f.field_key in wanted
    ]


async def extracted_tables(
    ctx: AuthContext, version_id: UUID, page: int | None
) -> tuple[ReadTable, ...]:
    version = await visible_version(ctx, version_id)
    async with tenant_session(ctx.tenant) as session:
        found = await session.execute(_TABLES, {"v": version.id, "page": page})
        tables = cast(Sequence[JsonRow], found.mappings().all())
        ids = [t["id"] for t in tables]
        cells: Sequence[JsonRow] = []
        if ids:
            read = await session.execute(_CELLS, {"tables": ids})
            cells = cast(Sequence[JsonRow], read.mappings().all())
    rows_of: dict[UUID, dict[int, list[ReadCell]]] = {}
    for c in cells:
        rows_of.setdefault(c["table_id"], {}).setdefault(c["row_no"], []).append(
            ReadCell(c["text"], _box(c["bbox"]), float(c["confidence"]))
        )
    return tuple(
        ReadTable(
            t["id"],
            t["page_no"],
            _box(t["bbox"]),
            tuple(tuple(r) for _, r in sorted(rows_of.get(t["id"], {}).items())),
        )
        for t in tables
    )


async def retry_text(ctx: AuthContext, version_id: UUID) -> OcrRefusal | None:
    """A person's retry (INV-1: the matrix denies agents and workers, and this refuses any context
    but a person's). The gate runs first; refused, the run is recorded and nothing is queued."""
    if ctx.tenant.actor_kind != "human":
        raise Forbidden("evidence.ocr_retry", "role")
    version = await visible_version(ctx, version_id)
    facts = await gate_facts(ctx.tenant, version.engagement_id)
    refusal = await first_refusal(ctx.tenant, facts)
    if refusal is not None:
        await record_run(
            ctx.tenant,
            evidence_version_id=version.id,
            inbox_file_id=None,
            provider=ROUTE,
            api=API,
            pages=[],
            refused=refusal,
            synthetic_firm=facts.synthetic_firm,
            request_ids=[],
        )
        return REFUSAL_WORDS[refusal]
    async with uow(ctx.tenant) as tx:
        tx.record(
            "evidence_version.ocr_retry_requested", target=Target("evidence_version", version.id)
        )
    await dispatch(
        UploadProcessing,
        UploadInput(str(ctx.tenant.tenant_id), VERSION, str(version.id), announce=False),
        id=f"upload_ocr_retry:{ctx.tenant.tenant_id}:{version.id}",
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return None
