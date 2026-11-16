"""A-08-T18: the confirmation follow-up by code (C4 reaches alternative procedures after its
second request, never Closed) and the reconciliation's content hash."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

from abacus.modules.assurance.confirmations_lifecycle import content_hash, follow_up_step

SENT = datetime(2026, 2, 2, 15, tzinfo=UTC)


def test_ac_c4_reaches_alternative_procedures_after_its_second_request() -> None:
    events = [("sent", SENT)]
    assert follow_up_step(events, "sent", SENT + timedelta(days=6)) is None
    assert follow_up_step(events, "sent", SENT + timedelta(days=7)) == "second_request"
    events.append(("second_request", SENT + timedelta(days=7)))
    assert follow_up_step(events, "sent", SENT + timedelta(days=13)) is None
    assert follow_up_step(events, "sent", SENT + timedelta(days=14)) == "alternative_procedures"


def test_a_response_or_a_later_status_stops_the_follow_up() -> None:
    events = [("sent", SENT), ("responded", SENT + timedelta(days=3))]
    assert follow_up_step(events, "sent", SENT + timedelta(days=30)) is None
    assert follow_up_step([("sent", SENT)], "responded", SENT + timedelta(days=30)) is None
    assert follow_up_step([("sent", SENT)], "closed", SENT + timedelta(days=30)) is None


def test_the_content_hash_moves_with_any_item() -> None:
    a = content_hash(D("125000.00"), D("118400.00"), [("Payment in transit", D("-6600.00"))])
    b = content_hash(D("125000.00"), D("118400.00"), [("Payment in transit", D("-6600.00"))])
    c = content_hash(D("125000.00"), D("118400.00"), [("Payment in transit", D("-6500.00"))])
    assert a == b != c and len(a) == 64
