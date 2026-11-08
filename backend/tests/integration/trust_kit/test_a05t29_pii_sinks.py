"""A-05-T29 (DEC-2956; A-05 §4.10): no participant's SSN or date of birth reaches a sink. A sealed
census row is revealed field by field, as a person does on EBP-03, and code compares census to HR
(which opens the date of birth for the entry date). Then every sink is read back: the structured
log, the audit trail, the outbox and the access record hold neither value in any spelling."""

from __future__ import annotations

from datetime import date

import pytest
from structlog.testing import capture_logs

from abacus.modules.assurance import ebp_participants
from abacus.modules.identity.authz import recording_checks

from .support import Firm, Seeder, make_firm
from .test_a05t18_participant_reveal import (  # T18 seals a census row the import's way
    DOB,
    SSN,
    _participant,  # pyright: ignore[reportPrivateUsage] -- reuse T18's sealed census row
)

pytestmark = pytest.mark.asyncio


def _spellings(ssn: str, dob: date) -> list[str]:
    digits = ssn.replace("-", "")
    return [
        ssn,
        digits,
        dob.isoformat(),
        dob.strftime("%m/%d/%Y"),
        dob.strftime("%m%d%Y"),
        dob.strftime("%B %-d, %Y"),
    ]


_SINKS = (
    "SELECT coalesce(string_agg(t::text, ''), '') FROM audit_events t WHERE tenant_id = $1",
    "SELECT coalesce(string_agg(t::text, ''), '') FROM outbox t WHERE tenant_id = $1",
    "SELECT coalesce(string_agg(t::text, ''), '') FROM access_events t WHERE tenant_id = $1",
    "SELECT coalesce(string_agg(t::text, ''), '') FROM pii_reveals t WHERE tenant_id = $1",
)


async def _sink_dump(seed: Seeder, firm: Firm) -> str:
    parts: list[str] = [str(await seed.value(sql, firm.tenant_id)) for sql in _SINKS]
    return "".join(parts)


async def test_ac_no_ssn_or_date_of_birth_reaches_a_log_the_trail_or_the_outbox(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    with capture_logs() as logs:
        work_item, participant = await _participant(seed, firm)
        with recording_checks():
            await ebp_participants.reveal(firm.person(), work_item, participant, "ssn", "row 14")
            await ebp_participants.reveal(firm.person(), work_item, participant, "dob", "row 14")
    logged = repr(logs)
    sinks = await _sink_dump(seed, firm)
    for spelling in _spellings(SSN, DOB):
        assert spelling not in logged, spelling
        assert spelling not in sinks, spelling
