"""A-02-T10 (TASK-1336; SPEC-333 AC-5, AC-9, AC-17, AC-18; C9 v1) on the live routes, through
the real `authorise`, walls, row-level security and the migrated test database.

The row's acceptance: the C9 consumer suite passes against live routes (the view by layer and the
leadsheet by area answer C9's models with server-computed figures), a walled member gets 404 with
no hidden count, and a member without an independence confirmation is refused
`independence_pending`. From the #417 security review (DEC-440): the area rules are the
engagement's own methodology's, read in the caller's tenant on every call, and one firm's rules
never group another firm's trial balance.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from decimal import Decimal
from typing import Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.assurance.tb_contract import TbLayerViewOut, TbLeadsheetAreaOut
from abacus.modules.assurance.tb_read_model import area_rules
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext

from .support import Env, Person, Seeder, Site

TB: Final = "/v1/engagements/{e}/trial-balances/{tb}"
Line = tuple[str, str, str, str]
# EOY and BOY trial balances (code, name, debit, credit); each balances.
EOY: Final[list[Line]] = [
    ("1000", "Cash", "500.00", "0.00"),
    ("1100", "Accounts receivable", "300.00", "0.00"),
    ("1500", "Equipment", "200.00", "0.00"),
    ("2000", "Accounts payable", "0.00", "400.00"),
    ("3000", "Net assets", "0.00", "600.00"),
]
BOY: Final[list[Line]] = [
    ("1000", "Cash", "400.00", "0.00"),
    ("1100", "Accounts receivable", "250.00", "0.00"),
    ("2000", "Accounts payable", "0.00", "250.00"),
    ("3000", "Net assets", "0.00", "400.00"),
]


async def _flag_on(seed: Seeder, tenant_id: uuid.UUID) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'ledger.tb_workpaper', 'true', 'test-seed', 'A-02-T10') "
        "ON CONFLICT DO NOTHING",
        tenant_id,
    )


async def _snapshot(
    seed: Seeder, tenant_id: uuid.UUID, entity_id: uuid.UUID, end: str, lines: list[Line]
) -> uuid.UUID:
    """A snapshot and its lines in one transaction (lines join a snapshot only in its own):
    one simple-protocol script of fixed test literals."""
    snapshot = uuid.uuid4()
    debit = sum((Decimal(x[2]) for x in lines), Decimal(0))
    credit = sum((Decimal(x[3]) for x in lines), Decimal(0))
    start = f"{int(end[:4])}-01-01"
    rows = ", ".join(
        f"('{tenant_id}', '{snapshot}', '{code}', '{name}', {dr}, {cr}, 'row:{n}')"
        for n, (code, name, dr, cr) in enumerate(lines, start=1)
    )
    fingerprint = hashlib.sha256(snapshot.bytes).hexdigest()
    await seed.run(
        "INSERT INTO ledger_snapshots (id, tenant_id, client_entity_id, period_start, "  # noqa: S608
        "period_end, pulled_at, source, raw_fingerprint, line_count, total_debit, total_credit) "
        f"VALUES ('{snapshot}', '{tenant_id}', '{entity_id}', '{start}', '{end}', "
        f"clock_timestamp(), 'import_netsuite_tb_csv', '{fingerprint}', {len(lines)}, "
        f"{debit}, {credit}); "
        "INSERT INTO trial_balance_lines (tenant_id, snapshot_id, account_code, account_name, "
        f"debit, credit, source_ref) VALUES {rows};"
    )
    return snapshot


async def _methodology(
    seed: Seeder, tenant_id: uuid.UUID, by: uuid.UUID, rules: list[tuple[str, str, str, str]]
) -> uuid.UUID:
    """A methodology version with areas and account rules: (code, name, from, to)."""
    template = await seed.value(
        "INSERT INTO methodology_templates (tenant_id, name, created_by) "
        "VALUES ($1, $2, $3) RETURNING id",
        tenant_id,
        f"Method {uuid.uuid4().hex[:6]}",
        by,
    )
    version = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO methodology_versions (tenant_id, template_id, version, "
            "source_fingerprint, imported_by) VALUES ($1, $2, 1, $3, $4) RETURNING id",
            tenant_id,
            template,
            hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            by,
        ),
    )
    for n, (code, name, start, end) in enumerate(rules):
        await seed.run(
            "INSERT INTO methodology_areas (tenant_id, version_id, code, name, position) "
            "VALUES ($1, $2, $3, $4, $5)",
            tenant_id,
            version,
            code,
            name,
            n,
        )
        await seed.run(
            "INSERT INTO methodology_account_rules (tenant_id, version_id, area_code, "
            "account_from, account_to, position) VALUES ($1, $2, $3, $4, $5, $6)",
            tenant_id,
            version,
            code,
            start,
            end,
            n,
        )
    return version


async def _trial_balance(
    seed: Seeder, tenant_id: uuid.UUID, site: Site, by: uuid.UUID
) -> uuid.UUID:
    """Site's engagement with an adopted TB (v1, with a prior year), seeded as C9's adopt would."""
    current = await _snapshot(seed, tenant_id, site.entity_id, "2025-12-31", EOY)
    prior = await _snapshot(seed, tenant_id, site.entity_id, "2024-12-31", BOY)
    item = await seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
        site.engagement_id,
    ) or await seed.value(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
        "name, created_by) VALUES ($1, $2, $3, $4, 'assurance', 'Audit', $5) RETURNING id",
        tenant_id,
        site.engagement_id,
        site.client_id,
        site.entity_id,
        by,
    )
    tb = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO trial_balances (tenant_id, engagement_id, work_item_id, "
            "client_entity_id, period_start, period_end, created_by) "
            "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5) RETURNING id",
            tenant_id,
            site.engagement_id,
            item,
            site.entity_id,
            by,
        ),
    )
    await seed.run(
        "INSERT INTO trial_balance_versions (tenant_id, trial_balance_id, client_entity_id, "
        "version_no, snapshot_id, prior_snapshot_id, adopted_by, actor_kind, "
        "content_fingerprint) VALUES ($1, $2, $3, 1, $4, $5, $6, 'human', $7)",
        tenant_id,
        tb,
        site.entity_id,
        current,
        prior,
        by,
        hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
    )
    return tb


async def _pin(seed: Seeder, site: Site, version: uuid.UUID) -> None:
    await seed.run(
        "UPDATE engagements SET methodology_version_id = $2 WHERE id = $1",
        site.engagement_id,
        version,
    )


RULES_A: Final = [("CASH", "Cash", "1000", "1099"), ("AR", "Receivables", "1100", "1199")]


async def _setup(env: Env) -> tuple[Person, uuid.UUID]:
    seed = env.net.seed
    await _flag_on(seed, env.tenant_id)
    manager = await seed.person(env.tenant_id)
    await seed.member(env.a, manager, "manager")
    version = await _methodology(seed, env.tenant_id, env.admin.user_id, RULES_A)
    await _pin(seed, env.a, version)
    tb = await _trial_balance(seed, env.tenant_id, env.a, env.admin.user_id)
    return manager, tb


async def test_ac17_the_view_by_layer_is_c9s_with_code_computed_figures(env: Env) -> None:
    manager, tb = await _setup(env)
    response = await env.get(
        manager, (TB + "/layers/unadjusted").format(e=env.a.engagement_id, tb=tb)
    )
    assert response.status_code == 200, response.text
    view = TbLayerViewOut.model_validate(response.json())
    groups = {g.label: g for g in view.groups}
    # The engagement's own rules group the accounts; the rest is Unassigned, last, none dropped.
    assert list(groups) == ["Cash", "Receivables", "Unassigned"]
    assert [x.account_code for x in groups["Unassigned"].lines] == ["1500", "2000", "3000"]
    assert (groups["Cash"].eoy, groups["Cash"].boy) == (Decimal("500.00"), Decimal("400.00"))
    assert groups["Unassigned"].eoy == Decimal("-800.00")  # 200 - 400 - 600, by code
    assert view.balance.debit == view.balance.credit == Decimal("1000.00")
    assert view.balance.balanced and view.balance.difference == Decimal("0.00")
    assert [m.value for m in view.layers_available] == ["unadjusted"]
    assert view.provenance.source_kind == "import"
    assert view.prior_period_end is not None and view.prior_period_end.isoformat() == "2024-12-31"
    assert view.checks.worst is None and view.newer_snapshots == 0
    assert "trial_balance.adopt" in view.allowed_actions
    # Amounts travel as decimal strings (ADR-050).
    assert response.json()["balance"]["debit"] == "1000.00"


async def test_ac18_the_leadsheet_by_area_and_unassigned(env: Env) -> None:
    manager, tb = await _setup(env)
    base = TB.format(e=env.a.engagement_id, tb=tb)
    cash = await env.get(manager, base + "/leadsheets/Cash")
    assert cash.status_code == 200, cash.text
    sheet = TbLeadsheetAreaOut.model_validate(cash.json())
    assert (sheet.py, sheet.cy, sheet.change, sheet.change_pct) == (
        Decimal("400.00"),
        Decimal("500.00"),
        Decimal("100.00"),
        Decimal("25.0"),
    )
    assert not sheet.unassigned
    rest = TbLeadsheetAreaOut.model_validate(
        (await env.get(manager, base + "/leadsheets/Unassigned")).json()
    )
    assert rest.unassigned and [r.account_code for r in rest.rows] == ["1500", "2000", "3000"]
    assert (await env.get(manager, base + "/leadsheets/Inventory")).status_code == 404


async def test_ac17_an_adjusted_layer_without_a_source_is_layer_unavailable(env: Env) -> None:
    manager, tb = await _setup(env)
    response = await env.get(manager, (TB + "/layers/final").format(e=env.a.engagement_id, tb=tb))
    assert response.status_code == 409
    assert response.json()["detail"] == "layer_unavailable"


async def test_ac9_a_walled_member_gets_404_with_no_hidden_count(env: Env) -> None:
    _, tb = await _setup(env)
    walled = await env.walled("manager")
    for path in ("/layers/unadjusted", "/leadsheets/Cash"):
        hidden = await env.get(walled, (TB + path).format(e=env.a.engagement_id, tb=tb))
        missing = await env.get(walled, (TB + path).format(e=uuid.uuid4(), tb=tb))
        assert hidden.status_code == 404
        assert (hidden.status_code, hidden.text) == (missing.status_code, missing.text)
        assert env.leaks(hidden) == [] and str(tb) not in hidden.text


async def test_ac9_a_member_without_independence_is_refused_independence_pending(env: Env) -> None:
    _, tb = await _setup(env)
    seed = env.net.seed
    pending = await seed.person(env.tenant_id)
    await seed.run(  # on the team, no independence confirmation
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'senior')",
        env.tenant_id,
        env.a.engagement_id,
        pending.user_id,
    )
    for path in ("/layers/unadjusted", "/leadsheets/Cash"):
        response = await env.get(pending, (TB + path).format(e=env.a.engagement_id, tb=tb))
        assert response.status_code == 403
        assert response.json()["detail"] == "independence_pending"


async def test_the_flag_off_answers_404_after_authorise(env: Env) -> None:
    manager, tb = await _setup(env)
    await env.net.seed.run(
        "DELETE FROM feature_flag_states WHERE tenant_id = $1 AND flag = 'ledger.tb_workpaper'",
        env.tenant_id,
    )
    response = await env.get(
        manager, (TB + "/layers/unadjusted").format(e=env.a.engagement_id, tb=tb)
    )
    assert response.status_code == 404


async def test_one_firms_rules_never_group_another_firms_trial_balance(env: Env) -> None:
    """DEC-440: firm B's methodology puts every account in "Everything"; firm A's view never
    sees it, and B's version id under A's tenant reads as missing (row-level security)."""
    manager, tb = await _setup(env)
    seed = env.net.seed
    other = await seed.firm()
    admin_b = await seed.person(other, "firm_admin")
    site_b = await seed.site(other, admin_b.user_id, "other-firm")
    manager_b = await seed.person(other)
    await seed.member(site_b, manager_b, "manager")
    await _flag_on(seed, other)
    version_b = await _methodology(seed, other, admin_b.user_id, [("ALL", "Everything", "0", "9")])
    await _pin(seed, site_b, version_b)
    tb_b = await _trial_balance(seed, other, site_b, admin_b.user_id)

    mine = TbLayerViewOut.model_validate(
        (
            await env.get(
                manager, (TB + "/layers/unadjusted").format(e=env.a.engagement_id, tb=tb)
            )
        ).json()
    )
    theirs = TbLayerViewOut.model_validate(
        (
            await env.get(
                manager_b, (TB + "/layers/unadjusted").format(e=site_b.engagement_id, tb=tb_b)
            )
        ).json()
    )
    assert [g.label for g in mine.groups] == ["Cash", "Receivables", "Unassigned"]
    assert [g.label for g in theirs.groups] == ["Everything"]

    # A forged reference carrying B's version id, in A's tenant: NotFound, never B's rules.
    ctx = AuthContext(
        TenantContext(env.tenant_id, "human", str(manager.user_id)),
        manager.user_id,
        cast(
            uuid.UUID,
            await seed.value(
                "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2",
                env.tenant_id,
                manager.user_id,
            ),
        ),
        None,
        None,
    )
    ref = await get_ref(ctx, env.a.engagement_id)
    assert len(await area_rules(ctx, ref)) == 2
    with pytest.raises(NotFound):
        await area_rules(ctx, replace(ref, methodology_version_id=version_b))
