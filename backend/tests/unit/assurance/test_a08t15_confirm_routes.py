"""A-08-T15 (SPEC-657 F7): the public confirm family answers unknown, expired and revoked tokens
identically: the same uniform `expired` view and the same padded floor (no timing oracle)."""

from __future__ import annotations

import time

import pytest

from abacus.modules.assurance import confirmations_contract as cc


@pytest.mark.asyncio
async def test_ac_unknown_expired_and_revoked_are_indistinguishable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def nothing(token: str) -> None:
        return None

    monkeypatch.setattr(cc, "_fixture_mode", lambda: False)
    monkeypatch.setattr(cc, "resolve_link", nothing)
    answers: list[tuple[dict[str, object], bool]] = []
    for token in ("unknown-token-aaaaaaaa", "expired-token-bbbbbbbb", "revoked-token-cccccccc"):
        started = time.monotonic()
        view = await cc.respondent_view(token)
        answers.append((view.model_dump(), time.monotonic() - started >= cc.CONFIRM_PAD_SECONDS))
    assert all(a == answers[0] for a in answers)
    assert answers[0][0]["state"] == "expired" and answers[0][1]
