"""Q-03-T164 (ED-301): the synthetic sink's sign-in code is a whole six-digit token."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from abacus_tools.harness.mailbox import Mail

AT = datetime(2026, 11, 3, tzinfo=UTC)


def _mail(body: str, subject: str = "Notice") -> Mail:
    return Mail(
        to="hannah.leclerc+a4b5c3e2@sink.example.test", subject=subject, body=body, sent_at=AT
    )


@pytest.mark.parametrize(
    "body",
    [
        "Engagement: Seeded client · 3f1e2a9b-457780ab-4c1d-9e2f-0a1b2c3d4e5f",  # inside a UUID
        "Open it: https://app.example.test/e/c486040120f1dda1",  # inside a hex id
        "Reply to hannah.leclerc+123456@sink.example.test",  # inside an address
        "Reference ab_123456 and 123456-7",  # joined to a word or a number
    ],
)
def test_ed301_six_digits_inside_another_token_are_not_a_code(body: str) -> None:
    assert _mail(body).code is None


@pytest.mark.parametrize(
    ("subject", "body", "code"),
    [
        ("Your sign-in code", "Your code is 457780.", "457780"),
        ("457780 is your code", "It expires in 10 minutes.", "457780"),
        ("Sign in", "Code: 012345\nIt works once.", "012345"),
    ],
)
def test_ed301_a_sign_in_code_standing_alone_is_read(subject: str, body: str, code: str) -> None:
    assert _mail(body, subject).code == code
