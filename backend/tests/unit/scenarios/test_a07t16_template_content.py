"""A-07-T16 (TASK-5122; A-07 §5; DEC-2418): template content part 2.

Reports load through C11's import, the catalogue's reason codes are AUD-23's four, each decision
kind that switches a paragraph is named, the signature is a placeholder, and no wording sits in
Python (AGENTS 16).
"""

from __future__ import annotations

from abacus_tools.synthetic.scenarios.brightwater_hale.report_templates import (
    a07_content,
    bundle,
)

REPORTS = (
    "BH Report · EBP 103(a)(3)(C) v3",
    "BH Report · FS Nonissuer Unmodified v4",
    "BH Report · AR-C 90 Review v1",
    "BH Report · AR-C 80 Compilation v1",
)


def test_the_four_reports_are_bundles() -> None:
    for name in REPORTS:
        found = bundle(name)
        assert found["layout_key"] == "report"
        assert found["body"]


def test_the_reason_codes_are_aud_23s() -> None:
    codes = {r["code"] for r in a07_content()["report_reason_codes"]}
    assert codes == {"ERISA-SUPP", "EOM-GC", "EOM-CHG", "OM-OTHER"}


def test_every_block_is_keyed_to_a_decision_or_a_reason_code() -> None:
    codes = {r["code"] for r in a07_content()["report_reason_codes"]}
    for block in a07_content()["report_paragraph_blocks"]:
        assert block.get("decision_kind") or block.get("reason_code") in codes


def test_the_signature_is_a_placeholder() -> None:
    signature = a07_content()["firm_signature"]
    assert signature["placeholder"] is True
