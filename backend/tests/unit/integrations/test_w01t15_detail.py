"""W-01-T15 (red): the timeline's labels are written at read time and failures read not ok."""

from __future__ import annotations

from abacus.modules.integrations import connect_detail as cd


def test_labels_are_read_time_words_and_failures_are_not_ok() -> None:
    assert cd.label_of("token_expired") == "Token expired"
    assert cd.label_of("run_failed") == "1 scheduled run failed"
    assert cd.label_of("something_new") == "Something new"
    assert "token_expired" in cd._FAILED  # pyright: ignore[reportPrivateUsage] -- the rule


def test_a_malformed_cursor_starts_from_the_newest() -> None:
    assert cd._cursor("garbage") == (None, None)  # pyright: ignore[reportPrivateUsage] -- the rule
