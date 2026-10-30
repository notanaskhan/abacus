"""T-01-T17 (TASK-2305; SPEC-501 AC-28 to AC-31; T-01 §3.1 Story 1.1; DF-16): §7216 consent
templates on P-11's report templates.

The row's acceptance: a template naming Anthropic as a recipient is refused, the rendered consent
names Amazon Web Services (Bedrock) from the register, and no consent text exists in code.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from abacus.kernel import _provider_terms
from abacus.kernel.provider_terms import TermsEntry
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.methodology import report_templates as store
from abacus.modules.reporting import consent, templates
from abacus.modules.reporting.contract import CONSENT_RECIPIENTS_KEY, TemplateImportIn
from abacus.modules.reporting.render.core import RenderInput, build_html

REPO = Path(__file__).resolve().parents[4]
ON = date(2026, 9, 14)
Json = dict[str, object]


def _bundle(**overrides: object) -> TemplateImportIn:
    raw: Json = {
        "family": "consent_7216",
        "name": "BH §7216 Consent to Disclose · AI sub-processors v2",
        "layout_key": "consent_7216",
        "variables": [
            {"key": "taxpayer.name", "label": "Taxpayer", "value_type": "name"},
            {"key": CONSENT_RECIPIENTS_KEY, "label": "Recipients", "value_type": "text"},
        ],
        "body": [
            {"type": "heading", "level": 1, "text": "Consent to disclose tax return information"},
            {
                "type": "paragraph",
                "runs": [
                    {"type": "text", "text": "I, "},
                    {"type": "var", "key": "taxpayer.name"},
                    {"type": "text", "text": ", authorize disclosure to: "},
                    {"type": "var", "key": CONSENT_RECIPIENTS_KEY},
                ],
            },
        ],
        "sample_data": {"taxpayer.name": "Claire Feld"},
        "consent": {
            "purpose": "ai_disclosure",
            "statement_version": "Rev. Proc. 2013-14",
            "counsel_attestation": True,
        },
    }
    raw.update(overrides)
    return TemplateImportIn.model_validate(raw)


def _codes(body: TemplateImportIn) -> set[tuple[str, str]]:
    errors, _ = templates.validate(body)
    return {(e.path, e.code) for e in errors}


def _register(monkeypatch: pytest.MonkeyPatch, *entries: TermsEntry) -> None:
    monkeypatch.setattr(_provider_terms, "ENTRIES", tuple(entries))


BEDROCK = TermsEntry(
    route="bedrock",
    provider="Amazon Web Services",
    region="us-east-1",
    approved_on=date(2026, 9, 1),
    review_by=date(2027, 8, 31),
)


# --- AC-28: the consent family's own rules -----------------------------------------------------


def test_ac28_a_clean_consent_template_validates() -> None:
    assert _codes(_bundle()) == set()


@pytest.mark.parametrize("party", ["Anthropic", "OpenAI", "Amazon Web Services (Bedrock)"])
def test_ac28_fixed_text_naming_a_recipient_is_refused(party: str) -> None:
    body = _bundle(
        body=[
            {
                "type": "paragraph",
                "runs": [
                    {"type": "text", "text": f"We disclose to {party}: "},
                    {"type": "var", "key": CONSENT_RECIPIENTS_KEY},
                ],
            }
        ]
    )
    assert ("body[0].runs[0].text", "recipient_in_text") in _codes(body)


def test_ac28_the_recipient_block_is_placed_exactly_once() -> None:
    once: Json = {"type": "var", "key": CONSENT_RECIPIENTS_KEY}
    twice = _bundle(body=[{"type": "paragraph", "runs": [once, once]}])
    assert ("body", "recipients_block_required") in _codes(twice)
    none = _bundle(body=[{"type": "paragraph", "runs": [{"type": "text", "text": "No block"}]}])
    assert ("body", "recipients_block_required") in _codes(none)
    typed = _bundle(sample_data={CONSENT_RECIPIENTS_KEY: "Somebody"})
    assert (f"sample_data.{CONSENT_RECIPIENTS_KEY}", "recipient_in_text") in _codes(typed)


def test_ac28_terms_belong_to_the_consent_family_only() -> None:
    assert ("consent", "consent_terms_required") in _codes(_bundle(consent=None))
    letter = _bundle(family="engagement_letter", layout_key="letter")
    assert ("consent", "consent_terms_required") in _codes(letter)
    assert ("layout_key", "unknown_layout") in _codes(_bundle(layout_key="letter"))


def test_ac28_one_purpose_and_counsel_attestation_are_required_by_shape() -> None:
    with pytest.raises(ValueError):
        _bundle(
            consent={"purpose": "use", "statement_version": "v1", "counsel_attestation": False}
        )
    with pytest.raises(ValueError):
        _bundle(
            consent={
                "purpose": ["use", "ai_disclosure"],
                "statement_version": "v1",
                "counsel_attestation": True,
            }
        )


def test_ac28_the_terms_are_part_of_the_content_hash() -> None:
    a = templates.content_sha256(_bundle())
    b = templates.content_sha256(
        _bundle(
            consent={
                "purpose": "ai_disclosure",
                "statement_version": "Rev. Proc. 2013-14",
                "counsel_attestation": True,
                "expiry_months": 12,
            }
        )
    )
    assert a != b


# --- AC-29: recipients come from the register at render time ----------------------------------


def test_ac29_the_recipient_line_comes_from_the_register(monkeypatch: pytest.MonkeyPatch) -> None:
    _register(monkeypatch, BEDROCK)
    found = consent.recipients(ON)
    assert found.line == "Amazon Web Services (Bedrock) · model inference · US"
    assert found.provider_terms_version


def test_ac29_with_no_covering_entry_a_consent_does_not_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register(monkeypatch)
    with pytest.raises(consent.RecipientsUnavailable) as refused:
        consent.recipients(ON)
    assert refused.value.code == "recipients_unavailable"
    expired = TermsEntry(
        "bedrock", "Amazon Web Services", "us-east-1", date(2025, 1, 1), date(2025, 12, 31)
    )
    _register(monkeypatch, expired)
    with pytest.raises(consent.RecipientsUnavailable):
        consent.recipients(ON)


def test_ac29_the_rendered_consent_names_the_register_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register(monkeypatch, BEDROCK)
    body = _bundle()
    request = RenderInput(
        layout_key="consent_7216",
        blocks=[b.model_dump(mode="json") for b in body.body],
        values={"taxpayer.name": "Claire Feld", **consent.recipient_values(ON)},
        title=body.name,
        as_of=datetime(2026, 9, 14, 14, 24),
        mode="draft",
        content_hash="e" * 64,
    )
    document, _, _ = build_html(request)
    assert "Amazon Web Services (Bedrock) · model inference · US" in document


# --- AC-30: a partner publishes a consent template ---------------------------------------------


def test_ac30_a_partner_publishes_a_consent_template_with_a_fresh_second_factor() -> None:
    rule = RULES["consent_template.publish"]
    assert rule.mfa_recent
    assert rule.decisions.get("agent") == "deny" and rule.decisions.get("system") == "deny"
    assert store.CONSENT_PUBLISH == "consent_template.publish"
    assert store.ConsentTermsMissing.code == "consent_terms_missing"
    assert store.NotCurrent.code == "not_current"


# --- AC-31: no consent text in code ------------------------------------------------------------

_CONSENT_WORDING = (
    "federal law requires this consent",
    "you are not required to complete this form",
    "if you agree to the disclosure",
    "this consent is valid for",
)


def test_ac31_no_consent_wording_exists_in_code() -> None:
    for root in (REPO / "backend/src/abacus", REPO / "backend/migrations"):
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in _CONSENT_WORDING:
                assert phrase not in text, (path, phrase)
    migration = (
        REPO / "backend/migrations/versions/0461_report_template_consent_terms.py"
    ).read_text()
    assert "INSERT INTO report_template_consent_terms" not in migration
