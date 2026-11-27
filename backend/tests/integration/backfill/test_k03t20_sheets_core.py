# ac-test-author: ayushkbhatia
"""K-03-T20 (TASK-9014; K-03 §3.7; SHT-01 a, b, c, f; DEC-6020) on the migrated Postgres. Row
acceptance: "A sheet is created empty when its procedure moves to in progress, 40 rows arrive from
sample seed 0x7C31B4 with totals 3,286,400.00 and 412,300.00, a stale row version answers 412, and
no cell is written outside record_value."

Granite Peak follows FS v5, whose BH-FS-430 sheet has two strata sections. The procedure's sheet is
created empty ("0 rows · View: Default"); the approved sample's 40 items arrive 24 and 16 in the
strata with code's totals; an edit at the row's version lands and a second edit at the old version
answers 412; every cell on the sheet has a `field_value_versions` row (record_value's), and the
stored views filter by code."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import cast

import pytest

from .p05_support import FLAG as COLLAB_FLAG
from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio

SEED = 0x7C31B4
STRATUM_1, STRATUM_2 = "stratum_1", "stratum_2"  # the definition's section codes
STRATA = [
    {"key": STRATUM_1, "title": "STRATUM 1 — PAYMENTS ≥ $50,000", "stratum": 1,
     "totals": {"sum": "amount"}},
    {"key": STRATUM_2, "title": "STRATUM 2 — RANDOM, $7,750–$49,999", "stratum": 2,  # noqa: RUF001 -- the design's en dash
     "totals": {"sum": "amount"}},
]  # fmt: skip
# 24 payments >= 50,000 summing 3,286,400.00 and 16 in the random band summing 412,300.00.
AMOUNTS = (
    [(1, Decimal("136000.00"))] * 23
    + [(1, Decimal("158400.00"))]
    + [(2, Decimal("25000.00"))] * 15
    + [(2, Decimal("37300.00"))]
)


async def _template(seed: Seeder, tenant: uuid.UUID, owner: Person) -> uuid.UUID:
    methodology = uuid.uuid4()
    await seed.run(
        "INSERT INTO methodology_templates (id, tenant_id, name, created_by, engagement_types, "
        "family) VALUES ($1, $2, 'BH Audit Methodology · FS', $3, '{fs_audit}', 'fs')",
        methodology,
        tenant,
        owner.user_id,
    )
    template = await seed.value(
        "INSERT INTO engagement_templates (tenant_id, methodology_template_id, name, family) "
        "VALUES ($1, $2, 'FS audit', 'fs') RETURNING id",
        tenant,
        methodology,
    )
    version = uuid.uuid4()
    await seed.run(
        "INSERT INTO template_versions (id, tenant_id, template_id, seq, label, created_by) "
        "VALUES ($1, $2, $3, 5, 'FS v5', $4)",
        version,
        tenant,
        template,
        owner.user_id,
    )
    definition = await seed.value(
        "INSERT INTO template_sheet_definitions (tenant_id, template_version_id, sheet_key, "
        "title, step_key, row_source, sections, position) VALUES ($1, $2, 'bh_fs_430', "
        "'Disbursements testing', 'BH-FS-430', 'sample_set', $3::jsonb, 1) RETURNING id",
        tenant,
        version,
        json.dumps(STRATA),
    )
    columns: list[tuple[str, str, str, dict[str, str] | None, dict[str, str]]] = [
        ("vendor", "Vendor", "text", {"sample": "display.vendor"}, {}),
        ("amount", "Amount", "currency", {"sample": "amount"}, {}),
        ("result", "Result", "single_select", None, {"exception_value": "Exception"}),
    ]
    for position, (key, name, kind, binding, config) in enumerate(columns, start=1):
        await seed.run(
            "INSERT INTO template_sheet_columns (tenant_id, template_version_id, "
            "sheet_definition_id, column_key, name, type, config, classification, "
            "source_binding, position) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 'confidential', "
            "$8::jsonb, $9)",
            tenant,
            version,
            definition,
            key,
            name,
            kind,
            json.dumps(config),
            None if binding is None else json.dumps(binding),
            position,
        )
    await seed.run(
        "UPDATE template_versions SET status = 'published', effective_from = DATE '2026-07-01', "
        "fingerprint = $2, published_by = $3, published_at = now() WHERE id = $1",
        version,
        "5" * 64,
        owner.user_id,
    )
    return version


async def _sample(seed: Seeder, site: Site, item: uuid.UUID, by: Person) -> uuid.UUID:
    sample_set = uuid.uuid4()
    population, version = uuid.uuid4(), uuid.uuid4()
    statements: list[tuple[str, tuple[object, ...]]] = [
        (
            "INSERT INTO sample_sets (id, tenant_id, engagement_id, work_item_id, title, "
            "created_by) VALUES ($1, $2, $3, $4, 'Disbursements 2025', $5)",
            (sample_set, site.tenant_id, site.engagement_id, item, by.user_id),
        ),
        (
            "INSERT INTO sample_set_versions (id, tenant_id, sample_set_id, version_no, "
            "population_id, method, parameters, computed_size, final_size, seed, seed_source, "
            "sampler_version, inputs_hash, items_hash, content_hash, status, approved_by, "
            "approved_at, approved_actor_kind, created_by) VALUES ($1, $2, $3, 1, $4, "
            "'threshold_random_stratified', '{}'::jsonb, 40, 40, $5, 'scenario', 'v1', $6, $6, "
            "$6, 'approved', $7, now(), 'human', $7)",
            (version, site.tenant_id, sample_set, population, SEED, "a" * 64, by.user_id),
        ),
    ]
    for position, (stratum, amount) in enumerate(AMOUNTS, start=1):
        statements += [
            (
                "INSERT INTO sample_population_records (tenant_id, population_id, ordinal, "
                "record_key, amount, display) VALUES ($1, $2, $3, $4, $5, $6::jsonb)",
                (site.tenant_id, population, position, f"PAY-{position:03d}", amount,
                 json.dumps({"vendor": f"Vendor {position}"})),
            ),
            (
                "INSERT INTO sample_items (tenant_id, sample_set_version_id, position, "
                "population_record_ordinal, record_key, stratum_position, selection_reason, "
                "display) VALUES ($1, $2, $3, $3, $4, $5, $6, $7::jsonb)",
                (site.tenant_id, version, position, f"PAY-{position:03d}", stratum,
                 "threshold" if stratum == 1 else "random",
                 json.dumps({"vendor": f"Vendor {position}"})),
            ),
        ]  # fmt: skip
    await seed.run_untriggered_many(statements)
    return sample_set


async def test_k03t20_acceptance_sheet_from_sample_totals_412_and_record_value(
    net: Net, seed: Seeder
) -> None:
    tenant = await seed.firm()
    for flag in ("sheets.enabled", "templates_v2.enabled"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'K-03-T20')",
            tenant,
            flag,
        )
    manager = await seed.person(tenant)
    granite = await seed.site(tenant, manager.user_id, "Granite Peak")
    await seed.member(granite, manager, "manager")
    await seed.attest(tenant, granite.engagement_id)
    item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            granite.engagement_id,
        ),
    )
    version = await _template(seed, tenant, manager)
    await seed.run(
        "INSERT INTO engagement_template_links (tenant_id, engagement_id, template_id, "
        "template_version_id) SELECT $1, $2, template_id, id FROM template_versions WHERE id = $3",
        tenant,
        granite.engagement_id,
        version,
    )
    procedure = uuid.uuid4()
    await seed.run_untriggered(
        "INSERT INTO program_procedures (id, tenant_id, engagement_id, work_item_id, "
        "methodology_version_id, program_step_key, level, mandatory, status, linked_work, "
        "created_by) VALUES ($1, $2, $3, $4, $5, 'BH-FS-430', 'testing', false, 'in_progress', "
        '\'{"kind": "sheet", "ref": "bh_fs_430"}\'::jsonb, $6)',
        procedure,
        tenant,
        granite.engagement_id,
        item,
        uuid.uuid4(),
        manager.user_id,
    )

    made = await net.call(
        "POST",
        f"/v1/work-items/{item}/sheets",
        manager,
        body={"procedure_id": str(procedure), "sheet_definition_ref": "bh_fs_430"},
    )
    assert made.status_code == 201, made.text
    sheet = made.json()
    assert sheet["status"]["summary"] == "0 rows · View: Default"
    assert [c["key"] for c in sheet["columns"]] == ["vendor", "amount", "result"]
    sheet_id = sheet["sheet_id"]
    again = await net.call(
        "POST",
        f"/v1/work-items/{item}/sheets",
        manager,
        body={"procedure_id": str(procedure), "sheet_definition_ref": "bh_fs_430"},
    )
    assert again.status_code == 201 and again.json()["sheet_id"] == sheet_id  # one per key

    sample_set = await _sample(seed, granite, item, manager)
    rows = await net.call(
        "POST",
        f"/v1/sheets/{sheet_id}/rows/from-sample",
        manager,
        body={"sample_set_id": str(sample_set)},
        headers=net.keyed(),
    )
    assert rows.status_code == 201, rows.text
    assert len(rows.json()["items"]) == 40
    vm = (await net.call("GET", f"/v1/sheets/{sheet_id}", manager)).json()
    assert [(s["title"], s["count"], s["total"]) for s in vm["sections"]] == [
        ("STRATUM 1 — PAYMENTS ≥ $50,000", 24, "3,286,400.00"),
        ("STRATUM 2 — RANDOM, $7,750–$49,999", 16, "412,300.00"),  # noqa: RUF001 -- the design's en dash
    ]
    assert vm["status"]["summary"] == "40 rows · 0 tested · seed 0x7C31B4"
    twice = await net.call(
        "POST",
        f"/v1/sheets/{sheet_id}/rows/from-sample",
        manager,
        body={"sample_set_id": str(sample_set)},
        headers=net.keyed(),
    )
    assert twice.status_code == 201 and twice.json()["items"] == []  # nothing added twice

    first = rows.json()["items"][0]
    edited = await net.call(
        "PATCH",
        f"/v1/sheets/{sheet_id}/rows/{first['row_id']}",
        manager,
        body={"cells": {"result": "Exception"}, "version": first["version"]},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["version"] == first["version"] + 1
    assert edited.json()["cells"]["result"]["exception"] is True
    stale = await net.call(
        "PATCH",
        f"/v1/sheets/{sheet_id}/rows/{first['row_id']}",
        manager,
        body={"cells": {"result": "Pass"}, "version": first["version"]},
    )
    assert stale.status_code == 412, stale.text

    cells = await seed.value("SELECT count(*) FROM sheet_cells WHERE sheet_id = $1", sheet_id)
    versioned = await seed.value(
        "SELECT count(*) FROM sheet_cells c WHERE c.sheet_id = $1 AND EXISTS (SELECT 1 FROM "
        "field_value_versions f JOIN sheet_columns k ON k.column_key = f.field_key "
        "WHERE f.target_type = 'sheet_row' AND f.target_id = c.row_id AND k.id = c.column_id)",
        sheet_id,
    )
    assert cells == 81 and versioned == cells  # 40 vendors, 40 amounts, 1 result

    for name, filters in (
        ("Exceptions", [{"column": "exception", "value": "true"}]),
        ("Above $50,000", [{"column": "amount", "op": "gte", "value": "50000"}]),
    ):
        saved = await net.call(
            "POST",
            f"/v1/sheets/{sheet_id}/views",
            manager,
            body={"name": name, "filters": filters},
        )
        assert saved.status_code == 201, saved.text
        got = await net.call(
            "GET", f"/v1/sheets/{sheet_id}/rows", manager, params={"view": saved.json()["view_id"]}
        )
        assert len(got.json()["items"]) == (1 if name == "Exceptions" else 24)
    listed = await net.call("GET", f"/v1/sheets/{sheet_id}/views", manager)
    assert next(v["name"] for v in listed.json()["items"]) == "Default"

    outsider = await seed.person(tenant)
    walled = await net.call("GET", f"/v1/sheets/{sheet_id}", outsider)
    assert walled.status_code in (403, 404), walled.text


async def test_k03t22_row_drawer_reads_facts_reason_and_links(net: Net, seed: Seeder) -> None:
    """K-03-T22 (TASK-9028; DEC-6033): SHT-01 e's drawer read. The row's facts in column order,
    the agent's reason for its suggested cell (the agents module's own read, walls and all), and
    its links; a row on another sheet answers 404, and a person outside the walls sees nothing."""
    tenant = await seed.firm()
    for flag in ("sheets.enabled", "templates_v2.enabled", COLLAB_FLAG):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'K-03-T22')",
            tenant,
            flag,
        )
    manager = await seed.person(tenant)
    granite = await seed.site(tenant, manager.user_id, "Granite Peak")
    await seed.member(granite, manager, "manager")
    await seed.attest(tenant, granite.engagement_id)
    item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            granite.engagement_id,
        ),
    )
    version = await _template(seed, tenant, manager)
    await seed.run(
        "INSERT INTO engagement_template_links (tenant_id, engagement_id, template_id, "
        "template_version_id) SELECT $1, $2, template_id, id FROM template_versions WHERE id = $3",
        tenant,
        granite.engagement_id,
        version,
    )
    procedure = uuid.uuid4()
    await seed.run_untriggered(
        "INSERT INTO program_procedures (id, tenant_id, engagement_id, work_item_id, "
        "methodology_version_id, program_step_key, level, mandatory, status, linked_work, "
        "created_by) VALUES ($1, $2, $3, $4, $5, 'BH-FS-430', 'testing', false, 'in_progress', "
        '\'{"kind": "sheet", "ref": "bh_fs_430"}\'::jsonb, $6)',
        procedure,
        tenant,
        granite.engagement_id,
        item,
        uuid.uuid4(),
        manager.user_id,
    )
    made = await net.call(
        "POST",
        f"/v1/work-items/{item}/sheets",
        manager,
        body={"procedure_id": str(procedure), "sheet_definition_ref": "bh_fs_430"},
    )
    sheet_id = made.json()["sheet_id"]
    sample_set = await _sample(seed, granite, item, manager)
    rows = await net.call(
        "POST",
        f"/v1/sheets/{sheet_id}/rows/from-sample",
        manager,
        body={"sample_set_id": str(sample_set)},
        headers=net.keyed(),
    )
    fifth = rows.json()["items"][4]
    row_id = fifth["row_id"]
    edited = await net.call(
        "PATCH",
        f"/v1/sheets/{sheet_id}/rows/{row_id}",
        manager,
        body={"cells": {"result": "Exception"}, "version": fifth["version"]},
    )
    assert edited.status_code == 200, edited.text

    # Before the agent: the facts in column order, no reason, no links.
    plain = await net.call("GET", f"/v1/sheets/{sheet_id}/rows/{row_id}", manager)
    assert plain.status_code == 200, plain.text
    body = plain.json()
    assert body["row"]["key"] == fifth["key"]
    assert body["engagement_id"] == str(granite.engagement_id)
    assert [(f["label"], f["type"], f["value"]) for f in body["facts"]] == [
        ("Vendor", "text", "Vendor 5"),
        ("Amount", "currency", "136000.00"),
        ("Result", "single_select", "Exception"),
    ]
    assert body["why"] == [] and body["links"] == []

    # The agent's suggestion behind the cell (from a live, non-shadow run: ED-171), and one
    # evidence link.
    run = uuid.uuid4()
    await seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, state, mode, trigger_kind, run_number) VALUES "
        "($1, $2, 'engagements.run', 1, $3, $4, ARRAY['engagement.read'], 'queued', 'run', "
        "'engagement_plan', 9022)",
        run,
        tenant,
        granite.engagement_id,
        manager.user_id,
    )
    suggestion = await seed.value(
        "INSERT INTO suggestions (tenant_id, engagement_id, target_type, target_id, field_key, "
        "proposed_value, agent_run_id) VALUES ($1, $2, 'sheet_row', $3, 'result', "
        '\'{"t": "text", "v": "Exception"}\', $4) RETURNING id',
        tenant,
        granite.engagement_id,
        uuid.UUID(row_id),
        run,
    )
    await seed.run_untriggered(
        "UPDATE sheet_cells SET value_state = 'suggested', suggestion_id = $1 WHERE row_id = $2 "
        "AND column_id = (SELECT id FROM sheet_columns WHERE sheet_id = $3 AND column_key = "
        "'result')",
        suggestion,
        uuid.UUID(row_id),
        uuid.UUID(sheet_id),
    )
    target = uuid.uuid4()
    await seed.run_untriggered(
        "INSERT INTO sheet_row_links (tenant_id, engagement_id, work_item_id, sheet_id, row_id, "
        "kind, target_id, linked_by) VALUES ($1, $2, $3, $4, $5, 'evidence', $6, $7)",
        tenant,
        granite.engagement_id,
        item,
        uuid.UUID(sheet_id),
        uuid.UUID(row_id),
        target,
        manager.user_id,
    )
    full = (await net.call("GET", f"/v1/sheets/{sheet_id}/rows/{row_id}", manager)).json()
    assert [
        (w["column_key"], w["suggestion_id"], w["status"], w["agent_run_id"]) for w in full["why"]
    ] == [("result", str(suggestion), "pending", str(run))]
    assert full["row"]["cells"]["result"]["state"] == "suggested"
    assert [(k["kind"], k["target_id"]) for k in full["links"]] == [("evidence", str(target))]

    # K-03-T23 (DEC-6034): the VM names its engagement, and threads open on the row (the drawer's
    # Comments tab) and on the sheet (SHT-02's "Suggest to <name>…"), labelled by code.
    vm = (await net.call("GET", f"/v1/sheets/{sheet_id}", manager)).json()
    assert vm["engagement_id"] == str(granite.engagement_id)
    for kind, anchor_id, words in (
        ("sheet_row", row_id, fifth["key"]),
        ("sheet", sheet_id, "Disbursements testing"),
    ):
        opened = await net.call(
            "POST",
            "/v1/comment-threads",
            manager,
            body={"anchor": {"anchor_kind": kind, "anchor_id": anchor_id}, "body": "Check this."},
        )
        assert opened.status_code == 201, opened.text
        assert words in str(opened.json())

    # Another sheet's row, and a person outside the walls.
    stranger = await net.call("GET", f"/v1/sheets/{sheet_id}/rows/{uuid.uuid4()}", manager)
    assert stranger.status_code == 404, stranger.text
    outsider = await seed.person(tenant)
    walled = await net.call("GET", f"/v1/sheets/{sheet_id}/rows/{row_id}", outsider)
    assert walled.status_code in (403, 404), walled.text
    hidden = await net.call(
        "POST",
        "/v1/comment-threads",
        outsider,
        body={"anchor": {"anchor_kind": "sheet_row", "anchor_id": row_id}, "body": "x"},
    )
    assert hidden.status_code in (403, 404), hidden.text
