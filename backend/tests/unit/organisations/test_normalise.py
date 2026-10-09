"""SPEC-025 AC-1 (TASK-043 D2): duplicate clients are caught by a normalised name; this mirrors
the database's generated column (migration 0035), checked against it in the local smoke."""

from __future__ import annotations

import pytest

from abacus.modules.organisations.api import normalise


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Halvorsen", "halvorsen"),
        ("  HALVORSEN, Inc. ", "halvorsen"),
        ("Halvorsen LLC", "halvorsen"),
        ("Halvorsen & Sons Ltd", "halvorsen sons"),
        ("Halvorsen-Sons Corporation", "halvorsen sons"),
        ("Co-op Foods Co.", "op foods"),
        ("ACME   Holdings  PLC", "acme holdings"),
        ("Inc.", ""),
    ],
)
def test_ac1_names_normalise_alike(name: str, expected: str) -> None:
    assert normalise(name) == expected
