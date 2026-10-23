"""Mailbox readers for the synthetic sink (F-04-T22; F-04.23): `mail.latest(to)`.

- **Local** (`LocalMailboxReader`): the JSON files `LocalMailbox` and `FakeSesTransport` write
  to `local_mailbox_dir`.
- **Staging** (`S3MailboxReader`): the raw messages the SES receipt rule for the staging sink
  domain stores in the sink bucket under `mail_sink_prefix` (Q-01-T47; kept 7 days).

`mail()` picks the reader from settings (the bucket set: staging). `latest(to)` matches the
recipient exactly, case-insensitively. A message's `code` is the first 6-digit sign-in code in
its subject or body (POR-01b). The readers only read.

CLI, for Playwright's hosted sign-in:

    python -m abacus_tools.harness.mailbox latest <address>   # prints the message as JSON

Its output is the message for a synthetic sink address, which carries no real person's mail.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, cast

from abacus.kernel.config import settings
from abacus.kernel.storage import s3_client

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

_CODE: Final = re.compile(r"(?<!\d)(\d{6})(?!\d)")


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    body: str
    sent_at: datetime
    sender_name: str | None = None

    @property
    def code(self) -> str | None:
        """The 6-digit code a sign-in email carries (POR-01b), if any."""
        found = _CODE.search(f"{self.subject}\n{self.body}")
        return found.group(1) if found else None


class MailboxReader(Protocol):
    def messages(self) -> list[Mail]: ...

    def latest(self, to: str) -> Mail | None: ...


def _latest(messages: list[Mail], to: str) -> Mail | None:
    wanted = to.strip().casefold()
    mine = [m for m in messages if m.to.strip().casefold() == wanted]
    return max(mine, key=lambda m: m.sent_at) if mine else None


class LocalMailboxReader:
    def __init__(self, directory: Path | None = None) -> None:
        self._dir = directory or Path(settings().local_mailbox_dir)

    def messages(self) -> list[Mail]:
        if not self._dir.is_dir():
            return []
        found: list[Mail] = []
        for path in sorted(self._dir.glob("*.json")):
            raw = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
            sender = raw.get("sender_name")
            found.append(
                Mail(
                    to=str(raw["to"]),
                    subject=str(raw["subject"]),
                    body=str(raw["body"]),
                    sent_at=datetime.fromisoformat(str(raw["sent_at"])),
                    sender_name=str(sender) if sender is not None else None,
                )
            )
        return found

    def latest(self, to: str) -> Mail | None:
        return _latest(self.messages(), to)


def _text_of(message: EmailMessage) -> str:
    part = message.get_body(preferencelist=("plain", "html"))
    return part.get_content() if part is not None else ""


def parse_raw(raw: bytes) -> list[Mail]:
    """One stored message, as one `Mail` per recipient it was addressed to."""
    message = message_from_bytes(raw, policy=policy.default)
    recipients = [a for _, a in getaddresses(message.get_all("To", []) or []) if a]
    sender = getaddresses([str(message.get("From", ""))])
    name = sender[0][0] if sender and sender[0][0] else None
    date = message.get("Date")
    sent = parsedate_to_datetime(str(date)) if date else datetime.fromtimestamp(0).astimezone()
    subject, body = str(message.get("Subject", "")), _text_of(message)
    return [Mail(to, subject, body, sent, name) for to in recipients]


class S3MailboxReader:
    """The staging sink bucket. Lists the prefix and parses each stored message."""

    def __init__(self, bucket: str, prefix: str = "", client: S3Client | None = None) -> None:
        self._bucket, self._prefix = bucket, prefix
        self._client = client or s3_client()

    def messages(self) -> list[Mail]:
        found: list[Mail] = []
        pages = self._client.get_paginator("list_objects_v2").paginate(
            Bucket=self._bucket, Prefix=self._prefix
        )
        for page in pages:
            for item in page.get("Contents", []):
                key = item.get("Key")
                if not key:
                    continue
                raw = self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
                found.extend(parse_raw(raw))
        return found

    def latest(self, to: str) -> Mail | None:
        return _latest(self.messages(), to)


def mail() -> MailboxReader:
    """The reader for this environment: the sink bucket when one is set, else the local box."""
    bucket = settings().mail_sink_bucket
    if bucket:
        return S3MailboxReader(bucket, settings().mail_sink_prefix)
    return LocalMailboxReader()


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "latest":
        print("usage: python -m abacus_tools.harness.mailbox latest <address>", file=sys.stderr)
        return 2
    found = mail().latest(argv[1])
    if found is None:
        print("no message", file=sys.stderr)
        return 1
    print(json.dumps({**asdict(found), "sent_at": found.sent_at.isoformat(), "code": found.code}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
