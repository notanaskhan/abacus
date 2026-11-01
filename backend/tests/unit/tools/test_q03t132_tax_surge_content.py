"""Q-03-T132: the tax-surge content's shape, without a database. Every x100 firm holds 5 to 15
returns, one in five a 1065; names fit the bridge's file-name rules; each K-1 set parses as the
engine's manifest and carries no full TIN."""

from __future__ import annotations

import json

from abacus.modules.tax.engine_adapter import parse_pdf
from abacus_tools.synthetic import fleet, fleet_tax


def test_every_firm_holds_5_to_15_returns_and_the_profiles_nest() -> None:
    counts = [fleet_tax.returns_per_firm(f) for f in fleet.plan("x100")]
    assert min(counts) == 5 and max(counts) == 15
    x25 = [fleet_tax.returns_per_firm(f) for f in fleet.plan("x25")]
    assert x25 == counts[:25]
    assert sum(x25) >= 25 * 5


def test_returns_use_clients_after_the_audits_and_fit_the_bridge_names() -> None:
    firm = fleet.plan("x1")[0]
    returns = fleet_tax.returns_of(firm)
    assert all(r.client >= firm.shape.audits for r in returns)
    assert firm.shape.clients >= firm.shape.audits + len(returns)
    for ret in returns:
        name = f"{ret.code}_{ret.engine_id}_V1_form_8879.pdf"
        assert parse_pdf(name, fleet_tax.engine_pdf(ret, "Form 8879")).kind == "form_8879"
    assert sum(r.partnership for r in returns) == len(returns) // 5


def test_a_k1_set_is_the_engines_manifest_without_a_full_tin() -> None:
    ret = next(r for r in fleet_tax.returns_of(fleet.plan("x1")[0]) if r.partnership)
    found = fleet_tax.k1_set(ret)
    manifest = json.loads(found.manifest())
    assert manifest["form"] == "1065" and manifest["is_final"] is False
    assert len(manifest["recipients"]) == fleet_tax.RECIPIENTS
    for recipient in manifest["recipients"]:
        assert len(recipient["tin_last4"]) == 4
        assert parse_pdf(recipient["documents"][0]["file_name"], b"%PDF-1.7\n%%EOF").kind == "k1"


def test_a_shape_without_room_for_the_returns_loads_no_tax() -> None:
    small = fleet.FirmShape(
        seats=7, clients=4, audits=3, requests_per_audit=1, portal_people_per_audit=1
    )
    assert fleet_tax.has_room(fleet.plan("x1")[0])
    assert not fleet_tax.has_room(fleet.plan("x1", small)[0])
