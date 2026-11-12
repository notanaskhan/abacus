"""C15's fixed error codes (P-02 §4.3; ADR-139). Facts are identifiers only, and never the search
text (ADR-241 decision 7)."""

from __future__ import annotations

from abacus.kernel.errors import DomainInvalid, DomainRateLimited, DomainUnavailable


class SearchQueryInvalid(DomainInvalid):
    """422: the search text is empty or over 100 characters after cleaning, outside agent mode."""

    code = "q_invalid"


class SearchRateLimited(DomainRateLimited):
    """429: over the person's search budget (10 a second, burst 20)."""

    code = "rate_limited"


class SearchUnavailable(DomainUnavailable):
    """503: the query hit its 1 s statement timeout or the index is unreachable."""

    code = "search_unavailable"
