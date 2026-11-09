"""The `tax_form_line` citable and box citations (T-04-T14; T-04 §4.5; ADR-166 §2; C4 §3.1;
DEC-3125). PROTECTED (red path: citations, INV-2).

- **`tax_form_line`**: a line of a return's worksheet (`return_fields`, 0761), locator
  `{return_id, field_key}`; the source is the return (C4's `SOURCES`). The verifier authorises
  `return_worksheet.read` on the anchor's engagement before it reads anything (a wall, a role, an
  agent outside its task scope: `source_not_visible`), so it is never an oracle across
  engagements; a return of another engagement is `source_not_found` exactly as if it did not
  exist. A claimed value must equal the field's current amount (`value_mismatch` otherwise); a
  quote must be the field's label, space- and case-folded. The display renders "Form 1040" and
  "Line 3b" by code from the stored locator (INV-2).
- **Box citations** (`box_claim`): a box an extraction found (`extracted_fields`, P-11) becomes a
  `document_text` claim with its page and bounding box, so the existing word-layer verifier
  re-reads the page; a fabricated value, page or box fails there. A superseding upload moves the
  citation through evidence's own moved detector (`citation.moved`), since the source is the
  evidence version.
- **Linked-figure labels** (`linked_label`): "Form 1040 · Line 3b 14,820" for the C4 regions API,
  composed by code from the field and its amount.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.errors import NotFound
from abacus.kernel.uow import UnitOfWork
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    CitationLabel,
    CitationVerdict,
    register_citable,
)
from abacus.modules.identity.api import Actor, AuthContext, Forbidden, authorise

SOURCE: Final = "tax_return"
NIL: Final = UUID(int=0)
VERIFIER_VERSION: Final = "v1"
_FIELD: Final = text(
    "SELECT f.engagement_id, f.field_key, f.line_ref, f.label, f.current_value, w.form_code "
    "FROM return_fields f JOIN return_worksheets w ON w.id = f.worksheet_id "
    "WHERE f.tax_return_id = :r AND f.field_key = :k"
)
_FORM_TITLE: Final[dict[str, str]] = {
    "1040": "Form 1040",
    "it201": "NY IT-201",
    "it203": "NY IT-203",
    "sch_e": "Schedule E",
}


def _locator(raw: Mapping[str, object]) -> tuple[UUID, str] | None:
    try:
        return UUID(str(raw["return_id"])), str(raw["field_key"])
    except (KeyError, ValueError):
        return None


def _amount_of(value: object) -> Decimal | None:
    """The field's typed value `{t: "amount", v: "14820"}` as a number; anything else None."""
    if not isinstance(value, Mapping):
        return None
    typed = cast(Mapping[str, object], value)
    if typed.get("t") != "amount" or typed.get("v") is None:
        return None
    try:
        return Decimal(str(typed["v"]))
    except ArithmeticError:
        return None


def _fold(words: str) -> str:
    return " ".join(words.split()).casefold()


async def _may_read(actor: Actor, engagement_id: UUID) -> bool:
    if not isinstance(actor, AuthContext):
        return False
    try:
        resource = await engagement_resource_of(actor.tenant, engagement_id)
        await authorise(actor, "return_worksheet.read", resource)
    except (Forbidden, NotFound):
        return False
    return True


def amount(printed: str) -> Decimal | None:
    """A printed amount as a number: `14,820`, `$14,820.00`, `(1,550)`; anything else None."""
    token = printed.strip()
    negative = (token.startswith("(") and token.endswith(")")) or token.startswith("-")
    digits = token.strip("()-$ ").replace(",", "")
    try:
        found = Decimal(digits)
    except ArithmeticError:
        return None
    return -found if negative else found


async def verify_tax_form_line(
    tx: UnitOfWork, actor: Actor, claim: CitationClaim, anchor: CitationAnchor
) -> CitationVerdict:
    at = _locator(claim.locator)
    if at is None:
        return CitationVerdict("locator_invalid", SOURCE, NIL)
    return_id, field_key = at
    if anchor.engagement_id is None or not await _may_read(actor, anchor.engagement_id):
        return CitationVerdict("source_not_visible", SOURCE, return_id)
    row = (await tx.session.execute(_FIELD, {"r": return_id, "k": field_key})).first()
    if row is None or row.engagement_id != anchor.engagement_id:
        return CitationVerdict("source_not_found", SOURCE, return_id)
    locator: dict[str, object] = {"return_id": str(return_id), "field_key": field_key}
    held = _amount_of(row.current_value)
    if claim.value is not None:
        claimed = amount(claim.value)
        if claimed is None or held is None or claimed != held:
            return CitationVerdict("value_mismatch", SOURCE, return_id, locator)
    if claim.quote is not None and _fold(claim.quote) != _fold(str(row.label)):
        return CitationVerdict("quote_not_found", SOURCE, return_id, locator)
    return CitationVerdict(
        None,
        SOURCE,
        return_id,
        locator,
        source_version=f"{row.form_code}:{row.line_ref or field_key}",
        match_id=f"tfl:{return_id}:{field_key}",
        value_text=None if held is None else f"{held:,}",
    )


def form_title(form_code: str) -> str:
    return _FORM_TITLE.get(form_code.lower(), f"Form {form_code}")


async def display_tax_form_line(
    session: AsyncSession, locator: Mapping[str, object], engagement_id: UUID | None
) -> CitationLabel:
    at = _locator(locator)
    if at is None or engagement_id is None:
        return CitationLabel("Tax form line", "")
    row = (await session.execute(_FIELD, {"r": at[0], "k": at[1]})).first()
    if row is None or row.engagement_id != engagement_id:
        return CitationLabel("Tax form line", "")
    return CitationLabel(form_title(str(row.form_code)), f"Line {row.line_ref or at[1]}")


def linked_label(form_code: str, line_ref: str, value: Decimal | None) -> str:
    """ "Form 1040 · Line 3b 14,820": the regions API's label for a linked figure (by code)."""
    figure = "" if value is None else f" {value:,.0f}"
    return f"{form_title(form_code)} · Line {line_ref}{figure}"


def box_claim(
    evidence_version_id: UUID,
    page_no: int,
    bbox: tuple[float, float, float, float],
    value_text: str | None,
) -> CitationClaim:
    """A box an extraction found, as a `document_text` claim the word-layer verifier re-reads."""
    return CitationClaim(
        "document_text",
        {
            "evidence_version_id": str(evidence_version_id),
            "page": page_no,
            "bbox": list(bbox),
        },
        quote=None,
        value=value_text,
    )


def register() -> None:
    """At import (tax/api.py)."""
    register_citable(
        "tax_form_line", verify_tax_form_line, display_tax_form_line, version=VERIFIER_VERSION
    )
