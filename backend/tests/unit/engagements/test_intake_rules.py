"""P-07-T42 (TASK-1326): the single intake's pure rules. The dedupe score (DEC-441), each
step's problems (CLI-06 i's `date_of_death_required`), the service grouping (one Prospect
engagement per type and period; Form 56 a line item) and the stored commit answer (identifiers
only)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from abacus.modules.engagements.intake import (
    Committed,
    Problem,
    _groups,  # pyright: ignore[reportPrivateUsage] -- the grouping rule under test
    problems_of,
)
from abacus.modules.organisations.intake import core_name, score_names

PERIOD = {"fiscal_period_start": "2026-01-01", "fiscal_period_end": "2026-12-31"}


def _estate(**entity: object) -> dict[str, object]:
    return {
        "entity": {
            "mode": "existing_client",
            "client_id": str(uuid.uuid4()),
            "entity_name": "Estate of Walter Thornbury",
            "entity_type": "estate",
            **entity,
        },
        "services": [
            {"type_code": "forms_706_709", "forms": ["706"], **PERIOD},
            {"type_code": "form_1041", **PERIOD},
            {"type_code": "form_1040", **PERIOD},
            {"type_code": "form_56"},
        ],
        "engagement_partner_user_id": str(uuid.uuid4()),
    }


@pytest.mark.parametrize(
    ("typed", "stored", "similarity", "score"),
    [
        ("walter thornbury", "walter thornbury", 0.0, 1.0),
        ("estate of walter thornbury", "walter thornbury", 0.6, 0.96),  # CLI-06 b
        ("walter thornbury", "estate of walter thornbury", 0.6, 0.96),
        ("thornbury family trust", "thornbury", 0.4, 0.96),
        ("calloway trust", "calloway", 0.5, 0.98),
        ("harborline partners", "harborline", 0.65, 0.65),
        ("harborline partners", "meridian", 0.1, None),
        ("", "walter thornbury", 0.0, None),
    ],
)
def test_dedupe_score(typed: str, stored: str, similarity: float, score: float | None) -> None:
    assert score_names(typed, stored, similarity) == score


def test_core_name_keeps_a_bare_designator() -> None:
    assert core_name("estate of walter thornbury") == ("walter thornbury", 2)
    assert core_name("trust") == ("trust", 0)  # never empties a name


def test_form_706_needs_the_date_of_death() -> None:
    assert Problem("entity.date_of_death", "date_of_death_required") in problems_of(
        _estate(), "services"
    )
    assert problems_of(_estate(date_of_death="2026-03-14"), "services") == []


def test_each_step_reports_codes() -> None:
    assert problems_of({}, "entity") == [
        Problem("entity.mode", "required"),
        Problem("entity.entity_type", "required"),
    ]
    p = _estate(entity_type="spaceship", date_of_death="2026-03-14")
    p["relationships"] = [{"kind": "cousin_of", "related_entity_id": str(uuid.uuid4())}]
    p["contacts"] = [{"display_name": "Paul Thornbury", "roles": ["executor", "wizard"]}]
    assert problems_of(p, "entity") == [Problem("entity.entity_type", "unknown_code")]
    assert problems_of(p, "relationships") == [Problem("relationships.0.kind", "unknown_code")]
    assert problems_of(p, "contacts") == [Problem("contacts.0.roles", "unknown_code")]
    p["services"] = [{"type_code": "single_audit", **PERIOD}, {"type_code": "form_1040"}]
    assert problems_of(p, "services") == [
        Problem("services.0.type_code", "unknown_engagement_type"),
        Problem("services.1.fiscal_period_start", "required"),
        Problem("services.1.fiscal_period_end", "required"),
    ]
    p["services"] = [{"type_code": "form_1040", "forms": ["1120"], **PERIOD}]
    p.pop("engagement_partner_user_id")
    assert problems_of(p, "services") == [
        Problem("services.0.forms", "unknown_code"),
        Problem("engagement_partner_user_id", "required"),
    ]
    p["services"] = []
    assert problems_of(p, "services") == [Problem("services", "required")]


def test_the_estate_is_one_engagement_with_three_returns() -> None:
    groups = _groups(_estate(date_of_death="2026-03-14"))
    assert list(groups) == [("tax_compliance", "tax", date(2026, 1, 1), date(2026, 12, 31))]
    forms = [f for _, fs in next(iter(groups.values())) for f in fs]
    assert forms == ["706", "1041", "1040"]


def test_the_stored_answer_round_trips_identifiers_only() -> None:
    ids = [uuid.uuid4() for _ in range(5)]
    done = Committed(ids[0], ids[1], ids[2], [ids[3]], "prospect", [ids[4]], None, None)
    stored = done.stored()
    assert all(isinstance(v, (str, list, type(None))) for v in stored.values())
    assert Committed.from_stored(stored) == done
