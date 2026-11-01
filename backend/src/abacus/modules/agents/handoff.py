"""The human handoff contract and typed citations (ADR-054, ADR-066). TASK-011 design §5.

Every agent output extends `Handoff`: a proposed action, a confidence, a short rationale,
citations to exact sources, and what couldn't be verified. Citations are verified by code before
anyone sees them (`citations.verify`); a failing citation is marked unverified, never shown as
fact. Agent text is untrusted: the board renders it as sanitised plain text (ADR-065).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel.classification import classified

CellRef = Annotated[str, Field(pattern=r"^[A-Z]{1,3}[1-9][0-9]{0,6}$")]


class Citation(BaseModel):
    """A spreadsheet cell, and optionally the exact text or number the agent says it holds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cell: Annotated[CellRef, classified("internal")]
    quote: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    value: Annotated[Decimal | None, classified("confidential")] = None


class Handoff(BaseModel):
    """Subclasses declare `action` as a Literal of the actions their agent may propose."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    confidence: Annotated[float, Field(ge=0, le=1), classified("internal")]
    rationale: Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]
    citations: Annotated[list[Citation], Field(max_length=50), classified("confidential")]
    unverified: Annotated[
        list[Annotated[str, Field(max_length=300)]],
        Field(max_length=50),
        classified("confidential"),
    ]


class ScreeningOutput(Handoff):
    """The screener's proposal (SPEC-000 §10)."""

    action: Annotated[Literal["ready_for_review", "needs_revision"], classified("internal")]


class VerifiedCitation(BaseModel):
    model_config = ConfigDict(frozen=True)

    cell: Annotated[str, classified("internal")]
    quote: Annotated[str | None, classified("confidential")]
    value: Annotated[str | None, classified("confidential")]
    verified: Annotated[bool, classified("internal")]
    reason: Annotated[str | None, classified("internal")]


# --- The upload reviewer (SPEC-030; TASK-058 D2) -------------------------------------------------

ReviewCategory = Literal["irrelevant", "draft", "altered"]


class DocumentCitation(BaseModel):
    """A quote from a PDF page, or from a spreadsheet's sheet and cell (exactly one of them)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    page: Annotated[int | None, Field(ge=1, le=1000), classified("internal")] = None
    sheet: Annotated[str | None, Field(max_length=100), classified("confidential")] = None
    cell: Annotated[CellRef | None, classified("internal")] = None
    # The prompt asks for at most 200 characters; models sometimes quote a few lines, and a
    # longer quote is still verified whole, so up to 1,000 is accepted (TASK-058 milestone).
    quote: Annotated[str, Field(min_length=1, max_length=1000), classified("confidential")]

    @model_validator(mode="after")
    def _one_place(self) -> DocumentCitation:
        if (self.page is None) == (self.cell is None):
            raise ValueError("a citation names a page or a cell")
        return self


class ReviewFlag(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    category: Annotated[ReviewCategory, classified("internal")]
    confidence: Annotated[float, Field(ge=0, le=1), classified("internal")]
    rationale: Annotated[str, Field(min_length=1, max_length=600), classified("confidential")]
    citations: Annotated[
        list[DocumentCitation], Field(min_length=1, max_length=5), classified("confidential")
    ]


class UploadReviewOutput(BaseModel):
    """The upload reviewer's proposal: flags for the firm, never a decision (ADR-005)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    no_concerns: Annotated[bool, classified("internal")]
    flags: Annotated[list[ReviewFlag], Field(max_length=5), classified("confidential")]


# --- The matcher (SPEC-033; TASK-065) ---------------------------------------------------------

# D1: candidates are given to the model as R1..R60; code maps them back to request items.
CandidateRef = Annotated[str, Field(pattern=r"^R([1-9]|[1-5][0-9]|60)$")]


class MatchProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request: Annotated[CandidateRef, classified("internal")]
    confidence: Annotated[float, Field(ge=0, le=1), classified("internal")]
    rationale: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]
    citations: Annotated[
        list[DocumentCitation], Field(min_length=1, max_length=3), classified("confidential")
    ]


class MatchOutput(BaseModel):
    """The matcher's proposal: requests an inbox file may belong to, or none; a person assigns
    (ADR-005)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    none_fit: Annotated[bool, classified("internal")]
    rationale: Annotated[str | None, Field(max_length=300), classified("confidential")] = None
    proposals: Annotated[list[MatchProposal], Field(max_length=3), classified("confidential")]

    @model_validator(mode="after")
    def _one_answer(self) -> MatchOutput:
        if self.none_fit == bool(self.proposals):
            raise ValueError("either proposals, or none_fit with no proposals")
        return self


# --- The matcher's intake mode (v3; N-01-T22; N-01 §6) ----------------------------------------

# Code gives the client's destinations as D1..D60 and maps the answer back (an unknown one is
# discarded); the model never sees a destination's id.
DestinationRef = Annotated[str, Field(pattern=r"^D([1-9]|[1-5][0-9]|60)$")]
_FORM_FAMILY = Annotated[str | None, Field(max_length=40), classified("internal")]


class PageCitation(BaseModel):
    """A quote from one page of the attachment's masked text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    page: Annotated[int, Field(ge=1, le=1000), classified("internal")]
    quote: Annotated[str, Field(min_length=1, max_length=1000), classified("confidential")]


class IntakeClassification(BaseModel):
    """What the document is, as far as its text shows; every field may be unknown."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    form_family: _FORM_FAMILY = None
    tax_year: Annotated[int | None, Field(ge=1990, le=2100), classified("internal")] = None
    issuer: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    kind: Annotated[
        Literal[
            "tax_form", "notice", "receipt", "census", "invoice", "statement", "return", "other"
        ],
        classified("internal"),
    ] = "other"
    confidence: Annotated[float, Field(ge=0, le=1), classified("internal")] = 0.0


class IntakeProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    destination: Annotated[DestinationRef, classified("internal")]
    confidence: Annotated[float, Field(ge=0, le=1), classified("internal")]
    rationale: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]
    citations: Annotated[
        list[PageCitation], Field(min_length=1, max_length=3), classified("confidential")
    ]


class IntakeMatchOutput(BaseModel):
    """The matcher's intake proposal: what an intake attachment is and up to three of its
    client's destinations, or none; a person files (ADR-005, I-AGENT-NEVER)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    none_fit: Annotated[bool, classified("internal")]
    classification: Annotated[IntakeClassification, classified("confidential")]
    rationale: Annotated[str | None, Field(max_length=300), classified("confidential")] = None
    proposals: Annotated[list[IntakeProposal], Field(max_length=3), classified("confidential")]

    @model_validator(mode="after")
    def _one_answer(self) -> IntakeMatchOutput:
        if self.none_fit == bool(self.proposals):
            raise ValueError("either proposals, or none_fit with no proposals")
        return self


# --- The guidance drafter (SPEC-035; TASK-072) -------------------------------------------------


class GuidanceDraft(BaseModel):
    """A draft of what a client reads about a request; a person approves it (ADR-005, ADR-111)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    why: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]
    good_looks_like: Annotated[
        str, Field(min_length=1, max_length=600), classified("confidential")
    ]
    effort: Annotated[Literal["small", "medium", "large"] | None, classified("internal")] = None
    effort_reason: Annotated[str | None, Field(max_length=160), classified("internal")] = None
    blocks_fieldwork: Annotated[bool | None, classified("internal")] = None
    blocks_reason: Annotated[str | None, Field(max_length=160), classified("internal")] = None


# --- The methodology importer (K-01-T21; K-01 §6; DEC-1856) ------------------------------------


class ImportedProgram(BaseModel):
    """A program heading the importer read; codes are the firm's own (`BH-EBP-110`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: Annotated[
        str,
        Field(pattern=r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$", max_length=40),
        classified("internal"),
    ]
    name: Annotated[str, Field(min_length=1, max_length=200), classified("internal")]


class ImportedStep(BaseModel):
    """One numbered step as printed, with the quote code verifies on its page. There is no
    mandatory, approval, effective-date or level field: those are a person's (K-01 §6.1, INV-1);
    `extra="forbid"` refuses an answer that adds one."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    program_code: Annotated[
        str,
        Field(pattern=r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$", max_length=40),
        classified("internal"),
    ]
    number: Annotated[int, Field(ge=1, le=999), classified("internal")]
    text: Annotated[str, Field(min_length=1, max_length=2000), classified("internal")]
    page: Annotated[int, Field(ge=1, le=400), classified("internal")]
    # The step runs onto the next page (a flag, `split_across_pages`).
    page_to: Annotated[int | None, Field(ge=1, le=400), classified("internal")] = None
    quote: Annotated[str, Field(min_length=1, max_length=400), classified("internal")]
    confidence: Annotated[float, Field(ge=0, le=1), classified("internal")]
    # Other steps the text refers to ("BH-EBP-410 step 6"), checked by code.
    refs: Annotated[list[str], Field(max_length=10), classified("internal")] = []


class ImportBatchOutput(BaseModel):
    """The importer's answer for one batch of up to eight pages."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    programs: Annotated[list[ImportedProgram], Field(max_length=40), classified("internal")] = []
    steps: Annotated[list[ImportedStep], Field(max_length=200), classified("internal")] = []


@dataclass(frozen=True)
class VerifiedDocumentCitation:
    page: int | None
    sheet: str | None
    cell: str | None
    quote: str
    verified: bool
    reason: str | None  # page_not_found | cell_not_found | quote_not_found


# --- The entry assessor (SPEC-037 Q4; TASK-085) -------------------------------------------------

# D1: the person's linked documents are given as D1..D3; code maps them back to versions.
DocumentRef = Annotated[str, Field(pattern=r"^D[1-3]$")]
EntryClaim = Literal["amount", "date", "party", "approval", "nature", "reference"]


class EntryCitation(BaseModel):
    """A quote from one of the entry's documents, saying what it shows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document: Annotated[DocumentRef, classified("internal")]
    claim: Annotated[EntryClaim, classified("internal")]
    page: Annotated[int | None, Field(ge=1, le=1000), classified("internal")] = None
    sheet: Annotated[str | None, Field(max_length=100), classified("confidential")] = None
    cell: Annotated[CellRef | None, classified("internal")] = None
    quote: Annotated[str, Field(min_length=1, max_length=1000), classified("confidential")]

    @model_validator(mode="after")
    def _one_place(self) -> EntryCitation:
        if (self.page is None) == (self.cell is None):
            raise ValueError("a citation names a page or a cell")
        return self


class EntryAssessment(BaseModel):
    """Whether the documents support the entry: a proposal for a person (ADR-005)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: Annotated[Literal["explained", "not_explained", "unclear"], classified("internal")]
    rationale: Annotated[str, Field(min_length=1, max_length=400), classified("confidential")]
    citations: Annotated[list[EntryCitation], Field(max_length=5), classified("confidential")] = []


# --- A-04-T11: the section drafter (workpapers.section_drafter; DEC-1868) ----------------------

FactRef = Annotated[str, Field(pattern=r"^F[1-9][0-9]{0,2}$")]
StepRef = Annotated[str, Field(pattern=r"^S[1-9][0-9]{0,2}$")]
DraftCellKey = Annotated[
    str, Field(pattern=r"^([a-z][a-z0-9_]{0,39}!)?[A-Z]{1,2}[1-9][0-9]{0,3}$")
]


class DraftCitation(BaseModel):
    """Where a drafted value comes from: a step of the pinned version (`S<n>`, as the context
    lists them) or a page of one of the documents (`D<n>`), with the exact words."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step: Annotated[StepRef | None, classified("internal")] = None
    document: Annotated[DocumentRef | None, classified("internal")] = None
    page: Annotated[int | None, Field(ge=1, le=1000), classified("internal")] = None
    quote: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]

    @model_validator(mode="after")
    def _one_source(self) -> DraftCitation:
        if (self.step is None) == (self.document is None):
            raise ValueError("a citation names a step or a document")
        if self.document is not None and self.page is None:
            raise ValueError("a document citation names its page")
        return self


class DraftedCell(BaseModel):
    """One proposed cell value. A number is never written by the model: a figure is a fact the
    context gives (`fact`, by reference); text may hold only numbers its sources show."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cell: Annotated[DraftCellKey, classified("internal")]
    text: Annotated[
        str | None, Field(min_length=1, max_length=2000), classified("confidential")
    ] = None
    fact: Annotated[FactRef | None, classified("internal")] = None
    citations: Annotated[list[DraftCitation], Field(max_length=4), classified("confidential")] = []

    @model_validator(mode="after")
    def _one_value(self) -> DraftedCell:
        if (self.text is None) == (self.fact is None):
            raise ValueError("a drafted cell is text or a fact")
        return self


class SectionDraft(BaseModel):
    """A section's proposed values: suggestions for a person to adopt (ADR-005, AC1.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cells: Annotated[list[DraftedCell], Field(max_length=200), classified("confidential")] = []


# --- A-04-T15: the materiality recommender (decisions.recommender; DEC-1953) ---------------------

RecommendFactRef = Annotated[
    str,
    Field(
        pattern=r"^(?:benchmark_key|benchmark_amount|policy|option:[a-z0-9_]{1,40}|factor:\d{1,2}|"
        r"prior:PY\d{4})$"
    ),
]


class RecommendationReason(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=600), classified("confidential")]
    facts: Annotated[
        list[RecommendFactRef], Field(min_length=1, max_length=8), classified("internal")
    ]


class DecisionSuggestion(BaseModel):
    """One code-computed option key and up to three reasons by fact reference: a tag on the
    partner's card, never a choice (INV-1; A-04 §6.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommended_option_key: Annotated[
        str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$"), classified("internal")
    ]
    reasons: Annotated[
        list[RecommendationReason], Field(min_length=1, max_length=3), classified("confidential")
    ]
