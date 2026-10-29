"""R-01-T27 pure rules (TASK-1850; R-01 story 8.3, 9.2; DEC-950 to DEC-955): a domain check's
transitions, the gate's audiences, the transport's From and the operator's command."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from abacus.modules.communications.sending_domains import (
    VERIFY_WINDOW,
    gated,
    next_state,
)
from abacus.modules.communications.ses_identities import IdentityStatus, State
from abacus.modules.communications.transport import LocalMailbox
from abacus_tools.client_mail import MailChange, Refused

ASKED = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


def _found(dkim: State, mail_from: State) -> IdentityStatus:
    return IdentityStatus("brightwaterhale.com", "pending", dkim, mail_from)


def test_ac1_dkim_and_mail_from_verified_moves_pending_dns_to_verified() -> None:
    made = next_state(
        "pending_dns", _found("verified", "verified"), ASKED, ASKED + timedelta(hours=1)
    )
    assert (made.status, made.failure_reason) == ("verified", None)


@pytest.mark.parametrize(
    ("dkim", "mail_from"),
    [("pending", "pending"), ("verified", "pending"), ("pending", "verified")],
)
def test_ac1_anything_less_stays_pending_inside_the_window(dkim: State, mail_from: State) -> None:
    made = next_state("pending_dns", _found(dkim, mail_from), ASKED, ASKED + timedelta(hours=71))
    assert made.status == "pending_dns" and made.failure_reason is None


@pytest.mark.parametrize(
    ("dkim", "mail_from", "reason"),
    [
        ("pending", "pending", "dkim_not_verified"),
        ("verified", "pending", "mail_from_not_verified"),
    ],
)
def test_ac1_72_hours_without_verification_fails_with_the_reason(
    dkim: State, mail_from: State, reason: str
) -> None:
    made = next_state("pending_dns", _found(dkim, mail_from), ASKED, ASKED + VERIFY_WINDOW)
    assert (made.status, made.failure_reason) == ("failed", reason)


def test_ac1_a_missing_identity_waits_then_fails_as_identity_missing() -> None:
    assert (
        next_state("pending_dns", None, ASKED, ASKED + timedelta(hours=1)).status == "pending_dns"
    )
    made = next_state("pending_dns", None, ASKED, ASKED + VERIFY_WINDOW)
    assert (made.status, made.failure_reason) == ("failed", "identity_missing")


def test_ac1_ses_saying_failed_fails_at_once() -> None:
    made = next_state(
        "pending_dns", _found("failed", "pending"), ASKED, ASKED + timedelta(hours=1)
    )
    assert (made.status, made.failure_reason) == ("failed", "dkim_not_verified")


def test_a_verified_domain_keeps_its_status_through_a_temporary_failure() -> None:
    assert next_state("verified", _found("pending", "verified"), ASKED, ASKED).status == "verified"
    made = next_state("verified", _found("verified", "failed"), ASKED, ASKED)
    assert (made.status, made.failure_reason) == ("failed", "mail_from_not_verified")
    assert next_state("verified", None, ASKED, ASKED).failure_reason == "identity_missing"


@pytest.mark.parametrize("status", ["failed", "revoked"])
def test_a_failed_or_revoked_domain_never_moves(status: str) -> None:
    made = next_state(status, _found("verified", "verified"), ASKED, ASKED)  # pyright: ignore[reportArgumentType] -- a status string the Literal names
    assert made.status == status


def test_ac2_the_gate_closes_every_audience_outside_the_firm() -> None:
    for audience in ("client", "third_party", "respondent"):
        assert gated([audience])
    assert not gated(["staff"]) and not gated([])


def test_the_local_mailbox_records_the_firm_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "test")
    LocalMailbox(tmp_path).send(
        to="claire@example.test",
        subject="Two things are still open",
        body="Hi Claire",
        sender_name="Brightwater Hale",
        reply_to=None,
        tenant_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        from_address="clients@brightwaterhale.com",
    )
    (written,) = tmp_path.iterdir()
    assert json.loads(written.read_text())["from_address"] == "clients@brightwaterhale.com"


def test_opening_client_mail_names_two_different_people() -> None:
    tenant = uuid.uuid4()
    with pytest.raises(Refused):
        MailChange(tenant, True, "ayush", None, "CR-1").checked()
    with pytest.raises(Refused):
        MailChange(tenant, True, "ayush", "ayush", "CR-1").checked()
    with pytest.raises(Refused):
        MailChange(tenant, True, "Ayush@firm.example", "anas", "CR-1").checked()
    assert MailChange(tenant, True, "ayush", "anas", "CR-1").checked().open
    assert not MailChange(tenant, False, "ayush", None, "CR-2").checked().open  # a rollback
