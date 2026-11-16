"""A-08-T19 (red): the respondent's answer. The server computes the difference; a second
submission answers 409 `already_answered` naming the original receipt."""

from __future__ import annotations

import uuid
from decimal import Decimal as D

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.assurance import confirmations_respondent as respondent
from abacus.modules.identity.api import LinkPrincipal


def test_the_server_computes_the_difference() -> None:
    assert respondent.difference(D("125000.00"), True, D("1.00")) == (D("125000.00"), D("0.00"))
    assert respondent.difference(D("125000.00"), False, D("118400.00")) == (
        D("118400.00"),
        D("6600.00"),
    )
    assert respondent.difference(D("125000.00"), False, None) == (D("125000.00"), D("0.00"))


def test_already_answered_is_a_409_naming_the_receipt() -> None:
    err = respondent.AlreadyAnswered(facts={"receipt_id": "C3-R1"})
    assert err.code == "already_answered" and err.facts["receipt_id"] == "C3-R1"


async def test_an_unverified_principal_never_answers() -> None:
    principal = LinkPrincipal(uuid.uuid4(), uuid.uuid4(), "confirmation", uuid.uuid4(), False)
    with pytest.raises(NotFound):
        await respondent.submit(
            principal, agrees=True, balance=None, respondent_name="A", explanation=None,
            attachment_ids=[],
        )  # fmt: skip
