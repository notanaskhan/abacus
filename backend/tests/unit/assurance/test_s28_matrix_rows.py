"""S28 (TASK-3400, DEC-2399): AUD-17's groups as the handoff draws them, and the three rows that
weren't reviewables (Materiality, Findings, Completion Checklist) hashed from their records."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.assurance import completion_reviewables as rows
from abacus.modules.assurance import review_matrix
from abacus.modules.workpapers.service import section_of


@pytest.mark.parametrize(
    ("kind", "area", "section"),
    [
        ("risk_assessment", None, "planning"),
        ("service_organizations", None, "planning"),
        ("general_audit_planning", None, "planning"),
        ("ebp_form5500", None, "fieldwork"),  # drawn under Fieldwork & Testing
        ("ebp_contributions", "Completion", "fieldwork"),  # a kind wins over its area
        (None, "Completion", "completion"),
        (None, " reporting ", "reporting"),
        (None, "Payroll", "fieldwork"),
        (None, None, "fieldwork"),
    ],
)
def test_ac_a_paper_sits_in_its_drawn_group(
    kind: str | None, area: str | None, section: str
) -> None:
    assert section_of(kind, area) == section


def test_ac_engagement_level_rows_sit_in_their_drawn_groups() -> None:
    of = review_matrix._SECTION_OF  # pyright: ignore[reportPrivateUsage] -- the table under test
    assert of["trial_balance"] == "planning"
    assert of["materiality"] == "planning"
    assert of["fs_package"] == "reporting"
    assert "sum_schedule" not in of  # Completion, the default


def test_ac_a_changed_materiality_figure_changes_its_hash() -> None:
    base = {
        "version_no": 3,
        "status": "decided",
        "overall": Decimal("252200"),
        "pm": None,
        "ct": None,
    }
    same = rows._materiality_hash(dict(base))  # pyright: ignore[reportPrivateUsage] -- the unit under test
    moved = rows._materiality_hash({**base, "overall": Decimal("252300")})  # pyright: ignore[reportPrivateUsage] -- the unit under test
    assert same == rows._materiality_hash(dict(base)) and same != moved  # pyright: ignore[reportPrivateUsage] -- the unit under test


def test_ac_a_finding_moving_or_a_checklist_item_closing_changes_the_hash() -> None:
    finding: dict[str, object] = {
        "ref": "F-01",
        "kind": "control_deficiency",
        "route": "under_evaluation",
        "evaluation": {},
        "version": 1,
    }
    before = rows._findings_hash([finding])  # pyright: ignore[reportPrivateUsage] -- the unit under test
    after = rows._findings_hash([{**finding, "route": "deficiency"}])  # pyright: ignore[reportPrivateUsage] -- the unit under test
    assert before != after
    item: dict[str, object] = {
        "item_key": "subsequent_events",
        "status": "open",
        "evidence_text": None,
    }
    assert rows._checklist_hash([item]) != rows._checklist_hash([{**item, "status": "done"}])  # pyright: ignore[reportPrivateUsage] -- the unit under test


def test_ac_the_three_kinds_are_registered_reviewables() -> None:
    import abacus.modules.assurance.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers them
    from abacus.modules.review.api import reviewable_fact_types

    assert {rows.MATERIALITY, rows.FINDINGS, rows.CHECKLIST} <= set(reviewable_fact_types())
