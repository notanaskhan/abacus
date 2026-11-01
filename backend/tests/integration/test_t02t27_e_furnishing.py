"""POR-13's electronic-furnishing consent (TASK-2538; S20e; T-02 §3.7, DV-12; Rev. Proc. 2012-17;
DEC-1579) against Postgres.

- The disclosure is firm content: a firm admin with a recent second factor imports each version;
  a manager, an agent and the system are refused; versions count up and never change.
- Until a version exists downloads are not gated. Once one exists, the first download waits on
  consent; a consent names the newest version (409 `stale_disclosure` otherwise); a decline keeps
  the firm's own channel (409 `e_furnishing_declined`), and a given consent lets the zip through.
- A recipient reads the newest disclosure; with none published, 404.

The released Ridgeline packages and their signed-in recipients are T-02-T26's harness.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.tax import k1_disclosures, k1_portal

from . import test_t02t09_practice_board as t02t09
from . import test_t02t21_k1_release as t02t21
from . import test_t02t26_portal_k1 as t02t26
from .test_t02t09_practice_board import Board

engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board
sent = t02t21.sent
signer = t02t21.signer
_released = t02t26._released  # pyright: ignore[reportPrivateUsage] -- T-02-T26's release

TEXT = "Synthetic electronic-furnishing disclosure for tests."


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch) -> None:
    async def content(tenant: object, version_id: uuid.UUID) -> bytes:
        return f"%PDF-1.4 {version_id} %%EOF".encode()

    monkeypatch.setattr(k1_portal, "version_content", content)


async def _admin(b: Board) -> AuthContext:
    admin = await b.person("Grace Holloway", "firm_admin")
    return replace(admin, mfa_at=datetime.now(UTC))


async def test_only_a_firm_admin_imports_and_versions_never_change(board: Board) -> None:
    admin = await _admin(board)
    first = await k1_disclosures.import_disclosure(admin, TEXT)
    second = await k1_disclosures.import_disclosure(admin, TEXT + " v2")
    assert (first.version_no, second.version_no) == (1, 2)
    assert (await k1_disclosures.current(admin.tenant)) == second
    manager = await board.person("Samuel Ito", None)
    for ctx in (
        manager,
        replace(admin, tenant=TenantContext(board.tenant, "agent", f"agent:x:{uuid.uuid4()}")),
        replace(admin, tenant=TenantContext(board.tenant, "system", "tax:planted")),
    ):
        with pytest.raises(Forbidden):
            await k1_disclosures.import_disclosure(ctx, TEXT)
    # Insert-only for the application role (0590): a version is never edited.
    with pytest.raises(ProgrammingError):
        async with tenant_session(admin.tenant) as session:
            await session.execute(
                text("UPDATE k1_furnishing_disclosures SET body = 'changed' WHERE id = :id"),
                {"id": first.id},
            )


async def test_downloads_wait_on_consent_once_a_disclosure_is_published(
    board: Board, sent: t02t21.Sent, signer: None, stored: None
) -> None:
    finals, (first, _second) = await _released(board)
    assert (await k1_portal.download(first, finals[0])).body  # nothing published: not gated
    with pytest.raises(NotFound):
        await k1_portal.furnishing_disclosure(first)
    published = await k1_disclosures.import_disclosure(await _admin(board), TEXT)
    assert (await k1_portal.furnishing_disclosure(first)).id == published.id
    with pytest.raises(k1_disclosures.ConsentRequired):
        await k1_portal.download(first, finals[0])
    with pytest.raises(k1_disclosures.StaleDisclosure):
        await k1_portal.e_furnishing(first, finals[0], "given", uuid.uuid4())
    await k1_portal.e_furnishing(first, finals[0], "declined", published.id)
    with pytest.raises(k1_disclosures.FurnishingDeclined):
        await k1_portal.download(first, finals[0])
    await k1_portal.e_furnishing(first, finals[0], "given", published.id)
    assert (await k1_portal.download(first, finals[0])).body
    [detail] = [v for v in await k1_portal.packages(first) if v.id == finals[0]]
    assert detail.e_furnishing_consent == "given"
