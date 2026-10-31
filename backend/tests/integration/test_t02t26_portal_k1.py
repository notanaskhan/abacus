"""T-02-T26 (TASK-2430; T-02 §3.6, §4.3; DEC-34, DEC-78; DEC-1478) against Postgres: POR-13's
portal routes.

The row's acceptance: "Pell Street Ventures' member cannot read Pell Street II's package and every
download writes an access event." Here the two Ridgeline recipients are T-02-T21's harness
packages, each delivered to a contact who already signs in, so the release grants each person
`k1_recipient` on their own package. Also: a draft never lists; the first read moves the package to
Viewed and the download to Downloaded; the zip is the same bytes twice; amounts need the second
step; a details change and the e-furnishing consent are recorded for the recipient.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import timedelta
from typing import cast

import pytest

from abacus.kernel.clock import frozen
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.tax import k1_portal, k1_release

from . import test_t02t09_practice_board as t02t09
from . import test_t02t21_k1_release as t02t21
from .test_t02t09_practice_board import DEMO, Board

engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board
sent = t02t21.sent
signer = t02t21.signer

LATER = DEMO + timedelta(seconds=11)


async def _signed_in(b: Board, package: uuid.UUID) -> AuthContext:
    """The package's delivery contact as a client user who signs in (an accepted invitation)."""
    contact = cast(
        uuid.UUID,
        await b.seed.value("SELECT delivery_contact_id FROM k1_packages WHERE id = $1", package),
    )
    user = cast(
        uuid.UUID,
        await b.seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) VALUES "
            "('https://probe.test', $1, $2, 'Recipient') RETURNING id",
            uuid.uuid4().hex,
            f"{uuid.uuid4().hex}@example.test",
        ),
    )
    membership = cast(
        uuid.UUID,
        await b.seed.value(
            "INSERT INTO memberships (tenant_id, user_id, status, kind) VALUES ($1, $2, "
            "'active', 'client') RETURNING id",
            b.tenant,
            user,
        ),
    )
    await b.seed.run(
        "UPDATE contacts SET user_id = $2, portal_state = 'active' WHERE id = $1", contact, user
    )
    return AuthContext(
        TenantContext(b.tenant, "human", str(user)),
        user,
        membership,
        None,
        None,
        client=True,
        portal_second_step=True,
    )


async def _released(b: Board) -> tuple[list[uuid.UUID], list[AuthContext]]:
    ridgeline, _feld, samuel, finals = await t02t21._ready(b)  # pyright: ignore[reportPrivateUsage] -- T-02-T21's harness
    people = [await _signed_in(b, p) for p in finals]
    with frozen(DEMO):
        made = await k1_release.request_release(
            samuel, ridgeline, finals, t02t21.TEMPLATE, 2, None
        )
    with frozen(LATER):
        assert await k1_release.start(b.tenant, made.id) == "running"
        for package in finals:
            await k1_release.deliver(b.tenant, made.id, package)
        await k1_release.complete(b.tenant, made.id)
    return finals, people


async def test_ac1_a_member_reads_only_their_own_package_and_each_download_is_logged(
    board: Board, sent: t02t21.Sent, signer: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def stored(tenant: object, version_id: uuid.UUID) -> bytes:
        return f"%PDF-1.4 {version_id} %%EOF".encode()  # the harness seeds rows, not objects

    monkeypatch.setattr(k1_portal, "version_content", stored)
    finals, (first, second) = await _released(board)
    mine = await k1_portal.packages(first)
    assert [p.id for p in mine] == [finals[0]]
    with pytest.raises(NotFound):
        await k1_portal.package(first, finals[1])
    with pytest.raises(NotFound):
        await k1_portal.download(first, finals[1])
    assert [p.id for p in await k1_portal.packages(second)] == [finals[1]]

    before = await board.seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND kind = 'schedule_k.read'",
        board.tenant,
    )
    viewed = await k1_portal.package(first, finals[0])
    assert [line.box_code for line in viewed.lines] == ["2"]
    one = await k1_portal.download(first, finals[0])
    two = await k1_portal.download(first, finals[0])
    assert one.body == two.body  # deterministic
    after = await board.seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND kind = 'schedule_k.read'",
        board.tenant,
    )
    assert after == cast(int, before) + 3
    status = await board.seed.value("SELECT status FROM k1_packages WHERE id = $1", finals[0])
    assert status == "downloaded"


async def test_amounts_need_the_second_step_and_drafts_never_list(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    finals, (first, _second) = await _released(board)
    with pytest.raises(k1_portal.K1MfaRequired):
        await k1_portal.package(replace(first, portal_second_step=False), finals[0])
    superseded = await board.seed.rows(
        "SELECT id FROM k1_packages WHERE status = 'superseded' AND released_at IS NULL"
    )
    listed = {p.id for p in await k1_portal.packages(first)}
    assert not listed & {cast(uuid.UUID, r["id"]) for r in superseded}


async def test_a_details_change_and_the_consent_are_the_recipients(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    finals, (first, _second) = await _released(board)
    recipient = cast(
        uuid.UUID,
        await board.seed.value("SELECT recipient_id FROM k1_packages WHERE id = $1", finals[0]),
    )
    change = await k1_portal.submit_details_change(
        first,
        recipient,
        "address",
        None,
        {"line1": "1 Main St", "city": "Brooklyn", "postal_code": "11201", "country": "US"},
    )
    assert change.status == "pending"
    decision, _on = await k1_portal.e_furnishing(first, finals[0], "given", uuid.uuid4())
    assert decision == "given"
    assert (
        await board.seed.value(
            "SELECT e_furnishing_consent FROM k1_packages WHERE id = $1", finals[0]
        )
        == "given"
    )
