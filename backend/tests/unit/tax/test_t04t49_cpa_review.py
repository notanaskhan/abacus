"""T-04-T49 (TASK-7524; DEC-4524): the individual engines' CPA memo names its case list, its
engines and its signature record; the record is unsigned until the CPA signs, and an unsigned
record keeps Tax Returns from a firm that isn't synthetic (`make entitlement`)."""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

from abacus.modules.tax.api import individual_review_signed
from abacus.modules.tax.compute.individual import review
from abacus_tools import tenants

ROOT = Path(__file__).resolve().parents[4]
MEMO = ROOT / "docs" / "quality" / "golden-reviews" / "tax-individual@v1.md"
CASES = ROOT / "backend" / "tests" / "golden" / "tax_individual" / "feld_ty2025.yaml"


def test_the_memo_names_this_case_list() -> None:
    digest = hashlib.sha256(CASES.read_bytes()).hexdigest()
    assert digest in MEMO.read_text(encoding="utf-8")


def test_the_memo_lists_every_engine_as_requiring_review() -> None:
    text = MEMO.read_text(encoding="utf-8")
    for engine in review.ENGINES:
        assert engine in text, engine


def test_the_record_and_the_memo_status_agree() -> None:
    text = MEMO.read_text(encoding="utf-8")
    signed = individual_review_signed()
    assert ("awaiting the CPA's signature" in text) is (not signed)
    assert signed is False  # unsigned until the CPA signs, in the same PR as the record


def test_make_entitlement_refuses_tax_returns_without_the_signature() -> None:
    source = inspect.getsource(tenants.set_entitlement)
    assert 'module == "tax_returns"' in source and "individual_review_signed()" in source
