"""The `pbc_screening` slice (TASK-7816; P-03-T25, P-04-T45; DEC-4814): Granite Peak Outdoor
Supply's FY2026 PBC list is asked of the client, Luis Ferrante answers its bank-statement request
with the wrong document, and the agent's upload reviewer flags it, before the Sep 24, 10:20 AM
snapshot that J04's trace to source and pbc-ai steps read on the full stack.

- **The list is published** (Thu Sep 17, 9:00 AM CT) by Omar Haddad, the engagement's Audit
  Manager (`team_of(A2)`): every request becomes Requested of Luis Ferrante, due Fri Oct 2 (the
  date the SURL Draft carries, `binders.SURL_DRAFT`). Bootstrapped, as `audit_core` writes
  Northwind's published list: `publish_binder` needs G3, and the seed's audits carry no recorded
  letter or acceptance record (DEC-310).
- **Luis uploads a card statement** (Tue Sep 22, 2:10 PM CT) to "Bank statements (year-end month
  + subsequent month)" from the portal, through `evidence.api.upload_synthetic` (the client's own
  upload without SPEC-025's client-data gate, which G1 holds shut on every seeded audit). The file
  is a June 2026 corporate card statement from the generator (`documents.card_statement_pdf`);
  its issuer, card and lines are the generator's defaults, dated into Granite's year-end month
  (DEC-4814, synthetic).
- **The reviewer screens it** (2:12 PM): the product's own path in the loader's process, as the
  upload reviewer's evaluation runs it on the fake route (`abacus_tools.evals.upload_review`):
  extraction, checks, words and the PII scan, then `create_review_run` for the engagement partner
  and `review` on the fake model answering from one recorded answer
  (`review_answers/granite_card_statement.json`, the evaluation's format; `responses/` holds
  only answers about `documents.py`'s documents). Code verifies the quotes against the
  masked page; the aggregate composes "Does this answer the request?" flagged, Wrong document,
  with the verified citation as the flag's region. The worker's own fake model has no reviewer
  answers (TASK-059 D3), so the dev stack never starts a second review of it.

Opt-in (`--slice pbc_screening`, which brings `sampling`: Caleb Dunn joins the team and its
members confirm independence on Sep 10). `build()` keeps its default, so SCENARIO_HASH is
unchanged.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final

from abacus_tools.synthetic.documents import card_statement_pdf
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import PBC_LISTS
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "pbc_screening"
NEEDS: Final = ("sampling",)
GRANITE: Final = "Granite Peak Outdoor Supply, Inc."
# SHL-20 on AUD-03 (P-06-T22); SHL-08's viewer (P-03-T16) and C4's citation reads (P-03-T08),
# which AUD-03's dock, SHL-07 and "Open source" read.
FLAGS: Final = ("screening.card", "evidence.viewer_v1", "evidence.citations_v2")
GRANITE_LIST: Final = next(p for p in PBC_LISTS if p.key == "granite-peak")
PUBLISHER: Final = "OH"  # Omar Haddad, Audit Manager on A2
PUBLISHED_AT: Final = datetime(2026, 9, 17, 9, 0, tzinfo=CT)
DUE_ON: Final = date(2026, 10, 2)
REQUEST_TITLE: Final = "Bank statements (year-end month + subsequent month)"
UPLOADER: Final = "Luis Ferrante"
UPLOADED_AT: Final = datetime(2026, 9, 22, 14, 10, tzinfo=CT)
REVIEWED_AT: Final = datetime(2026, 9, 22, 14, 12, tzinfo=CT)
FILE_NAME: Final = "Granite Peak card statement June 2026.pdf"
ANSWERS: Final = Path(__file__).parent / "review_answers"
RESPONSE_FILE: Final = "granite_card_statement.json"


def request_position() -> int:
    """The bank-statement request's position on Granite Peak's list (1-based)."""
    return next(n for n, r in enumerate(GRANITE_LIST.requests, 1) if r.title == REQUEST_TITLE)


def card_statement() -> bytes:
    """June 2026: the year-end month's corporate card statement, not its bank statement."""
    return card_statement_pdf(
        start=date(2026, 5, 22),
        end=date(2026, 6, 21),
        lines=(
            (date(2026, 5, 26), "PAYMENT THANK YOU", Decimal("-1250.00")),
            (date(2026, 5, 29), "OFFICE SUPPLY CO #221", Decimal("184.37")),
            (date(2026, 6, 2), "CLOUD HOSTING INC", Decimal("612.00")),
            (date(2026, 6, 9), "RETURN OFFICE SUPPLY CO", Decimal("-24.99")),
            (date(2026, 6, 15), "AIRLINE 0167 SEATTLE", Decimal("438.20")),
        ),
    )


@register_slice(SLICE)
def pbc_screening_events() -> list[Event]:
    position = request_position()
    return [
        *(
            Event(
                f"flag:{name}", PUBLISHED_AT, "platform.flag_set", "system", SLICE, {"flag": name}
            )
            for name in FLAGS
        ),
        Event(
            f"pbc-published:{GRANITE_LIST.key}",
            PUBLISHED_AT,
            "requests.pbc_list_published",
            PUBLISHER,
            SLICE,
            {"list": GRANITE_LIST.key, "due_on": DUE_ON.isoformat()},
            client=GRANITE,
        ),
        Event(
            f"client-upload:{GRANITE_LIST.key}:{position}",
            UPLOADED_AT,
            "evidence.pbc_file_uploaded",
            "system",
            SLICE,
            {
                "list": GRANITE_LIST.key,
                "position": position,
                "by": UPLOADER,
                "file": FILE_NAME,
            },
            client=GRANITE,
        ),
        Event(
            f"upload-reviewed:{GRANITE_LIST.key}:{position}",
            REVIEWED_AT,
            "agents.pbc_upload_reviewed",
            "system",
            SLICE,
            {"list": GRANITE_LIST.key, "position": position, "answers": RESPONSE_FILE},
            client=GRANITE,
        ),
    ]


__all__ = [
    "ANSWERS",
    "DUE_ON",
    "FILE_NAME",
    "FLAGS",
    "GRANITE",
    "GRANITE_LIST",
    "NEEDS",
    "PUBLISHED_AT",
    "PUBLISHER",
    "REQUEST_TITLE",
    "RESPONSE_FILE",
    "REVIEWED_AT",
    "SLICE",
    "UPLOADED_AT",
    "UPLOADER",
    "card_statement",
    "pbc_screening_events",
    "request_position",
]
