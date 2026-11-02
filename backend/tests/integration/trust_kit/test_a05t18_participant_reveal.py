"""A-05-T18 against Postgres (TASK-3020; A-05 §4.10; DEC-1858; DEC-2067): "A participant's SSN
and date of birth are sealed on import and shown only through a logged, MFA-fresh, onshore
person's reveal; an agent, a client principal or an offshore member is refused and nothing opens."

The participant's fields are sealed with `seal_pii` (as the census import seals them, T19) and
written as the import writes them. The reveal returns the value once with `expires_in` 30, one
`pii_reveals` row naming the field, not a region, and one `pii.revealed` audit event, none holding
the value. A sealed value copied to another participant never opens (the binding names the row).
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import date

import pytest
from sqlalchemy import text

from abacus.kernel.crypto import open_sealed
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.assurance import ebp_participants
from abacus.modules.assurance.ebp_participants import binding, seal_pii
from abacus.modules.identity.api import Forbidden, agent_context_for_run
from abacus.modules.identity.authz import recording_checks

from .support import Firm, Seeder, make_firm

SSN = "000-00-4417"
DOB = date(1981, 3, 9)


async def _participant(
    seed: Seeder, firm: Firm, key: str = "P-0001"
) -> tuple[uuid.UUID, uuid.UUID]:
    """A census import and one participant on it, sealed as the import seals; (work item, row)."""
    client_id = await seed.id(
        "SELECT client_id FROM engagements WHERE id = $1", firm.engagement_id
    )
    work_item = await seed.id(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, period_start, "
        "period_end, created_by) VALUES ($1, $2, $3, 'tax_return', 'Plan audit', '2025-01-01', "
        "'2025-12-31', $4) RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        client_id,
        firm.user_id,
    )
    # The import is a person's (its actor CHECK): written in a unit of work as the staff member.
    async with uow(firm.person().tenant) as tx:
        import_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO ebp_source_imports (tenant_id, engagement_id, work_item_id, "
                    "evidence_version_id, kind, sha256, status, imported_by) VALUES (:t, :e, :w, "
                    "gen_random_uuid(), 'census', repeat('a', 64), 'imported', :u) RETURNING id"
                ),
                {"t": firm.tenant_id, "e": firm.engagement_id, "w": work_item, "u": firm.user_id},
            )
        ).scalar_one()
        tx.record("ebp_import.imported", target=Target("ebp_source_import", import_id))
    sealed = await seal_pii(firm.tenant_id, import_id, key, SSN, DOB)
    row = await seed.id(
        "INSERT INTO ebp_participants (tenant_id, engagement_id, work_item_id, import_id, "
        "participant_key, name, ssn_sealed, ssn_fp, ssn_last4, dob_sealed, dob_fp, status) "
        "VALUES ($1, $2, $3, $4, $5, 'Ana Ortiz', $6, $7, $8, $9, $10, 'active') RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        work_item,
        import_id,
        key,
        sealed.ssn_sealed,
        sealed.ssn_fp,
        sealed.ssn_last4,
        sealed.dob_sealed,
        sealed.dob_fp,
    )
    return work_item, row


async def _traces(seed: Seeder, firm: Firm) -> tuple[int, int]:
    reveals = await seed.value(
        "SELECT count(*) FROM pii_reveals WHERE tenant_id = $1", firm.tenant_id
    )
    audits = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'pii.revealed'",
        firm.tenant_id,
    )
    return int(str(reveals)), int(str(audits))


async def test_ac_an_onshore_person_gets_the_ssn_once_with_a_logged_record(seed: Seeder) -> None:
    firm = await make_firm(seed)
    work_item, participant = await _participant(seed, firm)
    with recording_checks():
        revealed = await ebp_participants.reveal(
            firm.person(), work_item, participant, "ssn", "Eligibility test, row 14"
        )
    # shown as the form prints it (P-03's `shown`), once
    assert (revealed.value, revealed.expires_in) == ("000-00-4417", 30)
    [row] = await seed.rows(
        "SELECT field_ref, region_id, evidence_version_id, user_id FROM pii_reveals "
        "WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert row["field_ref"] == f"ebp_participant:{participant}:ssn"
    assert (row["region_id"], row["evidence_version_id"], row["user_id"]) == (
        None,
        None,
        firm.user_id,
    )
    assert await _traces(seed, firm) == (1, 1)
    access = await seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND kind = 'pii.revealed' "
        "AND subject_type = 'ebp_participant' AND subject_id = $2",
        firm.tenant_id,
        participant,
    )
    assert access == 1
    dump = await seed.value(
        "SELECT coalesce(string_agg(t::text, ''), '') FROM audit_events t WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert "000004417" not in str(dump) and "000-00-4417" not in str(dump)


async def test_ac_the_date_of_birth_reveals_as_its_iso_date(seed: Seeder) -> None:
    firm = await make_firm(seed)
    work_item, participant = await _participant(seed, firm)
    with recording_checks():
        revealed = await ebp_participants.reveal(
            firm.person(), work_item, participant, "dob", "Age check"
        )
    assert revealed.value == "1981-03-09"


async def test_ac_an_agent_is_refused_and_nothing_opens(seed: Seeder) -> None:
    firm = await make_firm(seed)
    work_item, participant = await _participant(seed, firm)
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="workpapers.section_drafter",
        engagement_id=firm.engagement_id,
        task_scope=frozenset({"ebp.read", "pii.reveal"}),
        initiator_user_id=firm.user_id,
    )
    with pytest.raises(Forbidden), recording_checks():
        await ebp_participants.reveal(agent, work_item, participant, "ssn", "Agent asked")  # type: ignore[arg-type]  # a refused principal on purpose
    assert await _traces(seed, firm) == (0, 0)


async def test_ac_a_client_principal_is_refused(seed: Seeder) -> None:
    firm = await make_firm(seed)
    work_item, participant = await _participant(seed, firm)
    client = dataclasses.replace(firm.person(), client=True)
    with pytest.raises((Forbidden, NotFound)), recording_checks():
        await ebp_participants.reveal(client, work_item, participant, "ssn", "Portal")
    assert await _traces(seed, firm) == (0, 0)


async def test_ac_an_offshore_member_is_refused(seed: Seeder) -> None:
    firm = await make_firm(seed)
    work_item, participant = await _participant(seed, firm)
    await seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        firm.user_id,
    )
    with pytest.raises(Forbidden), recording_checks():
        await ebp_participants.reveal(firm.person(), work_item, participant, "ssn", "Offshore")
    assert await _traces(seed, firm) == (0, 0)


async def test_ac_a_participant_on_another_work_item_is_not_found(seed: Seeder) -> None:
    firm = await make_firm(seed)
    _, participant = await _participant(seed, firm)
    with pytest.raises(NotFound), recording_checks():
        await ebp_participants.reveal(firm.person(), uuid.uuid4(), participant, "ssn", "Wrong")
    assert await _traces(seed, firm) == (0, 0)


async def test_a_sealed_value_opens_only_as_its_own_field_of_its_own_row(seed: Seeder) -> None:
    firm = await make_firm(seed)
    import_id = uuid.uuid4()
    sealed = await seal_pii(firm.tenant_id, import_id, "P-0001", SSN, DOB)
    assert sealed.ssn_sealed is not None and sealed.dob_sealed is not None
    opened = await open_sealed(
        firm.tenant_id, sealed.ssn_sealed, binding(import_id, "P-0001", "ssn")
    )
    assert opened == b"000004417"
    for wrong in (binding(import_id, "P-0002", "ssn"), binding(import_id, "P-0001", "dob")):
        with pytest.raises(Exception):  # noqa: B017 -- any refusal; the AEAD tag fails
            await open_sealed(firm.tenant_id, sealed.ssn_sealed, wrong)
