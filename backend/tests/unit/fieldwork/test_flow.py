"""SPEC-040 (TASK-100): the request's wording, stale sign-offs, and who may approve or sign."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from abacus.modules.fieldwork.flow import current_signoffs, initials, selection_wording
from abacus.modules.fieldwork.models import ItemResult, ItemSignoff
from abacus.modules.identity.authz.matrix import RULES

FIRM = ("engagement_partner", "manager", "senior", "staff", "reviewer")


def _allowed(action: str) -> set[str]:
    return {r for r in FIRM if RULES[action].decisions.get(r) == "allow"}


def test_ac1_only_a_manager_or_the_partner_approves_the_sample() -> None:
    assert _allowed("sample.approve") == {"engagement_partner", "manager"}
    assert RULES["sample.approve"].decisions.get("agent") == "deny"
    assert RULES["sample.approve"].independence


def test_ac6_preparers_are_staff_senior_or_manager_never_the_partner_or_eqr() -> None:
    assert _allowed("item.sign_prepared") == {"staff", "senior", "manager"}
    assert RULES["item.sign_prepared"].decisions.get("agent") == "deny"


def test_ac7_reviewers_are_senior_manager_or_partner_never_the_eqr() -> None:
    assert _allowed("item.sign_reviewed") == {"senior", "manager", "engagement_partner"}
    assert RULES["item.sign_reviewed"].decisions.get("agent") == "deny"


def test_ac4_one_request_lists_date_reference_and_amount_within_the_limit() -> None:
    lines = [(f"2026-12-{d:02d}", f"JE-{d}", f"{d * 1000:,.2f}") for d in range(1, 29)]
    wording = selection_wording(lines, len(lines))
    assert "2026-12-01 · JE-1 · 1,000.00" in wording
    assert len(wording) <= 2000
    assert wording.count("JE-") == 28  # all fit
    assert not wording.endswith("more")


def test_ac4_beyond_the_limit_it_counts_the_rest() -> None:
    lines = [("2026-12-31", f"JE-{n:05d}", "123,456.78") for n in range(300)]
    wording = selection_wording(lines, len(lines))
    assert len(wording) <= 2000
    assert wording.endswith("more")
    shown = wording.count("JE-")
    assert wording.endswith(f"and {300 - shown} more")


def test_ac8_a_signoff_on_an_older_result_is_stale() -> None:
    item = uuid.uuid4()
    old, new = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    results = {item: cast(ItemResult, SimpleNamespace(id=new, selected_item_id=item))}
    signoffs = [
        cast(
            ItemSignoff,
            SimpleNamespace(
                selected_item_id=item, item_result_id=old, level="prepared", created_at=now
            ),
        )
    ]
    assert current_signoffs(signoffs, results, "prepared") == {}
    fresh = cast(
        ItemSignoff,
        SimpleNamespace(
            selected_item_id=item, item_result_id=new, level="prepared", created_at=now
        ),
    )
    assert set(current_signoffs([*signoffs, fresh], results, "prepared")) == {item}
    assert current_signoffs([fresh], results, "reviewed") == {}


def test_ac12_initials() -> None:
    assert initials("Dana Leader") == "DL"
    assert initials("sam") == "S"
    assert initials("") == "?"
