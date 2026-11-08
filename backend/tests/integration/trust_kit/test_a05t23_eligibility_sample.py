"""A-05-T23 (DEC-2225, DEC-2328): EBP-03's sample read against Postgres. The participants are
sealed as the census import seals them; the grid and its sample are stubbed, this pins the join and
what leaves. Row acceptance: the rows keep A-03's order, and no response discloses a birth date."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from abacus.kernel.uow import Target, uow
from abacus.modules.assurance import ebp_eligibility_sample as sample_module
from abacus.modules.assurance.compute.ebp.eligibility import EntryRule
from abacus.modules.assurance.ebp_participants import seal_pii
from abacus.modules.assurance.ebp_provisions import EntryRuleRead

from .support import Firm, Seeder, make_firm

SSN = "000-00-4417"
ALICIA_DOB = date(1990, 1, 15)
YOUNG_DOB = date(2004, 9, 1)  # 21 after hire + 3 months: eligibility is the birthday
KWAME_DOB = date(1985, 5, 20)


async def _import(firm: Firm, work_item: uuid.UUID, kind: str) -> uuid.UUID:
    async with uow(firm.person().tenant) as tx:
        import_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO ebp_source_imports (tenant_id, engagement_id, work_item_id, "
                    "evidence_version_id, kind, sha256, status, imported_by) VALUES (:t, :e, :w, "
                    "gen_random_uuid(), :kind, repeat('a', 64), 'imported', :u) RETURNING id"
                ),
                {
                    "t": firm.tenant_id,
                    "e": firm.engagement_id,
                    "w": work_item,
                    "kind": kind,
                    "u": firm.user_id,
                },
            )
        ).scalar_one()
        tx.record("ebp_import.imported", target=Target("ebp_source_import", import_id))
    return import_id


async def _person(
    seed: Seeder,
    firm: Firm,
    work_item: uuid.UUID,
    import_id: uuid.UUID,
    key: str,
    name: str,
    hire: date,
    dob: date,
    election: Decimal | None,
    compensation: Decimal,
) -> None:
    sealed = await seal_pii(firm.tenant_id, import_id, key, SSN, dob)
    await seed.run(
        "INSERT INTO ebp_participants (tenant_id, engagement_id, work_item_id, import_id, "
        "participant_key, name, ssn_sealed, ssn_fp, ssn_last4, dob_sealed, dob_fp, status, "
        "hire_on, deferral_election_pct, compensation) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, "
        "$9, $10, $11, 'active', $12, $13, $14)",
        firm.tenant_id,
        firm.engagement_id,
        work_item,
        import_id,
        key,
        name,
        sealed.ssn_sealed,
        sealed.ssn_fp,
        sealed.ssn_last4,
        sealed.dob_sealed,
        sealed.dob_fp,
        hire,
        election,
        compensation,
    )


def _row(position: int, key: str, state: str) -> SimpleNamespace:
    return SimpleNamespace(
        position=position, item_id=uuid.uuid4(), record_key=key, state=state, cells=()
    )


@pytest.fixture
async def sample(seed: Seeder, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    firm = await make_firm(seed)
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
    census = await _import(firm, work_item, "census")
    roster = await _import(firm, work_item, "hr_roster")
    comp = Decimal("41200.00")
    hire = date(2025, 2, 10)
    await _person(seed, firm, work_item, census, "NW-1", "Alicia Brennan", hire, ALICIA_DOB,
                  Decimal(8), comp)  # fmt: skip
    await _person(seed, firm, work_item, census, "NW-2", "Young Hire", date(2025, 1, 6), YOUNG_DOB,
                  None, comp)  # fmt: skip
    await _person(seed, firm, work_item, census, "NW-3", "Kwame Mensah", date(2025, 3, 17),
                  KWAME_DOB, Decimal(0), comp)  # fmt: skip
    await _person(seed, firm, work_item, roster, "NW-1", "Alicia Brennan", date(2025, 2, 11),
                  ALICIA_DOB, None, comp)  # fmt: skip
    table = SimpleNamespace(
        version_no=3,
        workpaper_id=uuid.uuid4(),
        rows=(
            _row(1, "NW-1", "needs_human"),
            _row(2, "NW-2", "pass"),
            _row(3, "NW-3", "exception"),
            _row(4, "NW-9", "not_started"),
        ),
    )
    test_id = uuid.uuid4()

    async def latest(*_a: object) -> tuple[uuid.UUID, str] | None:
        return test_id, "b" * 64

    async def grid(*_a: object) -> object:
        return table

    async def states(*_a: object) -> dict[uuid.UUID, list[object]]:
        return {test_id: []}

    async def meta(*_a: object) -> object:
        return SimpleNamespace(engagement=SimpleNamespace(fiscal_period_end=date(2025, 12, 31)))

    async def item(*_a: object) -> object:
        return SimpleNamespace(engagement_id=firm.engagement_id)

    async def can(*_a: object) -> list[str]:
        return ["test.mark"]

    async def rule(*_a: object) -> EntryRuleRead:
        return EntryRuleRead("verified", EntryRule())

    for name, stub in (
        ("entry_rule_read", rule),
        ("latest_test_of_variant", latest),
        ("grid", grid),
        ("sign_off_states", states),
        ("engagement_metadata", meta),
        ("assurance_item", item),
        ("_can", can),
    ):
        monkeypatch.setattr(sample_module, name, stub)
    return SimpleNamespace(firm=firm, work_item=work_item, test_id=test_id)


@pytest.mark.asyncio
async def test_ac_the_rows_keep_the_samples_order_with_codes_figures(
    sample: SimpleNamespace,
) -> None:
    out = await sample_module.sample(sample.firm.person(), sample.work_item)
    assert out.test_id == sample.test_id
    assert [r.record_key for r in out.rows] == ["NW-1", "NW-2", "NW-3", "NW-9"]
    assert (out.exceptions, out.needs_human) == (1, 1)
    first, young, kwame, missing = out.rows
    assert (first.census_name, first.hr_first_name) == ("Alicia Brennan", "Alicia")
    assert (first.census_hire, first.hr_hire) == (date(2025, 2, 10), date(2025, 2, 11))
    assert first.eligible_on == date(2025, 5, 10)
    assert first.entry_on == date(2025, 6, 1)
    assert first.rate_label == "8% elected"
    assert first.note == "No effect on entry: both dates give the same entry date"
    assert young.rate_label == "6% default"
    assert kwame.rate_label == "0% — no opt-out"
    assert (kwame.missed_deferral, kwame.missed_match) == (Decimal("2472.00"), Decimal("1442.00"))
    assert (missing.census_hire, missing.note) == (None, "Not on the census")


@pytest.mark.asyncio
async def test_ac_no_response_discloses_a_date_of_birth(sample: SimpleNamespace) -> None:
    out = await sample_module.sample(sample.firm.person(), sample.work_item)
    young = out.rows[1]
    assert young.eligible_on is None  # it would be the 21st birthday
    assert young.entry_on == date(2025, 10, 1)
    body = out.model_dump_json()
    assert {r.dob_masked for r in out.rows} == {"••/••/••••"}
    for dob in (ALICIA_DOB, YOUNG_DOB, KWAME_DOB):
        assert dob.isoformat() not in body
        assert dob.replace(year=dob.year + 21).isoformat() not in body
    assert SSN not in body


@pytest.mark.asyncio
async def test_ac_no_test_yet_is_no_rows(
    sample: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def none(*_a: object) -> None:
        return None

    monkeypatch.setattr(sample_module, "latest_test_of_variant", none)
    out = await sample_module.sample(sample.firm.person(), sample.work_item)
    assert (out.test_id, out.rows) == (None, [])


@pytest.mark.asyncio
async def test_ac_an_unverified_entry_rule_computes_nothing_and_opens_no_birth_date(
    sample: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unverified(*_a: object) -> EntryRuleRead:
        return EntryRuleRead("unverified")

    async def never(*_a: object) -> date:
        raise AssertionError("a date of birth was opened with no verified rule")

    monkeypatch.setattr(sample_module, "entry_rule_read", unverified)
    monkeypatch.setattr(sample_module, "_dob", never)
    out = await sample_module.sample(sample.firm.person(), sample.work_item)
    assert out.entry_rule.state == "unverified"
    assert (out.entry_rule.minimum_age, out.entry_rule.service_months) == (None, None)
    first, young, kwame, missing = out.rows
    assert (first.entry_on, first.eligible_on, first.note) == (None, None, None)
    assert first.rate_label == "8% elected"  # the person's election, not a computed rate
    assert (young.entry_on, young.rate_label) == (None, "")
    assert (kwame.entry_on, kwame.missed_deferral, kwame.missed_match) == (None, None, None)
    assert kwame.result == "exception"  # a person's result stays
    assert missing.note == "Not on the census"


@pytest.mark.asyncio
async def test_ac_the_verified_rule_moves_the_entry_date(
    sample: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def six_months(*_a: object) -> EntryRuleRead:
        return EntryRuleRead("verified", EntryRule(minimum_age=21, service_months=6))

    monkeypatch.setattr(sample_module, "entry_rule_read", six_months)
    out = await sample_module.sample(sample.firm.person(), sample.work_item)
    assert (out.entry_rule.minimum_age, out.entry_rule.service_months) == (21, 6)
    first = out.rows[0]
    assert (first.eligible_on, first.entry_on) == (date(2025, 8, 10), date(2025, 9, 1))
