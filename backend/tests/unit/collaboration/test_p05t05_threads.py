"""P-05-T05 (TASK-6602; SPEC-650; ADR-236): the anchor slot's rules and the comment text rules,
without a database. The HTTP acceptance suite is P-05-T07's."""

from __future__ import annotations

import uuid

import pytest

from abacus.modules.collaboration import anchors
from abacus.modules.collaboration.anchors import AnchorFacts, Locator
from abacus.modules.collaboration.candidates import initials, matches
from abacus.modules.collaboration.errors import CommentTooLong, EmptyComment
from abacus.modules.collaboration.threads import MAX_BODY, clean_text
from abacus.modules.identity.api import AuthContext


class _Cells:
    locator_keys = frozenset({"sheet", "cell"})

    async def facts(
        self, ctx: AuthContext, anchor_id: uuid.UUID, locator: Locator | None
    ) -> AnchorFacts | None:
        return None


@pytest.mark.parametrize("kind", sorted(anchors.LIVE_SPEC032_KINDS))
def test_the_live_spec032_kinds_cannot_be_registered_for_v2(kind: str) -> None:
    with pytest.raises(ValueError, match="SPEC-032"):
        anchors.register_anchor(kind, _Cells())


def test_an_unregistered_kind_is_a_409_before_anything_is_read() -> None:
    with pytest.raises(anchors.AnchorKindNotRegistered):
        anchors.provider_of("sheet_row_unregistered")


def test_a_kind_registers_once() -> None:
    # A kind of its own per run: the registry is process-wide and mutmut re-runs the suite in one
    # process (Q-03-T147), so a fixed name would already be taken on the second pass.
    kind = "test_once_" + uuid.uuid4().hex[:12].translate(
        str.maketrans("0123456789", "ghijklmnop")
    )
    provider = _Cells()
    anchors.register_anchor(kind, provider)
    anchors.register_anchor(kind, provider)  # the same provider again is fine
    with pytest.raises(RuntimeError):
        anchors.register_anchor(kind, _Cells())


def test_the_locator_key_is_normalised_and_checked_against_the_schema() -> None:
    provider = _Cells()
    assert anchors.locator_key(provider, None) == ""
    one = anchors.locator_key(provider, {"sheet": "Exceptions", "cell": "A3"})
    two = anchors.locator_key(provider, {"cell": "A3", "sheet": "Exceptions"})
    assert one == two == '{"cell":"A3","sheet":"Exceptions"}'
    with pytest.raises(anchors.LocatorInvalid):
        anchors.locator_key(provider, {"row_text": "Cutoff"})


def test_a_comment_is_cleaned_and_bounded() -> None:
    assert clean_text("  Show it as factual.\u0007 ", MAX_BODY) == "Show it as factual."
    assert clean_text("a" * 4000, MAX_BODY) == "a" * 4000
    with pytest.raises(EmptyComment):
        clean_text(" \n\t ", MAX_BODY)
    with pytest.raises(CommentTooLong):
        clean_text("a" * 4001, MAX_BODY)


def test_a_mention_search_matches_the_start_of_a_word() -> None:
    assert matches("Hannah Leclerc", "Ha")
    assert matches("Hannah Leclerc", "le")
    assert not matches("Margaret Okonkwo", "Ha")
    assert matches("Anyone", None)
    assert initials("Hannah Leclerc") == "HL"
    assert initials("Cher") == "C"
