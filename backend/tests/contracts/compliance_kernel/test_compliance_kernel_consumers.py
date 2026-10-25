"""G-02's consumer view of compliance-kernel v1.1 (Q-02-T38), on the seed's facts (ADM-06 a, c,
d, g; Q-02 §5.1): INC-2026-005, discovered Thu Sep 10, 2026 at 2:14 AM CT, reads "Day 4 of 30"
with notice due Sat Oct 10 on Mon Sep 14 at 9:24 AM CT (E0) and is not a notification event with
0 confirmed; the export history (Sep 1 386 GB, Aug 1 371 GB, Jul 1 359 GB) and Felix Andersen's
request "Waiting for approval · Margaret Okonkwo" fit the stub's models. The same fixtures serve
fixture mode (`apps/web/src/fixtures/seed/compliance.ts`)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from abacus.modules.evidence.firm_export_contract import (
    FirmExportOut,
    FirmExportPageOut,
    FirmExportPersonOut,
)
from abacus.modules.platform.api import CLOCK_DAYS, incident_clock
from abacus.modules.platform.incident_routes import IncidentOut
from abacus.modules.platform.incidents import clock_day, notification_event

CT = ZoneInfo("America/Chicago")
ZONE = "America/Chicago"
E0 = datetime(2026, 9, 14, 9, 24, tzinfo=CT)
DISCOVERED = datetime(2026, 9, 10, 2, 14, tzinfo=CT)
FELIX = FirmExportPersonOut(user_id=uuid.uuid4(), display_name="Felix Andersen")
MARGARET = FirmExportPersonOut(user_id=uuid.uuid4(), display_name="Margaret Okonkwo")
GB = 1000**3


def test_inc_2026_005_reads_day_4_of_30_and_notify_by_oct_10() -> None:
    assert incident_clock(DISCOVERED, ZONE) == date(2026, 10, 10)
    assert clock_day(DISCOVERED, ZONE, E0.date()) == 4
    assert CLOCK_DAYS == 30
    assert notification_event(0, None) is False
    out = IncidentOut(
        id=uuid.uuid4(),
        ref="INC-2026-005",
        title="Credential-stuffing attempts against client portal sign-in",
        event_kind="credential_attack",
        discovered_at=DISCOVERED,
        consumers_affected=0,
        unencrypted=None,
        notification_event=False,
        ftc_notify_by=incident_clock(DISCOVERED, ZONE),
        clock_day=clock_day(DISCOVERED, ZONE, E0.date()),
        clock_days=CLOCK_DAYS,
        source="firm",
        created_at=DISCOVERED.astimezone(UTC),
    )
    assert (out.clock_day, out.clock_days, out.ftc_notify_by.isoformat()) == (4, 30, "2026-10-10")


def _monthly(day: date, size_gb: int) -> FirmExportOut:
    at = datetime(day.year, day.month, day.day, 2, 0, tzinfo=CT)
    return FirmExportOut(
        id=uuid.uuid4(),
        status="expired",  # the 7-day window ended before E0
        scope="all",
        origin="scheduled",
        requested_by=FELIX,
        requested_at=at,
        approver=MARGARET,
        decided_at=at,
        ready_at=at + timedelta(hours=1),
        available_until=at + timedelta(days=7),
        size_bytes=size_gb * GB,
        manifest_sha256="0" * 64,
    )


def test_the_history_and_the_pending_request_fit_the_models() -> None:
    pending = FirmExportOut(
        id=uuid.uuid4(),
        status="awaiting_approval",
        scope="all",
        origin="on_demand",
        requested_by=FELIX,
        requested_at=E0,
        approver=MARGARET,
    )
    page = FirmExportPageOut(
        items=[
            pending,
            _monthly(date(2026, 9, 1), 386),
            _monthly(date(2026, 8, 1), 371),
            _monthly(date(2026, 7, 1), 359),
        ]
    )
    assert page.items[0].approver.display_name == "Margaret Okonkwo"
    assert page.items[0].size_bytes is None and page.items[0].available_until is None
    assert [i.size_bytes for i in page.items[1:]] == [386 * GB, 371 * GB, 359 * GB]
    dumped = page.model_dump(mode="json")
    assert FirmExportPageOut.model_validate(dumped) == page
