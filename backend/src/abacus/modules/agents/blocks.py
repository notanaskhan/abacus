"""AgentBlocks v1: the closed shape of agent-authored output (P-09 §3.7; DEC-41, ADR P-24 owed).

Every agent surface renders the same few parts, and nothing else validates:

- `p`: a paragraph of segments, each `text`, a `cite` (a citation and its marker number) or a
  `fact` (a reference into the run's fact registry).
- `table`, `kv`, `metric`, `file`, `badge`, `cite_list`, `options`, `entity_ref`.

Validation (`validate_blocks`) is deterministic and runs on the server before anything is shown:

- **Numbers by reference** (ADR P-48, DE-3): a numeric token in text is refused. Figures travel as
  `fact` segments that code computed and registered, or as citations whose values were verified.
- **No markup** (ADR-065, DE-6): HTML, markdown and any link `sanitise_text` would remove are
  refused, not rewritten.
- **Copy lint** (DE-5, I-12): no claim of a human act ("approved", "signed off", "I decided",
  "sent"), no "memory", "trained" or "learned", no "!", no confidence figures.
- **Closed references**: every fact id is in the registry, every citation in the run's set, and
  every badge a stored status of its object (`kernel._statuses.STORED`).

The model never computes (ADR-050); it can only point at what code computed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Set
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from abacus.ai_gateway import CheckFailure, register_output_check, sanitise_text
from abacus.kernel._statuses import STORED
from abacus.kernel.classification import classified

TEXT_LIMIT: Final = 2000
_ID = r"^[a-z][a-z0-9_]{0,39}$"

# --- Parts ----------------------------------------------------------------------------------


class _Part(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TextSeg(_Part):
    kind: Annotated[Literal["text"], classified("internal")]
    text: Annotated[str, classified("confidential"), Field(min_length=1, max_length=TEXT_LIMIT)]


class CiteSeg(_Part):
    kind: Annotated[Literal["cite"], classified("internal")]
    citation_id: Annotated[UUID, classified("internal")]
    n: Annotated[int, classified("internal"), Field(ge=1, le=999)]


class FactSeg(_Part):
    kind: Annotated[Literal["fact"], classified("internal")]
    fact_id: Annotated[str, classified("internal"), Field(pattern=_ID)]


Segment = Annotated[TextSeg | CiteSeg | FactSeg, Field(discriminator="kind")]
Cell = Annotated[TextSeg | CiteSeg | FactSeg, Field(discriminator="kind")]


class ParagraphPart(_Part):
    kind: Annotated[Literal["p"], classified("internal")]
    segments: Annotated[
        list[Segment], classified("confidential"), Field(min_length=1, max_length=40)
    ]


class TablePart(_Part):
    kind: Annotated[Literal["table"], classified("internal")]
    head: Annotated[list[str], classified("confidential"), Field(min_length=1, max_length=8)]
    rows: Annotated[
        list[Annotated[list[Cell], Field(min_length=1, max_length=8)]],
        classified("confidential"),
        Field(max_length=50),
    ]


class KvRow(_Part):
    label: Annotated[str, classified("confidential"), Field(min_length=1, max_length=80)]
    value: Annotated[list[Segment], classified("confidential"), Field(min_length=1, max_length=8)]


class KvPart(_Part):
    kind: Annotated[Literal["kv"], classified("internal")]
    rows: Annotated[list[KvRow], classified("confidential"), Field(min_length=1, max_length=20)]


class MetricPart(_Part):
    kind: Annotated[Literal["metric"], classified("internal")]
    label: Annotated[str, classified("confidential"), Field(min_length=1, max_length=80)]
    fact_id: Annotated[str, classified("internal"), Field(pattern=_ID)]


class FilePart(_Part):
    kind: Annotated[Literal["file"], classified("internal")]
    artifact_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential"), Field(min_length=1, max_length=200)]
    meta: Annotated[str | None, classified("confidential"), Field(max_length=200)] = None


class BadgePart(_Part):
    kind: Annotated[Literal["badge"], classified("internal")]
    object: Annotated[str, classified("internal"), Field(pattern=_ID)]
    code: Annotated[str, classified("internal"), Field(pattern=_ID)]


class CiteListPart(_Part):
    kind: Annotated[Literal["cite_list"], classified("internal")]
    cites: Annotated[list[CiteSeg], classified("internal"), Field(min_length=1, max_length=50)]


class OptionRow(_Part):
    key: Annotated[str, classified("internal"), Field(pattern=_ID)]
    title: Annotated[str, classified("confidential"), Field(min_length=1, max_length=120)]
    detail: Annotated[str | None, classified("confidential"), Field(max_length=400)] = None
    recommended: Annotated[bool, classified("internal")] = False


class OptionsPart(_Part):
    kind: Annotated[Literal["options"], classified("internal")]
    options: Annotated[
        list[OptionRow], classified("confidential"), Field(min_length=2, max_length=9)
    ]


class EntityRefPart(_Part):
    """A record by type and id; its label is rendered by code, never by the model."""

    kind: Annotated[Literal["entity_ref"], classified("internal")]
    record_type: Annotated[str, classified("internal"), Field(pattern=_ID)]
    record_id: Annotated[UUID, classified("internal")]


AgentPart = Annotated[
    ParagraphPart
    | TablePart
    | KvPart
    | MetricPart
    | FilePart
    | BadgePart
    | CiteListPart
    | OptionsPart
    | EntityRefPart,
    Field(discriminator="kind"),
]


class AgentBlocks(BaseModel):
    """AgentBlocks v1: an ordered list of parts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[Literal[1], classified("internal")] = 1
    parts: Annotated[
        list[AgentPart], classified("confidential"), Field(min_length=1, max_length=50)
    ]


# --- The run's fact registry ----------------------------------------------------------------

FactKind = Literal["money", "count", "percent", "date", "number"]


class Fact(BaseModel):
    """A figure code computed (ADR-050), registered for the run before the model may cite it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Annotated[str, classified("internal"), Field(pattern=_ID)]
    kind: Annotated[FactKind, classified("internal")]
    value: Annotated[
        str, classified("confidential"), Field(max_length=40)
    ]  # a decimal or ISO date
    basis: Annotated[
        str, classified("internal"), Field(max_length=200)
    ]  # what code computed it from


# --- Validation -----------------------------------------------------------------------------


class BlocksRejected(Exception):
    """Agent output that may not be shown. `code` is one of the codes below; `where` is a path
    into the payload. Neither ever carries the offending text."""

    def __init__(self, code: str, where: str) -> None:
        super().__init__(f"{code} at {where}")
        self.code = code
        self.where = where


# A figure: digits, optionally with a currency sign, separators, decimals or a percent sign.
# Digits glued to letters ("401(k)", "W2", "Q4") are names, not figures.
_NUMBER = re.compile(r"(?<![A-Za-z0-9_])[$€£]?\d[\d,]*(?:\.\d+)?%?(?![A-Za-z0-9_(])")
_HTML = re.compile(r"<\s*/?\s*[A-Za-z][^>]{0,200}>")
_MARKDOWN = re.compile(
    r"(\*\*|__|`|\]\(|^\s{0,3}#{1,6}\s|^\s{0,3}[-*+]\s|^\s{0,3}>\s)", re.MULTILINE
)
_HUMAN_ACT = re.compile(
    r"\b(approved|signed[\s-]off|sign(?:ed)?[\s-]off|i\s+decided|i\s+have\s+decided|sent|posted|"
    r"released|accepted|rejected|filed)\b",
    re.IGNORECASE,
)
_BANNED = re.compile(
    r"\b(memory|memories|trained|learned|learnt|confidence|certain(?:ty)?)\b", re.I
)
_PERCENT_WORDS = re.compile(r"\b(percent|per\s+cent)\b", re.IGNORECASE)


def lint_text(text: str, where: str) -> None:
    """The deterministic copy lint on one string of agent text."""
    if sanitise_text(text) != text:
        raise BlocksRejected("link", where)
    if _HTML.search(text) or _MARKDOWN.search(text):
        raise BlocksRejected("markup", where)
    if _NUMBER.search(text) or _PERCENT_WORDS.search(text):
        raise BlocksRejected("free_number", where)
    if "!" in text:
        raise BlocksRejected("exclamation", where)
    if _HUMAN_ACT.search(text):
        raise BlocksRejected("human_act", where)
    if _BANNED.search(text):
        raise BlocksRejected("banned_word", where)


def _segments(
    segs: list[TextSeg | CiteSeg | FactSeg],
    where: str,
    facts: Mapping[str, Fact],
    citations: Set[UUID],
) -> None:
    for i, seg in enumerate(segs):
        at = f"{where}[{i}]"
        if isinstance(seg, TextSeg):
            lint_text(seg.text, at)
        elif isinstance(seg, FactSeg):
            if seg.fact_id not in facts:
                raise BlocksRejected("unknown_fact", at)
        elif seg.citation_id not in citations:
            raise BlocksRejected("unknown_citation", at)


_ADAPTER: Final = TypeAdapter(AgentBlocks)


def validate_blocks(
    payload: object, facts: Mapping[str, Fact], citations: Set[UUID]
) -> AgentBlocks:
    """The payload as AgentBlocks, or `BlocksRejected`: shape first, then every string and
    reference. `facts` is the run's registry; `citations` the run's verified citations."""
    try:
        blocks = _ADAPTER.validate_python(payload)
    except ValidationError as error:
        first = error.errors()[0]
        raise BlocksRejected("shape", ".".join(str(p) for p in first["loc"])) from None
    for n, part in enumerate(blocks.parts):
        at = f"parts[{n}]"
        if isinstance(part, ParagraphPart):
            _segments(part.segments, f"{at}.segments", facts, citations)
        elif isinstance(part, TablePart):
            for i, head in enumerate(part.head):
                lint_text(head, f"{at}.head[{i}]")
            for r, row in enumerate(part.rows):
                _segments(row, f"{at}.rows[{r}]", facts, citations)
        elif isinstance(part, KvPart):
            for r, row in enumerate(part.rows):
                lint_text(row.label, f"{at}.rows[{r}].label")
                _segments(row.value, f"{at}.rows[{r}].value", facts, citations)
        elif isinstance(part, MetricPart):
            lint_text(part.label, f"{at}.label")
            if part.fact_id not in facts:
                raise BlocksRejected("unknown_fact", f"{at}.fact_id")
        elif isinstance(part, FilePart):
            lint_text(part.name, f"{at}.name")
            if part.meta is not None:
                lint_text(part.meta, f"{at}.meta")
        elif isinstance(part, BadgePart):
            if part.code not in STORED.get(part.object, ()):
                raise BlocksRejected("unknown_status", at)
        elif isinstance(part, CiteListPart):
            _segments(list(part.cites), f"{at}.cites", facts, citations)
        elif isinstance(part, OptionsPart):
            if sum(o.recommended for o in part.options) > 1:
                raise BlocksRejected("two_recommended", at)
            for i, option in enumerate(part.options):
                lint_text(option.title, f"{at}.options[{i}].title")
                if option.detail is not None:
                    lint_text(option.detail, f"{at}.options[{i}].detail")
    return blocks


def fact_value(fact: Fact) -> Decimal | str:
    """The registered value: a Decimal for figures, the ISO string for a date."""
    return fact.value if fact.kind == "date" else Decimal(fact.value)


__all__ = [
    "AgentBlocks",
    "AgentPart",
    "BlocksRejected",
    "BlocksTurn",
    "Fact",
    "check_blocks",
    "fact_value",
    "lint_text",
    "validate_blocks",
]


# --- The gateway output check (P-09-T04) -----------------------------------------------------


@dataclass(frozen=True)
class BlocksTurn:
    """A converse() final turn as the check sees it: the payload and what it may reference."""

    payload: object
    facts: Mapping[str, Fact]
    citations: Set[UUID]


def check_blocks(output: object) -> CheckFailure | None:
    """The AgentBlocks output check: None when the turn may be shown."""
    if not isinstance(output, BlocksTurn):
        return CheckFailure("shape", "turn")
    try:
        validate_blocks(output.payload, output.facts, output.citations)
    except BlocksRejected as rejected:
        return CheckFailure(rejected.code, rejected.where)
    return None


register_output_check("agent_blocks", check_blocks)
