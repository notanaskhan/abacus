"""N-02-T21 (DEC-1174): the SIG-02 builder's additive C7 fields.

The signer's title and email (the sub-line and "Email required"), the draft's document order (the
drag and keyboard reorder) and the validation's code-only checks (the Checks band). Each is
optional with a default, so every earlier client and fixture still parses.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from abacus.modules.signatures import contract as c7


def test_ac_signer_title_and_email_default_to_none() -> None:
    fields = c7.SignerOut.model_fields
    assert fields["title"].default is None
    assert fields["email"].default is None


def test_ac_draft_carries_an_optional_document_order() -> None:
    assert c7.DraftUpdateIn.model_fields["document_order"].default is None
    body = c7.DraftUpdateIn(signers=[], document_order=[])
    assert body.document_order == []


def test_ac_checks_are_identifiers_never_prose() -> None:
    assert c7.ValidationOut(ok=True, problems=[]).checks == []
    c7.ValidationCheck(code="amounts_match", ok=True)
    with pytest.raises(ValidationError):
        c7.ValidationCheck(code="Amounts match the exported return", ok=True)
