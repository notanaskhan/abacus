"""P-11-T03 (SPEC-520 AC-31; `docs/contracts/c11-renderer.md`; ADR-320): every C11 route is in
the generated client, declares its one matrix action and answers 404 for a client principal, 404
with `reporting.generated_documents` off and 501 with it on; every field is classified; agent
principals are refused final renders, regeneration and template publication."""

from __future__ import annotations

import dataclasses
import inspect
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import cast

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import REPORTING_GENERATED_DOCUMENTS
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.kernel.uow import UnitOfWork
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.reporting import api as c11_api
from abacus.modules.reporting import contract as c11

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
Endpoint = Callable[..., Awaitable[object]]

ROUTES = [r for router in c11_api.ROUTERS for r in router.routes if isinstance(r, APIRoute)]
# P-11-T06 made the template routes live (`reporting/templates.py`; SPEC-520 AC-1 to AC-5); the
# rest stay stubs until P-11-T07 (preview) and T11 (generated documents).
LIVE = {
    "list_report_templates_route",
    "get_report_template_version_route",
    "import_report_template_route",
    "publish_report_template_route",
    "deprecate_report_template_route",  # T-01-T17 (C11 v1.1 additive)
}
STUBS = [r for r in ROUTES if r.name not in LIVE]
MODELS = [
    v
    for v in vars(c11).values()
    if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == c11.__name__
]
# C11 §2: every route the contract lists, by method and path.
CONTRACT_ROUTES = {
    ("get", "/v1/report-templates"),
    ("get", "/v1/report-templates/{template_id}/versions/{version_no}"),
    ("post", "/v1/report-templates/import"),
    ("post", "/v1/report-templates/{template_id}/versions/{version_no}/publish"),
    ("post", "/v1/report-templates/{template_id}/versions/{version_no}/deprecate"),  # T-01-T17
    ("post", "/v1/report-templates/{template_id}/versions/{version_no}/preview"),
    ("get", "/v1/generated-documents/{document_id}"),
    ("get", "/v1/generated-documents/{document_id}/versions/{version_no}/fields"),
    ("get", "/v1/generated-documents/{document_id}/versions/{version_no}/compare"),
    ("get", "/v1/generated-documents/{document_id}/changes"),
    ("post", "/v1/generated-documents/{document_id}/regenerate"),
}


def _ctx(*, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        None,
        None,
        client=client,
    )


def _call(endpoint: Endpoint, ctx: AuthContext) -> Awaitable[object]:
    params = inspect.signature(endpoint).parameters
    return endpoint(**{n: (ctx if n == "ctx" else None) for n in params})


def test_ac31_the_generated_api_carries_every_c11_route() -> None:
    present = {
        (m, p)
        for p, ops in PATHS.items()
        for m in ops
        if p.startswith(("/v1/report-templates", "/v1/generated-documents"))
    }
    assert present == CONTRACT_ROUTES


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: r.name)
def test_ac31_each_route_declares_one_matrix_action_and_stubs_answer_501(
    route: APIRoute,
) -> None:
    method = next(iter(route.methods or {"GET"})).lower()
    op = PATHS[route.path][method]
    assert op["x-abacus-action"] in c11.FIRM_ACTIONS
    assert op["x-abacus-action"] in RULES
    responses = set(cast(Json, op["responses"]))
    assert "404" in responses
    assert ("501" in responses) == (route.name not in LIVE)


@pytest.mark.parametrize("route", STUBS, ids=lambda r: r.name)
async def test_ac31_client_404_then_action_then_flag_then_501(
    route: APIRoute, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Flag] = []
    asked: list[str] = []
    state = {"on": False}

    async def flag_enabled(_tenant: object, f: Flag) -> bool:
        seen.append(f)
        return state["on"]

    async def authorise(_ctx: object, action: str, _resource: object) -> None:
        asked.append(action)

    monkeypatch.setattr(c11, "flag_enabled", flag_enabled)
    monkeypatch.setattr(c11, "authorise", authorise)
    endpoint = cast(Endpoint, route.endpoint)
    with pytest.raises(NotFound):
        await _call(endpoint, _ctx(client=True))
    assert (seen, asked) == ([], [])
    with pytest.raises(NotFound):
        await _call(endpoint, _ctx())
    method = next(iter(route.methods or {"GET"})).lower()
    assert asked == [PATHS[route.path][method]["x-abacus-action"]]
    assert seen == [REPORTING_GENERATED_DOCUMENTS]
    state["on"] = True
    with pytest.raises(NotImplementedYet):
        await _call(endpoint, _ctx())


@pytest.mark.parametrize("model", MODELS, ids=[m.__name__ for m in MODELS])
def test_adr031_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


@pytest.mark.parametrize(
    "action",
    ["generated_document.regenerate", "report_template.publish", "report_template.import"],
)
def test_ac31_the_agent_and_the_system_are_refused(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"


def test_ac3_publication_needs_a_fresh_second_factor_and_never_firm_admin() -> None:
    rule = RULES["report_template.publish"]
    assert rule.mfa_recent
    assert rule.decisions.get("firm_admin") == "deny"


@pytest.mark.parametrize("role", ["client_admin", "client_contributor", "third_party"])
def test_ac26_no_client_role_reaches_any_c11_action(role: str) -> None:
    for action in c11.FIRM_ACTIONS:
        assert RULES[action].decisions.get(role, "deny") == "deny", (action, role)


def _request(**changes: object) -> c11_api.RenderRequest:
    base = c11_api.RenderRequest(
        kind="engagement_letter",
        owner_ref=c11_api.OwnerRef("engagement_letter", uuid.uuid4()),
        scope=c11_api.RenderScope(uuid.uuid4(), uuid.uuid4()),
        template_version_id=uuid.uuid4(),
        requested_by=c11_api.Requester("human", user_id=uuid.uuid4()),
    )
    return dataclasses.replace(base, **changes)


def test_ac31_ac16_an_agent_never_asks_for_a_final_render() -> None:
    agent = c11_api.Requester("agent", run_id=uuid.uuid4(), on_behalf_of_user_id=uuid.uuid4())
    approval = c11_api.ApprovalRef("letter_approval", uuid.uuid4(), "0" * 64)
    with pytest.raises(c11_api.RenderRefused) as refused:
        c11_api.check_render_request(
            _request(requested_by=agent, mode="final", approval_ref=approval)
        )
    assert refused.value.code == "final_requires_approval"
    c11_api.check_render_request(_request(requested_by=agent))  # a draft is allowed


def test_ac16_an_agent_draft_names_its_run() -> None:
    with pytest.raises(c11_api.RenderRefused):
        c11_api.check_render_request(_request(requested_by=c11_api.Requester("agent")))


def test_ac15_a_final_render_needs_a_person_and_an_approval() -> None:
    with pytest.raises(c11_api.RenderRefused) as refused:
        c11_api.check_render_request(_request(mode="final"))
    assert refused.value.code == "final_requires_approval"
    system = c11_api.Requester("system")
    approval = c11_api.ApprovalRef("letter_approval", uuid.uuid4(), "0" * 64)
    with pytest.raises(c11_api.RenderRefused):
        c11_api.check_render_request(
            _request(requested_by=system, mode="final", approval_ref=approval)
        )
    c11_api.check_render_request(_request(mode="final", approval_ref=approval))


async def test_ac31_render_final_refuses_the_agent_before_any_work() -> None:
    agent = c11_api.Requester("agent", run_id=uuid.uuid4())
    approval = c11_api.ApprovalRef("letter_approval", uuid.uuid4(), "0" * 64)
    with pytest.raises(c11_api.RenderRefused):
        # P-11-T08: render_final runs in the caller's unit of work (C11 §2); the refusal comes
        # before the unit of work is touched.
        await c11_api.render_final(cast(UnitOfWork, None), uuid.uuid4(), approval, agent)
