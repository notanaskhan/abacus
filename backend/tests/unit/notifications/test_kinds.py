"""P-01-T06 (C16): the kind registry's rules, and the SPEC-013 catalogue registered through it."""

from __future__ import annotations

import re

import pytest

from abacus.modules.notifications.api import CATALOGUE, NotificationKind, register_kind
from abacus.modules.notifications.kinds import (
    AGENT_KINDS,
    INLINE_ACTIONS,
    InlineAction,
    kind_of,
    registered,
)

DB_CHECK = re.compile(r"^[a-z][a-z_]*(\.[a-z][a-z_]*)?$")  # migration 0090


def test_every_catalogued_kind_is_registered_and_passes_the_database_check() -> None:
    codes = {entry.kind for entry in CATALOGUE.values()}
    assert codes <= set(registered())
    assert all(DB_CHECK.fullmatch(code) for code in registered())


def test_a_new_dotted_code_is_refused() -> None:
    with pytest.raises(ValueError, match="undotted"):
        register_kind(NotificationKind("thing.happened", "other", "Bell"))


def test_a_code_registers_once() -> None:
    with pytest.raises(ValueError, match="already registered"):
        register_kind(NotificationKind("mention", "other", "Bell"))
    mention = kind_of("mention")
    assert mention is not None
    register_kind(mention)  # the same registration again is a no-op


def test_inline_actions_are_closed_and_agent_rows_offer_none() -> None:
    with pytest.raises(ValueError, match="inline action"):
        outside: tuple[InlineAction, ...] = ("approve",)  # type: ignore[assignment]  # on purpose
        register_kind(NotificationKind("probe_kind", "other", "Bell", inline_actions=outside))
    with pytest.raises(ValueError, match="agent rows"):
        register_kind(
            NotificationKind("run_finished", "run", "Zap", inline_actions=("accept_document",))
        )
    for code in registered():
        kind = kind_of(code)
        assert kind is not None and set(kind.inline_actions) <= INLINE_ACTIONS
        assert not (code in AGENT_KINDS and kind.inline_actions)


def test_the_renamed_kinds_carry_their_tabs() -> None:
    tabs = {code: kind_of(code) for code in ("client_uploaded", "mention", "review_assigned")}
    assert {code: k.category if k else None for code, k in tabs.items()} == {
        "client_uploaded": "client_activity",
        "mention": "mention",
        "review_assigned": "approval",
    }
