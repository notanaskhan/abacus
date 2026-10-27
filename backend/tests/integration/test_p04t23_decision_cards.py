"""P-04-T23 acceptance (TASK-1402; ADR-160 clause 8; SHL-11): the decision cards service.

"Only Margaret Okonkwo can decide the Northwind card, a decide without a rationale returns 422
rationale_required, and reassessment on $16,861,000 records No change with the $700 difference."

The platform test kind below is the Northwind planning-materiality golden: code computes every
figure (ADR-050) from the benchmark the test sets, 16,812,400 at planning (1.0% = 168,100; 1.5% =
252,200, PM 75% = 189,150, CT 5% = 12,610; overall rounded to 100, half up) and 16,861,000 at
final (1.5% = 252,900, a 700 difference, 0.3%). A reassessment within clearly trivial is No change.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_connection
from abacus.modules.identity.api import AgentContext, agent_context_for_run
from abacus.modules.review.api import (
    CardContext,
    CardFactor,
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    Reassessment,
    UnregisteredKind,
    raise_decision_card,
    register_decision_kind,
)

from .conftest import MigratedDatabase
from .review_support import Cast, as_, make_cast

pytestmark = pytest.mark.asyncio
KIND = "northwind_golden"
QUESTION = "materiality.planning"
BENCHMARK: dict[uuid.UUID, Decimal] = {}
RATES = (
    ("pct_1_0", Decimal("0.010")),
    ("pct_1_5", Decimal("0.015")),
    ("pct_2_0", Decimal("0.020")),
)


def _round(amount: Decimal) -> Decimal:
    return (amount / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 100


def _figures(base: Decimal, rate: Decimal) -> dict[str, str]:
    overall = _round(base * rate)
    pm = (overall * Decimal("0.75")).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    ct = (overall * Decimal("0.05")).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return {
        "rate": str(rate),
        "materiality": str(overall),
        "performance_materiality": str(pm),
        "clearly_trivial": str(ct),
    }


async def _compute(_tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    base = BENCHMARK[subject.engagement_id]
    return ComputedCard(
        options=tuple(
            CardOption(key, f"{rate * 100:.1f}%", _figures(base, rate)) for key, rate in RATES
        ),
        context=(CardContext("benchmark", "Net assets available for benefits", str(base)),),
        factors=(
            CardFactor("users", "Plan participants rely on the statements"),
            CardFactor("prior_year", "Consistent with the two prior years"),
        ),
    )


async def _reassess(
    tenant: TenantContext, subject: CardSubject, decided: str | None, stored: ComputedCard
) -> Reassessment:
    now = await _compute(tenant, subject)
    key = decided or "pct_1_5"
    before = Decimal(next(o for o in stored.options if o.key == key).figures["materiality"])
    after_figures = next(o for o in now.options if o.key == key).figures
    after = Decimal(after_figures["materiality"])
    difference = after - before
    trivial = Decimal(next(o for o in stored.options if o.key == key).figures["clearly_trivial"])
    return Reassessment(
        changed=abs(difference) > trivial,
        figures={
            "benchmark": str(BENCHMARK[subject.engagement_id]),
            "materiality": str(after),
            "difference": str(difference),
            "difference_pct": str((difference / before * 100).quantize(Decimal("0.1"))),
        },
        card=now,
    )


register_decision_kind(
    DecisionKind(
        KIND,
        "engagement_partner",
        _compute,
        questions={QUESTION: "What is planning materiality for Northwind Robotics 401(k) Plan?"},
        reassess=_reassess,
    )
)


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


@pytest.fixture
async def team(migrated_db: MigratedDatabase) -> Cast:
    found = await make_cast(migrated_db.superuser_dsn)
    BENCHMARK[found.engagement] = Decimal("16812400")
    return found


async def _agent(
    team: Cast, scope: frozenset[str] = frozenset({"decision_card.raise"})
) -> AgentContext:
    return await agent_context_for_run(
        tenant_id=team.tenant,
        run_id=uuid.uuid4(),
        agent_id="evidence.screener",
        engagement_id=team.engagement,
        task_scope=scope,
        initiator_user_id=team["hannah"].user_id,
    )


async def _suggestion(team: Cast, engagement: uuid.UUID) -> uuid.UUID:
    """The agent's recommendation, a suggestion on the engagement (agents' table)."""
    return cast(
        uuid.UUID,
        await team.seed.value(
            "INSERT INTO suggestions (tenant_id, engagement_id, target_type, target_id, "
            "field_key, proposed_value, agent_run_id) VALUES ($1, $2, 'decision_card', $3, "
            '\'option_key\', \'{"t": "text", "v": "pct_1_5"}\', $4) RETURNING id',
            team.tenant,
            engagement,
            uuid.uuid4(),
            uuid.uuid4(),
        ),
    )


async def _card(team: Cast) -> uuid.UUID:
    return await raise_decision_card(
        await _agent(team),
        engagement_id=team.engagement,
        kind=KIND,
        question_key=QUESTION,
        recommended_option_key="pct_1_5",
        recommendation_suggestion_id=await _suggestion(team, team.engagement),
    )


def _decide(seen: int = 1, **over: object) -> dict[str, object]:
    return {
        "option_key": "pct_1_5",
        "factors": ["users"],
        "rationale": "1.5% of net assets: participants rely on the statements.",
        "seen_version": seen,
    } | over


async def test_ac_only_margaret_decides_rationale_required_and_no_change_on_final(
    team: Cast,
) -> None:
    card = await _card(team)
    path = f"/v1/decision-cards/{card}"

    shown = await team.call("hannah")("GET", path)
    assert shown.status_code == 200, shown.text
    body = shown.json()
    assert body["card"]["status"] == "awaiting_role"
    assert body["card"]["reserved_user_name"] == "Margaret Okonkwo"
    assert body["card"]["allowed_actions"] == [
        "decision.request_analysis",
        "decision.notify",
        "decision.reassess",
    ]
    assert body["question"].startswith("What is planning materiality")
    figures = {o["key"]: o["figures"] for o in body["options"]}
    assert figures["pct_1_0"]["materiality"] == "168100"
    assert figures["pct_1_5"] == {
        "rate": "0.015",
        "materiality": "252200",
        "performance_materiality": "189150",
        "clearly_trivial": "12610",
    }
    assert [o["key"] for o in body["options"] if o["recommended"]] == ["pct_1_5"]
    assert body["recommendation"]["option_key"] == "pct_1_5"
    assert body["decision"] is None
    assert [(v["version_no"], v["event"], v["actor_kind"]) for v in body["history"]] == [
        (1, "proposed", "agent")
    ]

    # Only Margaret: the manager, the EQR and the agent are refused.
    for who in ("hannah", "thomas", "marcus"):
        refused = await team.call(who)("POST", f"{path}/decide", json=_decide())
        assert refused.status_code == 403, who
    agent = await _agent(team, frozenset({"decision.decide", "decision_card.raise"}))
    assert (await as_(agent)("POST", f"{path}/decide", json=_decide())).status_code == 403

    margaret = team.call("margaret")
    no_reason = await margaret("POST", f"{path}/decide", json=_decide(rationale=None))
    assert (no_reason.status_code, no_reason.json()["detail"]) == (422, "rationale_required")
    blank = await margaret("POST", f"{path}/decide", json=_decide(rationale="   "))
    assert (blank.status_code, blank.json()["detail"]) == (422, "rationale_required")
    stale = await margaret("POST", f"{path}/decide", json=_decide(seen=2))
    assert (stale.status_code, stale.json()["detail"]) == (409, "recommendation_changed")
    old_factor = await team.call("margaret", mfa_age=timedelta(minutes=16))(
        "POST", f"{path}/decide", json=_decide()
    )
    assert old_factor.status_code == 403
    assert old_factor.json() == {"detail": "mfa_required", "facts": {"max_age_s": 900}}
    assert await team.value("SELECT count(*) FROM decisions WHERE card_id = $1", card) == 0

    decided = await margaret("POST", f"{path}/decide", json=_decide())
    assert decided.status_code == 200, decided.text
    after = decided.json()
    assert after["card"]["status"] == "decided" and after["card"]["version_no"] == 2
    assert after["decision"]["decided_by_name"] == "Margaret Okonkwo"
    assert after["decision"]["rationale"].startswith("1.5% of net assets")
    assert after["decision"]["option_key"] == "pct_1_5"
    assert [f["key"] for f in after["factors"] if f["checked"]] == ["users"]
    again = await margaret("POST", f"{path}/decide", json=_decide(seen=2))
    assert (again.status_code, again.json()["detail"]) == (409, "decision_card_state")

    row = (
        await team.seed.rows(
            "SELECT rationale_sealed, actor_kind, mfa_at FROM decisions WHERE card_id = $1", card
        )
    )[0]
    assert row["actor_kind"] == "human" and row["mfa_at"] is not None
    assert b"net assets" not in bytes(row["rationale_sealed"])

    # Final: 16,861,000 after AJE-1. Code computes 252,900, a 700 difference: No change (v3).
    BENCHMARK[team.engagement] = Decimal("16861000")
    # On a decided card a reassessment is the decider's act (security review M6, DEC-505): the
    # manager is refused, and Margaret needs a fresh second factor.
    manager = await team.call("hannah")("POST", f"{path}/reassess")
    assert manager.status_code == 403
    stale_reassess = await team.call("margaret", mfa_age=timedelta(minutes=16))(
        "POST", f"{path}/reassess"
    )
    assert stale_reassess.json() == {"detail": "mfa_required", "facts": {"max_age_s": 900}}
    hannah_view = (await team.call("hannah")("GET", path)).json()
    assert "decision.reassess" not in hannah_view["card"]["allowed_actions"]
    reassessed = await margaret("POST", f"{path}/reassess")
    assert reassessed.status_code == 200, reassessed.text
    final = reassessed.json()
    assert final["card"]["id"] == str(card) and final["card"]["status"] == "decided"
    assert final["card"]["version_no"] == 3
    v3 = final["history"][-1]
    assert (v3["version_no"], v3["event"], v3["changed"]) == (3, "reassessed", False)
    assert v3["figures"]["materiality"] == "252900"
    assert v3["figures"]["difference"] == "700"
    assert v3["figures"]["difference_pct"] == "0.3"
    assert v3["actor_initials"] == "MO"
    assert [v["event"] for v in final["history"]] == ["proposed", "decided", "reassessed"]

    actions = await team.seed.rows(
        "SELECT action, actor_kind FROM audit_events WHERE tenant_id = $1 "
        "AND (action LIKE 'decision.%' OR action LIKE 'decision_card.%') ORDER BY seq",
        team.tenant,
    )
    assert [(a["action"], a["actor_kind"]) for a in actions] == [
        ("decision_card.raised", "agent"),
        ("decision.decided", "human"),
        ("decision.reassessed", "human"),
    ]
    outbox = await team.seed.rows(
        "SELECT event_type FROM outbox WHERE tenant_id = $1 "
        "AND event_type IN ('decision_card.raised', 'decision.decided')",
        team.tenant,
    )
    assert sorted(o["event_type"] for o in outbox) == ["decision.decided", "decision_card.raised"]


async def test_a_changed_outcome_supersedes_the_card(team: Cast) -> None:
    card = await _card(team)
    decided = await team.call("margaret")(
        "POST", f"/v1/decision-cards/{card}/decide", json=_decide()
    )
    assert decided.status_code == 200
    BENCHMARK[team.engagement] = Decimal("20000000")  # 1.5% = 300,000: past clearly trivial
    reassessed = await team.call("margaret")("POST", f"/v1/decision-cards/{card}/reassess")
    assert reassessed.status_code == 200, reassessed.text
    new = reassessed.json()
    assert new["card"]["id"] != str(card)
    assert (new["card"]["status"], new["card"]["version_no"]) == ("awaiting_role", 3)
    assert [(v["version_no"], v["event"], v["changed"]) for v in new["history"]] == [
        (1, "proposed", None),
        (2, "decided", None),
        (3, "reassessed", True),
    ]
    old = (await team.call("hannah")("GET", f"/v1/decision-cards/{card}")).json()
    assert old["card"]["status"] == "superseded"
    assert old["card"]["superseded_by_version"] == 3
    assert old["card"]["allowed_actions"] == []
    # The new card is decided on its own version.
    stale = await team.call("margaret")(
        "POST", f"/v1/decision-cards/{new['card']['id']}/decide", json=_decide(seen=2)
    )
    assert stale.json()["detail"] == "recommendation_changed"
    fresh = await team.call("margaret")(
        "POST", f"/v1/decision-cards/{new['card']['id']}/decide", json=_decide(seen=3)
    )
    assert fresh.status_code == 200, fresh.text
    listed = await team.call("hannah")(
        "GET", "/v1/decision-cards", params={"engagement_id": str(team.engagement)}
    )
    assert listed.status_code == 200
    assert listed.json()["counts"] == {"decided": 1, "superseded": 1}
    assert all("options" not in i and "question" not in i for i in listed.json()["items"])


async def test_notify_and_analysis_requests_are_recorded_and_sealed(team: Cast) -> None:
    card = await _card(team)
    hannah = team.call("hannah")
    notified = await hannah("POST", f"/v1/decision-cards/{card}/notify")
    assert notified.status_code == 200, notified.text
    assert notified.json()["notified_user_id"] == str(team["margaret"].user_id)
    events = await team.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'decision_card.notify_requested'",
        team.tenant,
    )
    assert len(events) == 1

    asked = await hannah(
        "POST",
        f"/v1/decision-cards/{card}/analysis-requests",
        json={"text": "Show the prior-year growth at 1.5%."},
    )
    assert asked.status_code == 201, asked.text
    stored = await team.seed.rows(
        "SELECT text_sealed, requested_by FROM decision_analysis_requests WHERE card_id = $1",
        card,
    )
    assert stored[0]["requested_by"] == team["hannah"].user_id
    assert b"prior-year" not in bytes(stored[0]["text_sealed"])
    agent = await _agent(team, frozenset({"decision.request_analysis", "decision.notify"}))
    assert (await as_(agent)("POST", f"/v1/decision-cards/{card}/notify")).status_code == 403


async def test_raising_is_the_agents_through_its_task_scope_and_fails_closed(
    team: Cast, migrated_db: MigratedDatabase
) -> None:
    with pytest.raises(Exception) as refused:
        await raise_decision_card(
            await _agent(team, frozenset({"suggestion.create"})),
            engagement_id=team.engagement,
            kind=KIND,
            question_key=QUESTION,
        )
    assert type(refused.value).__name__ == "Forbidden"
    with pytest.raises(UnregisteredKind):
        await raise_decision_card(
            await _agent(team), engagement_id=team.engagement, kind="no_such_kind",
            question_key=QUESTION,
        )  # fmt: skip
    with pytest.raises(Exception) as bad:
        await raise_decision_card(
            await _agent(team),
            engagement_id=team.engagement,
            kind=KIND,
            question_key=QUESTION,
            recommended_option_key="pct_9_9",
        )
    assert cast(str, getattr(bad.value, "code", "")) == "decision_invalid"
    # Security review L8: the work item and the recommended suggestion must be this engagement's.
    other = await make_cast(migrated_db.superuser_dsn)
    for extra in (
        {"work_item_id": uuid.uuid4()},
        {"recommendation_suggestion_id": uuid.uuid4()},
        {"recommendation_suggestion_id": await _suggestion(other, other.engagement)},
    ):
        with pytest.raises(Exception) as foreign:
            await raise_decision_card(
                await _agent(team),
                engagement_id=team.engagement,
                kind=KIND,
                question_key=QUESTION,
                recommended_option_key="pct_1_5",
                **extra,
            )
        assert cast(str, getattr(foreign.value, "code", "")) == "decision_invalid", extra
    assert (
        await team.value("SELECT count(*) FROM decision_cards WHERE tenant_id = $1", team.tenant)
        == 0
    )


async def test_the_data_layer_holds_the_card_transitions(team: Cast) -> None:
    """Security review M4 (0213): the app role can't decide or supersede a card by its status
    alone, and an agent changes no status."""
    card = await _card(team)
    for actor, status in (
        (("human", str(team["margaret"].user_id)), "decided"),  # no decision row
        (("human", str(team["margaret"].user_id)), "superseded"),  # nothing supersedes it
        (("agent", "agent:evidence.screener:run"), "decided"),
    ):
        tenant = TenantContext(team.tenant, actor[0], actor[1])  # type: ignore[arg-type]  # the actor kind under test
        with pytest.raises(DBAPIError):
            async with tenant_connection(tenant) as conn:
                await conn.execute(
                    text("UPDATE decision_cards SET status = :s WHERE id = :id"),
                    {"s": status, "id": card},
                )  # refused at the statement; the connection rolls back on leaving
    assert await team.value("SELECT status FROM decision_cards WHERE id = $1", card) == (
        "awaiting_role"
    )
