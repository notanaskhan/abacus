"""T-08-T10 (S51 partials, TASK-8741; DEC-5732; AC-16): the ics export is RFC 5545 all-day events
with client content escaped so no line break or separator starts a property of its own."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from abacus.modules.practice.deadlines_service import Row, ics, ics_text


def _row(client: object) -> Row:
    return Row(
        uuid4(), "tax_return", client, "Form 1040 · 2025", date(2026, 4, 15), None, None,  # type: ignore[arg-type]  # a stand-in id
        date(2026, 4, 15), None, "preparing", False, (), None, None, None, "tax", (),
        datetime(2026, 4, 1, tzinfo=UTC),
    )  # fmt: skip


def test_ac_client_text_never_breaks_out_of_its_property() -> None:
    assert ics_text("Ab, Inc.;x\r\nATTENDEE:evil") == "Ab\\, Inc.\\;x\\nATTENDEE:evil"
    client = uuid4()
    body = ics([_row(client)], {client: "Feld\nATTENDEE:mallory"}).decode()
    assert "\nATTENDEE" not in body
    assert "DTSTART;VALUE=DATE:20260415" in body and "DTEND;VALUE=DATE:20260416" in body
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
