"""A-05-T18 (TASK-3020; DEC-1858; DEC-2067): the census PII rules that need no database.

The binding names the import, the participant and the field, so a sealed value opens only where it
was sealed; masks show the last four of an SSN and nothing of a date of birth; an SSN that is not
nine digits is refused before anything is sealed; the reveal route's answer is `no-store` and the
only model carrying the value classifies it restricted.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from abacus.kernel.classification import restricted_fields
from abacus.modules.assurance import ebp_contract
from abacus.modules.assurance.ebp_participants import DOB_MASK, binding, seal_pii, ssn_mask


def test_ac_the_binding_names_import_participant_and_field() -> None:
    import_id = uuid.UUID(int=7)
    assert binding(import_id, "P-0001", "ssn") == f"ebp_participant:{import_id}:P-0001:ssn"
    assert binding(import_id, "P-0001", "ssn") != binding(import_id, "P-0001", "dob")
    assert binding(import_id, "P-0001", "ssn") != binding(import_id, "P-0002", "ssn")


def test_ac_masks_never_show_more_than_the_last_four() -> None:
    assert ssn_mask("4417") == "•••-••-4417"
    assert ssn_mask(None) is None
    assert not any(ch.isdigit() for ch in DOB_MASK)


@pytest.mark.parametrize("ssn", ["123", "1234567890", "12-345-678"])
async def test_ac_an_ssn_that_is_not_nine_digits_is_refused(ssn: str) -> None:
    with pytest.raises(ValueError, match="nine digits"):
        await seal_pii(uuid.uuid4(), uuid.uuid4(), "P-0001", ssn, date(1981, 3, 9))


def test_ac_the_revealed_value_is_restricted() -> None:
    assert restricted_fields(ebp_contract.ParticipantRevealOut) == ["value"]


def test_ac_the_reveal_route_is_served_not_a_stub() -> None:
    route = next(
        r
        for r in ebp_contract.router.routes
        if getattr(r, "path", "").endswith("/ebp/participants/{participant_id}/reveals")
    )
    assert getattr(route, "response_model", None) is ebp_contract.ParticipantRevealOut
