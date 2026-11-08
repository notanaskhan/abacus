"""R-02-T09 (TASK-6205; R-02 AC-26; DEC-2805): POR-09's rail from C10's portal read model.

Row acceptance (its unit half): "Meera Shah's read model lists only her Ridgeline K-1." Meera holds
`taxpayer` on her own 1040 and `k1_recipient` on Ridgeline's package; C10 rows reach her only where
a grant covers an audience (a K-1 recipient's grant never does), and her K-1s come through T-02's
slot, which lists her own released packages only.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.reporting import deliverables as c10
from abacus.modules.reporting.deliverables import PortalK1

pytestmark = pytest.mark.asyncio
CLIENT = uuid.uuid4()
RIDGELINE_K1 = PortalK1(
    uuid.uuid4(),
    "Ridgeline Property Partners, LP — 2025 Schedule K-1 (Form 1065)",
    date(2026, 9, 15),
)


class _Session:
    def __init__(self, rows: Sequence[Any]) -> None:
        self.rows = rows

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
        rows = self.rows
        self.rows = []  # the audiences query answers none
        return SimpleNamespace(all=lambda: rows)


def _ctx(client: bool = True) -> Any:  # noqa: ANN401 -- a stand-in AuthContext
    return SimpleNamespace(tenant=SimpleNamespace(actor_kind="human"), client=client, user_id=1)


def _row(title: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        kind="return_copy",
        title=title,
        client_id=CLIENT,
        client_entity_id=None,
        engagement_id=uuid.uuid4(),
        work_item_id=uuid.uuid4(),
        restricted_use=False,
        band_label="2025 Tax Return",
        version_no=1,
        page_count=40,
        is_draft=False,
        published_at=datetime(2026, 9, 15, tzinfo=UTC),
        withdrawn_at=None,
    )


@pytest.fixture
def k1_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mine(_ctx: object) -> list[PortalK1]:
        return [RIDGELINE_K1]

    monkeypatch.setattr(c10, "_K1_ROWS", [mine])
    monkeypatch.setattr(c10, "_ENVELOPE_ROWS", [])
    monkeypatch.setattr(c10, "_EXPECTED", [])


async def test_ac26_meera_sees_only_her_ridgeline_k1(
    monkeypatch: pytest.MonkeyPatch, k1_slot: None
) -> None:
    rows = [_row("Ridgeline Property Partners 2025 Form 1065"), _row("Another partner's K-1")]
    monkeypatch.setattr(c10, "tenant_session", lambda _t: _Session(rows))

    async def no_grant(*_a: object, **_k: object) -> None:
        return None  # her k1_recipient and taxpayer grants cover none of these audiences

    monkeypatch.setattr(c10, "first_covering_grant", no_grant)
    rail = await c10.portal_deliverables(_ctx(), [CLIENT])
    assert rail.bands == ()
    assert rail.k1s == (RIDGELINE_K1,)


async def test_a_covered_deliverable_is_banded_by_its_work_item(
    monkeypatch: pytest.MonkeyPatch, k1_slot: None
) -> None:
    row = _row("Independent auditor's report")
    monkeypatch.setattr(c10, "tenant_session", lambda _t: _Session([row]))

    async def grant(*_a: object, **_k: object) -> uuid.UUID:
        return uuid.uuid4()

    monkeypatch.setattr(c10, "first_covering_grant", grant)
    rail = await c10.portal_deliverables(_ctx(), [CLIENT])
    assert [b.key for b in rail.bands] == [f"work_item:{row.work_item_id}"]
    assert rail.bands[0].rows[0].status == "final"
    assert rail.bands[0].rows[0].released_on == date(2026, 9, 15)


async def test_a_firm_user_never_reads_the_rail() -> None:
    with pytest.raises(NotFound):
        await c10.portal_deliverables(_ctx(client=False), [CLIENT])


def test_the_statuses_are_the_clients_words() -> None:
    assert c10._status(is_draft=True, withdrawn=False) == "for_your_review"  # pyright: ignore[reportPrivateUsage]
    assert c10._status(is_draft=False, withdrawn=False) == "final"  # pyright: ignore[reportPrivateUsage]
    assert c10._status(is_draft=False, withdrawn=True) == "replaced"  # pyright: ignore[reportPrivateUsage]
