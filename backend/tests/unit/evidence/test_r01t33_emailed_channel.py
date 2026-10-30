"""R-01-T33: a file the firm filed from an emailed intake reads "Received by email" on POR-03."""

from __future__ import annotations

from abacus.modules.evidence.portal_files import (
    _arrived,  # pyright: ignore[reportPrivateUsage] -- the rule under test
)


def test_an_inbox_filed_email_reads_as_email() -> None:
    assert _arrived("inbox", "uploaded", "email") == "email"


def test_other_inbox_channels_read_as_the_firm() -> None:
    assert _arrived("inbox", "uploaded", "firm_upload") == "firm"
    assert _arrived("inbox", "uploaded", "portal") == "firm"
    assert _arrived("inbox", "uploaded", None) == "firm"
