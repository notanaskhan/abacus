"""Q-01-T12 / SPEC-050 AC-15: the SES transport (P3), written from the spec text.

Spec: "Given a message that passed `communications/scope.py` and the mechanical body check (no
SSN, TIN, account number or tax amount), when it is sent, then `SesTransport` sends through the
environment's configuration set with the firm's display name and Reply-To, and message tags carry
only `tenant_id` and `message_id` (never an address); given a blocked message, then the SES
client is never called." Also: any SES error fails closed (spec section "Failure modes"), and
ADR-065 (outbound messages are checked before they leave).

Public names and signatures only are taken from the code:
`SesTransport(client, *, configuration_set, from_address)` and its `send(...)`, `MessageBlocked`,
`TransportError`, `transport()`. SES is a real botocore client under `botocore.stub.Stubber`
(it validates every request against the service model); a hook counts the calls that reach it.

Sensitive numbers in the fixtures are assembled at run time so that no SSN-, EIN- or account-shaped
literal sits in this file.
"""

from __future__ import annotations

import copy
import json
import uuid

import pytest
from botocore.stub import Stubber

from abacus.modules.communications.body_check import MessageBlocked
from abacus.modules.communications.transport import SesTransport, transport

from .support import Json, fails, ses_client, use_environment, use_staging

CONFIGURATION_SET = "abacus-staging-fake"
PLATFORM_ADDRESS = "notifications@mail.example.test"
FIRM_NAME = "Brightwater and Hale LLP"
FIRM_REPLY_TO = "ops@firm.example.test"
CLIENT_ADDRESS = "pat.client@client.example.test"
TENANT = uuid.UUID("0a0a0a0a-0a0a-4a0a-8a0a-0a0a0a0a0a0a")
MESSAGE = uuid.UUID("0c0c0c0c-0c0c-4c0c-8c0c-0c0c0c0c0c0c")

CLEAN_SUBJECT = "Documents still needed for the year-end review"
CLEAN_BODY = "Please upload the March bank statement by Friday. 3 items remain for 2026."


def digits(*parts: str) -> str:
    return "".join(parts)


SSN = "-".join(("412", "34", "5678"))
EIN = "-".join(("12", "3456789"))
BARE_TIN = digits("4123", "4567", "8")
ACCOUNT = digits("4400", "1234", "5678")


class Ses:
    """A stubbed SES v2 client that records what reaches it."""

    def __init__(self, *, answer: bool = True) -> None:
        self.client = ses_client()
        self.requests: list[Json] = []
        self.reached = 0
        self.client.meta.events.register("provide-client-params.sesv2.SendEmail", self._record)
        self.client.meta.events.register("provide-client-params.sesv2", self._count)
        self.stub = Stubber(self.client)
        if answer:
            self.stub.add_response("send_email", {"MessageId": "fake-message-id"})

    def _record(self, params: Json, **_: object) -> None:
        self.requests.append(copy.deepcopy(params))

    def _count(self, **_: object) -> None:
        self.reached += 1


def transport_for(ses: Ses) -> SesTransport:
    return SesTransport(
        ses.client,
        configuration_set=CONFIGURATION_SET,
        from_address=PLATFORM_ADDRESS,
    )


def send(ses: Ses, **overrides: object) -> None:
    arguments: Json = {
        "to": CLIENT_ADDRESS,
        "subject": CLEAN_SUBJECT,
        "body": CLEAN_BODY,
        "sender_name": FIRM_NAME,
        "reply_to": FIRM_REPLY_TO,
        "tenant_id": TENANT,
        "message_id": MESSAGE,
    }
    arguments.update(overrides)
    with ses.stub:
        transport_for(ses).send(**arguments)


def sent_request(ses: Ses) -> Json:
    send(ses)
    assert ses.reached == 1
    (request,) = ses.requests
    return request


# --- what goes to SES ---------------------------------------------------------------------------


def test_ac15_a_clean_message_goes_out_through_the_configuration_set() -> None:
    request = sent_request(Ses())
    assert request["ConfigurationSetName"] == CONFIGURATION_SET


def test_ac15_the_message_is_addressed_to_the_recipient_and_carries_subject_and_body() -> None:
    request = sent_request(Ses())
    assert request["Destination"]["ToAddresses"] == [CLIENT_ADDRESS]
    content = json.dumps(request["Content"], default=repr)
    assert CLEAN_SUBJECT in content
    assert CLEAN_BODY in content


def test_ac15_the_firms_display_name_fronts_the_platform_address() -> None:
    request = sent_request(Ses())
    sender = request["FromEmailAddress"]
    assert FIRM_NAME in sender
    assert PLATFORM_ADDRESS in sender  # the address stays the platform's


def test_ac15_replies_go_to_the_firms_reply_to() -> None:
    request = sent_request(Ses())
    assert request["ReplyToAddresses"] == [FIRM_REPLY_TO]


def test_ac15_a_display_name_with_punctuation_cannot_break_out_of_the_header() -> None:
    ses = Ses()
    send(ses, sender_name='Hale, Brightwater & "Co"')
    (request,) = ses.requests
    sender = request["FromEmailAddress"]
    assert sender.endswith(f"<{PLATFORM_ADDRESS}>")
    assert "\n" not in sender and "\r" not in sender


def test_ac15_message_tags_carry_only_tenant_id_and_message_id() -> None:
    request = sent_request(Ses())
    tags = {tag["Name"]: tag["Value"] for tag in request["EmailTags"]}
    assert tags == {"tenant_id": str(TENANT), "message_id": str(MESSAGE)}
    assert len(request["EmailTags"]) == 2


def test_ac15_no_address_appears_in_a_tag_or_the_configuration_set() -> None:
    request = sent_request(Ses())
    carried = json.dumps([request["EmailTags"], request["ConfigurationSetName"]])
    for address in (CLIENT_ADDRESS, FIRM_REPLY_TO, PLATFORM_ADDRESS):
        assert address not in carried
    assert "@" not in carried


def test_ac15_the_tags_follow_the_ids_given_per_message() -> None:
    other_tenant, other_message = uuid.uuid4(), uuid.uuid4()
    ses = Ses()
    send(ses, tenant_id=other_tenant, message_id=other_message)
    (request,) = ses.requests
    tags = {tag["Name"]: tag["Value"] for tag in request["EmailTags"]}
    assert tags == {"tenant_id": str(other_tenant), "message_id": str(other_message)}


def test_ac15_a_message_without_a_firm_name_or_reply_to_still_sends() -> None:
    ses = Ses()
    send(ses, sender_name=None, reply_to=None)
    assert ses.reached == 1
    (request,) = ses.requests
    assert PLATFORM_ADDRESS in request["FromEmailAddress"]
    assert not request.get("ReplyToAddresses")


# --- the mechanical body check: a blocked message never reaches SES -----------------------------

BLOCKED_BODIES = {
    "ssn": f"For your records, the number on file is {SSN}.",
    "ssn_with_cue": f"Your SSN is {SSN}; please confirm.",
    "ein": f"Our EIN {EIN} is on the engagement letter.",
    "bare_tin": f"Taxpayer identification number: {BARE_TIN}",
    "account": f"Please wire it to account number {ACCOUNT}.",
    "tax_refund": "Your federal tax refund is $4,210.00 this year.",
    "tax_due": "Estimated tax due: $12,500 by April 15.",
    "tax_liability": "The total tax liability of $8,333.33 was computed.",
}


@pytest.mark.parametrize("kind", sorted(BLOCKED_BODIES))
def test_ac15_a_blocked_body_never_reaches_the_ses_client(kind: str) -> None:
    ses = Ses(answer=False)
    with pytest.raises(MessageBlocked):
        send(ses, body=BLOCKED_BODIES[kind])
    assert ses.reached == 0
    assert ses.requests == []


@pytest.mark.parametrize("kind", ["ssn", "ein", "account", "tax_refund"])
def test_ac15_a_blocked_subject_never_reaches_the_ses_client(kind: str) -> None:
    ses = Ses(answer=False)
    with pytest.raises(MessageBlocked):
        send(ses, subject=BLOCKED_BODIES[kind])
    assert ses.reached == 0


def test_ac15_a_blocked_message_leaks_none_of_the_blocked_value() -> None:
    ses = Ses(answer=False)
    error = fails(lambda: send(ses, body=BLOCKED_BODIES["ssn"]))
    assert isinstance(error, MessageBlocked)
    assert SSN not in str(error)


@pytest.mark.parametrize(
    "body",
    [
        CLEAN_BODY,
        "Hello, the engagement for 2026 is scheduled; 12 requests are open.",
        "Your invoice is attached. Call us with any question.",
    ],
)
def test_ac15_ordinary_messages_are_not_blocked(body: str) -> None:
    ses = Ses()
    send(ses, body=body)
    assert ses.reached == 1


# --- any SES error fails closed -----------------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [
        "MessageRejected",
        "TooManyRequestsException",
        "SendingPausedException",
        "AccountSuspendedException",
        "MailFromDomainNotVerifiedException",
        "LimitExceededException",
        "NotFoundException",
    ],
)
def test_ac15_an_ses_error_is_an_error_not_a_silent_success(code: str) -> None:
    ses = Ses(answer=False)
    ses.stub.add_client_error("send_email", service_error_code=code)
    error = fails(lambda: send(ses))
    assert not isinstance(error, AssertionError)
    assert ses.reached == 1  # one attempt: the relay retries, the transport does not loop
    assert CLIENT_ADDRESS not in str(error)  # an error text never carries the recipient


# --- selection by configuration (section 4.12 environment matrix) -------------------------------


def test_ac15_staging_sends_through_ses(monkeypatch: pytest.MonkeyPatch) -> None:
    use_staging(monkeypatch)
    assert isinstance(transport(), SesTransport)


def test_ac15_local_runs_do_not_need_ses(monkeypatch: pytest.MonkeyPatch) -> None:
    use_environment(monkeypatch, {"ABACUS_ENVIRONMENT": "local"})
    assert not isinstance(transport(), SesTransport)
