"""A-05-T57 close (S31; TASK-6232; DEC-2827): a related party's year transactions and disclosure
are a person's record; the agent never records them, and a note link needs the note's words.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid
from abacus.modules.assurance import aud27
from abacus.modules.identity.context import AuthContext


def _ctx(kind: str = "human") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type]  # actor kind under test
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


def test_the_record_keeps_the_persons_words_and_amounts() -> None:
    params = aud27.PartyRecord(
        transactions=[("Employer contributions", D("612000.00")), ("Compensation only", None)],
        disclosure="  Note 9 Retirement plan ",
        disclosure_note=True,
    ).params()
    assert json.loads(str(params["transactions"])) == [
        {"description": "Employer contributions", "amount": "612000.00"},
        {"description": "Compensation only", "amount": None},
    ]
    assert params["disclosure"] == "Note 9 Retirement plan"
    assert params["disclosure_note"] is True


@pytest.mark.parametrize("disclosure", [None, "   "])
def test_a_note_link_needs_the_notes_words(disclosure: str | None) -> None:
    with pytest.raises(DomainInvalid):
        aud27.PartyRecord(disclosure=disclosure, disclosure_note=True).params()


async def test_the_agent_never_records_a_partys_activity() -> None:
    with pytest.raises(DomainInvalid):
        await aud27.record_activity(
            _ctx("agent"), uuid.uuid4(), uuid.uuid4(), aud27.PartyRecord(disclosure="Note 9")
        )
