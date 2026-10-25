"""ADR-157 / platform-ops §3.7 (P-08-T21): `control_active` is the one reader of the kill
switches: a firm row or a platform row turns a control on, a change lands within the 10-second
cache, and an unreadable state fails closed only for `ai_pause` and `read_only`."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from abacus.kernel import controls
from abacus.kernel.controls import Active, control_active

FIRM = uuid.uuid4()
OTHER = uuid.uuid4()


@pytest.fixture(autouse=True)
def fresh(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[float]]:
    controls.forget_controls()
    now = [100.0]
    monkeypatch.setattr(controls, "_clock", lambda: now[0])
    yield now
    controls.forget_controls()


def _rows(
    monkeypatch: pytest.MonkeyPatch, *active: tuple[str, str, uuid.UUID | None, str | None]
) -> list[int]:
    reads: list[int] = []

    async def read() -> Active:
        reads.append(1)
        return frozenset(active)

    monkeypatch.setattr(controls, "_read", read)
    return reads


async def test_a_firm_row_pauses_only_that_firm(monkeypatch: pytest.MonkeyPatch) -> None:
    _rows(monkeypatch, ("portal_sign_in", "firm", FIRM, None))
    assert await control_active("portal_sign_in", FIRM)
    assert not await control_active("portal_sign_in", OTHER)
    assert not await control_active("portal_sign_in")
    assert not await control_active("email_pause", FIRM)


async def test_a_platform_row_covers_every_firm(monkeypatch: pytest.MonkeyPatch) -> None:
    _rows(monkeypatch, ("ai_pause", "platform", None, None))
    assert await control_active("ai_pause", FIRM) and await control_active("ai_pause")


async def test_a_route_block_needs_its_route(monkeypatch: pytest.MonkeyPatch) -> None:
    _rows(monkeypatch, ("model_route_block", "platform", None, "bedrock"))
    assert await control_active("model_route_block", route="bedrock")
    assert not await control_active("model_route_block", route="anthropic")


async def test_a_change_lands_within_the_cache_window(
    monkeypatch: pytest.MonkeyPatch, fresh: list[float]
) -> None:
    reads = _rows(monkeypatch)
    assert not await control_active("portal_sign_in", FIRM)
    _rows(monkeypatch, ("portal_sign_in", "firm", FIRM, None))
    fresh[0] += controls.CACHE_SECONDS - 1
    assert not await control_active("portal_sign_in", FIRM)  # still the cached state
    fresh[0] += 1
    assert await control_active("portal_sign_in", FIRM)
    assert reads == [1]
    assert controls.CACHE_SECONDS == 10.0


async def test_an_unreadable_state_fails_closed_for_ai_writes_and_the_sign_in_pause(
    monkeypatch: pytest.MonkeyPatch, fresh: list[float]
) -> None:
    """P-08-T21 security review: a sign-in pause that can't be read counts as on."""

    async def broken() -> Active:
        raise OSError("database unavailable")

    monkeypatch.setattr(controls, "_read", broken)
    assert await control_active("ai_pause", FIRM)
    assert await control_active("read_only", FIRM)
    assert await control_active("portal_sign_in", FIRM)
    assert not await control_active("email_pause", FIRM)


async def test_a_stale_sign_in_state_is_trusted_for_60_seconds_then_refused(
    monkeypatch: pytest.MonkeyPatch, fresh: list[float]
) -> None:
    _rows(monkeypatch)  # read once: not paused
    assert not await control_active("portal_sign_in", FIRM)

    async def broken() -> Active:
        raise OSError("database unavailable")

    monkeypatch.setattr(controls, "_read", broken)
    fresh[0] += controls.STALE_LIMIT_SECONDS
    assert not await control_active("portal_sign_in", FIRM)  # 60 s old: still trusted
    assert not await control_active("email_pause", FIRM)
    fresh[0] += 1
    assert await control_active("portal_sign_in", FIRM)  # older: counts as paused
    assert not await control_active("email_pause", FIRM)  # others keep the last known value
    assert controls.STALE_LIMIT_SECONDS == 60.0


async def test_an_unreadable_state_keeps_the_last_known_value(
    monkeypatch: pytest.MonkeyPatch, fresh: list[float]
) -> None:
    _rows(monkeypatch, ("portal_sign_in", "firm", FIRM, None))
    assert await control_active("portal_sign_in", FIRM)

    async def broken() -> Active:
        raise OSError("database unavailable")

    monkeypatch.setattr(controls, "_read", broken)
    fresh[0] += controls.CACHE_SECONDS
    assert await control_active("portal_sign_in", FIRM)
    assert await control_active("ai_pause", FIRM)  # fails closed whatever was known
