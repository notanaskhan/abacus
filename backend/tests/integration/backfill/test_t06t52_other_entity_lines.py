"""T-06-T52 (TASK-9031; DEC-6036): TXP-13's line-level reads on the migrated Postgres. The three
other-entity reads gain their lines (additive): Bluestem's Schedule M-2 across four columns and
the shareholders' allocation by name; Ashford's provision computation, its rate reconciliation
(an unclassified row last) and the deferred inventory; Lakeshore's Part IX lines with their
allocation basis and time-study percentages. The return row names a fiscal year's end."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest

from abacus.kernel.flags import forget_flags

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio
SIGNED_AT = datetime(2025, 3, 1, 15, 0, tzinfo=UTC)
SHA = hashlib.sha256(b"other entity consent text").digest()


async def _return(seed: Seeder, form: str) -> tuple[Person, Site, uuid.UUID]:
    tenant = await seed.firm()
    # `tax_entity_returns` is reviewed: it opens only for a synthetic firm (T-06-T69).
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, f"Form {form}")
    await seed.member(site, partner, "engagement_partner")
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.other_entity_workpapers', 'true', 'test-seed', 'T-06-T52')",
        tenant,
    )
    forget_flags()
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', $5, $6) RETURNING id",
            tenant, site.engagement_id, site.client_id, site.entity_id,
            f"2025 Form {form} {site.marker}", partner.user_id,
        ),
    )  # fmt: skip
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, $5, 2025)",
        tenant, item, site.engagement_id, site.entity_id, form,
    )  # fmt: skip
    # The read carries §7216 `use` and `ai_disclosure` (C19): the entity's consents are signed.
    for purpose in ("use", "ai_disclosure"):
        consent = await seed.value(
            "INSERT INTO consents (tenant_id, client_id, client_entity_id, purpose, tax_years, "
            "provider_terms_version, template_version_id, text_sha256, source, status, "
            "created_by, signed_at) VALUES ($1, $2, $3, $4, '{2025}', 'probe-terms', "
            "gen_random_uuid(), $5, 'record', 'signed', $6, $7) RETURNING id",
            tenant, site.client_id, site.entity_id, purpose, SHA, partner.user_id, SIGNED_AT,
        )  # fmt: skip
        await seed.run(
            "INSERT INTO consent_signers (tenant_id, consent_id, user_id, signer_role, required, "
            "signed_at, method) VALUES ($1, $2, $3, 'taxpayer', true, $4, 'record')",
            tenant, consent, partner.user_id, SIGNED_AT,
        )  # fmt: skip
    return partner, site, item


def _money(v: object) -> Decimal:
    return Decimal(str(v))


async def test_t06t52_aaa_reads_its_lines_and_the_allocation_by_name(
    net: Net, seed: Seeder
) -> None:
    partner, site, item = await _return(seed, "1120s")
    lines = [(1, 1240000), (2, 860000), (3, 12400), (5, 4200), (6, 2108200), (7, 620000),
             (8, 1488200)]  # fmt: skip
    for line_no, aaa in lines:
        await seed.run_untriggered(
            "INSERT INTO aaa_lines (tenant_id, engagement_id, work_item_id, line_no, col_aaa) "
            "VALUES ($1, $2, $3, $4, $5)",
            site.tenant_id, site.engagement_id, item, line_no, aaa,
        )  # fmt: skip
    for name, pct, rows in (
        ("Arjun Mehta", 70, (602000, 8680, 2940, 434000)),
        ("Sunita Rao", 30, (258000, 3720, 1260, 186000)),
    ):
        holder = await seed.value(
            "INSERT INTO k1_recipients (tenant_id, work_item_id, engine_ref, display_name, "
            "recipient_kind) VALUES ($1, $2, $3, $4, 'shareholder') RETURNING id",
            site.tenant_id, item, f"S{pct}", name,
        )  # fmt: skip
        await seed.run_untriggered(
            "INSERT INTO shareholder_allocations (tenant_id, engagement_id, work_item_id, "
            "partner_id, shares, days, pct, ordinary_income, interest, nondeductible, "
            "distributions) VALUES ($1, $2, $3, $4, $5, 365, $6, $7, $8, $9, $10)",
            site.tenant_id, site.engagement_id, item, holder, pct, Decimal(pct), *rows,
        )  # fmt: skip
    got = await net.call("GET", f"/v1/tax-returns/{item}/schedules/aaa", partner)
    assert got.status_code == 200, got.text
    body = got.json()
    assert [(x["line_no"], _money(x["aaa"])) for x in body["lines"]] == [
        (n, Decimal(v)) for n, v in lines
    ]
    assert _money(body["aaa"]) == Decimal("1488200")  # E10's roll over the stored lines
    assert [(h["name"], _money(h["pct"]), _money(h["ordinary_income"])) for h in body[
        "shareholders"
    ]] == [("Arjun Mehta", Decimal(70), Decimal(602000)), ("Sunita Rao", Decimal(30),
                                                         Decimal(258000))]  # fmt: skip
    total = sum(_money(h["distributions"]) for h in body["shareholders"])
    assert total == Decimal("620000")  # the allocation foots to line 7


async def test_t06t52_provision_reads_its_computation_reconciliation_and_inventory(
    net: Net, seed: Seeder
) -> None:
    partner, site, item = await _return(seed, "1120")
    provision = await seed.value(
        "INSERT INTO tax_provisions (tenant_id, engagement_id, work_item_id, pretax_book_income, "
        "permanent_total, temporary_total, taxable_income, blended_rate, current_tax, "
        "deferred_tax, total_provision, etr, recon_status, off_amount) VALUES ($1, $2, $3, "
        "7800000, 120000, -430000, 7490000, 28.5, 2134650, 122550, 2257200, 28.9, 'off', 1200) "
        "RETURNING id",
        site.tenant_id, site.engagement_id, item,
    )  # fmt: skip
    for key, text_, amount, effect, kind in (
        ("statutory", "Statutory federal", 1638000, 21.0, "rate"),
        ("state", "State, net of federal benefit", 585000, 7.5, "rate"),
        ("permanent", "Permanent differences", 34200, 0.4, "permanent"),
        ("unclassified_1", "Unclassified difference", 1200, None, "unclassified"),
    ):
        await seed.run(
            "INSERT INTO rate_recon_items (tenant_id, engagement_id, work_item_id, provision_id, "
            "item_key, description, amount, rate_effect, classification) VALUES ($1, $2, $3, "
            "$4, $5, $6, $7, $8, $9)",
            site.tenant_id, site.engagement_id, item, provision, key, text_, amount, effect, kind,
        )  # fmt: skip
    for kind, label, diff, amount in (
        ("dtl", "Bonus depreciation", 640000, 182400),
        ("dta", "Accrued bonuses", 210000, -59850),
    ):
        await seed.run(
            "INSERT INTO deferred_tax_items (tenant_id, engagement_id, work_item_id, "
            "provision_id, kind, label, temporary_difference, rate, amount) VALUES ($1, $2, $3, "
            "$4, $5, $6, $7, 28.5, $8)",
            site.tenant_id, site.engagement_id, item, provision, kind, label, diff, amount,
        )  # fmt: skip
    got = await net.call("GET", f"/v1/tax-returns/{item}/provision", partner)
    assert got.status_code == 200, got.text
    body = got.json()
    assert _money(body["pretax_book_income"]) == Decimal("7800000")
    assert _money(body["taxable_income"]) == Decimal("7490000")
    assert _money(body["blended_rate"]) == Decimal("28.5")
    assert [r["classification"] for r in body["recon_items"]][-1] == "unclassified"
    assert body["rate_reconciliation_tally"] == "off"
    assert _money(body["unclassified"]) == Decimal("1200")
    assert sum(_money(d["amount"]) for d in body["deferred_items"]) == Decimal("122550")
    assert [d["kind"] for d in body["deferred_items"]] == ["dtl", "dta"]


async def test_t06t52_part_ix_reads_its_lines_basis_and_time_study(net: Net, seed: Seeder) -> None:
    partner, site, item = await _return(seed, "990")
    await seed.run_untriggered(
        "UPDATE tax_returns SET fiscal_year_end = DATE '2026-06-30' WHERE work_item_id = $1", item
    )
    for line, label, total, prog, mg, fr, basis, study in (
        ("5", "Compensation of current officers", 162000, 81000, 65000, 16000, "time_study",
         {"pct": {"program": "50.0", "management_general": "40.1", "fundraising": "9.9"}}),
        ("24a", "Books and learning materials", 412000, 412000, 0, 0, "direct", None),
    ):  # fmt: skip
        await seed.run(
            "INSERT INTO functional_expense_lines (tenant_id, engagement_id, work_item_id, "
            "part_ix_line, label, total, program, management_general, fundraising, "
            "allocation_basis, time_study) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, "
            "$11::jsonb)",
            site.tenant_id, site.engagement_id, item, line, label, total, prog, mg, fr, basis,
            None if study is None else json.dumps(study),
        )  # fmt: skip
    got = await net.call("GET", f"/v1/tax-returns/{item}/functional-expenses", partner)
    assert got.status_code == 200, got.text
    lines = got.json()["lines"]
    assert [(x["line"], x["basis"]) for x in lines] == [("24a", "direct"), ("5", "time_study")]
    officers = next(x for x in lines if x["line"] == "5")
    assert {k: _money(v) for k, v in officers["time_study"].items()} == {
        "program": Decimal("50.0"),
        "management_general": Decimal("40.1"),
        "fundraising": Decimal("9.9"),
    }
    for x in lines:  # each line crossfoots (the table's CHECK, read back)
        assert _money(x["program"]) + _money(x["management"]) + _money(x["fundraising"]) == _money(
            x["total"]
        )
    # The record is the practice's: the firm holds the Tax Returns module.
    await seed.run(
        "INSERT INTO tenant_entitlements (tenant_id, module, valid_from, set_by) "
        "VALUES ($1, 'tax_returns', '2000-01-01', 'test-seed') ON CONFLICT DO NOTHING",
        site.tenant_id,
    )  # fmt: skip
    forget_flags()
    record = await net.call("GET", f"/v1/tax-returns/{item}", partner)
    assert record.status_code == 200, record.text
    assert record.json()["row"]["fiscal_year_end"] == "2026-06-30"
