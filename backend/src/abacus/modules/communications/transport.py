"""Email transport (SPEC-015 Q1; TASK-030 D4; SPEC-050 AC-15). Only communications delivers email
(COMM-001).

`LocalMailbox` writes each email as a JSON file in `local_mailbox_dir`, synthetic environments
only, so local runs can open invitation links. `SesTransport` sends through Amazon SES v2 in
staging and production. It is chosen by configuration (`ses_configuration_set` and
`ses_from_address`), never by default in local runs or tests, and with neither a real environment
has no transport and delivery fails (the relay retries, then parks the event).

Both run the mechanical body check first (`body_check.py`): a message with an SSN, a TIN, an
account number or a tax amount in it is blocked and never reaches the mail client. That is the
last check; the scope check (`scope.py`) has already passed upstream.
"""

from __future__ import annotations

import json
from email.utils import formataddr
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid4

from abacus.kernel.clock import system_now
from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings
from abacus.kernel.logging import get_logger
from abacus.kernel.storage import AwsError, error_code, sesv2_client
from abacus.modules.communications.body_check import ensure_sendable

if TYPE_CHECKING:
    from types_boto3_sesv2 import SESV2Client

_log = get_logger(__name__)


class TransportError(Exception):
    """The transport could not send the message. The text never carries an address."""


class Transport(Protocol):
    # `sender_name` is the display name (SPEC-025 AC-8: the firm's); the address stays ours.
    # `reply_to` is where a reply goes (the firm's). `tenant_id` and `message_id` identify the
    # message in delivery events (SES tags): IDs only, never an address.
    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        sender_name: str | None = None,
        reply_to: str | None = None,
        tenant_id: UUID | None = None,
        message_id: UUID | None = None,
    ) -> None: ...


class LocalMailbox:
    def __init__(self, directory: Path | None = None) -> None:
        if settings().environment not in SYNTHETIC_ENVIRONMENTS:
            raise RuntimeError("the local mailbox is for synthetic environments only")
        self._dir = directory or Path(settings().local_mailbox_dir)

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        sender_name: str | None = None,
        reply_to: str | None = None,
        tenant_id: UUID | None = None,
        message_id: UUID | None = None,
    ) -> None:
        ensure_sendable(subject, body)
        self._dir.mkdir(parents=True, exist_ok=True)
        sent = system_now()
        path = self._dir / f"{sent:%Y%m%dT%H%M%S}-{uuid4().hex[:8]}.json"
        record: dict[str, str | None] = {
            "to": to,
            "sender_name": sender_name,
            "subject": subject,
            "body": body,
            "sent_at": sent.isoformat(),
        }
        if reply_to is not None:
            record["reply_to"] = reply_to
        path.write_text(json.dumps(record), encoding="utf-8")


def _header_safe(value: str, what: str) -> str:
    """A header value without line breaks: anything that could add a header is refused."""
    if "\r" in value or "\n" in value or "\0" in value:
        raise ValueError(f"{what} has a line break")
    return value


class SesTransport:
    """Amazon SES v2 (P3). Sends from the platform's address under the firm's display name, with
    the firm's Reply-To, through the environment's configuration set. The tags are `tenant_id`
    and `message_id` and nothing else, so delivery events can be matched to a message without an
    address leaving the database. A send without both IDs is refused: it could not be matched.

    The body check runs before anything else, so a blocked message never reaches the client. Any
    SES error is a `TransportError` (the relay retries); nothing falls back to another path."""

    def __init__(self, client: SESV2Client, *, configuration_set: str, from_address: str) -> None:
        self._client = client
        self._configuration_set = configuration_set
        self._from = _header_safe(from_address, "from address")

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        sender_name: str | None = None,
        reply_to: str | None = None,
        tenant_id: UUID | None = None,
        message_id: UUID | None = None,
    ) -> None:
        if tenant_id is None or message_id is None:
            raise ValueError("a send carries its tenant ID and message ID")
        ensure_sendable(subject, body)
        source = (
            formataddr((_header_safe(sender_name, "sender name"), self._from))
            if sender_name
            else self._from
        )
        recipients = [_header_safe(to, "recipient")]
        replies = [_header_safe(reply_to, "reply-to")] if reply_to else []
        try:
            self._client.send_email(
                FromEmailAddress=source,
                Destination={"ToAddresses": recipients},
                ReplyToAddresses=replies,
                Content={
                    "Simple": {
                        "Subject": {"Data": _header_safe(subject, "subject"), "Charset": "UTF-8"},
                        "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                    }
                },
                ConfigurationSetName=self._configuration_set,
                EmailTags=[
                    {"Name": "tenant_id", "Value": str(tenant_id)},
                    {"Name": "message_id", "Value": str(message_id)},
                ],
            )
        except AwsError as exc:
            code = error_code(exc)
            _log.warning(
                "ses.send_failed",
                ses_error=code,
                error_type=type(exc).__name__,
                tenant_id=tenant_id,
                message_id=message_id,
            )
            raise TransportError("the email can't be sent") from None


_transport: Transport | None = None


def configure_transport(transport: Transport | None) -> None:
    global _transport
    _transport = transport


def transport() -> Transport:
    global _transport
    if _transport is None:
        s = settings()
        if s.ses_configuration_set is not None and s.ses_from_address is not None:
            _transport = SesTransport(
                sesv2_client(region=s.ses_region),
                configuration_set=s.ses_configuration_set,
                from_address=s.ses_from_address,
            )
        elif s.environment in SYNTHETIC_ENVIRONMENTS:
            _transport = LocalMailbox()
        else:
            raise RuntimeError("no email transport configured (set the SES settings)")
    return _transport
