"""The SES-shaped fake (F-04-T22; F-04.23): `FakeSesTransport` and its in-memory event queue.

It behaves as `SesTransport` does at its edges, for local stacks and tests (synthetic
environments only):
- a send needs its tenant ID and message ID (the SES tags), runs the body check and refuses
  header breaks;
- the message lands in the local mailbox (the harness's `mail.latest()` reads it);
- the delivery event SES would publish is queued in the EventBridge envelope that
  `deliveries.parse_ses_event` reads, so `drain_ses_events` records it and suppresses as for
  real. The SES mailbox simulator's addresses give their documented outcomes: `bounce@` a
  permanent bounce, `complaint@` a complaint, `suppressionlist@` a permanent bounce (the address
  is on the suppression list); any other address is delivered.

The fake never sees a real recipient for a synthetic firm: `send_email` has already routed it
to the sink (`sink.py`).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.clock import system_now
from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings
from abacus.modules.communications.body_check import ensure_sendable
from abacus.modules.communications.deliveries import QueuedEvent
from abacus.modules.communications.transport import header_safe, write_mailbox_record

SIMULATOR_DOMAIN: Final = "simulator.amazonses.com"


class FakeSesEventQueue:
    """The SQS queue SES's configuration set feeds, in memory (a `SesEventQueue`)."""

    def __init__(self) -> None:
        self._queued: list[QueuedEvent] = []

    def put(self, body: str) -> None:
        self._queued.append(QueuedEvent(uuid4().hex, body))

    def receive(self, limit: int) -> Sequence[QueuedEvent]:
        return list(self._queued[:limit])

    def delete(self, receipts: Sequence[str]) -> None:
        gone = set(receipts)
        self._queued = [e for e in self._queued if e.receipt not in gone]

    def __len__(self) -> int:
        return len(self._queued)


def _outcome(to: str) -> tuple[str, dict[str, object]]:
    local, _, domain = to.strip().lower().rpartition("@")
    recipient = [{"emailAddress": to}]
    if domain == SIMULATOR_DOMAIN and local in ("bounce", "suppressionlist"):
        return "Bounce", {"bounce": {"bounceType": "Permanent", "bouncedRecipients": recipient}}
    if domain == SIMULATOR_DOMAIN and local == "complaint":
        return "Complaint", {"complaint": {"complainedRecipients": recipient}}
    return "Delivery", {"delivery": {"recipients": [to]}}


class FakeSesTransport:
    """A `Transport` with SES's contract, writing to the local mailbox and queueing events."""

    def __init__(
        self, directory: Path | None = None, events: FakeSesEventQueue | None = None
    ) -> None:
        if settings().environment not in SYNTHETIC_ENVIRONMENTS:
            raise RuntimeError("the SES fake is for synthetic environments only")
        self._dir = directory or Path(settings().local_mailbox_dir)
        self.events = events if events is not None else FakeSesEventQueue()

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
        from_address: str | None = None,
    ) -> None:
        if tenant_id is None or message_id is None:
            raise ValueError("a send carries its tenant ID and message ID")
        ensure_sendable(subject, body)
        for value, what in ((to, "recipient"), (subject, "subject")):
            header_safe(value, what)
        if sender_name:
            header_safe(sender_name, "sender name")
        if reply_to:
            header_safe(reply_to, "reply-to")
        extra = {"tenant_id": str(tenant_id), "message_id": str(message_id)}
        if from_address:
            extra["from_address"] = header_safe(from_address, "from address")
        write_mailbox_record(
            self._dir,
            to=to,
            subject=subject,
            body=body,
            sender_name=sender_name,
            reply_to=reply_to,
            extra=extra,
        )
        event, section = _outcome(to)
        tags = {"tenant_id": [str(tenant_id)], "message_id": [str(message_id)]}
        envelope = {
            "id": str(uuid4()),
            "time": system_now().isoformat().replace("+00:00", "Z"),
            "detail-type": f"Email {event}",
            "detail": {"eventType": event, "mail": {"tags": tags}, **section},
        }
        self.events.put(json.dumps(envelope))
