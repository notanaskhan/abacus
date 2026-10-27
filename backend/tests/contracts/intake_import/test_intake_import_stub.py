"""The intake and import contract stubs, v1 (P-07-T37; `docs/contracts/intake-import.md`;
DEC-374): every route exists with its one matrix action and answers 404 with `clients.v2` off
(they answered 501 with it on until P-07-T42 and P-07-T52 made them live); commit and run
require an `Idempotency-Key`;
the agent and the system are refused before the flag is read; no client role holds an action;
no schema carries a plain TIN, a hidden-by-wall field or a walled count. The consumer suite is
P-07-T45's."""

from __future__ import annotations

import json
import uuid
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.kernel._flags import CLIENTS_V2
from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import ActorKind
from abacus.kernel.errors import NotFound
from abacus.modules.engagements import intake_contract
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
DRAFTS = "/v1/client-intake-drafts"
IMPORTS = "/v1/client-imports"

ROUTES: dict[tuple[str, str], str] = {
    ("post", "/v1/clients/dedupe"): "client.create",
    ("post", DRAFTS): "client.intake",
    ("get", f"{DRAFTS}/{{draft_id}}"): "client.intake",
    ("patch", f"{DRAFTS}/{{draft_id}}"): "client.intake",
    ("delete", f"{DRAFTS}/{{draft_id}}"): "client.intake",
    ("post", f"{DRAFTS}/{{draft_id}}/validate"): "client.intake",
    ("post", f"{DRAFTS}/{{draft_id}}/commit"): "client.intake",
    ("post", IMPORTS): "client_import.run",
    ("get", f"{IMPORTS}/{{import_id}}"): "client_import.run",
    ("get", f"{IMPORTS}/{{import_id}}/rows"): "client_import.run",
    ("put", f"{IMPORTS}/{{import_id}}/rows/{{row_id}}/decision"): "client_import.run",
    ("post", f"{IMPORTS}/{{import_id}}/run"): "client_import.run",
}
# P-07-T42 (TASK-1326): dedupe, the intake drafts and the commit are live; P-07-T52 (TASK-1503):
# the imports too. No route answers 501 any more.
LIVE = {path for (_, path) in ROUTES}
IDEMPOTENT = {f"{DRAFTS}/{{draft_id}}/commit", f"{IMPORTS}/{{import_id}}/run"}
PREFIXES = (
    "Dedupe",
    "Intake",
    "ClientIntake",
    "ClientImport",
    "ImportRow",
    "RowDecision",
)
CLIENT_ROLES = {"client_admin", "client_contributor"}


def _props(schema: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[schema].get("properties", {}))


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_action_and_the_stub_answer(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    responses = set(cast(Json, op["responses"]))
    assert "404" in responses
    assert ("501" in responses) is (path not in LIVE)


@pytest.mark.parametrize("path", sorted(IDEMPOTENT))
def test_commit_and_run_require_an_idempotency_key(path: str) -> None:
    params = cast(list[Json], PATHS[path]["post"].get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True


def test_run_answers_202_and_the_upload_takes_the_file_as_the_body() -> None:
    assert "202" in cast(Json, PATHS[f"{IMPORTS}/{{import_id}}/run"]["post"]["responses"])
    upload = PATHS[IMPORTS]["post"]
    names = {p["name"] for p in cast(list[Json], upload.get("parameters", []))}
    assert {"source", "filename"} <= names
    assert "multipart/form-data" not in json.dumps(upload.get("requestBody", {}))


def test_the_dedupe_name_is_in_the_body_never_the_url() -> None:
    op = PATHS["/v1/clients/dedupe"]["post"]
    assert not [p for p in cast(list[Json], op.get("parameters", [])) if p["name"] == "name"]
    assert "name" in _props("DedupeIn")


def test_no_schema_carries_a_plain_tin_or_a_wall_count() -> None:
    seen = 0
    for name, schema in SCHEMAS.items():
        if not name.startswith(PREFIXES):
            continue
        seen += 1
        props = cast(dict[str, Json], schema.get("properties", {}))
        assert all("cls" in p for p in props.values()), name
        assert not {p for p in props if "wall" in p or "hidden" in p}, name
        assert not {p for p in props if p in ("tin", "ssn", "ein", "itin")} - {"tin"}, name
    assert seen >= 15
    # A row's TIN is the masked shape and nothing more (DEC-141); dedupe takes no TIN at all.
    tin = json.dumps(_props("ClientImportRowOut")["tin"])
    assert "#/components/schemas/MaskedTinOut" in tin
    assert not {p for p in _props("DedupeIn") if "tin" in p or "ein" in p}
    assert set(_props("ClientImportCountsOut")) >= {"rows", "matched", "to_review", "new"}


@pytest.mark.parametrize("action", ["client.create", "client.intake", "client_import.run"])
def test_the_agent_and_the_system_are_denied_and_no_client_role_holds_it(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"
    granted = {r for r, d in rule.decisions.items() if d != "deny"}
    assert granted == {"firm_admin", "firm_partner", "firm_manager"}
    assert not granted & CLIENT_ROLES


def test_import_rows_mask_tins_for_an_offshore_reader() -> None:
    """AC9.4 (TASK-1207 review): the row routes pass through the one central mask."""
    import inspect

    for route in (
        intake_contract.client_import_rows_route,
        intake_contract.decide_import_row_route,
    ):
        assert "mask_tins_for(" in inspect.getsource(route)


def _ctx(kind: ActorKind = "human", *, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)), user, uuid.uuid4(), None, None, client=client
    )


async def test_authorise_first_then_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []

    async def authorised(_ctx: object, action: str, _resource: object) -> None:
        seen.append(action)

    async def off(_tenant: object, flag: object) -> bool:
        seen.append(flag)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(intake_contract, "authorise", authorised)
    monkeypatch.setattr(intake_contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await intake_contract._gate(_ctx(), "client.intake")  # pyright: ignore[reportPrivateUsage] -- the gate
    assert seen == ["client.intake", CLIENTS_V2]
    monkeypatch.setattr(intake_contract, "flag_enabled", on)
    await intake_contract._gate(_ctx(), "client_import.run")  # pyright: ignore[reportPrivateUsage] -- the gate
    assert seen == ["client.intake", CLIENTS_V2, "client_import.run"]


@pytest.mark.parametrize("who", ["agent", "system", "client"])
async def test_agent_system_and_client_are_refused_before_the_flag(
    monkeypatch: pytest.MonkeyPatch, who: str
) -> None:
    flags: list[object] = []

    async def flag(_tenant: object, f: object) -> bool:
        flags.append(f)
        return True

    monkeypatch.setattr(intake_contract, "flag_enabled", flag)
    ctx = _ctx("human", client=True) if who == "client" else _ctx(cast(ActorKind, who))
    with pytest.raises(Forbidden):
        await intake_contract._gate(ctx, "client.intake")  # pyright: ignore[reportPrivateUsage] -- the gate
    assert flags == []
