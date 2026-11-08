"""N-04-T06 (DEC-2950; ADR P-14, QN-7): the notice's retention record types are known to evidence,
and the letter's own kind is one of them (it was not)."""

from __future__ import annotations

from abacus.modules.evidence.retention import RECORD_TYPES
from abacus.modules.notices.search import KIND
from abacus.modules.notices.sending import RECORD_TYPE


def test_the_notice_and_its_letter_are_retention_record_types() -> None:
    assert {"notice", "notice_response"} <= RECORD_TYPES
    assert RECORD_TYPE in RECORD_TYPES


def test_the_notice_has_a_search_projection() -> None:
    from abacus.modules.notices import api

    assert api.ROUTERS
    from abacus.modules.platform.slots import (
        _PROJECTIONS,  # pyright: ignore[reportPrivateUsage] -- the slot's own registry under test
    )

    assert KIND in _PROJECTIONS
