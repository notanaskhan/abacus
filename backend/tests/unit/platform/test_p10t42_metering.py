"""P-10-T42 (TASK-6801; SPEC-647 §3.10 AC-M1, AC-M2, AC-M4; DEC-3401): agent-minute arithmetic,
the usage month, the event's payload and the Brightwater Hale seed's figures.

Row acceptance: "ADM-14's 14,920 and ENG-06's 412 = 46 + 24 + 342 foot from the seed ledger, and
a sub-30-second run posts 0 minutes but counts as a run."
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from abacus.kernel.errors import DomainInvalid
from abacus.modules.agents.events import RunCompleted
from abacus.modules.agents.usage_labels import CAPABILITY_LABELS
from abacus.modules.platform.metering import (
    SERVICE_LINE_LABELS,
    agent_minutes,
    run_minutes_from,
    usage_month_bounds,
    usage_month_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale import usage_slice


@pytest.mark.parametrize(
    ("ms", "minutes"),
    [(0, 0), (29_999, 0), (30_000, 1), (60_000, 1), (89_999, 1), (90_000, 2), (161_000, 3)],
)
def test_ac_m1_round_half_up(ms: int, minutes: int) -> None:
    assert agent_minutes(ms) == minutes


def test_ac_m2_a_sub_30_second_run_posts_zero() -> None:
    assert agent_minutes(29_999) == 0


def test_agent_minutes_refuses_negative() -> None:
    with pytest.raises(ValueError):
        agent_minutes(-1)


@pytest.mark.parametrize(
    ("day", "month"),
    [
        (date(2026, 9, 14), "2026-08"),
        (date(2026, 9, 15), "2026-09"),
        (date(2026, 10, 1), "2026-09"),
        (date(2026, 10, 14), "2026-09"),
        (date(2026, 10, 15), "2026-10"),
        (date(2027, 1, 3), "2026-12"),
    ],
)
def test_usage_month_runs_from_the_15th(day: date, month: str) -> None:
    assert usage_month_of(day) == month


def test_usage_month_bounds() -> None:
    assert usage_month_bounds("2026-09") == (date(2026, 9, 15), date(2026, 10, 14))
    assert usage_month_bounds("2026-12") == (date(2026, 12, 15), date(2027, 1, 14))
    with pytest.raises(DomainInvalid):
        usage_month_bounds("2026-13")


def test_the_event_payload_reads_back_as_a_line() -> None:
    run = uuid.uuid4()
    event = RunCompleted(
        run_id=run,
        state="succeeded",
        completed_on=date(2026, 9, 14),
        agent_ms=161_000,
        agent_minutes=3,
        capability="audit.planning",
        service_line="audit",
        engagement_id=None,
        run_number=4118,
        cost_usd="0.0123",
    )
    line = run_minutes_from(event.model_dump(mode="json"))
    assert (line.run_id, line.minutes, line.agent_ms, line.run_number) == (run, 3, 161_000, 4118)
    assert line.completed_on == date(2026, 9, 14)
    assert line.service_line == "audit" and line.engagement_id is None


def test_the_payload_carries_no_usd_label_or_text_beyond_codes() -> None:
    fields = set(RunCompleted.model_fields)
    assert "label" not in fields and "name" not in fields


def test_seed_adm14a_foots() -> None:
    lines = dict(usage_slice.SEPTEMBER_BY_LINE)
    assert sum(lines.values()) == usage_slice.ADM14_TOTAL == 14_920
    assert lines == {"tax": 8_640, "audit": 4_610, "cas": 1_420, "advisory": 120, "firm": 130}
    assert usage_month_of(usage_slice.SEPTEMBER_POSTED_ON) == "2026-09"
    assert [SERVICE_LINE_LABELS[k] for k, _ in usage_slice.SEPTEMBER_BY_LINE] == [
        "Tax",
        "Audit & assurance",
        "Client accounting",
        "Advisory & attest",
        "Firm operations",
    ]
    assert usage_slice.INCLUDED_MINUTES == 20_000


def test_seed_eng06a_foots_without_the_open_run() -> None:
    runs = usage_slice.NORTHWIND_RUNS
    assert [n for n, *_ in runs] == [4019, 4064, 4102]  # #4127 is open: nothing posts (AC-M4)
    assert sum(m for *_, m, _ in runs) == usage_slice.ENG06_TOTAL == 412
    assert all(usage_month_of(on) == "2026-08" for _, _, on, _, _ in runs)
    assert all(agent_minutes(m * usage_slice.MS) == m for *_, m, _ in runs)


def test_seed_events_post_every_line_once() -> None:
    events = usage_slice.usage_events()
    posted = [e for e in events if e.kind == "platform.agent_minutes_posted"]
    assert len(posted) == 3 + 5
    assert len({e.data["run_id"] for e in posted}) == 8
    assert sum(int(str(e.data["minutes"])) for e in posted) == 14_920 + 412


def test_eng06_capability_names_are_the_handoff_s() -> None:
    assert CAPABILITY_LABELS["requests.pbc_list_builder"] == "PBC list builder"
    assert CAPABILITY_LABELS["evidence.matcher"] == "Document classifier & matcher"
    assert CAPABILITY_LABELS["ebp.provisions_extractor"] == "Plan provisions extraction"
