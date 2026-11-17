"""C-01-T26: the closes registrations (C13 gates, HOME-01 tile, C15, C16, KNW-04, portal home)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

import abacus.api.app  # noqa: F401  # pyright: ignore[reportUnusedImport] -- every module registers at import
from abacus.modules.closes import registrations as r


def test_home_tile_reads_eleven_of_twenty_two() -> None:
    """HOME-01 "Closes 11 of 22 · August 2026": 22 = 3 + 11 + 5 + 3 on CLS-01's tiles."""
    statuses = ["not_started"] * 3 + ["in_progress"] * 11 + ["in_review"] * 4 + ["approved"]
    statuses += ["delivered"] * 2 + ["locked"]
    tiles = r.tile_counts(statuses)
    assert tiles == {"not_started": 3, "in_progress": 11, "in_review": 5, "delivered": 3}
    assert sum(tiles.values()) == 22


@pytest.mark.parametrize(
    ("on", "period"), [(date(2026, 9, 14), "2026-08"), (date(2027, 1, 4), "2026-12")]
)
def test_the_tile_counts_the_month_being_closed(on: date, period: str) -> None:
    assert r.closing_period(on) == period
    assert r.month_label("2026-08") == "August 2026"


def test_only_a_close_run_is_a_closes_run() -> None:
    close = UUID(int=7)
    assert r._close_id(f"close:{close}") == close  # pyright: ignore[reportPrivateUsage] -- unit
    assert r._close_id("tax_return:x") is None  # pyright: ignore[reportPrivateUsage] -- unit
    assert r._close_id(None) is None  # pyright: ignore[reportPrivateUsage] -- unit


def test_gates_home_count_and_search_are_registered() -> None:
    from abacus.modules.platform.api import home_count_keys
    from abacus.modules.platform.search.spec import projection
    from abacus.modules.review.gates import gate_sources

    subjects = {s.subject_type: s for s in gate_sources()}
    assert subjects[r.FLUX_GATE].kind == "proposal"
    assert subjects[r.RECON_GATE].kind == "sign_off_request"
    assert "closes" in home_count_keys()
    found = projection("close")
    assert found is not None and found.target == "CLS-02" and found.group == "closes"


def test_c16_close_kinds_store_identifiers_only() -> None:
    """DEC-61: each kind names its subject by id; the text is the catalogue's, at read."""
    from abacus.modules.notifications.api import CATALOGUE, TEMPLATES

    wanted = {
        "close_run.finished": "close_run_finished",
        "close_run.needs_input": "close_run_needs_input",
        "close_plan.publish_requested": "close_plan_publish_requested",
        "close_question.answered": "transaction_question_answered",
        "close_requests.published": "close_requests_published",
    }
    for event, code in wanted.items():
        assert CATALOGUE[event].kind == code
        assert CATALOGUE[event].subject_key in {"close_id", "plan_id"}
        assert event in TEMPLATES


def test_the_portal_home_loads_the_closes_source() -> None:
    from abacus.modules.portal.home_sources import home_sources

    assert "closes" in dict(home_sources())


def test_knw04_has_the_closes_examples_provider() -> None:
    from abacus.modules.methodology.standards import (
        _EXAMPLES,  # pyright: ignore[reportPrivateUsage] -- the registry under test
    )

    assert _EXAMPLES["aje_thresholds"] is r.aje_examples
