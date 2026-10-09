"""Email transport (SPEC-015 Q1; TASK-030 D4). Only communications delivers email (COMM-001).

`LocalMailbox` writes each email as a JSON file in `local_mailbox_dir`, synthetic environments
only, so local runs can open invitation links. SES arrives with TASK-014; until then a real
environment has no transport and delivery fails (the relay retries, then parks the event).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings


class Transport(Protocol):
    # `sender_name` is the display name (SPEC-025 AC-8: the firm's); the address stays ours.
    def send(
        self, *, to: str, subject: str, body: str, sender_name: str | None = None
    ) -> None: ...


class LocalMailbox:
    def __init__(self, directory: Path | None = None) -> None:
        if settings().environment not in SYNTHETIC_ENVIRONMENTS:
            raise RuntimeError("the local mailbox is for synthetic environments only")
        self._dir = directory or Path(settings().local_mailbox_dir)

    def send(self, *, to: str, subject: str, body: str, sender_name: str | None = None) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        sent = datetime.now(UTC)
        path = self._dir / f"{sent:%Y%m%dT%H%M%S}-{uuid4().hex[:8]}.json"
        path.write_text(
            json.dumps(
                {
                    "to": to,
                    "sender_name": sender_name,
                    "subject": subject,
                    "body": body,
                    "sent_at": sent.isoformat(),
                }
            ),
            encoding="utf-8",
        )


_transport: Transport | None = None


def configure_transport(transport: Transport | None) -> None:
    global _transport
    _transport = transport


def transport() -> Transport:
    global _transport
    if _transport is None:
        if settings().environment not in SYNTHETIC_ENVIRONMENTS:
            raise RuntimeError("no email transport configured (SES arrives with TASK-014)")
        _transport = LocalMailbox()
    return _transport
