"""SPEC-033 AC-5, AC-6 (TASK-066 D1): the matcher's picks lead the inbox suggestions, as request
IDs only, limited to requests the person may assign."""

from __future__ import annotations

import uuid

from abacus.modules.evidence.inbox import merged
from abacus.modules.evidence.matching import Reason, Suggestion

A, B, C, D = (uuid.uuid4() for _ in range(4))


def test_ac5_picks_come_first_without_reasons_then_code_without_repeats() -> None:
    code = [
        Suggestion(B, 90, (), "content", (Reason("kind", "bank_statement"),)),
        Suggestion(C, 60, ("bank",), "file_name", (Reason("file_name", "bank"),)),
    ]
    found = merged([(A, 92), (B, 70)], code, {A, B, C})
    assert [(s.request_item_id, s.source) for s in found] == [
        (A, "matcher"),
        (B, "matcher"),
        (C, "file_name"),
    ]
    assert found[0].reasons == () and found[0].matched == ()


def test_ac5_a_pick_the_person_cant_assign_is_left_out() -> None:
    found = merged([(D, 95)], [Suggestion(A, 80, (), "content")], {A})
    assert [s.request_item_id for s in found] == [A]


def test_ac6_without_picks_code_decides_as_before() -> None:
    code = [Suggestion(A, 80, (), "content")]
    assert merged([], code, {A}) == tuple(code)
