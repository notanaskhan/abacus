"""F-08-T13 (TASK-8845; F-08 §F1; DEC-5844): presence anchors and the base endpoint.

Row acceptance: "PUT /v1/presence accepts cell, section and card anchors only for registered kinds,
heartbeats expire after 45 s, and nothing is audited or sent through the outbox."
"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from typing import get_args

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.ephemeral import EPHEMERAL_TABLES, NotEphemeral, ephemeral_write
from abacus.kernel.errors import NotFound
from abacus.modules.platform import presence


def test_ac_unregistered_kind_refused() -> None:
    assert not asyncio.run(presence._may_read(object(), "no_such_kind", uuid.uuid4()))  # pyright: ignore[reportPrivateUsage] -- the unit under test
    with pytest.raises(NotFound):
        asyncio.run(presence.present(object(), "no_such_kind", uuid.uuid4()))


def test_ac_anchor_kinds() -> None:
    assert set(get_args(presence.AnchorKind)) == {"cell", "section", "card", "record"}


def test_ac_expires_after_45_seconds() -> None:
    assert presence.TTL.total_seconds() == 45
    assert "make_interval(secs => :ttl)" in inspect.getsource(presence.present)


def test_ac_not_audited_and_no_outbox() -> None:
    source = inspect.getsource(presence)
    assert "uow(" not in source and "tx.record" not in source and "tx.emit" not in source
    assert frozenset({"presence_heartbeats"}) == EPHEMERAL_TABLES


def test_ephemeral_refuses_any_other_table() -> None:
    with pytest.raises(NotEphemeral):
        asyncio.run(
            ephemeral_write(
                TenantContext(uuid.uuid4(), "human", "u"), "UPDATE issues SET x = 1", {}
            )
        )


def test_work_item_kind_registered() -> None:

    assert "work_item" in presence.presence_kinds()
