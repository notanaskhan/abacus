"""T-02-T21 (TASK-2428; T-02 §3.6, §4.11; DEC-24, DEC-53, DEC-88; DEC-1476) against Postgres: the
K-1 release gate and `K1ReleaseWorkflow`'s activities.

The row's acceptance: "Undo within ten seconds leaves no grant, email or portal change and a
replayed half-finished release sends no second email." Also: the release check names BH-TAX-02's
condition and a missing contact; only a person (with a fresh factor) releases, and the database
refuses a release row from anyone but the session's own person; after the window the workflow's
activities give each recipient access, release the package, email once and replace the hand-off
drafts with the final's values, which clears the Feld return's draft K-1 blockers.

The Ridgeline packages and the share to Feld are T-02-T20's harness. The activities run here as
the worker runs them, without Temporal (the workflow's order is the replay test's). The email is
the template send's contract (`send_templated`, idempotent by key), recorded by a stand-in so no
firm template or mail sink is needed.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast

import asyncpg
import pytest

from abacus.kernel.clock import frozen
from abacus.modules.communications.api import SendOutcome
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.tax import approval, k1_packages, k1_release

from . import test_t02t09_practice_board as t02t09
from . import test_t02t20_k1_packages as t02t20
from .test_t02t09_practice_board import DEMO, Board

engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board

TEMPLATE = uuid.UUID("00000000-0000-4000-8000-00000000d1e1")
LATER = DEMO + timedelta(seconds=11)


class Sent:
    """The template send's stand-in: one message per idempotency key, as the real one derives."""

    def __init__(self) -> None:
        self.keys: list[str] = []

    async def __call__(
        self, ctx: object, key: str, recipient: object, values: object, **kw: object
    ) -> SendOutcome:
        idem = cast(str, kw["idempotency_key"])
        self.keys.append(idem)
        return SendOutcome(uuid.uuid5(uuid.NAMESPACE_URL, idem), "queued", None)


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> Sent:
    stand_in = Sent()
    monkeypatch.setattr(k1_release, "send_templated", stand_in)

    async def in_use(tenant: object, key: str) -> uuid.UUID:
        return TEMPLATE

    monkeypatch.setattr(k1_release, "template_version_in_use", in_use)
    return stand_in


async def _ready(
    b: Board, *, contacts: bool = True
) -> tuple[uuid.UUID, uuid.UUID, AuthContext, list[uuid.UUID]]:
    """Ridgeline's drafts shared to Feld, then the final set; the return final-approved. The
    firm is synthetic, so a frozen business clock reaches `abacus_now()` (the grant's window)."""
    await b.seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", b.tenant)
    ridgeline, feld, samuel = await t02t20._ridgeline_with_drafts(b)  # pyright: ignore[reportPrivateUsage] -- T-02-T20's harness
    drafts = [
        cast(uuid.UUID, r["id"])
        for r in await b.seed.rows("SELECT id FROM k1_packages WHERE work_item_id = $1", ridgeline)
    ]
    assert await k1_packages.share_internal(samuel, ridgeline, drafts, [feld]) == 2
    await t02t20._apply(b, samuel, ridgeline, t02t20._set(final=True))  # pyright: ignore[reportPrivateUsage] -- T-02-T20's harness
    await b.seed.run(
        "UPDATE tax_returns SET status = 'approved' WHERE work_item_id = $1", ridgeline
    )
    finals = [
        cast(uuid.UUID, r["id"])
        for r in await b.seed.rows(
            "SELECT id FROM k1_packages WHERE work_item_id = $1 AND status = 'draft' "
            "ORDER BY version_no, id",
            ridgeline,
        )
    ]
    if contacts:
        client = await b.seed.value("SELECT client_id FROM work_items WHERE id = $1", ridgeline)
        for n, package in enumerate(finals):
            contact = await b.seed.value(
                "INSERT INTO contacts (tenant_id, client_id, display_name, email, contact_kind, "
                "portal_state) VALUES ($1, $2, $3, $4, 'k1_recipient', 'not_invited') "
                "RETURNING id",
                b.tenant,
                client,
                f"Recipient {n}",
                f"recipient{n}.{uuid.uuid4().hex[:6]}@example.test",
            )
            await b.seed.run(
                "UPDATE k1_packages SET delivery_contact_id = $2 WHERE id = $1", package, contact
            )
    samuel = replace(samuel, mfa_at=datetime.now(UTC))  # the matrix reads recency in real time
    return ridgeline, feld, samuel, finals


async def _named(tenant_id: uuid.UUID, client_id: uuid.UUID) -> uuid.UUID:
    return uuid.UUID("00000000-0000-4000-8000-0000000000da")


@pytest.fixture
def signer(monkeypatch: pytest.MonkeyPatch) -> None:
    """BH-TAX-02 names a signer for Ridgeline (the harness publishes no policy; K-02-T18's slice
    does on a seeded firm)."""
    monkeypatch.setattr(k1_release, "signer_for", _named)


async def test_the_check_names_bh_tax_02_and_a_missing_contact(board: Board, sent: Sent) -> None:
    ridgeline, _feld, samuel, _finals = await _ready(board, contacts=False)
    check = await k1_release.eligibility(samuel, ridgeline)
    assert not check.eligible
    assert {"no_release_policy", "recipient_contact_missing"} <= set(check.failing)


async def test_ac1_undo_inside_ten_seconds_leaves_no_grant_email_or_portal_change(
    board: Board, sent: Sent, signer: None
) -> None:
    ridgeline, _feld, samuel, finals = await _ready(board)
    with frozen(DEMO):
        made = await k1_release.request_release(samuel, ridgeline, finals, TEMPLATE, 2, None)
        assert made.status == "pending"
        assert made.not_before == DEMO + k1_release.UNDO_WINDOW
        undone = await k1_release.undo(samuel, made.id)
    assert undone.status == "undone"
    with frozen(LATER):
        assert await k1_release.start(board.tenant, made.id) == "undone"
    grant = await board.seed.rows(
        "SELECT used_at, voided_at FROM approval_grants WHERE subject_type = 'schedule_k_release' "
        "AND subject_id = $1",
        made.id,
    )
    assert grant[0]["used_at"] is None and grant[0]["voided_at"] is not None
    assert sent.keys == []
    assert (
        await board.seed.value(
            "SELECT count(*) FROM client_access_grants WHERE tenant_id = $1 "
            "AND scope_kind = 'k1_package'",
            board.tenant,
        )
        == 0
    )
    statuses = await board.seed.rows(
        "SELECT DISTINCT status FROM k1_packages WHERE id = ANY($1::uuid[])", finals
    )
    assert [r["status"] for r in statuses] == ["draft"]
    # After the window, Undo is refused.
    with frozen(LATER), pytest.raises(k1_release.K1UndoClosed):
        await k1_release.undo(samuel, made.id)


async def test_ac1_a_replayed_half_finished_release_sends_no_second_email(
    board: Board, sent: Sent, signer: None
) -> None:
    ridgeline, feld, samuel, finals = await _ready(board)
    with frozen(DEMO):
        made = await k1_release.request_release(samuel, ridgeline, finals, TEMPLATE, 2, None)
    with frozen(LATER):
        assert await k1_release.start(board.tenant, made.id) == "running"
        # Half-finished: the first recipient delivered, then the worker died and replayed it.
        assert await k1_release.deliver(board.tenant, made.id, finals[0]) == "released"
        assert await k1_release.deliver(board.tenant, made.id, finals[0]) == "released"
        assert await k1_release.deliver(board.tenant, made.id, finals[1]) == "released"
        assert await k1_release.complete(board.tenant, made.id) == "completed"
    assert sorted(sent.keys) == sorted(
        f"schedule_k_release:{made.id}:{p}" for p in finals
    )  # one each, never a second
    released = await board.seed.rows(
        "SELECT status, released_at FROM k1_packages WHERE id = ANY($1::uuid[])", finals
    )
    assert {r["status"] for r in released} == {"released"}
    invited = await board.seed.value(
        "SELECT count(*) FROM client_access_grants WHERE scope_kind = 'k1_package' "
        "AND role = 'k1_recipient' AND scope_id = ANY($1::uuid[])",
        finals,
    )
    assert invited == 2  # a pending grant per recipient, carried by its invitation
    handoffs = await board.seed.rows(
        "SELECT status, final_values FROM k1_handoffs WHERE target_work_item_id = $1", feld
    )
    assert {r["status"] for r in handoffs} == {"final_replaced"}
    assert all('"2": "12500.00"' in cast(str, r["final_values"]) for r in handoffs)
    blockers = [b.kind for b in (await approval.eligibility(samuel, feld)).blockers]
    assert "draft_k1" not in blockers


async def test_only_a_person_releases_and_the_database_agrees(
    board: Board, sent: Sent, signer: None
) -> None:
    ridgeline, _feld, samuel, finals = await _ready(board)
    agent = replace(samuel, tenant=replace(samuel.tenant, actor_kind="agent"))
    with frozen(DEMO), pytest.raises(Forbidden):
        await k1_release.request_release(agent, ridgeline, finals, TEMPLATE, 2, None)
    stale = replace(samuel, mfa_at=None)
    with frozen(DEMO), pytest.raises(Forbidden):
        await k1_release.request_release(stale, ridgeline, finals, TEMPLATE, 2, None)
    # The database: a release row only from the session's own person.
    engagement = await board.seed.value(
        "SELECT engagement_id FROM tax_returns WHERE work_item_id = $1", ridgeline
    )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await board.seed.as_actor(
            board.tenant,
            ("system", "system"),
            "INSERT INTO k1_releases (tenant_id, engagement_id, work_item_id, package_ids, "
            "grant_id, not_before, requested_by, mfa_at, email_template_version_id) VALUES "
            "($1, $2, $3, $4, gen_random_uuid(), now(), $5, now(), $6)",
            board.tenant,
            engagement,
            ridgeline,
            finals,
            samuel.user_id,
            TEMPLATE,
        )
    # And a package is released only while a release naming it runs.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await board.seed.as_actor(
            board.tenant,
            ("system", "system"),
            "UPDATE k1_packages SET status = 'released', released_at = now() WHERE id = $1",
            finals[0],
        )


async def test_a_contact_of_another_client_is_never_given_the_k1(
    board: Board, sent: Sent, signer: None
) -> None:
    ridgeline, feld, samuel, finals = await _ready(board)
    other_client = await board.seed.value("SELECT client_id FROM work_items WHERE id = $1", feld)
    stranger = await board.seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, email, contact_kind, "
        "portal_state) VALUES ($1, $2, 'Not a partner', 'stranger@example.test', "
        "'k1_recipient', 'not_invited') RETURNING id",
        board.tenant,
        other_client,
    )
    await board.seed.run(
        "UPDATE k1_packages SET delivery_contact_id = $2 WHERE id = $1", finals[0], stranger
    )
    with frozen(DEMO):
        made = await k1_release.request_release(samuel, ridgeline, finals, TEMPLATE, 2, None)
    with frozen(LATER):
        assert await k1_release.start(board.tenant, made.id) == "running"
        with pytest.raises(Exception, match="contact_missing"):
            await k1_release.deliver(board.tenant, made.id, finals[0])
    assert sent.keys == []
    assert (
        await board.seed.value(
            "SELECT count(*) FROM client_access_grants WHERE contact_id = $1", stranger
        )
        == 0
    )
