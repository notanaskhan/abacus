"""Seeded synthetic client generator (SPEC-001, ADR-085). Never imported by `abacus` (ADR-101)."""

from abacus_tools.synthetic.adversarial import ADVERSARIAL_CATEGORIES
from abacus_tools.synthetic.export import to_csv, to_json, to_xlsx
from abacus_tools.synthetic.flaws import FAILURE_CATEGORIES
from abacus_tools.synthetic.generator import GENERATOR_VERSION, generate
from abacus_tools.synthetic.model import (
    Account,
    AdversarialPayload,
    Aging,
    AgingLine,
    BankAccount,
    BankLine,
    BankStatement,
    ClientEntity,
    Flaw,
    JournalEntry,
    JournalLine,
    Manifest,
    ReconcilingItem,
    RequestItem,
    RequestList,
    SyntheticClient,
    TrialBalance,
    TrialBalanceLine,
)

__all__ = [
    "ADVERSARIAL_CATEGORIES",
    "FAILURE_CATEGORIES",
    "GENERATOR_VERSION",
    "Account",
    "AdversarialPayload",
    "Aging",
    "AgingLine",
    "BankAccount",
    "BankLine",
    "BankStatement",
    "ClientEntity",
    "Flaw",
    "JournalEntry",
    "JournalLine",
    "Manifest",
    "ReconcilingItem",
    "RequestItem",
    "RequestList",
    "SyntheticClient",
    "TrialBalance",
    "TrialBalanceLine",
    "generate",
    "to_csv",
    "to_json",
    "to_xlsx",
]
