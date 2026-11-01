"""N-02-T24 (TASK-2234; DEC-1286): N-02's registrations, without a database.

The firm and portal CSPs name no e-signature provider (DocuSeal is a same-tab redirect,
DEC-1278); the signing email keys are registrations with no words in them and no amount variable;
the envelope notification kinds are registered and the three outcome events fan out to the
sender; `envelope_signer` is on the MFA floor; the Sign to-do is a home source.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Final

import pytest

from abacus.modules.communications.template_keys import SIGNING
from abacus.modules.communications.template_registry import VARIABLES
from abacus.modules.identity import mfa_floor
from abacus.modules.notifications.api import CATALOGUE, registered
from abacus.modules.portal import home
from abacus.modules.portal.home_sources import home_sources
from abacus.modules.signatures import api as signatures_api

ROOT: Final = Path(__file__).parents[4]
CSP_FILES: Final = (
    ROOT / "infra" / "modules" / "cloudfront-firm" / "variables.tf",
    ROOT / "infra" / "modules" / "cloudfront-portal" / "variables.tf",
)
PROVIDERS: Final = ("docuseal", "docusign")


@pytest.mark.source_scan
@pytest.mark.parametrize("path", CSP_FILES, ids=lambda p: p.parent.name)
def test_ac_neither_csp_names_an_esignature_provider(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    assert "content-security-policy" in text or "frame-src" in text or "csp" in text
    assert not [p for p in PROVIDERS if p in text]


def test_ac_the_signing_email_keys_carry_no_words_and_no_amount() -> None:
    assert {r.key for r in SIGNING} == {
        "signature_reminder",
        "signed_copy",
        "rep_letter_sign_today",
        "paper_form_follows",
    }
    fields = {f.name for f in dataclasses.fields(SIGNING[0])}
    assert not fields & {"body", "subject", "text", "html", "copy", "default_body"}
    for registration in SIGNING:
        assert registration.firm_editable
        assert registration.audience == ("client",)
        kinds = {VARIABLES[v].kind for v in registration.variables}
        assert "amount" not in kinds and not {v for v in registration.variables if "amount" in v}
    paper = next(r for r in SIGNING if r.key == "paper_form_follows")
    assert paper.cta_targets == ()  # DF-11: no retry, no other method to press


def test_the_envelope_kinds_are_registered_and_the_outcomes_reach_the_sender() -> None:
    codes = set(registered())
    assert {
        "envelope_completed",
        "envelope_declined",
        "envelope_expired",
        "envelope_signer_verification_failed",
        "envelope_countersign_requested",
        "letter_approval_requested",
    } <= codes
    for event, code in (
        ("envelope.completed", "envelope_completed"),
        ("envelope.declined", "envelope_declined"),
        ("envelope.expired", "envelope_expired"),
    ):
        assert (CATALOGUE[event].kind, CATALOGUE[event].subject_type) == (code, "envelope")


async def test_the_sender_is_the_only_recipient() -> None:
    import uuid

    sender = uuid.uuid4()
    recipients = CATALOGUE["envelope.declined"].recipients
    assert await recipients(uuid.uuid4(), {"sent_by": str(sender)}) == [sender]
    assert await recipients(uuid.uuid4(), {"sent_by": None}) == []  # an import has no sender


def test_envelope_signers_are_on_the_mfa_floor_and_the_sign_todo_is_a_home_source() -> None:
    assert signatures_api.sign_todo  # exported for the home source
    assert "envelope_signer" in mfa_floor._REQUIREMENTS  # pyright: ignore[reportPrivateUsage] -- the registry under test
    assert "signatures" in {name for name, _ in home_sources()}
    assert any(s.__module__.endswith("home_sources.signatures") for s in home.LOADED)
