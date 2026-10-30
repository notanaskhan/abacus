"""The `firm_inbox` slice (N-01-T11; N-01 §5.3; INB-01, INB-02, FIL-01; DEC-47, DF-33; DEC-836):
the docs@ mailbox at E0 and the figures FIL-01's Files seed foots to, as events the loader
replays through the communications module's intake service. Synthetic, Brightwater Hale only.

- **The Intake team** (N-01-T08, DEC-20): a team of kind `intake` with Grace Holloway on it, so the
  unmatched rows are hers to triage.
- **docs@ rows 1-17** (`files/firm_inbox_e0.json`, from the File Kit's W0 dataset that INB-01's
  fixture seed mounts): each message through `communications.api.record_inbound_message` (email;
  a reply names the message before it, so it joins its thread) and each file through
  `add_attachment` (scanned, stored write-once). A matched thread names its client as staff would
  (`staff_selected`); the four unmatched rows (9, 13, 16, 17) name none. W0's `ignored` row (Varga)
  is set by a bootstrap write, as no ignore service exists before N-01-T15; W0's three `filed`
  attachments (Feld's W-2 and 1098 of Aug 3, Whitley's Q3 estimates) are not loaded until a filing
  service exists (a filed row needs its evidence version), so they are absent, not waiting.
- **Footing** (N-01 §5.3, DEC-47: derived, never typed): 2+1+3+3+2+2+2+2+1+1+4 = 23 waiting; rows
  9, 13, 16, 17 = 4 unmatched; 21 after INB-02 applies Feld's two; the FIL-01 figures below.

`export()` writes the fixture-side summary `apps/web/src/fixtures/seed/inbox-e0.json` (`python -m
abacus_tools.synthetic.scenarios.brightwater_hale.firm_inbox --export`), which the web suite holds
INB-01's and FIL-01's fixture seeds and HOME-01's "Inbox waiting" to. Opt-in
(`--slice firm_inbox`).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Final, cast

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "firm_inbox"
NEEDS: Final[tuple[str, ...]] = ()
DATA: Final = Path(__file__).parent / "files" / "firm_inbox_e0.json"
EXPORT: Final = Path(__file__).resolve().parents[6] / "apps/web/src/fixtures/seed/inbox-e0.json"
E0: Final = datetime(2026, 9, 14, 9, 24, tzinfo=CT)
REPLAY_FROM: Final = datetime(2026, 9, 2, 8, 0, tzinfo=CT)  # DEC-363: acts before setup
INTAKE_TEAM: Final = "Intake"
TRIAGER: Final = "GH"  # Grace Holloway
MAILBOX: Final = "docs@"
APPLIED_ON_FELD: Final = 2  # INB-02 a files the 2025 form and ignores the 2024 one

# FIL-01's Files seed (N-01 §5.3; docs/screens/FIL-01.md): Ridgeline Property Partners, LP's TY2025
# Form 1065. The web suite holds `apps/web/src/fixtures/seed/files.ts` to them.
RIDGELINE_FOLDERS: Final[dict[str, int]] = {
    "permanent_file": 6,
    "workpapers": 3,
    "correspondence": 4,
    "deliverables": 5,
    "signed_authorizations": 0,
}
RIDGELINE_SOURCE_DOCUMENTS: Final = 12
RIDGELINE_VIRTUAL: Final[tuple[int, ...]] = (3, 4)  # mortgage statements, property-manager reports
MORTGAGE_STATEMENTS: Final[tuple[Decimal, ...]] = (
    Decimal("214600"),
    Decimal("168300"),
    Decimal("129500"),
)
MORTGAGE_ACCOUNT: Final = "5500"
IYER_DIV_1A: Final = Decimal("5120.00")  # total ordinary dividends
IYER_DIV_1B: Final = Decimal("3310.00")  # qualified dividends (never above 1a)


@dataclass(frozen=True)
class Attachment:
    name: str
    state: str  # W0's: wait, new, filed, ignored


@dataclass(frozen=True)
class Message:
    key: str
    subject: str
    sender: str
    days_ago: int
    body: str | None
    attachments: tuple[Attachment, ...]

    @property
    def received_at(self) -> datetime:
        return E0 - timedelta(days=self.days_ago)

    @property
    def internet_message_id(self) -> str:
        return f"<{self.key}@docs.brightwater-hale.test>"


@dataclass(frozen=True)
class Thread:
    key: str
    subject: str
    sender: str
    state: str
    client: str | None  # the scenario's client
    chip: str | None  # the name INB-01 shows
    messages: tuple[Message, ...]

    @property
    def waiting(self) -> int:
        return sum(a.state == "wait" for m in self.messages for a in m.attachments)


@cache
def threads() -> tuple[Thread, ...]:
    raw = cast(dict[str, list[dict[str, object]]], json.loads(DATA.read_text("utf-8")))
    out: list[Thread] = []
    for t in raw["threads"]:
        messages = tuple(
            Message(
                str(m["key"]),
                str(m["subject"]),
                str(m["sender"]),
                int(cast(int, m["days_ago"])),
                None if m["body"] is None else str(m["body"]),
                tuple(
                    Attachment(str(a["name"]), str(a["state"]))
                    for a in cast(list[dict[str, str]], m["attachments"])
                ),
            )
            for m in cast(list[dict[str, object]], t["messages"])
        )
        client, chip = t["client"], t["chip"]
        out.append(
            Thread(
                str(t["key"]),
                str(t["subject"]),
                str(t["sender"]),
                str(t["state"]),
                None if client is None else str(client),
                None if chip is None else str(chip),
                messages,
            )
        )
    return tuple(out)


def waiting_total() -> int:
    return sum(t.waiting for t in threads())


def unmatched_rows() -> list[int]:
    """1-based INB-01 rows (newest first) that match no client."""
    return [n for n, t in enumerate(threads(), start=1) if t.client is None]


def summary() -> dict[str, object]:
    """What INB-01, FIL-01 and HOME-01 must agree on at E0 (DEC-47)."""
    mortgage = sum(MORTGAGE_STATEMENTS, Decimal(0))
    return {
        "scenario": "brightwater_hale",
        "snapshot": "E0",
        "inbox": {
            "waiting": waiting_total(),
            "unmatched": len(unmatched_rows()),
            "unmatched_rows": unmatched_rows(),
            "waiting_after_feld_applied": waiting_total() - APPLIED_ON_FELD,
            "threads": [
                {
                    "key": t.key,
                    "subject": t.subject,
                    "sender": t.sender,
                    "state": t.state,
                    "client": t.chip,
                    "waiting": t.waiting,
                    "messages": len(t.messages),
                    "attachments": [
                        {"name": a.name, "state": a.state}
                        for m in t.messages
                        for a in m.attachments
                    ],
                }
                for t in threads()
            ],
        },
        "files": {
            "ridgeline_folders": RIDGELINE_FOLDERS,
            "ridgeline_source_documents": RIDGELINE_SOURCE_DOCUMENTS,
            "ridgeline_virtual": sum(RIDGELINE_VIRTUAL),
            "mortgage_statements": [str(d) for d in MORTGAGE_STATEMENTS],
            "mortgage_total": str(mortgage),
            "mortgage_account": MORTGAGE_ACCOUNT,
            "iyer_dividends": {"box_1a": str(IYER_DIV_1A), "box_1b": str(IYER_DIV_1B)},
        },
    }


def export(path: Path = EXPORT) -> None:
    path.write_text(json.dumps(summary(), indent=2, ensure_ascii=False) + "\n", "utf-8")


def _at(when: datetime) -> datetime:
    return max(when, REPLAY_FROM)


@register_slice(SLICE)
def firm_inbox_events() -> list[Event]:
    events = [
        Event(
            "team:intake",
            SETUP_AT,
            "organisations.intake_team_created",
            "system",
            SLICE,
            {"name": INTAKE_TEAM, "members": [TRIAGER]},
        )
    ]
    for thread in threads():
        previous: str | None = None
        for message in thread.messages:
            events.append(
                Event(
                    f"inbound:{thread.key}:{message.key}",
                    _at(message.received_at),
                    "communications.inbound_email_recorded",
                    "system",
                    SLICE,
                    {
                        "thread": thread.key,
                        "client": thread.client,
                        "sender": message.sender,
                        "subject": message.subject,
                        "body": message.body,
                        "received_at": message.received_at.isoformat(),
                        "internet_message_id": message.internet_message_id,
                        "in_reply_to": previous,
                        "attachments": [
                            {"name": a.name, "state": a.state} for a in message.attachments
                        ],
                    },
                    client=thread.client,
                )
            )
            previous = message.internet_message_id
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="firm_inbox")
    parser.add_argument("--export", action="store_true", help=f"write {EXPORT.name}")
    args = parser.parse_args(argv)
    if args.export:
        export()
    print(json.dumps(summary()["inbox"], ensure_ascii=False)[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
