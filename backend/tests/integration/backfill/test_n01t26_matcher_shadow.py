"""N-01-T26 (TASK-2334; DEC-1380): the matcher's shadow stage (SPEC-036 D2; chapter 10 QD-10).

- A shadow run's proposals are recorded but never offered on INB-02 (nor raise
  `ambiguous_candidates`): nothing a shadow run produces is shown.
- The shadow score counts the matcher: each attachment's newest shadow run against the person's
  triage decision on it (filed where it proposed: agreed; ignored instead: overridden).

Boundary: T22's fake-model harness (ADR-076) with the firm's stage as shadow; the person's decision
through `communications.triage_apply` as a signed-in member.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents import intake_match
from abacus.modules.agents.shadow_score import MATCHER, shadow_score
from abacus.modules.communications import triage_apply
from abacus.modules.communications.intake_candidates import card_candidates
from abacus.modules.identity.api import AuthContext, member_context

from .support import Net
from .test_n01t22_intake_match import (  # T22's fake-model harness (ADR-076)
    Firm,
    Stub,
    _firm,  # pyright: ignore[reportPrivateUsage] -- T22's firm builder, shared harness
    answer,
)
from .test_n01t22_intake_match import raw as raw
from .test_n01t22_intake_match import stub as stub
from .test_n01t22_intake_match import wired as wired

pytestmark = pytest.mark.asyncio


@pytest.fixture
def in_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    """The firm's stage for the matcher is shadow (a synthetic firm never is: set it here)."""

    async def shadow(*_: object) -> bool:
        return True

    monkeypatch.setattr(intake_match, "starts_in_shadow", shadow)


async def _member(firm: Firm) -> AuthContext:
    found = await member_context(firm.tenant_id, firm.partner.user_id)
    assert found is not None
    return found


async def _request_id(net: Net, firm: Firm) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await net.seed.value(
            "SELECT id FROM request_items WHERE engagement_id = $1 AND description = $2",
            firm.site.engagement_id,
            firm.request_marker,
        ),
    )


async def _message(net: Net, attachment: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await net.seed.value("SELECT message_id FROM inbox_attachments WHERE id = $1", attachment),
    )


async def test_ac_a_shadow_runs_proposals_are_never_offered(
    net: Net,
    stub: Stub,
    in_shadow: None,
) -> None:
    firm = await _firm(net)
    stub.answer = answer(firm.request_marker, confidence=0.95)
    attachment = await firm.receive()
    _, status = await firm.match(attachment)
    assert status == "completed"
    shadow = await net.seed.value(
        "SELECT shadow FROM agent_runs WHERE inbox_attachment_id = $1", attachment
    )
    assert shadow is True
    shown = await net.seed.value(
        "SELECT count(*) FROM inbox_match_proposals p JOIN inbox_match_runs r "
        "ON r.id = p.match_id WHERE r.inbox_attachment_id = $1 AND p.shown",
        attachment,
    )
    assert shown == 1  # recorded as it would have shown
    assert (await card_candidates(await _member(firm), [attachment])).get(attachment, []) == []
    ambiguous = await net.seed.value(
        "SELECT count(*) FROM inbox_attachment_flags WHERE attachment_id = $1 "
        "AND kind = 'ambiguous_candidates'",
        attachment,
    )
    assert ambiguous == 0


async def test_ac_the_shadow_score_counts_the_matcher_against_triage(
    net: Net,
    stub: Stub,
    in_shadow: None,
) -> None:
    firm = await _firm(net)
    stub.answer = answer(firm.request_marker, confidence=0.95)
    followed = await firm.receive()
    overridden = await firm.receive()
    for attachment in (followed, overridden):
        _, status = await firm.match(attachment)
        assert status == "completed"
    member = await _member(firm)
    request = await _request_id(net, firm)
    await triage_apply.apply(
        member,
        await _message(net, followed),
        [triage_apply.Decision(followed, "file", "request", request, "new_document")],
    )
    await triage_apply.apply(
        member,
        await _message(net, overridden),
        [triage_apply.Decision(overridden, "ignore", reason_codes=("duplicate",))],
    )

    found = await shadow_score(
        TenantContext(firm.tenant_id, "system", "test.n01t26"), MATCHER, datetime.now(UTC)
    )
    assert (found.runs, found.scored, found.agreed) == (2, 2, 1)
    assert found.disagreement == "0.5000"
    assert found.qd10 is False  # too few scored, and over 8 %: the live stage waits
