# ac-test-author: ayushkbhatia
"""T-06-T69 (TASK-9018; DEC-6024) on the migrated Postgres. Row acceptance: "the retired flags are
gone from feature-flags.yaml with _flags.py regenerated, and a firm without the tax entitlement
still gets 404 on every retired route."

One route of each retired family (T-04's workspace and worksheets, T-07's instrument,
beneficiaries and estate, T-05's workbook) answers 404 for a firm without its entitlement, even
with the old flag's state row still on, and stops answering 404 once the firm holds it. 1034's
backfill gives a firm that had a retired flag on the module it now needs, and no other firm."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.kernel import _flags
from abacus.kernel.flags import forget_flags

from .support import Net, Person, Seeder

pytestmark = pytest.mark.asyncio
MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "migrations"
    / "versions"
    / "1034_tax_flags_into_entitlements.py"
)

RETIRED = {
    "tax.review_workspace": "tax_returns",
    "tax.individual_workpapers": "tax_returns",
    "tax.fiduciary_workpapers": "tax_returns",
    "tax.fiduciary_k1_release": "tax_returns",
    "tax.estate_workpapers": "tax_returns",
    "tax.entity_workspace": "tax_entity_returns",
    "tax.workbook_run": "tax_entity_returns",
}
ROUTES = {  # route: the form of the return it reads
    "/v1/tax/returns/{r}/workspace": "1040",
    "/v1/tax/returns/{r}/leadsheets": "1040",
    "/v1/tax/returns/{r}/instrument": "1041",
    "/v1/tax/returns/{r}/beneficiaries": "1041",
    "/v1/tax/returns/{r}/estate/inventory": "706",
    "/v1/tax-returns/{r}/general-information": "1065",
}


async def test_t06t69_acceptance_the_retired_flags_are_gone_from_the_registry() -> None:
    assert not set(RETIRED) & set(_flags.FLAGS)
    assert {"tax_agents.enabled", "tax.entity_agents"} <= set(_flags.FLAGS)  # renewed, not retired


async def _returns(seed: Seeder, tenant: uuid.UUID, partner: Person) -> dict[str, uuid.UUID]:
    site = await seed.site(tenant, partner.user_id, "Retired")
    await seed.member(site, partner, "engagement_partner")
    out: dict[str, uuid.UUID] = {}
    for form in sorted(set(ROUTES.values())):
        item = cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
                "kind, name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', $5, $6) "
                "RETURNING id",
                tenant, site.engagement_id, site.client_id, site.entity_id,
                f"2025 Form {form}", partner.user_id,
            ),
        )  # fmt: skip
        await seed.run(
            "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, "
            "form, tax_year) VALUES ($1, $2, $3, $4, $5, 2025)",
            tenant, item, site.engagement_id, site.entity_id, form,
        )  # fmt: skip
        out[form] = item
    return out


async def test_t06t69_acceptance_a_firm_without_the_entitlement_gets_404_on_every_route(
    net: Net, seed: Seeder
) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    for flag in RETIRED:  # the old states stay as history and open nothing
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'T-06-T69')",
            tenant,
            flag,
        )
    forget_flags()
    returns = await _returns(seed, tenant, partner)
    for route, form in ROUTES.items():
        found = await net.call("GET", route.format(r=returns[form]), partner)
        assert found.status_code == 404, (route, found.text)

    for module in ("tax_returns", "tax_entity_returns"):
        await seed.run(
            "INSERT INTO tenant_entitlements (tenant_id, module, valid_from, set_by) "
            "VALUES ($1, $2, DATE '2000-01-01', 'test')",
            tenant,
            module,
        )
    # `tax_entity_returns` is a reviewed module: until its CPA review registers, only a synthetic
    # firm holds it (fail closed), so the firm under test is marked synthetic.
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    for route, form in ROUTES.items():
        found = await net.call("GET", route.format(r=returns[form]), partner)
        assert found.status_code != 404, (route, found.text)  # the same return, past the gate


async def test_t06t69_1034_writes_the_module_for_a_firm_that_had_a_retired_flag_on(
    seed: Seeder,
) -> None:
    had, never = await seed.firm(), await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.estate_workpapers', 'true', 'test-seed', 'T-06-T69'), "
        "($1, 'tax.workbook_run', 'true', 'test-seed', 'T-06-T69')",
        had,
    )
    statements: list[str] = []
    spec = importlib.util.spec_from_file_location("m1034", MIGRATION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    vars(migration)["op"] = SimpleNamespace(execute=statements.append)  # its own SQL, run here
    migration.upgrade()
    for statement in statements:
        await seed.run(statement)
    rows = await seed.rows(
        "SELECT tenant_id, module FROM tenant_entitlements WHERE set_by = 'T-06-T69' "
        "AND tenant_id = ANY($1) ORDER BY module",
        [had, never],
    )
    assert [(r["tenant_id"], r["module"]) for r in rows] == [
        (had, "tax_entity_returns"),
        (had, "tax_returns"),
    ]
