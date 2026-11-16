"""W-01-T10 (SPEC-659 AC-1 to AC-5, OQ-2, OQ-4; DF-34 to DF-36; L10; DEC-89): the reviewed
catalogue content v1 (`abacus_tools/catalogue/connect_v2.yaml`).

62 rows: the canvas's 55 Connect tiles and the 7 portal-only client feeds. At E0 the workbench
lists 53 (Drata and Vanta publish Oct 1), 6 of them coming soon; the category totals are WB-10
a's; at E2 55 with GRC & Compliance 2. No auth line names a person (DF-34); a declared write
names a registry entry (OQ-4); the kit-sample lint (L10) and the payments boundary (DEC-89) hold.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml

from abacus.modules.integrations.catalog_import import CatalogDocumentV2, CatalogRowV2In
from abacus_tools import integration_catalog as ops
from abacus_tools.quality.seed_contamination import findings_in
from abacus_tools.synthetic.scenarios.brightwater_hale import connect_catalog as scenario

DOCUMENT = Path(ops.__file__).resolve().parent / "catalogue" / "connect_v2.yaml"
E0 = datetime.fromisoformat("2026-09-14T09:24:00-05:00")
E2 = datetime.fromisoformat("2026-10-01T09:24:00-05:00")


def _doc() -> CatalogDocumentV2:
    return CatalogDocumentV2.model_validate(yaml.safe_load(DOCUMENT.read_text(encoding="utf-8")))


def _bench(at: datetime) -> list[CatalogRowV2In]:
    return [
        r
        for r in _doc().rows
        if "workbench" in r.surfaces
        and r.listing_status != "hidden"
        and r.published_at is not None
        and r.published_at <= at
    ]


def test_the_document_holds_62_rows_55_tiles_and_7_portal_feeds() -> None:
    rows = _doc().rows
    assert len(rows) == 62
    assert sum("workbench" in r.surfaces for r in rows) == 55
    portal_only = sorted(r.key for r in rows if r.surfaces == ["portal"])
    assert portal_only == sorted(
        [
            "american_express",
            "bamboohr",
            "front_range_bank",
            "jira",
            "payroll_provider",
            "shopify",
            "square",
        ]
    )


def test_ac1_ac3_e0_lists_53_with_6_coming_soon_and_e2_55() -> None:
    e0 = _bench(E0)
    assert len(e0) == 53 and sum(r.listing_status == "coming_soon" for r in e0) == 6
    assert len(_bench(E2)) == 55


def test_ac2_the_category_totals_are_wb10_as() -> None:
    tags = Counter(c for r in _bench(E0) for c in r.categories)
    assert dict(tags) == {
        "tax": 8,
        "practice": 5,
        "erp": 8,
        "docs": 13,
        "comms": 8,
        "prod": 12,
        "crm": 3,
        "hris": 3,
        "spend": 5,
    }
    assert Counter(c for r in _bench(E2) for c in r.categories)["grc"] == 2


def test_the_canvas_list_and_order_win() -> None:
    names = [r.name for r in _doc().rows if "workbench" in r.surfaces]
    assert names == [str(r["name"]) for r in scenario.rows(E2)]


def test_df34_no_auth_line_names_a_person_and_oq4_writes_are_registered() -> None:
    rows = _doc().rows
    assert not [r.key for r in rows if r.auth_line and "added by" in r.auth_line]
    assert {r.key: r.writes for r in rows if r.writes} == {"cch": ["tax_engine_file_bridge"]}


def test_l10_dec89_no_kit_sample_text_and_no_payment_copy() -> None:
    text = DOCUMENT.read_text(encoding="utf-8")
    assert list(findings_in(text)) == []
    for word in ("Stripe Checkout", "pay now", "pricing", "free trial", "credit card on file"):
        assert word.lower() not in text.lower()


def test_personal_tiles_carry_their_consent_and_firm_apps_their_provider() -> None:
    for row in _doc().rows:
        if row.ownership_mode == "personal":
            assert row.consent_copy is not None and row.consent_version == 1, row.key
        if row.ownership_mode == "client_authorised":
            assert row.connector_provider == row.key, row.key


def test_workstream_names_its_prerequisite_scope() -> None:
    row = next(r for r in _doc().rows if r.key == "workstream")
    assert row.prerequisite is not None
    assert (row.prerequisite.key, row.prerequisite.scope) == ("cch", "workstream")
