"""C4 v1.1, the OCR and box-extraction stub (P-11-T19; P-11 §4.3, F7, F8, F10; DEC-2204).
Contract: `docs/contracts/c04-citations-viewer.md` §"v1.1 additive"; consumers NOT-01 b to d
(N-04), TAX-03 a (T-04), INB-02 g (N-01), SHL-08, CLS-05.

Additive to C4 v1: the viewer manifest's pages gain `text_source` and `ocr` facts (in
`trust_contract.py`); these routes add the boxes code read from a known form (`…/fields`), the
tables of a statement page (`…/tables`) and a person's "Read text again" after a cleared refusal
(`…/text/retry`). Code reads every value with its page, box and confidence; a model never does
(ADR-050). A field below 0.90 confidence is `low_confidence` and stored as read; a TIN box
returns its mask token only (reveal stays P-03's logged route). Text is hostile client content
(ADR-052): it never reaches logs or events.

Every route answers, in order: a client principal 404 (INV-4); the matrix action at the firm (the
service narrows to the version with `visible()`, or the inbox preview's `evidence.upload` for an
unfiled file); 404 with its flag off (`evidence.form_extraction` for fields and tables,
`evidence.ocr` for retry); 501 until P-11-T22 onward.
"""

from __future__ import annotations

from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import EVIDENCE_FORM_EXTRACTION, EVIDENCE_OCR
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled, flag_variant
from abacus.modules.evidence.events import OcrRefusal
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
VersionId = Annotated[UUID, Path()]
Internal = classified("internal")
Confidence = Annotated[float, Field(ge=0, le=1), Internal]
LOW_CONFIDENCE: float = 0.90

ValueType = Literal["money", "date", "text", "code", "checkbox", "tin"]
ExtractorKind = Literal["text_layer_map", "ocr_map", "key_value"]


class BoxOut(BaseModel):
    """A rectangle in page points (the viewer's grammar)."""

    model_config = ConfigDict(frozen=True)

    x: Annotated[float, Internal]
    y: Annotated[float, Internal]
    w: Annotated[float, Field(ge=0), Internal]
    h: Annotated[float, Field(ge=0), Internal]


class ExtractedFieldOut(BaseModel):
    """One box: `match_id` is `ev:<version>#field:<key>`, which SHL-08's regions accept. A TIN
    box carries `mask_token` ("•••-••-6081") and never `value_text`."""

    model_config = ConfigDict(frozen=True)

    field_key: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.]{0,79}$"), Internal]
    label: Annotated[str, Internal]  # "Form W-2 · box 1"
    value_type: Annotated[ValueType, Internal]
    value_text: Annotated[str | None, classified("restricted", tri=True)] = None
    mask_token: Annotated[str | None, classified("confidential")] = None
    page: Annotated[int, Field(ge=1), Internal]
    bbox: Annotated[BoxOut, Internal]
    confidence: Confidence
    low_confidence: Annotated[bool, Internal]
    extractor_kind: Annotated[ExtractorKind, Internal]
    match_id: Annotated[str, Internal]


class ExtractedFieldsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    form_type: Annotated[str | None, Internal] = None  # null: unsupported form or year
    tax_year: Annotated[int | None, Internal] = None
    corrected: Annotated[bool, Internal] = False  # 1099 "CORRECTED" checked (INB-02 g)
    form_map_version: Annotated[str | None, Internal] = None
    items: Annotated[list[ExtractedFieldOut], classified("restricted", tri=True)]


class TableCellOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: Annotated[str, classified("restricted")]
    bbox: Annotated[BoxOut, Internal]
    confidence: Confidence


class ExtractedTableOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_id: Annotated[UUID, Internal]
    page: Annotated[int, Field(ge=1), Internal]
    bbox: Annotated[BoxOut, Internal]
    rows: Annotated[list[list[TableCellOut]], classified("restricted")]


class ExtractedTablesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ExtractedTableOut], classified("restricted")]


class TextRetryOut(BaseModel):
    """`queued`, or `refused` with the first failing gate's reason (never retried by itself)."""

    model_config = ConfigDict(frozen=True)

    status: Annotated[Literal["queued", "refused"], Internal]
    reason: Annotated[OcrRefusal | None, Internal] = None


async def _gate(ctx: AuthContext, action: str, gate: Flag) -> None:
    if ctx.client:
        raise NotFound("evidence_version")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if gate is EVIDENCE_FORM_EXTRACTION:
        if await flag_variant(ctx.tenant, gate) == "off":
            raise NotFound(gate.name)
    elif not await flag_enabled(ctx.tenant, gate):
        raise NotFound(gate.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


ocr_router = AbacusRouter(prefix="/v1", tags=["trust kit"])
_V = "/evidence-versions/{version_id}"


@ocr_router.get(
    f"{_V}/fields", action="evidence.read", response_model=ExtractedFieldsOut, errors=(501,)
)
async def extracted_fields_route(
    version_id: VersionId,
    ctx: Ctx,
    form: Annotated[str | None, Query(max_length=40)] = None,
    key: Annotated[str | None, Query(max_length=80)] = None,
) -> ExtractedFieldsOut:
    """The boxes code read; an unsupported form or year answers no items (manual entry)."""
    await _gate(ctx, "evidence.read", EVIDENCE_FORM_EXTRACTION)
    _not_yet()


@ocr_router.get(
    f"{_V}/tables", action="evidence.read", response_model=ExtractedTablesOut, errors=(501,)
)
async def extracted_tables_route(
    version_id: VersionId,
    ctx: Ctx,
    page: Annotated[int | None, Query(ge=1, le=5000)] = None,
) -> ExtractedTablesOut:
    """A statement page's transaction rows with cell boxes (CLS-05)."""
    await _gate(ctx, "evidence.read", EVIDENCE_FORM_EXTRACTION)
    _not_yet()


@ocr_router.post(
    f"{_V}/text/retry", action="evidence.ocr_retry", response_model=TextRetryOut, errors=(409, 501)
)
async def text_retry_route(version_id: VersionId, ctx: Ctx) -> TextRetryOut:
    """A person's "Read text again" after a cleared refusal; the agent and workers are refused
    by the matrix (INV-1)."""
    await _gate(ctx, "evidence.ocr_retry", EVIDENCE_OCR)
    _not_yet()
