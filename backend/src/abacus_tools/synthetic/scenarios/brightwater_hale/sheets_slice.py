"""SHT-01 e: the row drawer on SURL-05 (K-03-T22, TASK-9028; DEC-6033). Synthetic content for the
fixture export, never product code.

Granite Peak FY2026's one unrecorded liability, blueprint §9.3.5 field for field: Front Range
Freight Co. invoice FRF-30418, dated Jun 29, 2026, billing June inbound freight, paid by ACH on Jul
22 for $68,400.00 and posted in July (FY2027 period 1), so not in the June 30 AP aging. The agent's
reason measures it against clearly trivial ($7,750) and performance materiality ($116,250), the
thresholds the sampling slice draws its strata with. Its two sources are the invoice's first page
and the NetSuite bill's posting period. The run finished Mon Sep 28, 4:52 PM CT (SHT-01 a's
status bar); Luis Ferrante uploaded the invoice on Sat Sep 26.

`make fixtures` (or `scenario_files()`) writes
`apps/web/src/fixtures/seed/scenario.sht01-drawer.json`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.sampling_content import SURL

CDT: Final = timezone(timedelta(hours=-5))
ROW_KEY: Final = "SURL-05"
INVOICE: Final = "FRF-30418"
INVOICE_ON: Final = date(2026, 6, 29)
PAID_ON: Final = date(2026, 7, 22)
METHOD: Final = "ACH"
SERVICE: Final = "June inbound freight"
RECORDED_IN: Final = "Jul 2026 (FY2027 period 1)"
CLEARLY_TRIVIAL: Final = Decimal("7750")
PERFORMANCE_MATERIALITY: Final = Decimal("116250")
AGENT_LABEL: Final = "Unrecorded liabilities tester"
FINISHED_AT: Final = datetime(2026, 9, 28, 16, 52, tzinfo=CDT)
STARTED_AT: Final = datetime(2026, 9, 28, 16, 47, tzinfo=CDT)
UPLOADED_BY: Final = "Luis Ferrante"
UPLOADED_ON: Final = date(2026, 9, 26)
FILE_NAME: Final = f"{INVOICE}.pdf"


def _month_day(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}"


def _long(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def _full(d: date, year: bool = True) -> str:
    return f"{d.strftime('%B')} {d.day}, {d.year}" if year else f"{d.strftime('%B')} {d.day}"


def _dollars(n: Decimal, cents: bool = True) -> str:
    return f"${n:,.2f}" if cents else f"${n:,.0f}"


def sht01_row_drawer() -> dict[str, object]:
    """SURL-05's drawer read (`GET /v1/sheets/{sid}/rows/{rid}`) and its two citations."""
    key, vendor, paid, amount_text = next(r for r in SURL if r[0] == ROW_KEY)
    amount = Decimal(amount_text)
    # The sample's draw and §9.3.5 agree, and code (not the agent) measures the amount.
    measured = CLEARLY_TRIVIAL < amount < PERFORMANCE_MATERIALITY
    if paid != _month_day(PAID_ON) or not measured:
        raise ValueError(f"{ROW_KEY} no longer matches §9.3.5")
    rationale = (
        f"Invoice {INVOICE} is dated {_full(INVOICE_ON)} and bills {SERVICE}. It was paid on "
        f"{_full(PAID_ON, year=False)} and posted in July, so it was not in accounts payable at "
        "June 30. "
        f"I suggest Improperly excluded. {_dollars(amount, cents=False)} is above clearly trivial "
        f"({_dollars(CLEARLY_TRIVIAL, cents=False)}) and below performance materiality "
        f"({_dollars(PERFORMANCE_MATERIALITY, cents=False)})."
    )
    return {
        "row_key": key,
        "vendor": vendor,
        "facts": [
            {
                "label": "Payment",
                "type": "text",
                "value": f"{METHOD} · {_long(PAID_ON)} · {_dollars(amount)}",
            },
            {"label": "Invoice", "type": "text", "value": f"{INVOICE} · {_long(INVOICE_ON)}"},
            {"label": "Service", "type": "text", "value": SERVICE},
            {"label": "Recorded in", "type": "text", "value": RECORDED_IN},
            {"label": "In 6/30 AP aging", "type": "text", "value": "No"},
        ],
        "conclusion": "improperly_excluded",
        "rationale": rationale,
        "citations": [
            {
                "title": FILE_NAME,
                "loc": "p.1",
                "kind": "document_text",
                "quote": None,
            },  # the handoff names both sources without their text
            {
                "title": f"NetSuite bill {INVOICE}",
                "loc": "posting period Jul 2026",
                "kind": "record_field",
                "quote": None,
            },
        ],
        "agent": {
            "label": AGENT_LABEL,
            "started_at": STARTED_AT.isoformat(),
            "finished_at": FINISHED_AT.isoformat(),
        },
        "evidence": {
            "label": FILE_NAME,
            "uploaded_by": UPLOADED_BY,
            "linked_at": datetime(2026, 9, 26, 11, 0, tzinfo=CDT).isoformat(),
        },
    }
