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
# A-08-T09 (ADR-400, P-58): the journal-entry fields an export may carry. Each is optional in the
# file: a column the export leaves out is "Not available from this ledger", never a parse error.
JeField = Literal["posted_by", "entered_at", "source", "approver"]
JE_FIELDS: Final[tuple[JeField, ...]] = ("posted_by", "entered_at", "source", "approver")


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
    # A-08-T09 (ADR-400): the JE fields' columns where the system's export carries them.
    posted_by_header: str | None = None  # the user who entered the entry
    entered_at_header: str | None = None  # when it was entered (not its posting date)
    source_header: str | None = None  # manual or system (a journal source column)
    approver_header: str | None = None  # who approved a manual journal

    @property
    def source(self) -> str:
        return f"import_{self.id}"

    @property
    def je_headers(self) -> dict[JeField, str]:
        """The JE fields this format can carry, by field."""
        given: dict[JeField, str | None] = {
            "posted_by": self.posted_by_header,
            "entered_at": self.entered_at_header,
            "source": self.source_header,
            "approver": self.approver_header,
        }
        return {k: v for k, v in given.items() if v is not None}


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
            # A-08-T09: QuickBooks Online's General Ledger report can add "Create Date" and
            # "Created By" (Customize, Change columns); it has no source or approver column.
            posted_by_header="Created By",
            entered_at_header="Create Date",
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
            # A-08-T09: Xero's General Ledger Detail has no user, entry time or source column.
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
            # A-08-T09: QuickBooks Desktop prints only "Last modified by" and "Entered/Last
            # Modified", which name the last editor, not the entry's creator: never mapped.
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
            # A-08-T09: NetSuite's columns for created by, date created, the journal's source and
            # its approver (Approved By, where approval routing is on).
            posted_by_header="Created By",
            entered_at_header="Date Created",
            source_header="Source",
            approver_header="Approved By",
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
            # A-08-T09: Sage Intacct's General ledger report lists who created each entry, when,
            # and whether a person or a subledger posted it.
            posted_by_header="Created by",
            entered_at_header="Date created",
            source_header="Source",
        ),
    )
}
