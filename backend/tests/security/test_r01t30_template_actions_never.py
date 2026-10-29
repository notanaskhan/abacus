"""R-01-T30 (ADR-005, I-AGENT-NEVER): the email-template, portal-settings and sending-domain
actions R-01-T19, T23, T24 and T26 added are denied to an agent, a system run and a support
session, whatever a person would need (DEC-74: an agent never edits, tests, publishes or imports
client email; a scheduled reminder is `SystemSendContext`, never one of these actions)."""

from __future__ import annotations

import pytest

from .matrix_harness import Principal, principal_outcome

ACTIONS = (
    "email_template.edit",
    "email_template.test_send",
    "email_template.publish",
    "email_template.import",
    "portal_settings.manage",
    "sending_domain.manage",
)
PRINCIPALS: tuple[Principal, ...] = ("agent", "system", "support")


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("principal", PRINCIPALS)
async def test_the_principal_is_denied(
    monkeypatch: pytest.MonkeyPatch, action: str, principal: Principal
) -> None:
    assert await principal_outcome(monkeypatch, action, principal) == "deny"
