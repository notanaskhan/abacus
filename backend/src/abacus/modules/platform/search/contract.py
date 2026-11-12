"""C15 v1, the HTTP contract: `POST /v1/search` and the recents routes (P-02-T01; P-02 §4.3).
Contract: `docs/contracts/c15-search.md`. ADR-241 (P-33) binds.

Search text travels only in the POST body (ADR-241 decision 7): `SearchQueryIn.q` is trimmed,
stripped of control and bidi characters, and must be 1-100 characters after that. There is no
`hidden_by_wall` field anywhere, and `total_visible` counts only rows the viewer could open
(capped at 99; DEC-43).

Classification (ADR-031): titles, context lines, related names, the suggestion and the query text
are `confidential`; identifiers, codes, dates, counts and match ranges `internal`. Nothing here is
Restricted: a search document is metadata only.
"""

from __future__ import annotations

import unicodedata
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from abacus.kernel.classification import classified
from abacus.modules.platform.search.spec import SearchGroup

Q_MAX = 100
TOTAL_VISIBLE_CAP = 99
ObjectType = Annotated[str, Field(pattern=r"^[a-z][a-z_]{1,39}$")]
ScreenId = Annotated[str, Field(pattern=r"^[A-Z]{2,4}-\d{2}$")]
# Bidi embeddings, overrides and isolates (U+202A-202E, U+2066-2069), plus every control
# character (Unicode category Cc and Cf), are dropped from search text (ADR-052).
_BIDI = frozenset(chr(c) for c in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)))


def clean_query(raw: str) -> str:
    """Search text as the server matches it: control, format and bidi characters dropped, runs of
    whitespace collapsed, trimmed."""
    kept = (
        " " if ch.isspace() else ch
        for ch in raw
        if ch not in _BIDI and (ch.isspace() or unicodedata.category(ch) not in ("Cc", "Cf"))
    )
    return " ".join("".join(kept).split())


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class SearchContextIn(BaseModel):
    """The record the palette was opened on, for context-bound actions ("New to-do on …")."""

    model_config = _frozen()
    object_type: Annotated[ObjectType, classified("internal")]
    object_id: Annotated[UUID, classified("internal")]


class SearchQueryIn(BaseModel):
    """`POST /v1/search`. `types: ["agents"]` with an empty `q` lists installed agents (`>` mode,
    served only with `search.agent_mode` on); any other query needs 1-100 characters."""

    model_config = _frozen()
    q: Annotated[str, Field(max_length=400), classified("confidential")]
    types: Annotated[
        list[SearchGroup] | None, Field(min_length=1, max_length=11), classified("internal")
    ] = None
    limit_per_group: Annotated[int, Field(ge=1, le=10), classified("internal")] = 5
    context: Annotated[SearchContextIn | None, classified("internal")] = None

    @field_validator("q")
    @classmethod
    def _clean(cls, value: str) -> str:
        cleaned = clean_query(value)
        if len(cleaned) > Q_MAX:
            raise ValueError("q_invalid")
        return cleaned


class SearchStatusOut(BaseModel):
    """The owner's C2 status, as `{code, context}`; the words come from `status.ts`."""

    model_config = _frozen()
    code: Annotated[str, classified("internal")]
    context: Annotated[str | None, classified("internal")] = None


class SearchTargetOut(BaseModel):
    """Where a row opens: a manifest screen and its identifier-only parameters."""

    model_config = _frozen()
    screen_id: Annotated[ScreenId, classified("internal")]
    params: Annotated[dict[str, str], classified("internal")]


MatchRange = tuple[int, int]


class SearchItemOut(BaseModel):
    """One result row (or one recent). `match_ranges` are `[start, end)` offsets into `title`."""

    model_config = _frozen()
    object_type: Annotated[ObjectType, classified("internal")]
    object_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("confidential")]
    context: Annotated[str | None, classified("confidential")] = None
    status: Annotated[SearchStatusOut | None, classified("internal")] = None
    due_on: Annotated[date | None, classified("internal")] = None
    tag: Annotated[str | None, classified("internal")] = None
    use_count: Annotated[int | None, Field(ge=0), classified("internal")] = None
    target: Annotated[SearchTargetOut, classified("internal")]
    match_ranges: Annotated[list[MatchRange], classified("internal")] = Field(default_factory=list)


class SearchGroupOut(BaseModel):
    """One canonical group; a group with no rows is omitted, never sent empty."""

    model_config = _frozen()
    group: Annotated[SearchGroup, classified("internal")]
    items: Annotated[list[SearchItemOut], Field(min_length=1), classified("confidential")]
    has_more: Annotated[bool, classified("internal")]


class SearchSuggestionOut(BaseModel):
    """ "Did you mean …?" over visible documents only, sent only when every group is empty."""

    model_config = _frozen()
    title: Annotated[str, classified("confidential")]
    context: Annotated[str | None, classified("confidential")] = None
    target: Annotated[SearchTargetOut, classified("internal")]


class SearchResultsOut(BaseModel):
    """`POST /v1/search`. No field names, counts or hints at a row the viewer cannot open."""

    model_config = _frozen()
    groups: Annotated[list[SearchGroupOut], classified("confidential")]
    suggestion: Annotated[SearchSuggestionOut | None, classified("confidential")] = None
    total_visible: Annotated[int, Field(ge=0, le=TOTAL_VISIBLE_CAP), classified("internal")]


class SearchRecentsOut(BaseModel):
    """`GET /v1/search/recents`: the viewer's own, newest first, re-filtered by `visible()`."""

    model_config = _frozen()
    items: Annotated[list[SearchItemOut], Field(max_length=10), classified("confidential")]


class SearchRecentIn(BaseModel):
    """`POST /v1/search/recents`: a record route loaded; identifiers only."""

    model_config = _frozen()
    object_type: Annotated[ObjectType, classified("internal")]
    object_id: Annotated[UUID, classified("internal")]


class SearchRecentRecordedOut(BaseModel):
    """`POST /v1/search/recents`: the record, now first in the viewer's recents."""

    model_config = _frozen()
    object_type: Annotated[ObjectType, classified("internal")]
    object_id: Annotated[UUID, classified("internal")]


RecentsLimit = Annotated[int, Field(ge=1, le=10)]
SearchErrorCode = Literal["q_invalid", "rate_limited", "search_unavailable"]
