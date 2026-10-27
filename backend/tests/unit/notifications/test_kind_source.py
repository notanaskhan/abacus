"""ED-015 (C16 §3; P-01 §4.6): `register_kind_source` adds a producing event to an existing kind
and subscribes the relay to it; an unknown kind or an event that already produces a kind fails."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest

from abacus.modules.notifications import api as notifications

EVENT = "test_source.mentioned"


async def _nobody(_tenant: UUID, _payload: dict[str, object]) -> list[UUID]:
    return []


@pytest.fixture
def clean() -> Iterator[None]:
    yield
    notifications.CATALOGUE.pop(EVENT, None)
    notifications.SUBSCRIPTIONS.pop(EVENT, None)


@pytest.mark.usefixtures("clean")
def test_a_new_event_produces_an_existing_kind_and_reaches_the_relay() -> None:
    notifications.register_kind_source(
        "mention", EVENT, _nobody, ("request_item", "request_item_id")
    )
    entry = notifications.CATALOGUE[EVENT]
    assert (entry.kind, entry.subject_type, entry.subject_key) == (
        "mention",
        "request_item",
        "request_item_id",
    )
    assert notifications.SUBSCRIPTIONS[EVENT] is notifications.SUBSCRIPTIONS["comment.mentioned"]


@pytest.mark.usefixtures("clean")
def test_an_unregistered_kind_fails() -> None:
    with pytest.raises(ValueError, match="not registered"):
        notifications.register_kind_source("no_such_kind", EVENT, _nobody, ("engagement", None))
    assert EVENT not in notifications.CATALOGUE
    assert EVENT not in notifications.SUBSCRIPTIONS


def test_an_event_that_already_produces_a_kind_fails() -> None:
    with pytest.raises(ValueError, match="already produces"):
        notifications.register_kind_source(
            "mention", "comment.mentioned", _nobody, ("request_item", "request_item_id")
        )
    assert notifications.CATALOGUE["comment.mentioned"].kind == "mention"
