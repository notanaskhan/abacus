"""SPEC-302 (TASK-303): the palette's search takes the query literally."""

from __future__ import annotations

from abacus.modules.requests.repository import like_pattern


def test_ac2_wildcards_in_the_query_are_literal() -> None:
    assert like_pattern("bank") == "%bank%"
    assert like_pattern("50%_a\\b") == "%50\\%\\_a\\\\b%"
