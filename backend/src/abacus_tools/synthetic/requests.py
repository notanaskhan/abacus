"""Request list for a synthetic engagement (SPEC-001 AC-16). Glossary terms only."""

from __future__ import annotations

from abacus_tools.synthetic.model import RequestItem, RequestList, Tier

# (description, audit area, retrievability tier, artefact)
_ITEMS: tuple[tuple[str, str, Tier, str | None], ...] = (
    ("Trial balance at period end", "general", "A", "trial_balance"),
    ("General ledger detail for the period", "general", "A", "general_ledger"),
    ("Bank statements for all accounts, every month of the period", "cash", "A", "bank_statement"),
    ("Bank reconciliations at period end", "cash", "B", None),
    ("Bank confirmations", "cash", "C", None),
    ("Accounts receivable aging at period end", "receivables", "A", "ar_aging"),
    ("Subsequent receipts testing support", "receivables", "B", None),
    ("Accounts payable aging at period end", "payables", "A", "ap_aging"),
    ("Search for unrecorded liabilities support", "payables", "C", None),
    ("Inventory count instructions and results", "inventory", "D", None),
    ("Fixed asset rollforward", "fixed_assets", "B", None),
    ("Debt agreements and amendments", "debt", "D", None),
    ("Payroll registers for two pay periods", "payroll", "C", None),
    ("Board minutes for the period and subsequent events", "equity", "E", None),
    ("Significant customer contracts", "revenue", "D", None),
    ("Management representation letter", "general", "E", None),
)


def request_list() -> RequestList:
    return RequestList(
        tuple(
            RequestItem(f"RI-{n:03d}", description, area, tier, artefact)
            for n, (description, area, tier, artefact) in enumerate(_ITEMS, start=1)
        )
    )
