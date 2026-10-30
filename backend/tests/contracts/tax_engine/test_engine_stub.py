"""T-01-T02 (TASK-2106; SPEC-501 AC-5 to AC-8): the engine-bridge and e-file-record stubs on the
wire and in the matrix (`docs/contracts/tax-engine-bridge.md`, `efile-record.md`).

Every route declares its action and is a stub; every write denies the agent and the system and is
never in an agent's task scope; nothing names a transmission to the IRS (R-04); the TRI fields are
tagged; the red files are named in the tax module's seam note."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import unclassified_fields
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.integrations import engine_settings_contract
from abacus.modules.tax import engine_contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
ROOT = Path(__file__).resolve().parents[4]
WRITES = (
    "tax_return.approve",
    "tax_return.export",
    "engine_import.create",
    "engine_import.approve",
    "delivery_packet.prepare",
    "delivery_packet.approve",
    "transmission.record",
    "efile_ack.record",
    "deliverable.publish",
    "integration.configure",
    "integration.test",
    "member.set_ero",
)
# T-01-T20 built ADM-08's settings, mappings and format check.
SETTINGS_LIVE = [
    ("get", "/v1/firm/integrations/{key}/settings", "integration.read"),
    ("put", "/v1/firm/integrations/{key}/settings", "integration.configure"),
    ("put", "/v1/firm/integrations/{key}/user-mapping", "integration.configure"),
    ("put", "/v1/firm/integrations/{key}/office-mapping", "integration.configure"),
    ("put", "/v1/firm/integrations/{key}/status-mirror", "integration.configure"),
    ("post", "/v1/firm/integrations/{key}/test", "integration.test"),
]
ROUTES = [
    ("get", "/v1/tax-returns/{return_id}/final-approval", "tax_return.read"),
    ("post", "/v1/tax-returns/{return_id}/final-approval", "tax_return.approve"),
    ("get", "/v1/tax-returns/{return_id}/engine-sync", "tax_return.read"),
    ("post", "/v1/tax-returns/{return_id}/engine-exports", "tax_return.export"),
    ("get", "/v1/engine-exports/{export_id}/file", "tax_return.export"),
    ("post", "/v1/engine-exports/{export_id}/mark-exported", "tax_return.export"),
    ("post", "/v1/tax-returns/{return_id}/engine-imports", "engine_import.create"),
    ("get", "/v1/engine-imports/{import_id}", "tax_return.read"),
    ("post", "/v1/engine-imports/{import_id}/approve", "engine_import.approve"),
    ("post", "/v1/engine-imports/{import_id}/reject", "engine_import.approve"),
    ("get", "/v1/tax-returns/{return_id}/delivery", "tax_return.read"),
    ("post", "/v1/tax-returns/{return_id}/delivery-packet:assemble", "delivery_packet.prepare"),
    ("patch", "/v1/delivery-packets/{packet_id}", "delivery_packet.prepare"),
    ("post", "/v1/delivery-packets/{packet_id}/letter:regenerate", "delivery_packet.prepare"),
    ("post", "/v1/delivery-packets/{packet_id}/approve", "delivery_packet.approve"),
    ("post", "/v1/tax-returns/{return_id}/efile-envelope", "delivery_packet.prepare"),
    ("post", "/v1/tax-returns/{return_id}/ero-notices", "delivery_packet.prepare"),
    ("post", "/v1/tax-returns/{return_id}/transmissions", "transmission.record"),
    ("post", "/v1/tax-returns/{return_id}/acks", "efile_ack.record"),
    ("post", "/v1/tax-returns/{return_id}/deliverables:publish", "deliverable.publish"),
    ("put", "/v1/firm/members/{user_id}/ero", "member.set_ero"),
]


@pytest.mark.parametrize(("method", "path", "action"), ROUTES)
def test_ac5_every_route_declares_its_action_and_is_a_stub(
    method: str, path: str, action: str
) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == action
    assert "501" in cast(Json, op["responses"])


@pytest.mark.parametrize(("method", "path", "action"), SETTINGS_LIVE)
def test_t01t20_the_settings_routes_are_live(method: str, path: str, action: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == action
    assert "501" not in cast(Json, op["responses"])


@pytest.mark.parametrize("action", WRITES)
def test_ac6_no_agent_or_system_holds_a_write(action: str) -> None:
    decisions = RULES[action].decisions
    for principal in ("agent", "system", "client_admin", "client_contributor", "third_party"):
        assert decisions.get(principal, "deny") == "deny", (action, principal)


def test_ac6_final_approval_and_the_transmission_record_are_the_signers() -> None:
    assert "signer" in RULES["tax_return.approve"].function_in
    assert "signer" in RULES["transmission.record"].function_in


def test_ac7_nothing_names_a_transmission_to_the_irs() -> None:
    text = json.dumps({p: v for p, v in PATHS.items() if "tax-returns" in p or "engine" in p})
    for banned in ("MeF", "A2A", "ETIN", "EFIN", "irs.gov", "TCC"):
        assert re.search(rf"\b{re.escape(banned)}\b", text) is None, banned


def test_ac7_figures_and_engine_messages_are_tri() -> None:
    models: list[type[BaseModel]] = [
        v
        for module in (engine_contract, engine_settings_contract)
        for v in vars(module).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == module.__name__
    ]
    for model in models:
        assert unclassified_fields(model) == [], model.__name__
    for model in (engine_contract.ImportDiffRowOut, engine_contract.EngineDiagnosticOut):
        assert '"x-tri": true' in json.dumps(model.model_json_schema()), model.__name__


def test_ac8_the_contract_docs_and_the_seam_note_exist() -> None:
    assert (ROOT / "docs/contracts/tax-engine-bridge.md").is_file()
    assert (ROOT / "docs/contracts/efile-record.md").is_file()
    readme = (ROOT / "backend/src/abacus/modules/tax/README.md").read_text()
    for red in ("approval.py", "export.py", "filing.py", "tri.py"):
        assert red in readme, red
