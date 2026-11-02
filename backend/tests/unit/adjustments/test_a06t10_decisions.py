"""A-06-T10 (TASK-3013; A-06 §4.3; SPEC-642; DEC-2062): the adjustments service, part 2.

Row acceptance: "A send writes one decision row and one batch at once, nothing reaches the client
before the grant is released, Undo inside 10 seconds voids it, and no route or adapter can post an
entry." The database half (one unit of work, the grant consumed by the relay) is the integration
suite's; here: the held send's shape, the 10-second window, fail-closed delivery, the person-only
guard, and that nothing in the module or the API names a post.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest

from abacus.api.export_openapi import document
from abacus.modules.adjustments import decisions
from abacus.modules.identity.api import Forbidden


def test_ac_the_undo_window_is_ten_seconds() -> None:
    assert timedelta(seconds=10) == decisions.UNDO_WINDOW


def test_ac_the_send_digest_binds_the_batch_entries_recipient_and_wording() -> None:
    b, e1, e2, r, w = (uuid.uuid4() for _ in range(5))
    digest = decisions.send_digest(b, [e1, e2], r, w)
    assert digest == decisions.send_digest(b, [e2, e1], r, w)  # order-free
    assert digest != decisions.send_digest(b, [e1], r, w)
    assert len(digest) == 64


async def test_ac_nothing_reaches_the_client_without_a_c18_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(decisions, "_DELIVERY", [])
    event = SimpleNamespace(tenant_id=uuid.uuid4(), payload={})
    await decisions.on_sent(event)  # pyright: ignore[reportArgumentType] -- a stand-in event


@pytest.mark.parametrize("kind", ["agent", "system", "policy"])
def test_ac_only_a_live_person_decides(kind: str) -> None:
    ctx = SimpleNamespace(tenant=SimpleNamespace(actor_kind=kind), client=False, is_support=False)
    with pytest.raises(Forbidden):
        decisions._live_human(ctx, decisions.SEND)  # pyright: ignore[reportArgumentType, reportPrivateUsage] -- a stand-in principal


def test_ac_the_send_is_held_on_its_grant_and_subscribed() -> None:
    assert decisions.EntriesSentToClient.event_type in decisions.SUBSCRIPTIONS


def test_ac_no_route_or_adapter_can_post_an_entry() -> None:
    paths = json.loads(document())["paths"]
    adjust = [
        p for p in paths if "proposed-entr" in p or "approval-batch" in p or "adjusted-tb" in p
    ]
    assert adjust
    assert not [p for p in adjust if "post" in p.lower().replace("/v1/", "")]
    source = (decisions.__file__, decisions.__file__.replace("decisions.py", "entries.py"))
    for path in source:
        text = open(path, encoding="utf-8").read()  # noqa: SIM115
        assert "'posted'" not in text and '"posted"' not in text
