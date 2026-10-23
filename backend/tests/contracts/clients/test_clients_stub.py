"""The clients family contract stub, v1 (P-07-T04; SPEC-321 AC-1 to AC-5): every route exists with
its one matrix action and answers 404 with `clients.v2` off and 501 with it on; no payload carries
a hidden-by-wall field or a TIN beyond the masked last four and the one reveal; the reveal is a
live person's act. The consumers' own tests are P-07-T06's."""

from __future__ import annotations

import ast
import json
import uuid
from pathlib import Path
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.kernel._flags import CLIENTS_V2
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.organisations import contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
ORGANISATIONS = Path(contract.__file__).parent

# (method, path) -> the one matrix action (P-07 §4.3).
ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/clients"): "client.read",
    ("get", "/v1/clients/{client_id}"): "client.read",
    ("get", "/v1/clients/{client_id}/overview"): "client.read",
    ("patch", "/v1/clients/{client_id}"): "client.update",
    ("get", "/v1/clients/{client_id}/relationships"): "client.read",
    ("post", "/v1/client-entities/{entity_id}/tin/reveal"): "tin.reveal",
}
FIRM_ROLES = {
    "firm_admin",
    "practice_leader",
    "quality_partner",
    "security_admin",
    "firm_partner",
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "reviewer",
    "eqr_reviewer",
    "specialist",
    "client_service",
}
CLIENT_ROLES = {"client_admin", "client_contributor"}


def _granted(action: str) -> set[str]:
    return {r for r, d in RULES[action].decisions.items() if d != "deny"}


# Live since P-07-T08 (the index) and P-07-T09 (record, overview, PATCH, relationships); the
# reveal stays a stub until P-07-T10.
STUBBED = {("post", "/v1/client-entities/{entity_id}/tin/reveal")}


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_ac1_each_route_declares_its_action_and_the_stub_answer(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    responses = set(cast(Json, op["responses"]))
    assert "404" in responses
    assert ("501" in responses) == ((method, path) in STUBBED)


def test_ac2_statuses_are_the_registry_enums() -> None:
    def ref(model: str, field: str) -> object:
        return cast(dict[str, Json], SCHEMAS[model]["properties"])[field].get("$ref")

    assert ref("ClientRowOut", "status") == "#/components/schemas/ClientStatus"
    assert ref("ClientRecordOut", "status") == "#/components/schemas/ClientStatus"
    assert ref("ClientStatusChangeIn", "status") == "#/components/schemas/ClientStatus"
    assert ref("ClientRowOut", "portal_status") == "#/components/schemas/InvitationStatus"


def test_ac2_the_list_row_carries_no_restricted_field_and_no_tin() -> None:
    props = cast(dict[str, Json], SCHEMAS["ClientRowOut"]["properties"])
    assert all(p.get("cls") != "restricted" for p in props.values())
    assert not {n for n in props if "tin" in n.split("_") or n in {"ssn", "ein", "itin"}}


def test_ac2_the_masked_tin_is_last_four_digits_and_restricted() -> None:
    props = cast(dict[str, Json], SCHEMAS["MaskedTinOut"]["properties"])
    assert set(props) == {"kind", "presence", "last4"}
    last4 = cast(list[Json], props["last4"]["anyOf"])
    assert {"type": "string", "pattern": "^[0-9]{4}$"} in last4
    assert props["last4"]["cls"] == "restricted"


def test_ac2_no_clients_model_has_a_wall_count() -> None:
    for name, schema in SCHEMAS.items():
        if name.startswith(("Client", "MaskedTin", "TinReveal", "ListPage_Client")):
            props = cast(dict[str, Json], schema.get("properties", {}))
            assert not {p for p in props if "wall" in p or "hidden" in p}, name


def test_ac3_client_read_is_every_firm_role_and_no_one_else() -> None:
    # P-07-T08 (DEC-141): a partner with no firm role reads through the derived `firm_partner`.
    assert _granted("client.read") == FIRM_ROLES
    rule = RULES["client.read"]
    assert rule.decisions["agent"] == rule.decisions["system"] == "deny"


def test_ac3_client_update_is_firm_admin_and_partners_never_the_agent() -> None:
    assert _granted("client.update") == {"firm_admin", "firm_partner"}
    assert RULES["client.update"].decisions["agent"] == "deny"
    assert RULES["client.update"].decisions["system"] == "deny"


def test_ac3_tin_reveal_is_a_live_person_with_mfa_and_a_reason() -> None:
    rule = RULES["tin.reveal"]
    assert _granted("tin.reveal") == {"engagement_partner", "manager", "eqr_reviewer"}
    assert rule.decisions["agent"] == rule.decisions["system"] == "deny"
    assert rule.mfa_recent and rule.requires_reason  # `not_offshore` with the live route
    assert not _granted("tin.reveal") & CLIENT_ROLES


async def test_ac4_flag_off_is_404_and_flag_on_is_501(monkeypatch: pytest.MonkeyPatch) -> None:
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    seen: list[object] = []

    async def off(_tenant: object, flag: object) -> bool:
        seen.append(flag)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await contract._stub(ctx)  # pyright: ignore[reportPrivateUsage] -- the stub gate
    assert seen == [CLIENTS_V2]
    monkeypatch.setattr(contract, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await contract._stub(ctx)  # pyright: ignore[reportPrivateUsage] -- the stub gate


def test_ac5_organisations_never_imports_the_model_gateway_or_agents() -> None:
    forbidden = ("abacus.ai_gateway", "abacus.modules.agents")
    for path in ORGANISATIONS.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            assert not [n for n in names if n.startswith(forbidden)], path.name
