# ac-test-author: ayushkbhatia
"""Q-02-T46 (TASK-1455): independent AC tests (ADR-078) for the incident register, Q-02 AC-38 and
AC-39 (SPEC-341 story 9; I-CLOCKS).

I-CLOCKS: an incident discovered Thu Sep 10, 2026 is due for FTC notice on Sat Oct 10, 2026 (30
calendar days, counted from the discovery date in the firm's time zone, no business-day roll); it
is a notification event only for unencrypted data of 500 or more consumers, and unknown counts
are not (yet) an event; on Mon Sep 14 the clock reads day 4 of 30; a discovery in the future is
refused. Propagation: an Accrued-side incident lands in each named firm's register with
`source = 'accrued'`, Accrued's facts, `dpa_notice_at` within 72 hours of Accrued's confirmation,
the system as actor and an `incident_from_accrued` notice queued; a repeat with changed facts is
refused and writes nothing.

Boundary: `create_app()` over HTTP for `POST /v1/firm/security/incidents`; the public
`platform.api.propagate_into` step (the contract's §7 internal API, what the staff route's
workflow runs per firm); the register, audit and outbox rows read as the superuser. Expectations:
Q-02 §3.9, SPEC-341 AC-38/AC-39 and §12, `docs/contracts/security-incidents.md` v0.1 (its 403
for a role refusal, DEC-290's reference and recipients). Each probe returns what it found wrong;
`test_seeded_*` feed it planted violations (a rolled date, a UTC date, a 499 event, changed facts,
a late notice) and require it to catch each, so the suite cannot pass by construction.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Final, cast
from zoneinfo import ZoneInfo

import pytest

from abacus.kernel import clock
from abacus.kernel.flags import forget_flags
from abacus.modules.platform.api import (
    IncidentFactsChanged,
    IncidentFactsInput,
    IncidentPropagationStep,
    propagate_into,
)

from .support import Net, Person, Seeder

Json = dict[str, object]
CHICAGO: Final = "America/Chicago"
PACIFIC: Final = "America/Los_Angeles"
INCIDENTS: Final = "/v1/firm/security/incidents"
# Thu Sep 10, 2026 2:14 AM CT (the seed's INC-2026-005 discovery).
DISCOVERED: Final = datetime(2026, 9, 10, 2, 14, tzinfo=ZoneInfo(CHICAGO))
DUE: Final = date(2026, 10, 10)  # Sat Oct 10, 2026: never rolled to Monday
MON_SEP_14: Final = datetime(2026, 9, 14, 9, 24, tzinfo=ZoneInfo(CHICAGO))
DPA_WINDOW: Final = timedelta(hours=72)


@pytest.fixture(autouse=True)
def _flags() -> Iterator[None]:
    forget_flags()
    yield
    forget_flags()


async def _firm(seed: Seeder, *, zone: str = CHICAGO, flag: bool = True) -> uuid.UUID:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET time_zone = $2 WHERE tenant_id = $1", tenant, zone)
    if flag:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, 'compliance.incidents', 'true', 'test-seed', 'Q-02-T46')",
            tenant,
        )
    return tenant


async def _qi(seed: Seeder, tenant: uuid.UUID) -> Person:
    """The firm's Qualified Individual: its security admin."""
    return await seed.person(tenant, "security_admin")


def _incident(
    discovered: datetime, consumers: int | None, unencrypted: bool | None, title: str = "Probe"
) -> Json:
    return {
        "title": title,
        "event_kind": "credential_attack",
        "discovered_at": discovered.isoformat(),
        "consumers_affected": consumers,
        "unencrypted": unencrypted,
    }


async def _record(net: Net, qi: Person, body: Json) -> Json:
    response = await net.call("POST", INCIDENTS, qi, body=body)
    assert response.status_code == 201, response.text
    return cast(Json, response.json())


# --- probes --------------------------------------------------------------------------------------


def clock_problems(incident: Mapping[str, object], zone: str) -> list[str]:
    """What breaks I-CLOCKS in one register entry, recomputed from its own facts (AC-38)."""
    found: list[str] = []
    discovered = datetime.fromisoformat(str(incident["discovered_at"]))
    local = discovered.astimezone(ZoneInfo(zone)).date()
    expected_due = local + timedelta(days=30)
    if str(incident["ftc_notify_by"]) != expected_due.isoformat():
        found.append(f"ftc_notify_by {incident['ftc_notify_by']} != {expected_due}")
    consumers = incident.get("consumers_affected")
    unencrypted = incident.get("unencrypted")
    event = unencrypted is True and isinstance(consumers, int) and consumers >= 500
    if incident["notification_event"] is not event:
        found.append(f"notification_event {incident['notification_event']} != {event}")
    if "clock_days" in incident and incident["clock_days"] != 30:
        found.append(f"clock_days {incident['clock_days']} != 30")
    return found


def propagation_problems(
    entry: Mapping[str, object], facts: IncidentFactsInput, accrued_ref: str, zone: str
) -> list[str]:
    """What an Accrued entry in one firm's register gets wrong against Accrued's facts (AC-39)."""
    found: list[str] = []
    if entry["source"] != "accrued":
        found.append(f"source {entry['source']!r}")
    if entry["accrued_ref"] != accrued_ref:
        found.append(f"accrued_ref {entry['accrued_ref']!r}")
    for field in ("title", "event_kind", "consumers_affected", "unencrypted"):
        if entry[field] != getattr(facts, field):
            found.append(f"{field} {entry[field]!r} is not Accrued's {getattr(facts, field)!r}")
    discovered = cast(datetime, entry["discovered_at"])
    if discovered != datetime.fromisoformat(facts.discovered_at):
        found.append("discovered_at is not Accrued's")
    confirmed = datetime.fromisoformat(facts.confirmed_at)
    if entry["accrued_confirmed_at"] != confirmed:
        found.append("accrued_confirmed_at is not Accrued's")
    notice = entry["dpa_notice_at"]
    if not isinstance(notice, datetime) or not confirmed <= notice <= confirmed + DPA_WINDOW:
        found.append(f"dpa_notice_at {notice} not within 72 hours of {confirmed}")
    found += clock_problems({**entry, "discovered_at": discovered.isoformat()}, zone)
    return found


# --- AC-38: the FTC clock (I-CLOCKS) -------------------------------------------------------------


async def test_ac38_sep_10_with_600_unencrypted_is_an_event_due_sat_oct_10(net: Net) -> None:
    tenant = await _firm(net.seed)
    qi = await _qi(net.seed, tenant)
    body = await _record(net, qi, _incident(DISCOVERED, 600, True, "Credential stuffing"))
    assert body["notification_event"] is True
    assert body["ftc_notify_by"] == DUE.isoformat()
    assert body["clock_days"] == 30
    assert body["source"] == "firm"
    assert str(body["ref"]).startswith("INC-2026-")
    assert clock_problems(body, CHICAGO) == []


@pytest.mark.parametrize(
    ("consumers", "unencrypted", "event"),
    [
        (499, True, False),  # one short of the rule
        (500, True, True),  # the rule's own threshold: 500 or more
        (600, False, False),  # encrypted data is not an event
        (None, True, False),  # unknown counts are not (yet) an event
        (600, None, False),  # unknown encryption is not (yet) an event
    ],
)
async def test_ac38_the_500_consumer_rule(
    net: Net, consumers: int | None, unencrypted: bool | None, event: bool
) -> None:
    tenant = await _firm(net.seed)
    qi = await _qi(net.seed, tenant)
    body = await _record(net, qi, _incident(DISCOVERED, consumers, unencrypted))
    assert body["notification_event"] is event
    assert body["ftc_notify_by"] == DUE.isoformat()  # the date never depends on the event
    assert clock_problems(body, CHICAGO) == []


async def test_ac38_on_mon_sep_14_the_clock_reads_day_4_of_30(net: Net) -> None:
    tenant = await _firm(net.seed)
    qi = await _qi(net.seed, tenant)
    with clock.frozen(MON_SEP_14):
        body = await _record(net, qi, _incident(DISCOVERED, 0, True))
    assert (body["clock_day"], body["clock_days"]) == (4, 30)
    assert body["ftc_notify_by"] == DUE.isoformat()


async def test_ac38_days_are_counted_from_the_discovery_date_in_the_firms_zone(net: Net) -> None:
    # 10:30 PM on Thu Sep 10 in a Pacific firm is already Sep 11 in UTC: the firm's date counts.
    tenant = await _firm(net.seed, zone=PACIFIC)
    qi = await _qi(net.seed, tenant)
    late_evening = datetime(2026, 9, 11, 5, 30, tzinfo=UTC)
    body = await _record(net, qi, _incident(late_evening, 600, True))
    assert body["ftc_notify_by"] == DUE.isoformat()
    assert clock_problems(body, PACIFIC) == []


async def test_ac38_a_discovery_in_the_future_is_refused(net: Net) -> None:
    tenant = await _firm(net.seed)
    qi = await _qi(net.seed, tenant)
    with clock.frozen(MON_SEP_14):
        response = await net.call(
            "POST", INCIDENTS, qi, body=_incident(MON_SEP_14 + timedelta(days=1), 600, True)
        )
    assert response.status_code == 422, response.text
    assert cast(Json, response.json())["detail"] == "discovered_in_future"
    count = await net.seed.value(
        "SELECT count(*) FROM security_incidents WHERE tenant_id = $1", tenant
    )
    assert count == 0


async def test_ac38_only_the_qi_records_and_it_is_audited_by_name(net: Net) -> None:
    tenant = await _firm(net.seed)
    qi = await _qi(net.seed, tenant)
    for role in ("firm_admin", None):
        other = await net.seed.person(tenant, role)
        refused = await net.call("POST", INCIDENTS, other, body=_incident(DISCOVERED, 600, True))
        assert refused.status_code == 403, (role, refused.text)
    body = await _record(net, qi, _incident(DISCOVERED, 600, True))
    rows = await net.seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'incident.recorded'",
        tenant,
    )
    assert [(r["actor_kind"], r["actor_id"]) for r in rows] == [("human", str(qi.user_id))]
    outbox = await net.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'incident.recorded'",
        tenant,
    )
    assert outbox == 1
    assert body["id"]


async def test_ac38_the_register_is_behind_its_flag_and_another_firm_gets_404(net: Net) -> None:
    off = await _firm(net.seed, flag=False)
    qi_off = await _qi(net.seed, off)
    response = await net.call("POST", INCIDENTS, qi_off, body=_incident(DISCOVERED, 600, True))
    assert response.status_code == 404, response.text
    # A QI of firm A naming firm B by header reaches nothing in firm B.
    on = await _firm(net.seed)
    response = await net.call(
        "POST", INCIDENTS, qi_off, body=_incident(DISCOVERED, 600, True), tenant=on
    )
    assert response.status_code in (401, 403, 404), response.text
    count = await net.seed.value(
        "SELECT count(*) FROM security_incidents WHERE tenant_id = $1", on
    )
    assert count == 0


# --- AC-39: propagation of an Accrued incident with Accrued's facts ------------------------------


def _accrued(confirmed: datetime, consumers: int = 750) -> IncidentFactsInput:
    return IncidentFactsInput(
        title="Accrued storage misconfiguration",
        event_kind="data_exposure",
        discovered_at=DISCOVERED.isoformat(),
        consumers_affected=consumers,
        unencrypted=True,
        confirmed_at=confirmed.isoformat(),
    )


async def _entries(seed: Seeder, tenant: uuid.UUID, accrued_ref: str) -> list[Json]:
    rows = await seed.rows(
        "SELECT * FROM security_incidents WHERE tenant_id = $1 AND accrued_ref = $2",
        tenant,
        accrued_ref,
    )
    return [dict(r) for r in rows]


async def test_ac39_each_affected_firm_gets_accrueds_facts_as_the_system(net: Net) -> None:
    firms = [await _firm(net.seed), await _firm(net.seed, zone=PACIFIC), await _firm(net.seed)]
    zones = [CHICAGO, PACIFIC, CHICAGO]
    accrued_ref = f"ACC-2026-{uuid.uuid4().hex[:6]}"
    confirmed = datetime.now(UTC) - timedelta(hours=1)
    facts = _accrued(confirmed)
    staff, reason = str(uuid.uuid4()), "b" * 64
    for tenant in firms:
        await propagate_into(
            IncidentPropagationStep(accrued_ref, str(tenant), facts, staff, reason)
        )
    for tenant, zone in zip(firms, zones, strict=True):
        entries = await _entries(net.seed, tenant, accrued_ref)
        assert len(entries) == 1, tenant
        assert propagation_problems(entries[0], facts, accrued_ref, zone) == []
        assert entries[0]["notification_event"] is True
        audit = await net.seed.rows(
            "SELECT actor_kind FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'incident.propagated'",
            tenant,
        )
        assert [a["actor_kind"] for a in audit] == ["system"]
        notices = await net.seed.value(
            "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
            "AND event_type = 'incident.propagated'",
            tenant,
        )
        assert notices == 1  # -> `incident_from_accrued` to the QI (contract §6)
    untouched = await _firm(net.seed)
    assert await _entries(net.seed, untouched, accrued_ref) == []


async def test_ac39_a_repeat_with_the_same_facts_writes_nothing_more(net: Net) -> None:
    tenant = await _firm(net.seed)
    accrued_ref = f"ACC-2026-{uuid.uuid4().hex[:6]}"
    facts = _accrued(datetime.now(UTC) - timedelta(hours=2))
    step = IncidentPropagationStep(accrued_ref, str(tenant), facts, str(uuid.uuid4()), "c" * 64)
    await propagate_into(step)
    await propagate_into(step)
    assert len(await _entries(net.seed, tenant, accrued_ref)) == 1


async def test_ac39_a_repeat_with_changed_facts_is_refused_and_nothing_is_written(
    net: Net,
) -> None:
    tenant = await _firm(net.seed)
    accrued_ref = f"ACC-2026-{uuid.uuid4().hex[:6]}"
    confirmed = datetime.now(UTC) - timedelta(hours=2)
    staff = str(uuid.uuid4())
    await propagate_into(
        IncidentPropagationStep(accrued_ref, str(tenant), _accrued(confirmed), staff, "d" * 64)
    )
    before = await _entries(net.seed, tenant, accrued_ref)
    changed = _accrued(confirmed, consumers=10)
    with pytest.raises(IncidentFactsChanged):
        await propagate_into(
            IncidentPropagationStep(accrued_ref, str(tenant), changed, staff, "d" * 64)
        )
    assert await _entries(net.seed, tenant, accrued_ref) == before


# --- the probes catch planted violations ---------------------------------------------------------


async def test_seeded_clock_violations_are_caught(net: Net) -> None:
    tenant = await _firm(net.seed)
    qi = await _qi(net.seed, tenant)
    real = await _record(net, qi, _incident(DISCOVERED, 499, True))
    assert clock_problems(real, CHICAGO) == []
    planted = [
        {**real, "ftc_notify_by": "2026-10-12"},  # a business-day roll to Monday
        {**real, "ftc_notify_by": "2026-10-09"},  # 29 days
        {**real, "notification_event": True},  # 499 counted as an event
    ]
    for violation in planted:
        assert clock_problems(violation, CHICAGO), violation
    # A UTC count instead of the firm's: a Pacific late-evening discovery due Oct 11.
    late = {**real, "discovered_at": "2026-09-11T05:30:00+00:00", "ftc_notify_by": "2026-10-11"}
    assert clock_problems(late, PACIFIC)
    # 500 unencrypted read as no event.
    assert clock_problems({**real, "consumers_affected": 500}, CHICAGO)


async def test_seeded_propagation_violations_are_caught(net: Net) -> None:
    tenant = await _firm(net.seed)
    accrued_ref = f"ACC-2026-{uuid.uuid4().hex[:6]}"
    confirmed = datetime.now(UTC) - timedelta(hours=1)
    facts = _accrued(confirmed)
    await propagate_into(
        IncidentPropagationStep(accrued_ref, str(tenant), facts, str(uuid.uuid4()), "e" * 64)
    )
    (entry,) = await _entries(net.seed, tenant, accrued_ref)
    assert propagation_problems(entry, facts, accrued_ref, CHICAGO) == []
    planted: list[Json] = [
        {**entry, "source": "firm"},
        {**entry, "title": "The firm's own words"},
        {**entry, "consumers_affected": 0},
        {**entry, "dpa_notice_at": confirmed + DPA_WINDOW + timedelta(minutes=1)},
        {**entry, "dpa_notice_at": None},
        {**entry, "ftc_notify_by": date(2026, 10, 12)},
    ]
    for violation in planted:
        assert propagation_problems(violation, facts, accrued_ref, CHICAGO), violation
