"""SPEC-025 AC-8 (TASK-043): invitations go out in the firm's name, naming client and year."""

from __future__ import annotations

from abacus.modules.communications.invitations import (
    STAFF_SUBJECT,
    STAFF_TEMPLATE,
    SUBJECT,
    TEMPLATE,
)

NAMES = {"firm": "Whitfield & Lane", "client": "Halvorsen", "year": "2026"}


def test_ac8_client_invitations_name_the_firm_client_and_year() -> None:
    subject = SUBJECT.format(**NAMES)
    body = TEMPLATE.format(link="https://x.test/a", expires="23 October 2026", **NAMES)
    assert subject == "Whitfield & Lane invites you to their FY2026 audit of Halvorsen"
    assert body.startswith("Whitfield & Lane has invited you")
    assert "Halvorsen" in body and "FY2026" in body


def test_ac8_staff_invitations_name_the_firm() -> None:
    assert STAFF_SUBJECT.format(firm="Whitfield & Lane").startswith("Whitfield & Lane invites")
    body = STAFF_TEMPLATE.format(firm="Whitfield & Lane", link="l", expires="e")
    assert body.startswith("Whitfield & Lane has invited you")
