"""General ledger detail export formats, as configuration (SPEC-034; TASK-069; ADR-107).
PROTECTED.

A GL export lists each account under a heading row, then an opening balance row (when the system
prints one), the account's postings, and a total row. Each format names its header labels, how an
account heading carries its code, how amounts are given (one signed column, or debit and credit),
and its opening, total and closing labels. Built from each system's documented export with
synthetic fixtures (SPEC-034 Q1); checked against real anonymised samples when shared.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from abacus.modules.connections.import_formats import CodeStyle, FileType

AmountMode = Literal["signed", "split"]
# `headings`: an account heading row, then its lines; `flat` (TASK-071): every line names its
# account in a column (or its code and title in two).
Layout = Literal["headings", "flat"]


@dataclass(frozen=True)
class GlFormat:
    id: str
    system: str
    system_key: str
    file_type: FileType
    code_style: CodeStyle
    amount_mode: AmountMode
    date_header: str
    kind_header: str | None
    reference_header: str | None
    counterparty_header: str | None
    description_header: str | None
    amount_header: str | None  # signed: debit positive
    debit_header: str | None
    credit_header: str | None
    balance_header: str | None  # the running balance, where an opening balance is printed
    opening_labels: tuple[str, ...]  # in the first column, or the kind column
    total_prefixes: tuple[str, ...]
    skip_labels: tuple[str, ...]  # rows to ignore ("Closing Balance")
    steps: tuple[str, ...]
    layout: Layout = "headings"
    account_header: str | None = None  # flat: the account (code and name, or the title)
    code_header: str | None = None  # flat: the account code's own column

    @property
    def source(self) -> str:
        return f"import_{self.id}"


GL_FORMATS: Final[dict[str, GlFormat]] = {
    f.id: f
    for f in (
        GlFormat(
            id="qbo_gl_csv",
            system="QuickBooks Online",
            system_key="qbo",
            file_type="csv",
            code_style="leading",
            amount_mode="signed",
            date_header="Date",
            kind_header="Transaction Type",
            reference_header="Num",
            counterparty_header="Name",
            description_header="Memo/Description",
            amount_header="Amount",
            debit_header=None,
            credit_header=None,
            balance_header="Balance",
            opening_labels=("Beginning Balance",),
            total_prefixes=("Total for ", "TOTAL"),
            skip_labels=(),
            steps=(
                "In QuickBooks Online, go to Reports and open General Ledger.",
                "Set the report period to the engagement's fiscal year, then select Run report.",
                "Select Export (the arrow icon), then Export to CSV.",
                "Upload the CSV file here.",
            ),
        ),
        GlFormat(
            id="xero_gl_xlsx",
            system="Xero",
            system_key="xero",
            file_type="xlsx",
            code_style="parenthesised",
            amount_mode="split",
            date_header="Date",
            kind_header="Source",
            reference_header="Reference",
            counterparty_header=None,
            description_header="Description",
            amount_header=None,
            debit_header="Debit",
            credit_header="Credit",
            balance_header="Running Balance",
            opening_labels=("Opening Balance",),
            total_prefixes=("Total ",),
            skip_labels=("Closing Balance",),
            steps=(
                "In Xero, go to Accounting, then Reports, and open General Ledger Detail.",
                "Set the dates to the engagement's fiscal year, then select Update.",
                "Select Export, then Excel.",
                "Upload the Excel file here.",
            ),
        ),
        # TASK-071 (D1): from each system's documented general ledger export; checked against
        # synthetic fixtures until real anonymised samples are shared.
        GlFormat(
            id="qbd_gl_xlsx",
            system="QuickBooks Desktop",
            system_key="qbd",
            file_type="xlsx",
            code_style="leading",
            amount_mode="split",
            date_header="Date",
            kind_header="Type",
            reference_header="Num",
            counterparty_header="Name",
            description_header="Memo",
            amount_header=None,
            debit_header="Debit",
            credit_header="Credit",
            balance_header="Balance",
            opening_labels=("Beginning Balance",),
            total_prefixes=("Total ", "TOTAL"),
            skip_labels=(),
            steps=(
                "In QuickBooks Desktop, go to Reports, then Accountant & Taxes, and open General "
                "Ledger.",
                "Set the dates to the engagement's fiscal year, then select Refresh.",
                "Select Excel, then Create New Worksheet, and save it as an Excel workbook "
                "(.xlsx).",
                "Upload the Excel file here.",
            ),
        ),
        GlFormat(
            id="netsuite_gl_csv",
            system="NetSuite",
            system_key="netsuite",
            file_type="csv",
            code_style="leading",
            amount_mode="split",
            date_header="Date",
            kind_header="Type",
            reference_header="Document Number",
            counterparty_header="Name",
            description_header="Memo",
            amount_header=None,
            debit_header="Debit",
            credit_header="Credit",
            balance_header=None,
            opening_labels=("Opening Balance",),
            total_prefixes=("Total",),
            skip_labels=(),
            steps=(
                "In NetSuite, go to Reports, then Financial, and open General Ledger.",
                "Set the period to the engagement's fiscal year, then select Refresh.",
                "Select Export, then CSV.",
                "Upload the CSV file here.",
            ),
            layout="flat",
            account_header="Account",
        ),
        GlFormat(
            id="intacct_gl_csv",
            system="Sage Intacct",
            system_key="intacct",
            file_type="csv",
            code_style="column",
            amount_mode="split",
            date_header="Date",
            kind_header="Journal",
            reference_header="Document",
            counterparty_header=None,
            description_header="Description",
            amount_header=None,
            debit_header="Debit",
            credit_header="Credit",
            balance_header=None,
            opening_labels=("Beginning balance",),
            total_prefixes=("Total",),
            skip_labels=(),
            steps=(
                "In Sage Intacct, go to General Ledger, then Reports, and open General ledger.",
                "Set the dates to the engagement's fiscal year, then select Run.",
                "Select Export, then CSV.",
                "Upload the CSV file here.",
            ),
            layout="flat",
            account_header="Account title",
            code_header="Account no.",
        ),
    )
}
