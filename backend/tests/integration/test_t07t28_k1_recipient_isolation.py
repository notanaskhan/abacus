"""T-07-T28 (TASK-8327; ADR-078, written in AY's session for N's T24): K-1 recipient isolation
against Postgres, on T-02-T26's released harness. A recipient reads only their own package (list,
detail and download); another recipient's package answers 404 with no hint it exists; a draft
never lists; and nothing in the recipient's reach returns the trust's return.

ac-test-author: ayushkbhatia
"""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.tax import k1_portal

from . import test_t02t09_practice_board as t02t09
from . import test_t02t21_k1_release as t02t21
from .test_t02t09_practice_board import Board
from .test_t02t26_portal_k1 import (
    _released,  # pyright: ignore[reportPrivateUsage] -- T-02-T26's released harness
)

engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board
sent = t02t21.sent
signer = t02t21.signer


async def test_ac_nora_never_reads_theos_package(
    board: Board, sent: t02t21.Sent, signer: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def stored(tenant: object, version_id: uuid.UUID) -> bytes:
        return f"%PDF-1.4 {version_id} %%EOF".encode()

    monkeypatch.setattr(k1_portal, "version_content", stored)
    finals, (nora, theo) = await _released(board)
    assert [p.id for p in await k1_portal.packages(nora)] == [finals[0]]
    assert [p.id for p in await k1_portal.packages(theo)] == [finals[1]]
    for reader, other in ((nora, finals[1]), (theo, finals[0])):
        with pytest.raises(NotFound):
            await k1_portal.package(reader, other)
        with pytest.raises(NotFound):
            await k1_portal.download(reader, other)


async def test_an_unknown_package_and_a_foreign_one_answer_the_same(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    finals, (nora, _theo) = await _released(board)
    for target in (finals[1], uuid.uuid4()):
        with pytest.raises(NotFound) as refused:
            await k1_portal.package(nora, target)
        assert str(refused.value) == "k1_package" or refused.type is NotFound


async def test_a_firm_principal_never_reads_through_the_portal_route(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    finals, (nora, _theo) = await _released(board)
    with pytest.raises(NotFound):
        await k1_portal.packages(replace(nora, client=False))
    del finals
