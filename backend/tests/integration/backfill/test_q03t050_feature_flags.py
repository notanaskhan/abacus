# ac-test-author: ayushkbhatia
"""SPEC-011 AC-1 to AC-4, AC-6, DEC-55 and ADR-148 (TASK-026; Q-03-T050, TASK-1440): flags carry
in-progress rollout only, live a bounded time, and can never switch on a module the firm's
entitlements refuse.

Boundary: the public read `kernel.flags.flag`, the operator's `make flag` function
(`abacus_tools.flags.set_flag`), the registry validator SPEC-011 §8 names
(`abacus_tools.codegen.feature_flags.parse` and `expired`), the registry files themselves, and
`create_app()` over HTTP for the entitlement-gated catalogue (`GET /v1/engagement-types`), on the
migrated Postgres. Entitlements are seeded as the superuser: the app role may not write them
(ADR-148, operator only).

Later decisions followed instead of the spec's words: DEC-55 and ADR-148 (a module is an
entitlement row, never a flag; flag names are `area.feature`); DEC-137 (an entry may carry
`override: DEC-nnn`, which allows one renewal of up to 180 days; without it ADR-089's 90 days
hold).
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final, cast

import pytest
import yaml

from abacus.kernel._flags import FLAGS
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import Flag, flag, forget_flags
from abacus.modules.platform.api import EntitlementRequired, check_entitlement
from abacus_tools.codegen.feature_flags import RegistryError, expired, parse
from abacus_tools.flags import set_flag

from .support import Net, Person, Seeder

Json = Any  # untyped JSON, YAML and SDK payloads read as data, never trusted
REGISTRY: Final = Path(__file__).resolve().parents[4] / "docs/architecture/feature-flags"
NAME: Final = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
# ADR-148 names these; the database's CHECK on tenant_entitlements.module is the fixed list.
NAMED_MODULES: Final = {"attest", "internal_audit", "insights", "office_addins"}
ROLLOUT_FLAG: Final = "evidence.viewer_v1"  # a registered boolean with default false
RETIRED: Final = "engagements.v2"  # P-07-T59


def _registry() -> list[dict[str, Json]]:
    entries: list[dict[str, Json]] = []
    for path in sorted(REGISTRY.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        loaded = cast(dict[str, Json], yaml.safe_load(path.read_text()) or {})
        entries.extend(cast(list[dict[str, Json]], loaded.get("flags") or []))
    return entries


async def _modules(seed: Seeder) -> set[str]:
    """The entitlement modules, from the CHECK the database enforces on `module`."""
    definition = await seed.value(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
        "JOIN pg_class t ON t.oid = c.conrelid WHERE t.relname = 'tenant_entitlements' "
        "AND c.contype = 'c' AND pg_get_constraintdef(c.oid) LIKE '%module%'"
    )
    return set(re.findall(r"'([a-z_]+)'", str(definition)))


def _flag(name: str) -> Flag:
    return FLAGS[name]


def _entry(**change: object) -> str:
    base: dict[str, object] = {
        "name": "reports.preview",
        "description": "A rollout.",
        "owner": "ayushkbhatia",
        "created": date(2026, 10, 1),
        "expires": date(2026, 12, 30),  # 90 days
        "kind": "boolean",
        "default": False,
    }
    base.update(change)
    return yaml.safe_dump({"flags": [{k: v for k, v in base.items() if v is not None}]})


# --- AC-6, DEC-55, ADR-089: the registry ------------------------------------------------------


async def test_ac6_every_flag_has_an_owner_a_description_and_a_bounded_lifetime() -> None:
    entries = _registry()
    assert entries
    for e in entries:
        name = e["name"]
        assert str(e.get("owner") or "").strip(), name
        assert str(e.get("description") or "").strip(), name
        created, expires = cast(date, e["created"]), cast(date, e["expires"])
        if e.get("override") is None:
            assert created < expires <= created + timedelta(days=90), name
        else:  # DEC-137: one founder-approved renewal, named, up to 180 days
            assert re.fullmatch(r"DEC-\d+", str(e["override"])), name
            assert created < expires <= created + timedelta(days=180), name
        if e["kind"] == "boolean":
            assert str(e["default"]).lower() in {"true", "false"}, name
        else:
            assert e["kind"] == "variant", name
            assert str(e["default"]) in [str(v) for v in e["values"]], name


async def test_dec55_no_flag_is_a_module_every_flag_is_area_feature(seed: Seeder) -> None:
    modules = await _modules(seed)
    assert modules >= NAMED_MODULES
    for e in _registry():
        name = str(e["name"])
        assert NAME.fullmatch(name), name
        assert not name.startswith("ff."), name
        assert name.split(".", 1)[0] not in modules, name


@pytest.mark.parametrize(
    "change",
    [
        {"expires": date(2026, 12, 31)},  # 91 days, no override
        {"expires": date(2027, 3, 31), "override": "DEC-137"},  # 181 days
        {"override": "because"},  # an override names its decision
        {"owner": None},
        {"description": " "},
        {"default": "maybe"},
        {"name": "ff.attest"},
        {"name": "attest.soc_reports"},
        {"name": "insights.dashboards"},
        {"kind": "variant", "values": ["a", "b"], "default": "c"},
    ],
)
async def test_ac6_the_validator_refuses_an_entry_outside_the_rules(
    change: dict[str, object],
) -> None:
    with pytest.raises(RegistryError):
        parse(_entry(**change))


async def test_ac6_the_validator_accepts_ninety_days_and_a_named_override_to_180() -> None:
    assert [e.name for e in parse(_entry())] == ["reports.preview"]
    renewed = parse(_entry(expires=date(2027, 3, 30), override="DEC-137"))
    assert [e.name for e in renewed] == ["reports.preview"]


async def test_ac4_a_flag_past_its_expiry_is_reported_with_its_owner() -> None:
    [entry] = parse(_entry())
    assert expired([entry], today=date(2026, 12, 30)) == []
    [late] = expired([entry], today=date(2026, 12, 31))
    assert (late.name, late.owner) == ("reports.preview", "ayushkbhatia")


async def test_ac4_no_registered_flag_has_expired_on_the_main_line() -> None:
    today = date.today()
    late = [e["name"] for e in _registry() if cast(date, e["expires"]) < today]
    assert late == []


# --- AC-1 to AC-3: reading and setting --------------------------------------------------------


async def test_ac1_a_firm_with_no_state_reads_the_default_and_a_set_firm_reads_true(
    seed: Seeder,
) -> None:
    firm = TenantContext(await seed.firm(), "system", "test")
    other = TenantContext(await seed.firm(), "system", "test")
    forget_flags()
    assert await flag(firm, _flag(ROLLOUT_FLAG), fresh=True) is False
    await set_flag(firm.tenant_id, ROLLOUT_FLAG, "true", "ayush", "TASK-1440 canary")
    assert await flag(firm, _flag(ROLLOUT_FLAG), fresh=True) is True
    assert await flag(other, _flag(ROLLOUT_FLAG), fresh=True) is False  # per firm


async def test_ac1_a_change_is_read_within_thirty_seconds(seed: Seeder) -> None:
    """The cache holds a value at most 30 s; the operator's set clears this process's cache."""
    firm = TenantContext(await seed.firm(), "system", "test")
    forget_flags()
    assert await flag(firm, _flag(ROLLOUT_FLAG)) is False
    await set_flag(firm.tenant_id, ROLLOUT_FLAG, "true", "ayush", "TASK-1440")
    assert await flag(firm, _flag(ROLLOUT_FLAG)) is True


async def test_ac2_an_unreachable_database_reads_the_default_and_never_raises(
    seed: Seeder, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    caplog.set_level(logging.DEBUG)
    firm = TenantContext(await seed.firm(), "system", "test")
    await set_flag(firm.tenant_id, ROLLOUT_FLAG, "true", "ayush", "TASK-1440")
    forget_flags()
    await dispose_engine()
    configure_engine("postgresql+asyncpg://nobody:nothing@127.0.0.1:9/none")
    assert await flag(firm, _flag(ROLLOUT_FLAG), fresh=True) is False  # the registry default
    out, err = capfd.readouterr()
    logged = " ".join(r.getMessage() for r in caplog.records) + out + err
    assert "flag.read_failed" in logged
    assert "nothing@" not in logged  # identifiers only


async def test_ac3_the_operator_set_is_audited_with_the_name_and_both_values(
    seed: Seeder,
) -> None:
    tenant_id = await seed.firm()
    assert await set_flag(tenant_id, ROLLOUT_FLAG, "true", "ayush", "TASK-1440") is None
    assert await set_flag(tenant_id, ROLLOUT_FLAG, "false", "ayush", "rolled back") == "true"
    rows = await seed.rows(
        "SELECT to_jsonb(a)::text AS doc, actor_kind, actor_id FROM audit_events a "
        "WHERE tenant_id = $1 AND action = 'feature_flag.set' ORDER BY seq",
        tenant_id,
    )
    assert len(rows) == 2
    for r in rows:
        assert r["actor_kind"] == "system"
        assert r["actor_id"] == "operator:ayush"
    # Old and new values: as typed, or as their fingerprint (variants).
    first, second = (str(r["doc"]) for r in rows)
    assert _holds(second, "true") and _holds(second, "false")
    assert _holds(first, "true")
    stored = await seed.rows(
        "SELECT value, set_by, reason FROM feature_flag_states WHERE tenant_id = $1",
        tenant_id,
    )
    assert [(s["value"], s["set_by"], s["reason"]) for s in stored] == [
        ("false", "ayush", "rolled back")
    ]


def _holds(doc: str, value: str) -> bool:
    return f'"{value}"' in doc or hashlib.sha256(value.encode()).hexdigest() in doc


@pytest.mark.parametrize(
    ("name", "value"),
    [("ff.attest", "true"), ("evidence.no_such_flag", "true"), (ROLLOUT_FLAG, "maybe")],
)
async def test_ac3_an_unknown_flag_or_value_is_refused_and_nothing_is_stored(
    seed: Seeder, name: str, value: str
) -> None:
    tenant_id = await seed.firm()
    with pytest.raises(ValueError):
        await set_flag(tenant_id, name, value, "ayush", "TASK-1440")
    count = await seed.value(
        "SELECT count(*) FROM feature_flag_states WHERE tenant_id = $1", tenant_id
    )
    assert int(str(count)) == 0
    assert "feature_flag.set" not in await seed.actions(tenant_id)


# --- Q-03-T050: a flag cannot enable a module the entitlements refuse -------------------------


async def _every_flag_on(seed: Seeder, tenant_id: uuid.UUID) -> None:
    """The firm with every registered boolean flag switched on, as an operator could."""
    for e in _registry():
        if e["kind"] == "boolean":
            await seed.run(
                "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
                "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1440')",
                tenant_id,
                e["name"],
            )
    forget_flags()


async def _entitle(seed: Seeder, tenant_id: uuid.UUID, module: str) -> None:
    await seed.run(
        "INSERT INTO tenant_entitlements (tenant_id, module, enabled, valid_from, set_by) "
        "VALUES ($1, $2, true, current_date - 1, 'operator:test')",
        tenant_id,
        module,
    )


async def test_t050_every_flag_on_still_leaves_every_module_refused(seed: Seeder) -> None:
    tenant_id = await seed.firm()
    await _every_flag_on(seed, tenant_id)
    tenant = TenantContext(tenant_id, "system", "test")
    for module in sorted(await _modules(seed)):
        with pytest.raises(EntitlementRequired):
            await check_entitlement(tenant, cast(Json, module))
    await _entitle(seed, tenant_id, "attest")
    held = await check_entitlement(tenant, "attest")
    assert held is not None


async def _catalogue(net: Net, who: Person) -> dict[str, dict[str, object]]:
    response = await net.call("GET", "/v1/engagement-types", who)
    assert response.status_code == 200, response.text
    return {str(i["code"]): i for i in response.json()["items"]}


async def test_t050_with_every_flag_on_soc_engagements_still_need_attest(
    net: Net, seed: Seeder
) -> None:
    tenant_id = await seed.firm()
    await _every_flag_on(seed, tenant_id)
    admin = await seed.person(tenant_id, "firm_admin")
    items = await _catalogue(net, admin)
    for code in ("soc1", "soc2"):
        assert items[code]["entitlement"] == "attest", code
        assert items[code]["availability"] == "needs_entitlement", code
    assert items["fs_audit"]["availability"] == "available"
    assert "single_audit" not in items

    await _entitle(seed, tenant_id, "attest")
    entitled = await _catalogue(net, admin)
    assert entitled["soc1"]["availability"] == "available"
    assert entitled["soc2"]["availability"] == "available"


async def test_t050_the_catalogue_answers_once_its_rollout_flag_retires(
    net: Net, seed: Seeder
) -> None:
    """The flag only rolled the surface out (ADR-089): `engagements.v2` retired with P-07-T59
    (DEC-905), the catalogue answers for every firm and the entitlement alone still decides
    what is available."""
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    forget_flags()
    response = await net.call("GET", "/v1/engagement-types", admin)
    assert response.status_code == 200, response.text
    items = {i["code"]: i for i in cast(list[Json], response.json()["items"])}
    assert items["soc1"]["availability"] == "needs_entitlement"
    assert RETIRED not in {e["name"] for e in _registry()}
