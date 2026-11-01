"""A-03-T17 part two (TASK-2820; ADR-078): the independent AC tests for the stale
computation A-03-T14 added.

Row acceptance (with part one, TASK-2815): "The suite passes on main and fails when any
human-only CHECK, the freeze trigger, the unmapped guard or the stale computation is removed."
These tests break when the computation is removed in any of its three places:
- the mapping's content hash (`ledger.mapping.content_hash`), which a sign-off records. It must
  move with every change a signer saw (an account added, an account moved, an account left
  unmapped, the grouping version), and stay put when nothing changed (no false staleness);
- the follow step (`assurance.mapping.on_tb_version`), which must ask review's computed
  staleness about the view's own current hash;
- the announcement, which follows that answer exactly: stale means one `mapping_set.went_stale`
  to the signers, and not stale means none.
Written from the spec and the contract (docs/contracts/ledger-mapping.md), not from T14's tests.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance import mapping as follow
from abacus.modules.ledger.mapping import content_hash

GROUPING_V1, GROUPING_V2 = UUID(int=101), UUID(int=102)
CASH, AR = UUID(int=201), UUID(int=202)
PREPARER, REVIEWER = UUID(int=301), UUID(int=302)
BASE = [("1000", CASH), ("1200", AR), ("3000", None)]


def test_the_hash_ignores_order_so_an_unchanged_mapping_is_never_stale() -> None:
    assert content_hash(GROUPING_V1, BASE) == content_hash(GROUPING_V1, list(reversed(BASE)))


@pytest.mark.parametrize(
    "changed",
    [
        [*BASE, ("1950", None)],  # a new account the rules leave unmapped
        [*BASE, ("1950", AR)],  # a new account the rules map
        [("1000", CASH), ("1200", CASH), ("3000", None)],  # an account moved line
        [("1000", CASH), ("1200", None), ("3000", None)],  # an account left unmapped
        [("1000", CASH), ("3000", None)],  # an account gone
    ],
)
def test_every_change_a_signer_saw_moves_the_hash(changed: list[tuple[str, UUID | None]]) -> None:
    assert content_hash(GROUPING_V1, changed) != content_hash(GROUPING_V1, BASE)


def test_the_grouping_version_is_part_of_the_hash() -> None:
    assert content_hash(GROUPING_V2, BASE) != content_hash(GROUPING_V1, BASE)


def test_the_hash_is_a_sha256_hex() -> None:
    found = content_hash(GROUPING_V1, BASE)
    assert len(found) == 64 and int(found, 16) >= 0


class _Tx:
    def __init__(self, sink: list[object]) -> None:
        self.sink = sink

    def record(self, action: str, **_: object) -> None:
        self.sink.append(action)

    def emit(self, event: object) -> None:
        self.sink.append(event)


def _version_two() -> OutboxEvent:
    return OutboxEvent(
        uuid4(),
        UUID(int=1),
        "trial_balance.version_created",
        {"trial_balance_id": str(uuid4()), "engagement_id": str(uuid4()), "version_no": 2},
    )


def _wire(monkeypatch: pytest.MonkeyPatch, *, signed_on: str) -> tuple[list[object], list[str]]:
    """The follow step over fakes: the view's hash is `now`; the newest sign-off is on
    `signed_on`; staleness is review's computed query, faked here by the same comparison."""
    sink: list[object] = []
    asked: list[str] = []
    set_id = UUID(int=7)

    async def on(*_: object) -> bool:
        return True

    async def mapping_set_of(*_: object) -> object:
        return SimpleNamespace(id=set_id)

    async def mapping_with_prior(*_: object) -> object:
        return SimpleNamespace(content_hash="now", unmapped=1)

    async def stale_of(_tenant: object, target: str, hashes: dict[UUID, str]) -> list[object]:
        asked.append(hashes[set_id])
        assert target == follow.TARGET
        return [object()] if hashes[set_id] != signed_on else []

    async def sign_off_states(*_: object) -> dict[UUID, list[object]]:
        return {
            set_id: [
                SimpleNamespace(level=1, signed_by=PREPARER),
                SimpleNamespace(level=2, signed_by=REVIEWER),
            ]
        }

    async def follow_tb_version(*_: object) -> object:
        return SimpleNamespace(kept_edits=0, dropped_edits=0)

    @asynccontextmanager
    async def uow(_t: object) -> AsyncGenerator[_Tx]:
        yield _Tx(sink)

    for name, fake in {
        "flag_enabled": on,
        "mapping_set_of": mapping_set_of,
        "mapping_with_prior": mapping_with_prior,
        "stale_of": stale_of,
        "sign_off_states": sign_off_states,
        "follow_tb_version": follow_tb_version,
        "uow": uow,
    }.items():
        monkeypatch.setattr(follow, name, fake)
    return sink, asked


async def test_staleness_is_asked_about_the_views_own_current_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, asked = _wire(monkeypatch, signed_on="before")
    assert await follow.on_tb_version(_version_two())
    assert asked == ["now"]


async def test_a_changed_signed_mapping_is_announced_stale_once_to_its_signers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink, _ = _wire(monkeypatch, signed_on="before")
    assert await follow.on_tb_version(_version_two())
    announced = [e for e in sink if isinstance(e, follow.MappingSetWentStale)]
    assert len(announced) == 1
    assert set(announced[0].recipient_user_ids) == {PREPARER, REVIEWER}
    assert announced[0].unmapped == 1
    assert sink.count("mapping_set.went_stale") == 1


async def test_an_unchanged_signed_mapping_is_not_announced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink, _ = _wire(monkeypatch, signed_on="now")
    assert await follow.on_tb_version(_version_two())
    assert not [e for e in sink if isinstance(e, follow.MappingSetWentStale)]
    assert "mapping_set.went_stale" not in sink
    # The version is still followed, once.
    assert len([e for e in sink if isinstance(e, follow.MappingSetFollowedVersion)]) == 1
