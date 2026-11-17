"""G-04-T10: support availability, help grouping and blocks, status merge, the operator's
incident note (SPEC-680 AC-45, AC-50, AC-54, AC-55; DEC-5417)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from abacus.modules.platform import support
from abacus_tools.platform_console import NOTE_MAX, Refused, check_note, check_operator

HOURS = {
    "tz": "America/Chicago",
    "weekly": {"mon": [["08:00", "18:00"]], "tue": [["08:00", "18:00"]]},
}
MON_0924_CT = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)  # 9:24 AM CT
MON_2000_CT = datetime(2026, 9, 15, 1, 0, tzinfo=UTC)  # 8:00 PM CT


def test_ac45_online_inside_hours_with_the_median_after_five_samples() -> None:
    online, minutes, nxt = support.availability(HOURS, MON_0924_CT, [3, 4, 5, 6, 40])
    assert (online, minutes, nxt) == (True, 5, None)
    assert support.availability(HOURS, MON_0924_CT, [3, 4])[1] is None  # under five samples


def test_ac45_offline_after_hours_names_the_next_opening() -> None:
    online, minutes, nxt = support.availability(HOURS, MON_2000_CT, [])
    assert online is False and minutes is None
    assert nxt is not None and (nxt.weekday(), nxt.hour) == (1, 8)


def test_no_hours_on_file_reads_offline() -> None:
    assert support.availability(None, MON_0924_CT, []) == (False, None, None)


def _row(slug: str, group: str, contexts: list[str]) -> dict[str, object]:
    return {"slug": slug, "title": slug.title(), "summary": "s", "group_key": group,
            "read_minutes": 2, "context_screen_ids": contexts}  # fmt: skip


def test_ac50_the_screens_articles_come_first_as_suggested() -> None:
    rows = [_row("seats", "billing", []), _row("closes-plan", "closes", ["CLS-09"])]
    groups = support.help_groups(rows, "CLS-09")  # type: ignore[arg-type] -- dicts stand in for rows
    assert [g.key for g in groups] == ["suggested", "billing"]
    assert groups[0].label == "Suggested"


def test_help_blocks_drop_anything_outside_schema_v1() -> None:
    blocks = support.blocks_of(
        [{"kind": "paragraph", "text": "Hi"}, {"kind": "html", "text": "<b>x</b>"}, "raw"]
    )
    assert [b.kind for b in blocks] == ["paragraph"]


def test_ac54_a_component_shows_the_worse_of_incident_and_own_health() -> None:
    assert support.worse("operational", "needs_attention") == "needs_attention"
    assert support.worse("outage", "needs_attention") == "outage"


def test_ac55_an_incident_note_is_at_most_280_characters() -> None:
    assert check_note("  Delayed syncs  ") == "Delayed syncs"
    with pytest.raises(Refused):
        check_note("x" * (NOTE_MAX + 1))
    with pytest.raises(Refused):
        check_operator("rowan@accrued.example")
