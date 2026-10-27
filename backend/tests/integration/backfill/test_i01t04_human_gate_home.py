"""I-01-T04 (TASK-1425): the C13 gate half's migration and its one count source.

Acceptance (I-01.tasks.csv): up/down/up passes (`tests/integration/test_migrations.py` runs every
revision), a rebuild leaves rows unchanged, and Daniel's E0 counts read 11 = 3 + 6 + 2 (the
ADR-078 suite, `test_i01t03_c13_gate_half_ac.py`, now unmarked) while Lena Park's omit every
Ashford gate. Here, from outside `review`:
- Lena's counts and list leave Ashford out entirely, with the same response shape (DEC-43);
- a rebuild writes nothing and leaves every row, Home columns included, as it was; the
  re-projection command is the same call;
- `subkind` is the source's registered name and `office_id` the engagement's (DEC-30);
- a snooze takes a gate out of the list and the total into `snoozed`, for that person only;
- an unassigned gate naming a role waits on that role's holders only;
- snoozes and reassignments are a person's, bound to the session's actor, and insert-only;
- `decision_cards.reserved_user_id` moves only with a person's reassignment written now, on an
  open card, and opens no status write.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Final, cast

import asyncpg
import pytest

from abacus.modules.review.api import rebuild_human_gates

from .support import Json, Migrated, Person
from .test_p04t17_human_gates_independent import (
    Firm,
    _daniels_eleven,  # pyright: ignore[reportPrivateUsage] -- P-04-T17's seed of Daniel's eleven
    _deliver,  # pyright: ignore[reportPrivateUsage] -- the projector, as the worker drives it
    _event,  # pyright: ignore[reportPrivateUsage] -- a C13 event, as the relay hands it over
    _waiting,  # pyright: ignore[reportPrivateUsage] -- what a consumer source says waits now
    firm,
)

__all__ = ["firm"]
pytestmark = pytest.mark.asyncio

COUNTS: Final = "/v1/human-gates/counts"
SHAPE: Final = {"total", "bands", "overdue", "snoozed"}


async def _counts(f: Firm, who: Person, query: str = "") -> Json:
    response = await f.net.call("GET", f"{COUNTS}{query}", who)
    assert response.status_code == 200, response.text
    return cast(Json, response.json())


async def _rows(f: Firm) -> list[tuple[object, ...]]:
    rows = await f.net.seed.rows(
        "SELECT id, kind, subkind, subject_ref::text, engagement_id, assignee_user_id, due_on, "
        "state, office_id, blocked, blocked_reason_code, sort_hint, source_event_id, updated_at "
        "FROM human_gates WHERE tenant_id = $1 ORDER BY id",
        f.tenant_id,
    )
    return [tuple(r.values()) for r in rows]


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _as(
    db: Migrated,
    tenant: uuid.UUID,
    actor: tuple[str, str],
    statements: Sequence[tuple[str, Sequence[object]]],
) -> None:
    """Statements in one app-role transaction acting as `actor` (as `tenant_connection` sets)."""
    conn = await asyncpg.connect(_dsn(db.app_url))
    try:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', $1, true), "
                "set_config('app.actor_kind', $2, true), set_config('app.actor_id', $3, true)",
                str(tenant),
                *actor,
            )
            for sql, args in statements:
                await conn.execute(sql, *args)
    finally:
        await conn.close()


def _human(who: Person) -> tuple[str, str]:
    return ("human", str(who.user_id))


async def _a_gate(f: Firm, who: Person) -> uuid.UUID:
    _waiting(f.tenant_id, "consumer_decision", f.bayside.engagement_id, assignee=who)
    await _deliver(_event(f.tenant_id, f.bayside.engagement_id))
    return cast(
        uuid.UUID,
        await f.net.seed.value(
            "SELECT id FROM human_gates WHERE tenant_id = $1 AND assignee_user_id = $2 LIMIT 1",
            f.tenant_id,
            who.user_id,
        ),
    )


# --- Acceptance: Lena's counts omit every Ashford gate ----------------------------------------


async def test_ac_lenas_counts_and_list_omit_every_ashford_gate(firm: Firm) -> None:
    for _ in range(2):
        _waiting(
            firm.tenant_id, "consumer_decision", firm.ashford.engagement_id, assignee=firm.lena
        )
    _waiting(
        firm.tenant_id, "consumer_sign_off_request", firm.ashford.engagement_id, assignee=firm.lena
    )
    _waiting(firm.tenant_id, "consumer_export", firm.ashford.engagement_id)  # unassigned
    _waiting(
        firm.tenant_id, "consumer_sign_off_request", firm.bayside.engagement_id, assignee=firm.lena
    )
    for site in (firm.ashford, firm.bayside):
        await _deliver(_event(firm.tenant_id, site.engagement_id))
    before = await _counts(firm, firm.lena)
    assert before["total"] == 5

    await firm.net.wall(firm.admin, firm.lena, firm.ashford)
    after = await _counts(firm, firm.lena)
    assert set(after) == SHAPE
    assert after == {
        "total": 1,
        "bands": {"decisions": 0, "sign_offs": 1, "agent_outputs": 0, "approvals_sends": 0},
        "overdue": 0,
        "snoozed": 0,
    }
    _status, page = await firm.gates(firm.lena)
    items = cast(list[Json], page["items"])
    assert {i["engagement_id"] for i in items} == {str(firm.bayside.engagement_id)}
    assert page["total"] == after["total"]
    # Daniel, not walled, still counts Ashford's unassigned export.
    assert (await _counts(firm, firm.daniel))["bands"] == {
        "decisions": 0,
        "sign_offs": 0,
        "agent_outputs": 0,
        "approvals_sends": 1,
    }


# --- Acceptance: a rebuild leaves rows unchanged --------------------------------------------


async def test_ac_a_rebuild_leaves_every_row_unchanged(firm: Firm) -> None:
    await _daniels_eleven(firm)
    before = await _rows(firm)
    assert len(before) == 14
    assert await rebuild_human_gates(firm.tenant_id) == 0
    assert await rebuild_human_gates(firm.tenant_id) == 0
    assert await _rows(firm) == before
    assert (await _counts(firm, firm.daniel))["total"] == 11


async def test_subkind_is_the_registered_name_and_office_the_engagements(firm: Firm) -> None:
    await _daniels_eleven(firm)
    seed = firm.net.seed
    office = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO offices (tenant_id, name, time_zone) "
            "VALUES ($1, 'Denver', 'America/Denver') RETURNING id",
            firm.tenant_id,
        ),
    )
    await seed.run_untriggered(
        "UPDATE engagements SET office_id = $1 WHERE id = $2", office, firm.bayside.engagement_id
    )
    # No C13 event names an office change yet: the re-projection command picks it up.
    assert await rebuild_human_gates(firm.tenant_id) == 8  # Bayside's 5 of Daniel's, 3 of Hannah's
    rows = await seed.rows(
        "SELECT subkind, subject_ref ->> 'type' AS type, engagement_id, office_id "
        "FROM human_gates WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert all(r["subkind"] == r["type"] for r in rows)
    assert {(r["engagement_id"], r["office_id"]) for r in rows} == {
        (firm.ashford.engagement_id, None),
        (firm.bayside.engagement_id, office),
    }
    counts = await _counts(firm, firm.daniel, f"?office_id={office}")
    assert counts["bands"] == {
        "decisions": 1,
        "sign_offs": 2,
        "agent_outputs": 0,
        "approvals_sends": 2,
    }
    assert counts["total"] == 5
    assert await rebuild_human_gates(firm.tenant_id) == 0


# --- Snoozes and role routing on the count source ---------------------------------------------


async def test_a_snooze_moves_a_gate_from_total_to_snoozed_for_that_person_only(
    firm: Firm, migrated_db: Migrated
) -> None:
    gate = await _a_gate(firm, firm.daniel)
    _waiting(firm.tenant_id, "consumer_decision", firm.bayside.engagement_id)  # unassigned
    await _deliver(_event(firm.tenant_id, firm.bayside.engagement_id))
    unassigned = cast(
        uuid.UUID,
        await firm.net.seed.value(
            "SELECT id FROM human_gates WHERE tenant_id = $1 AND assignee_user_id IS NULL",
            firm.tenant_id,
        ),
    )
    snooze = (
        "INSERT INTO human_gate_snoozes (tenant_id, gate_id, user_id, until, actor_kind, "
        "actor_id) VALUES ($1, $2, $3, $4, 'human', $5)"
    )
    later = datetime(2999, 1, 1, tzinfo=UTC)
    await _as(
        migrated_db,
        firm.tenant_id,
        _human(firm.daniel),
        [
            (snooze, (firm.tenant_id, gate, firm.daniel.user_id, later, str(firm.daniel.user_id)))
            for gate in (gate, unassigned)
        ],
    )
    counts = await _counts(firm, firm.daniel)
    assert (counts["total"], counts["snoozed"]) == (0, 2)
    _status, page = await firm.gates(firm.daniel)
    assert page["total"] == 0
    hannah = await _counts(firm, firm.hannah)  # the unassigned gate still waits on her
    assert (hannah["total"], hannah["snoozed"]) == (1, 0)
    # An unsnooze is a later row whose time has come: the gate is back.
    await _as(
        migrated_db,
        firm.tenant_id,
        _human(firm.daniel),
        [
            (
                snooze,
                (
                    firm.tenant_id,
                    gate,
                    firm.daniel.user_id,
                    datetime(2001, 1, 1, tzinfo=UTC),
                    str(firm.daniel.user_id),
                ),
            )
        ],
    )
    counts = await _counts(firm, firm.daniel)
    assert (counts["total"], counts["snoozed"]) == (1, 1)


async def test_an_unassigned_gate_naming_a_role_waits_on_its_holders_only(firm: Firm) -> None:
    subject = _waiting(firm.tenant_id, "consumer_decision", firm.bayside.engagement_id)
    await _deliver(_event(firm.tenant_id, firm.bayside.engagement_id))
    await firm.net.seed.run(
        "UPDATE human_gates SET role = 'manager' "
        "WHERE tenant_id = $1 AND subject_ref ->> 'id' = $2",
        firm.tenant_id,
        str(subject),
    )
    assert (await _counts(firm, firm.hannah))["total"] == 1  # the engagement's manager
    assert (await _counts(firm, firm.daniel))["total"] == 0  # its partner
    assert (await _counts(firm, firm.lena))["total"] == 0  # staff


async def test_an_overdue_gate_is_counted_overdue(firm: Firm) -> None:
    _waiting(
        firm.tenant_id,
        "consumer_decision",
        firm.bayside.engagement_id,
        assignee=firm.daniel,
        due_on=date(2001, 1, 1),
    )
    await _deliver(_event(firm.tenant_id, firm.bayside.engagement_id))
    counts = await _counts(firm, firm.daniel)
    assert (counts["total"], counts["overdue"]) == (1, 1)


# --- Human-only and insert-only at the database ----------------------------------------------

_SNOOZE: Final = (
    "INSERT INTO human_gate_snoozes (tenant_id, gate_id, user_id, until, actor_kind, actor_id) "
    "VALUES ($1, $2, $3, '2999-01-01T00:00:00Z', $4, $5)"
)
_REASSIGN: Final = (
    "INSERT INTO human_gate_reassignments (tenant_id, gate_id, subject_ref, from_user_id, "
    "to_user_id, actor_kind, actor_id) VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7)"
)


async def test_s42_an_agent_or_system_never_snoozes_or_reassigns(
    firm: Firm, migrated_db: Migrated
) -> None:
    gate = await _a_gate(firm, firm.daniel)
    ref = json.dumps({"type": "consumer_decision", "id": str(uuid.uuid4())})
    for kind, actor in (("agent", "agent:run:1"), ("system", "review.human_gates")):
        for sql, args in (
            (_SNOOZE, (firm.tenant_id, gate, firm.daniel.user_id, kind, actor)),
            (
                _REASSIGN,
                (firm.tenant_id, gate, ref, firm.daniel.user_id, firm.hannah.user_id, kind, actor),
            ),
        ):
            with pytest.raises(asyncpg.CheckViolationError):
                await _as(migrated_db, firm.tenant_id, (kind, actor), [(sql, args)])
    # A row claiming a person while the session is the agent's is refused too.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await _as(
            migrated_db,
            firm.tenant_id,
            ("agent", "agent:run:1"),
            [
                (
                    _SNOOZE,
                    (firm.tenant_id, gate, firm.daniel.user_id, "human", str(firm.daniel.user_id)),
                )
            ],
        )


async def test_s42_the_row_is_the_session_persons_and_a_snooze_their_own(
    firm: Firm, migrated_db: Migrated
) -> None:
    gate = await _a_gate(firm, firm.daniel)
    daniel = str(firm.daniel.user_id)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # another person's id
        await _as(
            migrated_db,
            firm.tenant_id,
            _human(firm.daniel),
            [
                (
                    _SNOOZE,
                    (firm.tenant_id, gate, firm.daniel.user_id, "human", str(firm.hannah.user_id)),
                )
            ],
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # snoozing for someone else
        await _as(
            migrated_db,
            firm.tenant_id,
            _human(firm.daniel),
            [(_SNOOZE, (firm.tenant_id, gate, firm.hannah.user_id, "human", daniel))],
        )
    await _as(
        migrated_db,
        firm.tenant_id,
        _human(firm.daniel),
        [(_SNOOZE, (firm.tenant_id, gate, firm.daniel.user_id, "human", daniel))],
    )
    for sql in (
        "UPDATE human_gate_snoozes SET until = now() WHERE tenant_id = $1",
        "DELETE FROM human_gate_snoozes WHERE tenant_id = $1",
        "UPDATE human_gate_reassignments SET reason_code = 'x' WHERE tenant_id = $1",
        "DELETE FROM human_gate_reassignments WHERE tenant_id = $1",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await _as(migrated_db, firm.tenant_id, _human(firm.daniel), [(sql, (firm.tenant_id,))])


async def test_s42_another_firms_gate_cannot_be_snoozed(firm: Firm, migrated_db: Migrated) -> None:
    gate = await _a_gate(firm, firm.daniel)
    other = await firm.net.seed.firm()
    with pytest.raises(asyncpg.PostgresError):
        await _as(
            migrated_db,
            other,
            _human(firm.daniel),
            [(_SNOOZE, (other, gate, firm.daniel.user_id, "human", str(firm.daniel.user_id)))],
        )


# --- decision_cards.reserved_user_id: the reassign hook's one column ---------------------------


async def _card(f: Firm) -> tuple[uuid.UUID, uuid.UUID]:
    """A card reserved to Daniel and its gate (seeded as the owner: triggers off)."""
    card = uuid.uuid4()
    await f.net.seed.run_untriggered(
        "INSERT INTO decision_cards (id, tenant_id, engagement_id, kind, question_key, "
        "reserved_role, reserved_user_id, options, raised_by_kind, raised_by_id) VALUES "
        "($1, $2, $3, 'materiality', 'materiality.overall', 'engagement_partner', $4, '[]', "
        "'human', $5)",
        card,
        f.tenant_id,
        f.bayside.engagement_id,
        f.daniel.user_id,
        str(f.daniel.user_id),
    )
    gate = cast(
        uuid.UUID,
        await f.net.seed.value(
            "INSERT INTO human_gates (tenant_id, kind, subkind, subject_ref, engagement_id, "
            "assignee_user_id, source_event_id) VALUES ($1, 'decision', 'decision_card', "
            "jsonb_build_object('type', 'decision_card', 'id', $2::text), $3, $4, $5) "
            "RETURNING id",
            f.tenant_id,
            str(card),
            f.bayside.engagement_id,
            f.daniel.user_id,
            uuid.uuid4(),
        ),
    )
    return card, gate


_MOVE: Final = "UPDATE decision_cards SET reserved_user_id = $1 WHERE tenant_id = $2 AND id = $3"


async def test_s42_a_card_moves_only_with_a_persons_reassignment_written_now(
    firm: Firm, migrated_db: Migrated
) -> None:
    card, gate = await _card(firm)
    ref = json.dumps({"type": "decision_card", "id": str(card)})
    daniel = str(firm.daniel.user_id)
    move = (_MOVE, (firm.hannah.user_id, firm.tenant_id, card))
    reassignment = (
        _REASSIGN,
        (
            firm.tenant_id,
            gate,
            ref,
            firm.daniel.user_id,
            firm.hannah.user_id,
            "human",
            daniel,
        ),
    )
    with pytest.raises(asyncpg.CheckViolationError):  # no reassignment row
        await _as(migrated_db, firm.tenant_id, _human(firm.daniel), [move])
    with pytest.raises(asyncpg.CheckViolationError):  # an agent, whatever it writes
        await _as(migrated_db, firm.tenant_id, ("agent", "agent:run:1"), [move])
    with pytest.raises(asyncpg.CheckViolationError):  # the status rides along: refused
        await _as(
            migrated_db,
            firm.tenant_id,
            _human(firm.daniel),
            [
                reassignment,
                (
                    "UPDATE decision_cards SET reserved_user_id = $1, status = 'decided' "
                    "WHERE tenant_id = $2 AND id = $3",
                    (firm.hannah.user_id, firm.tenant_id, card),
                ),
            ],
        )
    await _as(migrated_db, firm.tenant_id, _human(firm.daniel), [reassignment, move])
    assert (
        await firm.net.seed.value(
            "SELECT reserved_user_id FROM decision_cards WHERE id = $1", card
        )
        == firm.hannah.user_id
    )
    # No other column opened: the app still can't touch the card's question.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await _as(
            migrated_db,
            firm.tenant_id,
            _human(firm.daniel),
            [("UPDATE decision_cards SET question_key = 'x.y' WHERE id = $1", (card,))],
        )
