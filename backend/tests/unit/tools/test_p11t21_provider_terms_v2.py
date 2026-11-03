"""P-11-T21 (TASK-3217; DEC-2217): provider-terms register v2, document services.

Row acceptance: the register carries a `textract` document-service entry beside the model routes,
drafted and left unapproved until counsel signs, so `covering('textract', on)` answers None; an
approved one is compiled in with its AI-services opt-out evidence and §7216 basis.
"""

from __future__ import annotations

from datetime import date

import pytest
import yaml

from abacus.kernel.provider_terms import covering
from abacus_tools.codegen import provider_terms as codegen


def test_ac_the_draft_textract_entry_covers_nothing() -> None:
    assert covering("textract", date(2026, 11, 3)) is None
    source = yaml.safe_load(codegen.SOURCE.read_text())
    textract = next(s for s in source["document_services"] if s["route"] == "textract")
    assert textract["status"] == "draft"
    assert textract["approved_on"] is None


def _approved() -> dict[str, object]:
    return {
        "route": "textract",
        "status": "approved",
        "provider": "Amazon Web Services",
        "documents": [
            {"title": "AWS Service Terms", "version": "2026-10", "accepted_on": date(2026, 11, 1)}
        ],
        "training": "none",
        "retention": {"beyond_processing": False, "exceptions": []},
        "region": "us-east-2",
        "subprocessors": [],
        "breach_notice": "AWS security incident notification",
        "ai_services_opt_out": "AWS Organizations AI services opt-out policy p-123",
        "tri_basis": "Counsel memo 2026-11-02: §301.7216-2(d) auxiliary service",
        "second_approver": "counsel",
        "second_approved_on": date(2026, 11, 2),
        "approved_by": "founder",
        "approved_on": date(2026, 11, 3),
        "review_by": date(2027, 11, 2),
    }


def test_ac_an_approved_entry_is_compiled_with_its_basis() -> None:
    out = codegen.render(yaml.safe_dump({"entries": [], "document_services": [_approved()]}))
    assert 'kind="document_service"' in out
    assert "tri_basis=" in out and "DOCUMENT_SERVICES" in out


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"route": "azure_ocr"}, "textract"),
        ({"status": "pending"}, "draft or approved"),
        ({"region": "eu-west-1"}, "US region"),
        ({"second_approver": "founder"}, "counsel"),
    ],
)
def test_ac_an_invalid_document_service_is_refused(
    change: dict[str, object], message: str
) -> None:
    with pytest.raises(codegen.TermsInvalid, match=message):
        codegen.render(
            yaml.safe_dump({"entries": [], "document_services": [_approved() | change]})
        )
