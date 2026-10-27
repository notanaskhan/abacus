"""Ledger export formats, as configuration (SPEC-028; TASK-052; ADR-107). PROTECTED.

Each format says how a system's trial balance export is laid out: the file type, the column
labels that mark its header row, where the account code is, which columns hold amounts, the
total row's label, and the line that names the period end. The parser applies them as plain
code. Built from each system's documented export layout with synthetic fixtures (TASK-052 D4);
checked against real anonymised samples when the founder shares them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

FileType = Literal["csv", "xlsx"]
# Where the account code is: a leading number ("1000 Checking", "1000 · Checking"), in
# parentheses at the end ("Sales (200)"), or its own column (TASK-068); none found: the name is
# the code.
CodeStyle = Literal["leading", "parenthesised", "column"]


@dataclass(frozen=True)
class Format:
    id: str
    system: str  # shown to people
    system_key: str  # for failure codes: looks_like_<system_key>
    file_type: FileType
    account_header: str  # "" when the account column's header cell is blank
    debit_headers: tuple[str, ...]  # the first present is used
    credit_headers: tuple[str, ...]
    code_style: CodeStyle
    total_labels: tuple[str, ...]
    period_prefixes: tuple[str, ...]  # "As of", "As at": the rest of that line is the date
    steps: tuple[str, ...]  # guided export steps (SPEC-028 §4.6)
    code_header: str = ""  # the account code's own column (code style `column`)

    @property
    def source(self) -> str:
        """The run's and snapshot's source (`sync_runs.source`: lowercase, digits, `_`)."""
        return f"import_{self.id}"


FORMATS: Final[dict[str, Format]] = {
    f.id: f
    for f in (
        Format(
            id="qbo_tb_csv",
            system="QuickBooks Online",
            system_key="qbo",
            file_type="csv",
            account_header="",
            debit_headers=("Debit",),
            credit_headers=("Credit",),
            code_style="leading",
            total_labels=("TOTAL", "Total"),
            period_prefixes=("As of",),
            steps=(
                "In QuickBooks Online, go to Reports and open Trial Balance.",
                "Set the report period to the engagement's year end, then select Run report.",
                "Select Export (the arrow icon), then Export to CSV.",
                "Upload the CSV file here.",
            ),
        ),
        Format(
            id="xero_tb_xlsx",
            system="Xero",
            system_key="xero",
            file_type="xlsx",
            account_header="Account",
            debit_headers=("YTD Debit", "Debit"),
            credit_headers=("YTD Credit", "Credit"),
            code_style="parenthesised",
            total_labels=("Total",),
            period_prefixes=("As at",),
            steps=(
                "In Xero, go to Accounting, then Reports, and open Trial Balance.",
                "Set the date to the engagement's year end, then select Update.",
                "Select Export, then Excel.",
                "Upload the Excel file here.",
            ),
        ),
        # TASK-068 (D1, D3): from each system's documented trial balance export; checked against
        # synthetic fixtures until real anonymised samples are shared.
        Format(
            id="qbd_tb_xlsx",
            system="QuickBooks Desktop",
            system_key="qbd",
            file_type="xlsx",
            account_header="",
            debit_headers=("Debit",),
            credit_headers=("Credit",),
            code_style="leading",
            total_labels=("TOTAL", "Total"),
            period_prefixes=("As of",),
            steps=(
                "In QuickBooks Desktop, go to Reports, then Accountant & Taxes, and open Trial "
                "Balance.",
                "Set the dates to the engagement's year end, then select Refresh.",
                "Select Excel, then Create New Worksheet, and save it as an Excel workbook "
                "(.xlsx).",
                "Upload the Excel file here.",
            ),
        ),
        Format(
            id="netsuite_tb_csv",
            system="NetSuite",
            system_key="netsuite",
            file_type="csv",
            account_header="Account",
            debit_headers=("Debit", "Amount (Debit)"),
            credit_headers=("Credit", "Amount (Credit)"),
            code_style="leading",
            total_labels=("Total",),
            period_prefixes=("End of", "As of", "Period:"),
            steps=(
                "In NetSuite, go to Reports, then Financial, and open Trial Balance.",
                "Set the period to the engagement's year-end month, then select Refresh.",
                "Select Export, then CSV.",
                "Upload the CSV file here.",
            ),
        ),
        Format(
            id="intacct_tb_csv",
            system="Sage Intacct",
            system_key="intacct",
            file_type="csv",
            account_header="Account title",
            debit_headers=("Debit",),
            credit_headers=("Credit",),
            code_style="column",
            code_header="Account no.",
            total_labels=("Total",),
            period_prefixes=("As of",),
            steps=(
                "In Sage Intacct, go to General Ledger, then Reports, and open Trial balance.",
                "Set the as-of date to the engagement's year end, then select Run.",
                "Select Export, then CSV.",
                "Upload the CSV file here.",
            ),
        ),
        # A-02-T22 (R-7, DEC-610): the Accrued trial balance template, for plans and entities
        # without a ledger; human-keyed and footed by code like any export. The template file and
        # its guided steps are the product's own format, not firm content. Its `system` words
        # never say "Accrued": a client may upload it in the portal (DEC-01, ADR-133).
        Format(
            id="accrued_template",
            system="Trial balance template",
            system_key="accrued_template",
            file_type="xlsx",
            account_header="Account name",
            debit_headers=("Debit",),
            credit_headers=("Credit",),
            code_style="column",
            code_header="Account",
            total_labels=("Total",),
            period_prefixes=("Period end:", "Period end"),
            steps=(
                "Download the trial balance template.",
                "Key one row per account: its number, its name, and its debit or credit balance "
                "at the engagement's year end. Totals are computed when you upload.",
                "Set Period end to the engagement's year end, then save the workbook (.xlsx).",
                "Upload the workbook here. Debits must equal credits.",
            ),
        ),
    )
}


def source_format(source: str) -> Format | None:
    """The format a run's source names (`import_<format id>`), if it's an import."""
    return FORMATS.get(source.removeprefix("import_")) if source.startswith("import_") else None
