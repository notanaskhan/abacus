"""`tax.return_drafter` v1, mode `draft` (T-04-T25; T-04 §6; SPEC-649 AC-9.x; ADR-050, ADR-052,
ADR-005, ADR-166; §7216). PROTECTED (red: an agent on tax return information).

Code computes, the model judges, a person decides:

1. **Consent and boundary first.** The run's first call is the C17 `tax.read_return` read: C19's
   tool-layer gate refuses it before any query when the taxpayer lacks either §7216 consent for
   the year (`consent_required`). The run then waits on inputs (`consent_7216`) and nothing else
   runs, no model call (AC-9.3). Every later read and the proposal go through C17 too, so the gate
   holds on every call; the gateway refuses again on `consent_7216` (defence in depth).
2. **The deterministic box-to-field mapper** (`map_boxes`, code): each box the form maps read
   (`extracted_fields`, P-11) lands on its worksheet field by `BOX_MAP` for the tax year. A box
   with no field on the drafted worksheets is a self-check gap; so is the K-1 box 18 code A
   (tax-exempt interest: IT-201 line 20 needs the obligations' state first, the Feld box 18A
   issue). An engine-derived field is never proposed (the engine computes tax, DEC-77).
3. **The worksheet set** (`worksheet_set`, code) from the return's documents: IT-201 always, one
   W-2 worksheet when there are W-2s, Sch E page 2 for a partnership or S corporation K-1, IT-653
   when a K-1 carries a New York PTET attachment. The **model judges** only TSJ and the
   new-this-year note per worksheet (`tax.return_drafter@v1`, `ReturnDraftJudgment`); a key it
   was not offered, a TSJ outside T/S/J or a number in a note is dropped for code's default.
4. **Verified citations**: each proposed value carries its box as a `document_text` claim that the
   word-layer verifier re-reads (`form_line_citations.box_claim`); a box whose citation does not
   verify is not proposed and becomes a gap (INV-2: no uncited row).
5. **The proposal**: one `return_field_changes` proposal through C17 `tax.propose_field_changes`,
   and a **Proposed checkpoint "Initial draft"** on the return naming it (deciding the proposal
   in SHL-10 decides the checkpoint in SHL-16). Nothing changes until a person approves it.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified

DRAFTER: Final = "tax.return_drafter"
PROMPT: Final = "tax.return_drafter@v1"
CHECKPOINT_NAME: Final = "Initial draft"
TSJ: Final = frozenset({"T", "S", "J"})

# --- the box-to-field map (code; P-11's box keys → T-04's worksheet fields) --------------------

# (worksheet key, field key) per box key, per tax year. Rows the year does not change inherit.
BOX_MAP: Final[Mapping[int, Mapping[str, tuple[str, str]]]] = {
    2025: {
        "w2.box1": ("w2", "w2.box1"),
        "w2.box2": ("w2", "w2.box2"),
        "w2.box16": ("w2", "w2.box16"),
        "w2.box17": ("w2", "w2.box17"),
        "w2.box19": ("w2", "w2.box19"),
        "k1_1065.box1": ("sch_e_p2", "sch_e_p2.k1_box1"),
        "k1_1065.box2": ("sch_e_p2", "sch_e_p2.k1_box2"),
        "k1_1065.box5": ("sch_e_p2", "sch_e_p2.k1_box5"),
        "k1_1065.box19": ("sch_e_p2", "sch_e_p2.k1_box19"),
        "k1_1120s.box1": ("sch_e_p2", "sch_e_p2.k1_box1"),
        "k1_1120s.box2": ("sch_e_p2", "sch_e_p2.k1_box2"),
        "k1_1120s.box4": ("sch_e_p2", "sch_e_p2.k1_box5"),
        "1099_int.box1": ("it201", "it201.interest"),
    }
}
# The K-1 boxes whose code A is tax-exempt interest: IT-201 line 20 needs the obligations' state.
BOX_18A: Final = ("k1_1065.box18", "k1_1065.box18a", "k1_1120s.box16", "k1_1120s.box16a")
K1_FORMS: Final = frozenset({"k1_1065", "k1_1120s"})
_PTET: Final = re.compile(r"\bptet\b|\.state_ny_ptet")
_DIGIT: Final = re.compile(r"\d")

Worksheet = Literal["it201", "w2", "sch_e_p2", "it653"]
WORKSHEET_TITLES: Final[Mapping[str, str]] = {
    "it201": "IT-201",
    "w2": "Wages (W-2)",
    "sch_e_p2": "Sch E p 2",
    "it653": "IT-653 · PTET credit",
}


def box_map(tax_year: int) -> Mapping[str, tuple[str, str]]:
    """The map for `tax_year`: the latest year at or before it (inherited where unchanged)."""
    years = sorted(y for y in BOX_MAP if y <= tax_year)
    if not years:
        raise LookupError(f"no box map for {tax_year}")
    return BOX_MAP[years[-1]]


@dataclass(frozen=True)
class Box:
    """One box a form map read on a document version (`evidence.api.extracted_fields_of`)."""

    id: UUID
    evidence_version_id: UUID
    form_type: str
    field_key: str
    value_text: str | None
    page_no: int
    bbox: tuple[float, float, float, float]
    low_confidence: bool = False


@dataclass(frozen=True)
class TargetField:
    """A worksheet field the drafter may propose on (`tax.read_worksheet`)."""

    worksheet_key: str
    worksheet_id: UUID
    field_id: UUID
    field_key: str
    current: Decimal | None
    derivation: str = "input"


@dataclass(frozen=True)
class Mapped:
    box: Box
    target: TargetField
    value: Decimal


@dataclass(frozen=True)
class Gap:
    """A self-check issue the draft raises: a box with no field, or one a person must look at."""

    code: Literal["box_18a_state", "box_unmapped", "box_low_confidence", "citation_unverified"]
    field_key: str
    evidence_version_id: UUID


@dataclass(frozen=True)
class Mapping_:
    changes: tuple[Mapped, ...]
    gaps: tuple[Gap, ...]


def _amount(text: str | None) -> Decimal | None:
    if text is None:
        return None
    cleaned = text.replace(",", "").replace("$", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def map_boxes(
    tax_year: int, boxes: Sequence[Box], fields: Mapping[tuple[str, str], TargetField]
) -> Mapping_:
    """Code: each box's amount onto its field; the rest are gaps. A field already holding the
    value, or one the engine derives, is not proposed."""
    mapping = box_map(tax_year)
    changes: list[Mapped] = []
    gaps: list[Gap] = []
    for box in sorted(boxes, key=lambda b: (b.form_type, b.field_key, str(b.id))):
        if box.field_key in BOX_18A and _amount(box.value_text):
            gaps.append(Gap("box_18a_state", box.field_key, box.evidence_version_id))
            continue
        target_key = mapping.get(box.field_key)
        value = _amount(box.value_text)
        if target_key is None or value is None:
            if value:  # a box with an amount nothing receives
                gaps.append(Gap("box_unmapped", box.field_key, box.evidence_version_id))
            continue
        target = fields.get(target_key)
        if target is None:
            gaps.append(Gap("box_unmapped", box.field_key, box.evidence_version_id))
            continue
        if box.low_confidence:
            gaps.append(Gap("box_low_confidence", box.field_key, box.evidence_version_id))
            continue
        if target.derivation == "engine" or target.current == value:
            continue
        changes.append(Mapped(box, target, value))
    return Mapping_(tuple(changes), tuple(gaps))


def worksheet_set(boxes: Sequence[Box]) -> tuple[str, ...]:
    """Code: the worksheets the return's documents call for, in TXI-01's order."""
    forms = {b.form_type for b in boxes}
    found: list[str] = ["it201"]
    if "w2" in forms:
        found.append("w2")
    if forms & K1_FORMS:
        found.append("sch_e_p2")
    if any(b.form_type in K1_FORMS and _PTET.search(b.field_key) for b in boxes):
        found.append("it653")
    order = ("w2", "sch_e_p2", "it201", "it653")
    return tuple(sorted(found, key=order.index))


# --- the model's judgment (TSJ and new-this-year notes only) -----------------------------------


class WorksheetJudgment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[str, Field(min_length=1, max_length=40), classified("internal")]
    tsj: Annotated[Literal["T", "S", "J"], classified("internal")]
    new_this_year_note: Annotated[
        str | None, Field(max_length=300), classified("confidential")
    ] = None


class ReturnDraftJudgment(BaseModel):
    """`tax.return_drafter@v1`'s answer: per offered worksheet, its TSJ and an optional
    new-this-year note. Never a value, never a decision (INV-1, ADR-050)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    worksheets: Annotated[
        list[WorksheetJudgment], Field(min_length=1, max_length=20), classified("internal")
    ]


@dataclass(frozen=True)
class WorksheetPlan:
    key: str
    title: str
    tsj: str
    new_this_year_note: str | None
    judged: bool  # the model's judgment stood (False: code's default)


def judged_set(
    offered: Sequence[str], default_tsj: str, judgment: ReturnDraftJudgment | None
) -> tuple[WorksheetPlan, ...]:
    """The model's judgment over code's offer: an unoffered key, a TSJ outside T/S/J or a note
    with a digit (a number the model was not given) is dropped for code's default."""
    by_key = {j.key: j for j in (judgment.worksheets if judgment is not None else [])}
    plans: list[WorksheetPlan] = []
    for key in offered:
        j = by_key.get(key)
        note = j.new_this_year_note if j is not None else None
        if note is not None and _DIGIT.search(note):
            note = None
        plans.append(
            WorksheetPlan(
                key,
                WORKSHEET_TITLES.get(key, key),
                j.tsj if j is not None and j.tsj in TSJ else default_tsj,
                note,
                j is not None,
            )
        )
    return tuple(plans)


def draft_hash(changes: Sequence[Mapped]) -> str:
    """The proposed checkpoint's content hash: its field changes, canonical (code)."""
    body = json.dumps(
        sorted([c.target.worksheet_key, c.target.field_key, str(c.value)] for c in changes),
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode()).hexdigest()


Outcome = Literal["proposed", "waiting_on_inputs", "nothing_to_propose", "refused"]


@dataclass(frozen=True)
class DraftResult:
    outcome: Outcome
    needs: tuple[str, ...] = ()
    proposal_id: UUID | None = None
    checkpoint_id: UUID | None = None
    worksheets: tuple[WorksheetPlan, ...] = ()
    changes: int = 0
    gaps: tuple[Gap, ...] = ()
    issue_ids: tuple[UUID, ...] = field(default_factory=tuple[UUID, ...])
    code: str | None = None


def as_money(value: object) -> Decimal | None:
    if isinstance(value, dict):
        raw = cast(dict[str, object], value).get("v")
        return _amount(str(raw)) if raw is not None else None
    if isinstance(value, int | float | str | Decimal):
        return _amount(str(value))
    return None


__all__ = [
    "BOX_18A",
    "BOX_MAP",
    "CHECKPOINT_NAME",
    "DRAFTER",
    "PROMPT",
    "Box",
    "DraftResult",
    "Gap",
    "Mapped",
    "ReturnDraftJudgment",
    "TargetField",
    "WorksheetJudgment",
    "WorksheetPlan",
    "as_money",
    "box_map",
    "draft_hash",
    "judged_set",
    "map_boxes",
    "worksheet_set",
]
