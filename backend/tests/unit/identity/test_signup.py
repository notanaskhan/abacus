"""SPEC-024 AC-1 (TASK-040): firm names and sign-up codes."""

from __future__ import annotations

import re

import pytest

from abacus.modules.identity.signup import SignupInvalid, clean_firm_name
from abacus_tools.signup_codes import new_code


@pytest.mark.parametrize(
    ("raw", "kept"),
    [
        ("  Whitfield   &  Lane ", "Whitfield & Lane"),
        ("Firm​\tName", "Firm Name"),
        ("x" * 200, "x" * 200),
    ],
)
def test_ac1_firm_names_are_single_line_printable_text(raw: str, kept: str) -> None:
    assert clean_firm_name(raw) == kept


@pytest.mark.parametrize("raw", ["", "   ", "​", "x" * 201])
def test_ac1_empty_or_overlong_firm_names_are_refused(raw: str) -> None:
    with pytest.raises(SignupInvalid):
        clean_firm_name(raw)


def test_ac1_codes_are_grouped_and_avoid_confusable_characters() -> None:
    codes = {new_code() for _ in range(200)}
    assert len(codes) == 200
    assert all(re.fullmatch(r"[A-HJKMNP-Z2-9]{4}(-[A-HJKMNP-Z2-9]{4}){3}", c) for c in codes)
