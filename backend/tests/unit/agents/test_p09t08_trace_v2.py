"""P-09-T08 (TASK-6305; SPEC-648; P-09 Stories 4.1, 4.2; DEC-87, DEC-3005): the v2 trace read
model: timeline rows from plan and steps, metadata projection, records read by source, sample
records fail closed, region from the register, TINs scrubbed."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel.tin_patterns import has_tin
from abacus.modules.agents import trace as t
from abacus.modules.agents.runs import WRITE_STATE
from abacus.modules.agents.trace import (
    PlanDecision,
    Sample,
    StepRow,
    args_summary_text,
    records_read_by_source,
    region_of,
    sample_refs,
    samples_for,
    timeline,
)
from abacus.modules.identity.api import AuthContext

AT = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
MARCUS = uuid.uuid4()
NAMES = {MARCUS: "Marcus Delaney"}
PLAN = PlanDecision(
    {
        "trial_balance": "Run trial balance workpaper",
        "materiality": "Propose materiality",
        "risk_assessment": "Draft risk assessment",
        "general_planning": "General audit planning",
    },
    MARCUS,
    AT,
    "approved",
)


def _step(seq: int, key: str, kind: str, state: str, minutes: int, **extra: object) -> StepRow:
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "seq": seq,
        "plan_step_key": key,
        "kind": kind,
        "tool_name": None,
        "state": state,
        "needs": None,
        "started_at": AT + timedelta(minutes=minutes),
        "ended_at": None,
        "created_at": AT + timedelta(minutes=minutes),
        "error_code": None,
        "records_read": 0,
        "args_summary": None,
        "sample_refs": None,
        "source_ref": None,
    }
    base.update(extra)
    return StepRow(**base)  # type: ignore[arg-type] -- a test double stands in


STEPS = [
    _step(1, "trial_balance", "tool", "succeeded", 2,
          ended_at=AT + timedelta(minutes=3, seconds=52)),
    _step(2, "materiality", "approval", "blocked", 3),
    _step(3, "risk_assessment", "tool", "running", 7),
    _step(4, "general_planning", "tool", "waiting_on_inputs", 9,
          needs=["trust_agreement", "irs_opinion_letter"]),
]  # fmt: skip


def test_ac_4127_rows_from_the_plan_and_steps() -> None:
    rows = timeline(PLAN, STEPS, NAMES, metadata=False, blocked_role="engagement_partner")
    assert [(r.seq, r.phase, r.mark) for r in rows] == [
        (1, "plan", "plan"),
        (2, "execute", "done"),
        (3, "proposed_write", "blocked"),
        (4, "execute", "running"),
        (5, "execute", "waiting"),
    ]
    assert rows[0].title == "Plan approved" and rows[0].actor == "Marcus Delaney"
    assert rows[1].title == "Execute › Run trial balance workpaper"  # noqa: RUF001
    assert rows[1].duration_ms == 112_000  # 1 m 52 s
    assert rows[2].detail == "engagement_partner"
    assert rows[4].detail == "trust_agreement,irs_opinion_letter"


def test_metadata_rows_hold_no_labels_details_or_names_but_the_plan_decider() -> None:
    rows = timeline(PLAN, STEPS, NAMES, metadata=True, blocked_role="engagement_partner")
    assert [r.title for r in rows[1:]] == ["Execute", "Propose", "Execute", "Execute"]
    assert all(r.detail is None for r in rows)


def test_a_failed_step_details_its_error_code() -> None:
    failed = _step(1, "list_returns", "tool", "failed", 0, error_code="connection_401")
    (row,) = timeline(None, [failed], {}, metadata=False)
    assert (row.mark, row.state, row.detail) == ("failed", "failed", "connection_401")


def test_records_read_sum_by_type_and_source() -> None:
    conn = str(uuid.uuid4())
    steps = [
        _step(1, "a", "tool", "succeeded", 0, records_read=224, source_ref=conn),
        _step(2, "b", "tool", "succeeded", 1, records_read=214, source_ref="accrued"),
        _step(3, "c", "tool", "succeeded", 2, records_read=0, source_ref="accrued"),
    ]
    found = records_read_by_source(steps)
    assert sum(c.count for c in found) == 438
    through = {(c.connection_id is not None, c.through) for c in found}
    assert through == {(True, None), (False, "Accrued")}


def test_sample_refs_hold_at_most_five_well_formed_refs() -> None:
    raw = [{"record_type": "tax_return", "id": str(uuid.uuid4())} for _ in range(7)]
    raw.insert(1, {"record_type": "x", "id": "not-a-uuid"})
    assert len(sample_refs(raw)) == 4  # the first five entries, one malformed
    assert sample_refs("nope") == []


async def test_samples_without_a_resolver_show_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(t, "_RESOLVERS", {})
    raw = [{"record_type": "tax_return", "id": str(uuid.uuid4())}]
    assert await samples_for(object(), raw, 5) == []  # type: ignore[arg-type] -- a test double stands in


async def test_samples_keep_only_what_the_resolver_lets_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown, hidden = uuid.uuid4(), uuid.uuid4()

    async def resolver(_: AuthContext, ids: object) -> list[Sample]:
        return [Sample("tax_return", shown, "Return 912-70-3344", f"/tax/returns/{shown}")]

    monkeypatch.setattr(t, "_RESOLVERS", {"tax_return": resolver})
    raw = [{"record_type": "tax_return", "id": str(i)} for i in (hidden, shown)]
    found = await samples_for(object(), raw, 5)  # type: ignore[arg-type] -- a test double stands in
    assert [s.id for s in found] == [shown]
    assert not has_tin(found[0].label)


def test_args_summaries_are_scrubbed() -> None:
    assert not has_tin(str(args_summary_text({"ssn": "912-70-3344", "tax_year": 2025})))
    assert args_summary_text(None) is None


def test_region_is_the_united_states_for_a_us_route_or_none() -> None:
    assert region_of(None, AT) == "United States (data and inference)"


@pytest.mark.parametrize(
    ("state", "word"),
    [("pending", "waiting"), ("approved_with_edits", "approved"), ("rejected", "declined"),
     ("superseded", "superseded")],
)  # fmt: skip
def test_write_states_follow_wb_09(state: str, word: str) -> None:
    assert WRITE_STATE[state] == word
