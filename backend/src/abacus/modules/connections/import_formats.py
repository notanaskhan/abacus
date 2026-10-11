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
# Where the account code is: a leading number ("1000 Checking"), in parentheses at the end
# ("Sales (200)"), or none (the name is the code).
CodeStyle = Literal["leading", "parenthesised"]


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
    )
}


def source_format(source: str) -> Format | None:
    """The format a run's source names (`import_<format id>`), if it's an import."""
    return FORMATS.get(source.removeprefix("import_")) if source.startswith("import_") else None
