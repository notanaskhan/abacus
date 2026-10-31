"""T-02-T27 (TASK-2531; T-02 §3.7; DV-12; ADR-031; DEC-1576) against Postgres: the additive POR-13
reads behind the screen's fixture-to-live swap.

- `expected` names who issues the person's unreleased K-1 and by when (POR-13 b): no amounts,
  no documents, no package id, only the person's own recipients, and only on a return a grant
  of theirs already reaches (INV-4); before any grant both reads answer 404.
- After release the card carries the issuer's name; a row carries no TIN; the detail carries the
  recipient's own TIN masked and whether an address is on file (Your details).

The Ridgeline packages and their signed-in recipients are T-02-T26's harness.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import cast

import pytest

from abacus.kernel.errors import NotFound
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


async def test_nothing_is_named_before_a_grant_reaches_the_return(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    """INV-4: before any K-1 of theirs is released the person holds no grant on the issuing
    return, so neither read names it (404, as for a person with nothing)."""
    _ridgeline, _feld, _samuel, finals = await t02t21._ready(board)  # pyright: ignore[reportPrivateUsage] -- T-02-T21's harness
    first = await _signed_in(board, finals[0])
    with pytest.raises(NotFound):
        await k1_portal.expected(first)
    with pytest.raises(NotFound):
        await k1_portal.packages(first)


async def test_an_expected_k1_on_a_return_a_grant_reaches_names_only_issuer_and_date(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    finals, (first, _second) = await _released(board)
    # A second recipient record of the same person on the same return, still a draft.
    item = await board.seed.value("SELECT work_item_id FROM k1_packages WHERE id = $1", finals[0])
    contact = await board.seed.value(
        "SELECT delivery_contact_id FROM k1_packages WHERE id = $1", finals[0]
    )
    recipient = await board.seed.value(
        "INSERT INTO k1_recipients (tenant_id, work_item_id, engine_ref, display_name, "
        "recipient_kind, contact_id) VALUES ($1, $2, 'P09', 'Second Entity LLC', 'lp', $3) "
        "RETURNING id",
        board.tenant,
        item,
        contact,
    )
    draft = await board.seed.value(
        "INSERT INTO k1_packages (tenant_id, recipient_id, work_item_id, form, tax_year, status, "
        "version_no) VALUES ($1, $2, $3, '1065', 2025, 'draft', 1) RETURNING id",
        board.tenant,
        recipient,
        item,
    )
    [found] = await k1_portal.expected(first)
    shown = asdict(found)
    assert set(shown) == {"issuer_name", "form", "tax_year", "k3_status", "expected_on"}
    assert shown["issuer_name"] == await _issuer(board, finals[0])
    assert str(draft) not in json.dumps(shown, default=str)
    assert "Second Entity LLC" not in json.dumps(shown, default=str)


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
    assert await k1_portal.expected(first) == []  # released: a card now, nothing waiting
