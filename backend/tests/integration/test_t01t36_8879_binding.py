"""T-01-T36 (TASK-2518; T-01 §3.12; I-8879-DRIFT; DEC-85; DEC-1566) against Postgres: "A later
import moving AGI by 51 dollars supersedes the signed Feld 8879 and relocks transmission, while
a 50-dollar move does not."

The drift rule is code (`filing.drift`) and proven on its own; the relock runs on the Feld return
(T-01-T19's world) with a binding as the draft leaves it. The return's values, the tolerances
reference set and C7's marker are stubbed at filing's boundary (`current_values`,
`pub1345_tolerances`, `supersede_for_amount_change`) so the test controls the move exactly.
Also: tolerances come from the reference set (a corrected set rechecks every open binding), the
system only relocks (the database refuses an unlock), and the envelope is drafted only for an
approved packet.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Mapping
from types import SimpleNamespace

import asyncpg
import pytest

from abacus.kernel.uow import OutboxEvent
from abacus.modules.tax import filing

from .conftest import MigratedDatabase
from .test_t01t25_engine_export import Feld, engines, feld_return

__all__ = ["engines"]

BOUND = {"US": {"agi": "245310", "refund": "253", "tax": "123223"}}


def test_ac_a_51_dollar_agi_move_drifts_and_50_does_not() -> None:
    def moved(agi: str = "245310", refund: str = "253") -> list[str]:
        now = {"US": {"agi": agi, "refund": refund, "tax": "123223"}}
        return filing.drift(BOUND, now, 50, 14)

    assert moved(agi="245361") == ["US.agi"]
    assert moved(agi="245360") == []
    assert moved(agi="245259") == ["US.agi"]  # down by 51
    assert moved(refund="267") == []  # exactly the $14 tolerance holds
    assert moved(refund="268") == ["US.refund"]
    gone = filing.drift(BOUND, {"US": {"agi": "245310", "tax": "123223"}}, 50, 14)
    assert gone == ["US.refund"]  # a figure that disappears relocks


def test_figures_are_read_from_the_engines_fields_only() -> None:
    values: Mapping[str, Mapping[str, object]] = {
        "f1040.agi": {"t": "decimal", "v": "245310"},
        "f1040.refund": {"t": "decimal", "v": "253"},
        "it201.balance_due": {"t": "decimal", "v": "1269"},
        "f1040.ip_pin_primary": {"t": "text", "v": "123456"},
    }
    assert filing.figures_of(values) == {
        "US": {"agi": "245310", "refund": "253"},
        "NY": {"balance_due": "1269"},
    }


class Stubs:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, object]] = {
            "f1040.agi": {"t": "decimal", "v": "245310"},
            "f1040.refund": {"t": "decimal", "v": "253"},
            "f1040.total_tax": {"t": "decimal", "v": "123223"},
        }
        self.income = 50
        self.amounts = 14
        self.superseded: list[tuple[uuid.UUID, str]] = []


@pytest.fixture
def stubs(monkeypatch: pytest.MonkeyPatch) -> Iterator[Stubs]:
    state = Stubs()

    async def values(_tenant: object, _t: str, _id: uuid.UUID) -> dict[str, dict[str, object]]:
        return state.values

    async def tolerances(tax_year: int, *, as_of: object) -> SimpleNamespace:
        return SimpleNamespace(
            tax_year=tax_year,
            total_income_or_agi_usd=state.income,
            tax_withholding_refund_balance_usd=state.amounts,
            reference_set_version_id=uuid.UUID(int=85),
        )

    async def supersede(tenant: object, envelope_id: uuid.UUID, binding: str) -> bool:
        assert getattr(tenant, "actor_kind") == "system"  # noqa: B009 -- the marker is system-only
        state.superseded.append((envelope_id, binding))
        return True

    monkeypatch.setattr(filing, "current_values", values)
    monkeypatch.setattr(filing, "pub1345_tolerances", tolerances)
    monkeypatch.setattr(filing, "supersede_for_amount_change", supersede)
    yield state


async def _bound(feld: Feld) -> tuple[uuid.UUID, uuid.UUID]:
    """A binding as `draft_envelope` leaves it (the envelope is C7's)."""
    binding, envelope = uuid.uuid4(), uuid.uuid4()
    await feld.seed.run(
        "INSERT INTO efile_amount_bindings (id, tenant_id, return_id, envelope_id, "
        "checkpoint_id, figures, figures_sha256, tolerances_ref) VALUES ($1, $2, $3, $4, $5, "
        "$6::jsonb, $7, $8)",
        binding,
        feld.tenant,
        feld.item,
        envelope,
        feld.checkpoint,
        json.dumps(BOUND),
        filing.figures_sha256(BOUND),
        uuid.UUID(int=85),
    )
    return binding, envelope


def _approved(feld: Feld) -> OutboxEvent:
    return OutboxEvent(
        event_id=uuid.uuid4(),
        tenant_id=feld.tenant,
        event_type="checkpoint.approved",
        payload={"target_type": "tax_return", "target_id": str(feld.item)},
    )


async def test_ac_a_50_dollar_move_holds_and_a_51_dollar_move_relocks(
    migrated_db: MigratedDatabase, stubs: Stubs
) -> None:
    feld = await feld_return(migrated_db)
    binding, envelope = await _bound(feld)
    stubs.values["f1040.agi"] = {"t": "decimal", "v": "245360"}
    await filing.on_checkpoint_approved(_approved(feld))
    assert stubs.superseded == []
    assert await filing.binding_state(feld.samuel.tenant, feld.item) == (binding, False)

    stubs.values["f1040.agi"] = {"t": "decimal", "v": "245361"}
    await filing.on_checkpoint_approved(_approved(feld))
    assert stubs.superseded == [(envelope, str(binding))]
    assert await filing.binding_state(feld.samuel.tenant, feld.item) == (binding, True)
    reason = await feld.seed.value(
        "SELECT superseded_reason FROM efile_amount_bindings WHERE id = $1", binding
    )
    assert reason == "amount_change: US.agi"
    actions = await feld.seed.rows(
        "SELECT action, actor_kind FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'efile_binding.superseded'",
        feld.tenant,
    )
    assert [(a["action"], a["actor_kind"]) for a in actions] == [
        ("efile_binding.superseded", "system")
    ]
    relocked = await feld.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'efile.relocked'",
        feld.tenant,
    )
    assert relocked == 1
    # Once superseded, nothing further happens to it.
    await filing.on_checkpoint_approved(_approved(feld))
    assert len(stubs.superseded) == 1


async def test_corrected_tolerances_recheck_every_open_binding(
    migrated_db: MigratedDatabase, stubs: Stubs
) -> None:
    feld = await feld_return(migrated_db)
    binding, _envelope = await _bound(feld)
    stubs.values["f1040.refund"] = {"t": "decimal", "v": "263"}  # a $10 move
    published = OutboxEvent(
        event_id=uuid.uuid4(),
        tenant_id=feld.tenant,
        event_type="reference_set.published",
        payload={"version_id": str(uuid.uuid4()), "set_key": "form_8879_set"},
    )
    await filing.on_tolerances_published(published)
    assert stubs.superseded == []
    stubs.amounts = 5  # the corrected set narrows the tolerance
    await filing.on_tolerances_published(published)
    assert [b for _e, b in stubs.superseded] == [str(binding)]


async def test_the_system_only_relocks_it_never_unlocks(
    migrated_db: MigratedDatabase, stubs: Stubs
) -> None:
    feld = await feld_return(migrated_db)
    binding, _envelope = await _bound(feld)
    stubs.values["f1040.agi"] = {"t": "decimal", "v": "300000"}
    await filing.recheck(feld.tenant, feld.item)
    with pytest.raises(asyncpg.CheckViolationError):
        await feld.seed.run(
            "UPDATE efile_amount_bindings SET superseded_at = NULL, superseded_reason = NULL "
            "WHERE id = $1",
            binding,
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await feld.seed.run("DELETE FROM efile_amount_bindings WHERE id = $1", binding)


async def test_the_envelope_waits_for_an_approved_packet(migrated_db: MigratedDatabase) -> None:
    feld = await feld_return(migrated_db)
    await feld.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.delivery_efile', 'true', 't01-t36', 'T-01-T36')",
        feld.tenant,
    )
    drafted = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/efile-envelope",
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert (drafted.status_code, drafted.json()["detail"]) == (409, "packet_not_approved")
