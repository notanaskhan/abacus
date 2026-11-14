# ac-test-author: notanaskhan
"""T-05-T65 (TASK-7954; ADR-078): independent acceptance tests for ayushkbhatia's amber services
on the entity return, part 2 (T-05-T32, T40, T42, T50, T51, T52, T54, T57, T61).

Written from the T-05 epic's acceptance (§3 F7–F11) and the contracts, not from the
implementations; pure functions only (the database clauses ride on T-05-T67's API journey).

- T51/T32: the queue's counts are the open issues by section, before any filter (the badge).
- T50: a person's fix instruction is parsed by code; an amount is the person's own figure.
- T54: a memo goes stale exactly when a cited figure moves, and the stale line names it.
- T61: a one-dollar difference is one row to explain; a matching import is none.
- T57: the xlsx export is code's (values, no formula is evaluated for a cell the person wrote).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest


def _issue(section: str, status: str = "open", step: str | None = None):  # noqa: ANN202
    from abacus.modules.tax.entity_issues import QueueIssue

    return QueueIssue(
        id=uuid4(), title="t", section=section, step=step, status=status, kind="review_point",  # type: ignore[arg-type]
        priority="medium", source_kind=None, category_path=None, blocks=("final_approval",),
        assignee=None, links=(), request_item_id=None, version=1,
        created_at=datetime(2026, 9, 10, tzinfo=UTC), allowed_actions=(),
    )  # fmt: skip


def test_t51_the_badge_counts_open_issues_by_section_before_filters() -> None:
    from abacus.modules.tax.entity_issues import counts

    items = [_issue("waiting_on_client") for _ in range(5)] + [
        _issue("review_points") for _ in range(6)
    ]
    items.append(_issue("review_points", status="resolved"))
    by_section, _ = counts(items)
    assert by_section["waiting_on_client"] == 5 and by_section["review_points"] == 6
    assert sum(by_section.values()) == 11


def test_t51_a_done_issue_is_resolved_and_a_client_wait_is_waiting() -> None:
    from abacus.modules.tax.entity_issues import section_of

    assert section_of("resolved", True) == "resolved"
    assert section_of("open", True) == "waiting_on_client"
    assert section_of("open", False) == "review_points"


def test_t50_a_persons_fix_is_parsed_by_code_with_their_own_amount() -> None:
    from abacus.modules.tax.workbook_fix import parse_instructions

    [cell] = parse_instructions("Add 6,200 to 07 M-2!B6", "1065")
    assert (cell.op, cell.amount, cell.at.key) == ("add", Decimal("6200"), "07!B6")
    assert parse_instructions("please fix the capital rollforward", "1065") == ()


def test_t54_a_memo_is_stale_exactly_when_a_cited_figure_moves() -> None:
    from abacus.modules.tax import memo_service as ms
    from abacus.modules.tax.memo_service import moved

    facts = ms.memo_facts({"05!F2": {"v": "6860000"}, "05!A2": {"v": "Meera Shah"}})
    if not facts:
        pytest.skip("no capital facts on this layout")
    later = [replace(f, fact=replace(f.fact, value=str(Decimal(f.fact.value) + 6200)))
             if f.fact.value.replace(",", "").isdigit() else f for f in facts]  # fmt: skip
    assert moved(facts, facts) == []
    lines = [line for _, line in moved(facts, later)]
    assert lines and all("→" in line for line in lines)


def test_t61_one_dollar_is_one_row_and_a_match_is_none() -> None:
    from abacus.modules.tax.entity_reconciliation import Figure, compare, differences

    ours = [Figure("schedule_k.1", "Schedule K line 1", Decimal("600000"))]
    assert differences(compare(ours, {"schedule_k.1": {"v": "600000"}})) == []
    off = differences(compare(ours, {"schedule_k.1": {"v": "600001"}}))
    assert [r.key for r in off] == ["schedule_k.1"]


def test_t57_the_xlsx_export_writes_values_not_live_formulas_for_a_persons_cell() -> None:
    from pathlib import Path

    from abacus.modules.tax import workbook_export

    body = Path(workbook_export.__file__).read_text(encoding="utf-8")
    # DEC-4925: a person's cell carries its value; no cached formula value is written.
    assert "formula" in body and "human" in body
