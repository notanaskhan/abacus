"""T-02-T27 (TASK-2531; T-02 §3.7; DV-12; ADR-031; DEC-1576) against Postgres: the additive POR-13
reads behind the screen's fixture-to-live swap.

- Before release, `expected` names who issues the person's K-1 and by when (POR-13 b): no
  amounts, no documents, no package id, and only the person's own recipients.
- After release the card carries the issuer's name; a row carries no TIN; the detail carries the
  recipient's own TIN masked and whether an address is on file (Your details).

The Ridgeline packages and their signed-in recipients are T-02-T26's harness.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import cast

from abacus.modules.tax import k1_portal

from . import test_t02t09_practice_board as t02t09
from . import test_t02t21_k1_release as t02t21
from . import test_t02t26_portal_k1 as t02t26
from .test_t02t09_practice_board import Board

engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board
sent = t02t21.sent
signer = t02t21.signer

_signed_in = t02t26._signed_in  # pyright: ignore[reportPrivateUsage] -- T-02-T26's recipient
_released = t02t26._released  # pyright: ignore[reportPrivateUsage] -- T-02-T26's release


async def _issuer(b: Board, package: uuid.UUID) -> str:
    return cast(
        str,
        await b.seed.value(
            "SELECT c.name FROM k1_packages p JOIN work_items w ON w.id = p.work_item_id "
            "JOIN clients c ON c.id = w.client_id WHERE p.id = $1",
            package,
        ),
    )


async def test_before_release_the_person_sees_only_who_issues_and_by_when(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    _ridgeline, _feld, _samuel, finals = await t02t21._ready(board)  # pyright: ignore[reportPrivateUsage] -- T-02-T21's harness
    first, second = [await _signed_in(board, p) for p in finals]
    mine = await k1_portal.expected(first)
    assert len(mine) == 1
    found = asdict(mine[0])
    assert set(found) == {"issuer_name", "form", "tax_year", "k3_status", "expected_on"}
    assert found["issuer_name"] == await _issuer(board, finals[0])
    assert (found["form"], found["tax_year"]) == ("1065", 2025)
    assert str(finals[0]) not in json.dumps(found, default=str)
    assert len(await k1_portal.expected(second)) == 1
    assert await k1_portal.packages(first) == []  # a draft never lists


async def test_after_release_the_card_names_the_issuer_and_only_the_detail_has_the_tin(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    finals, (first, _second) = await _released(board)
    [row] = await k1_portal.packages(first)
    assert row.issuer_name == await _issuer(board, finals[0])
    assert (row.tin_kind, row.tin_last4, row.address_on_file) == (None, None, None)
    detail = await k1_portal.package(first, finals[0])
    last4 = await board.seed.value(
        "SELECT r.tin_last4 FROM k1_packages p JOIN k1_recipients r ON r.id = p.recipient_id "
        "WHERE p.id = $1",
        finals[0],
    )
    assert detail.tin_last4 == last4
    assert detail.address_on_file is not None
    assert detail.issuer_name == row.issuer_name
    assert await k1_portal.expected(first) == []  # released: it is a card now
