"""TASK-7322 (T-04-T29 rest): the review tree names each document's live approval at the shown
level, so Unapprove reaches one made in another session; the workspace summary names BH-TAX-02's
signer only to a viewer who may request final approval. The query's database half is
`tests/integration/test_t04t29_live_approval_ids.py`."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import cast

import pytest

from abacus.modules.identity.api import AuthContext
from abacus.modules.tax import approval, review_tree

RETURN = uuid.uuid4()
ENGAGEMENT = uuid.uuid4()
CLIENT = uuid.uuid4()
DANIEL = uuid.uuid4()
A, B = uuid.uuid4(), uuid.uuid4()


@dataclass
class _Ctx:
    tenant: object = None
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID = field(default_factory=uuid.uuid4)
    client: bool = False


def _ctx() -> AuthContext:
    return cast(AuthContext, _Ctx())


@dataclass
class _Ref:
    client_id: uuid.UUID


class _Session:
    async def scalar(self, *_args: object, **_kw: object) -> str | None:
        return None


@asynccontextmanager
async def _session(_tenant: object) -> AsyncGenerator[_Session]:
    yield _Session()


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    held: frozenset[str],
    allowed: set[str],
    ready: tuple[bool, str | None] = (True, None),
) -> list[str]:
    asked: list[str] = []

    async def _return(_ctx: object, _r: uuid.UUID, action: str) -> tuple[uuid.UUID, object]:
        asked.append(action)
        return ENGAGEMENT, object()

    async def functions_on(*_a: object) -> frozenset[str]:
        return held

    async def live(*_a: object) -> dict[tuple[uuid.UUID, str], int]:
        return {(A, "manager"): 2, (B, "detail"): 1}

    async def live_ids(_ctx: object, _r: uuid.UUID, level: str) -> dict[uuid.UUID, uuid.UUID]:
        return {A: uuid.UUID(int=9)} if level == "manager" else {B: uuid.UUID(int=7)}

    async def documents(*_a: object) -> list[tuple[object, ...]]:
        return [(A, None, "K-1", "K-1s", 2, True), (B, None, "W-2", "Wages", 1, True)]

    async def allowed_actions(_ctx: object, _res: object, actions: tuple[str, ...]) -> set[str]:
        return {a for a in actions if a in allowed}

    async def get_ref(*_a: object) -> _Ref:
        return _Ref(CLIENT)

    async def signer_for(_t: uuid.UUID, client_id: uuid.UUID) -> uuid.UUID | None:
        asked.append(f"signer:{client_id}")
        return DANIEL

    monkeypatch.setattr(review_tree, "_return", _return)
    monkeypatch.setattr(review_tree, "functions_on", functions_on)
    monkeypatch.setattr(review_tree, "_live", live)
    monkeypatch.setattr(review_tree, "_live_ids", live_ids)
    monkeypatch.setattr(review_tree, "engagement_documents", documents)
    monkeypatch.setattr(review_tree, "allowed_actions", allowed_actions)
    monkeypatch.setattr(review_tree, "get_ref", get_ref)
    monkeypatch.setattr(review_tree, "tenant_session", _session)

    async def capability_ready(
        _ctx: object, engagement: uuid.UUID, capability: str
    ) -> tuple[bool, str | None]:
        asked.append(f"capability:{capability}:{engagement}")
        return ready

    monkeypatch.setattr(approval, "signer_for", signer_for)
    monkeypatch.setattr(review_tree, "capability_ready", capability_ready)
    return asked


async def test_an_approved_document_names_its_live_approval_at_the_shown_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch, held=frozenset({"manager_reviewer"}), allowed=set())
    docs, review, at = await review_tree.tree(
        _ctx(),
        RETURN,
        level=None,
        q=None,
        category=None,
    )
    assert at == "manager"
    by = {d.evidence_version_id: d for d in docs}
    assert (by[A].approval, by[A].approval_id) == ("approved", uuid.UUID(int=9))
    # B is approved at detail only: unapproved at manager, so nothing to reverse here.
    assert (by[B].approval, by[B].approval_id) == ("unapproved", None)
    assert review == 1


async def test_a_lower_level_shows_that_levels_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, held=frozenset({"manager_reviewer"}), allowed=set())
    docs, _review, _at = await review_tree.tree(
        _ctx(),
        RETURN,
        level="detail",
        q=None,
        category=None,
    )
    by = {d.evidence_version_id: d for d in docs}
    assert by[B].approval_id == uuid.UUID(int=7)
    assert by[A].approval_id is None


async def test_the_summary_names_the_signer_to_a_viewer_who_may_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _wire(
        monkeypatch,
        held=frozenset({"manager_reviewer"}),
        allowed={"document.approve", "tax_return.request_approval"},
    )
    found = await review_tree.summary(_ctx(), RETURN)
    assert found.final_approver_user_id == DANIEL
    assert f"signer:{CLIENT}" in asked
    assert "tax_return.request_approval" in found.allowed


async def test_the_summary_names_no_signer_without_the_request_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _wire(monkeypatch, held=frozenset({"preparer"}), allowed={"document.approve"})
    found = await review_tree.summary(_ctx(), RETURN)
    assert found.final_approver_user_id is None
    assert not any(a.startswith("signer:") for a in asked)


# TASK-7323 (SPEC-649 AC-6.1, AC-6.8): the workspace's `assistant` reads tax.assistant's
# availability for this person, never a constant.
@pytest.mark.parametrize(
    ("ready", "word"),
    [
        ((True, None), "available"),
        ((False, "consent_7216"), "consent_required"),
        ((False, "paused"), "agents_off"),
        ((False, "ai_policy_off"), "agents_off"),
        ((False, "ai_excluded"), "ai_unavailable"),
        ((False, "not_on_team"), "ai_unavailable"),
        ((False, "capability_unavailable"), "ai_unavailable"),
    ],
)
async def test_the_summary_reads_the_assistants_availability(
    monkeypatch: pytest.MonkeyPatch, ready: tuple[bool, str | None], word: str
) -> None:
    asked = _wire(
        monkeypatch, held=frozenset({"preparer"}), allowed={"document.approve"}, ready=ready
    )
    found = await review_tree.summary(_ctx(), RETURN)
    assert found.assistant == word
    assert f"capability:tax.assistant:{ENGAGEMENT}" in asked
