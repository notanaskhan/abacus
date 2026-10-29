"""N-01-T02 stubs and N-01-T03 consumer contract tests (`docs/contracts/firm-intake.md`,
`files-browser.md`; SPEC-380). Every route declares its one matrix action and answers 404 for the
wrong kind of principal, 404 with its flag off and 501 with it on; every field is classified;
every intake write is a person's (the agent and the system denied, INV-1); and the shapes carry
what R-01, T-02, I-01, P-11, N-02 and A-07 build against: client words, "Waiting n", folder
kinds and identifier-only flag facts."""

from __future__ import annotations

import inspect
import json
import typing
import uuid
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import Final, cast, get_args

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import FILES_BROWSER, INBOX_FIRM_INTAKE, PORTAL_INTAKE_UPLOAD
from abacus.kernel._statuses import (
    FileDocumentStatus,
    InboxItemStatus,
    InboxThreadStatus,
    PortalIntakeUploadStatus,
)
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.communications import intake_contract as inbox
from abacus.modules.evidence import files_contract as files
from abacus.modules.evidence import files_shapes
from abacus.modules.identity.api import AbacusRouter, AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.portal import intake_contract as portal

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])

ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/inbox/summary"): "inbox.read",
    ("get", "/v1/inbox/threads"): "inbox.read",
    ("get", "/v1/inbox/threads/{thread_id}"): "inbox.read",
    ("post", "/v1/inbox/intake"): "inbox.log_intake",
    ("post", "/v1/inbox/intake/{message_id}/files"): "inbox.log_intake",
    ("post", "/v1/inbox/threads/{thread_id}/match-client"): "inbox.match_sender",
    ("post", "/v1/inbox/threads/{thread_id}/ignore"): "inbox.triage",
    ("get", "/v1/inbox/attachments/{attachment_id}/viewer"): "inbox.read_content",
    ("get", "/v1/inbox/attachments/{attachment_id}/content"): "inbox.download",
    ("get", "/v1/inbox/messages/{message_id}/attachments.zip"): "inbox.download",
    ("get", "/v1/inbox/messages/{message_id}/triage"): "inbox.triage",
    ("post", "/v1/inbox/messages/{message_id}/triage/apply"): "inbox.file",
    ("post", "/v1/inbox/attachments/bulk-file"): "inbox.file",
    ("get", "/v1/destinations"): "inbox.triage",
    ("post", "/v1/portal/intake-uploads"): "portal_intake.upload",
    ("post", "/v1/portal/intake-uploads/{upload_id}/files"): "portal_intake.upload",
    ("get", "/v1/portal/intake-uploads"): "portal_intake.read_own",
    ("post", "/v1/portal/intake-uploads/{upload_id}/withdraw"): "portal_intake.withdraw",
    ("get", "/v1/files/tree"): "evidence.read_metadata",
    ("get", "/v1/files/folders/{folder_ref}/items"): "evidence.read_metadata",
    ("get", "/v1/evidence-items/{item_id}/drawer"): "evidence.read_metadata",
    ("get", "/v1/evidence-items/{item_id}/access-log"): "evidence.read_access_log",
}
# The firm-intake writes no agent or system may hold (SPEC-380 §9; I-AGENT-NEVER).
HUMAN_ONLY = (
    "inbox.file",
    "inbox.triage",
    "inbox.match_sender",
    "inbox.ask_client",
    "inbox.log_intake",
    "inbox_sender_rule.create",
)

Endpoint = Callable[..., Awaitable[object]]


def _endpoints(module: ModuleType, *routers: AbacusRouter) -> list[tuple[str, Endpoint]]:
    out: list[tuple[str, Endpoint]] = []
    for router in routers:
        for route in router.routes:
            assert isinstance(route, APIRoute)
            out.append((route.path, cast(Endpoint, route.endpoint)))
    assert out, module.__name__
    return out


FIRM: list[tuple[str, Endpoint, Flag, ModuleType]] = [
    (p, e, INBOX_FIRM_INTAKE, inbox)
    for p, e in _endpoints(inbox, inbox.intake_router, inbox.destinations_router)
] + [(p, e, FILES_BROWSER, files) for p, e in _endpoints(files, files.files_router)]
PORTAL: list[tuple[str, Endpoint]] = _endpoints(portal, portal.intake_router)
# Live since N-01-T09 (staff-logged intake; DEC-821): their own codes, never 501.
LIVE_PATHS = frozenset(
    {
        "/v1/inbox/intake",
        "/v1/inbox/intake/{message_id}/files",
        # N-01-T13 (DEC-1059): the read APIs, match-client and ignore.
        "/v1/inbox/summary",
        "/v1/inbox/threads",
        "/v1/inbox/threads/{thread_id}",
        "/v1/inbox/threads/{thread_id}/match-client",
        "/v1/inbox/threads/{thread_id}/ignore",
        "/v1/inbox/attachments/{attachment_id}/viewer",
        "/v1/inbox/attachments/{attachment_id}/content",
        "/v1/inbox/messages/{message_id}/attachments.zip",
        # N-01-T14 (DEC-1060): portal intake.
        "/v1/portal/intake-uploads",
        "/v1/portal/intake-uploads/{upload_id}/files",
        "/v1/portal/intake-uploads/{upload_id}/withdraw",
    }
)
STUBBED = [f for f in FIRM if f[0] not in LIVE_PATHS]


def _models(module: ModuleType) -> list[type[BaseModel]]:
    return [
        v
        for v in vars(module).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == module.__name__
    ]


# N-01-T19 moved the Files shapes beside the routes into `files_shapes`.
MODELS = _models(inbox) + _models(portal) + _models(files_shapes)
# Live with the flag on (no longer 501): N-01-T19 serves the Files routes
# (tests/integration/backfill/test_n01t19_files.py; DEC-1051).
LIVE: Final = frozenset({e.__name__ for _p, e in _endpoints(files, files.files_router)})


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


@pytest.mark.parametrize(("method", "path"), sorted(k for k in ROUTES if k[1] not in LIVE_PATHS))
def test_n01t02_each_route_declares_its_one_action_and_is_a_stub(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


def test_n01t02_the_endpoints_are_the_routes_above() -> None:
    assert len(FIRM) + len(PORTAL) == len(ROUTES)


@pytest.mark.parametrize(
    ("path", "endpoint", "flag", "module"),
    STUBBED,
    ids=[e.__name__ for _p, e, _f, _m in STUBBED],
)
async def test_n01t02_firm_routes_client_404_then_action_then_flag_then_501(
    path: str,
    endpoint: Endpoint,
    flag: Flag,
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Flag] = []
    asked: list[str] = []
    state = {"on": False}

    async def flag_enabled(_tenant: object, f: Flag) -> bool:
        seen.append(f)
        return state["on"]

    async def authorise(_ctx: object, action: str, _resource: object) -> None:
        asked.append(action)

    monkeypatch.setattr(module, "flag_enabled", flag_enabled)
    monkeypatch.setattr(module, "authorise", authorise)
    with pytest.raises(NotFound):
        await _call(endpoint, _ctx(client=True))
    assert (seen, asked) == ([], [])
    with pytest.raises(NotFound):
        await _call(endpoint, _ctx())
    assert seen == [flag] and len(asked) == 1
    if endpoint.__name__ in LIVE:
        return  # served with the flag on; its integration tests cover the answers
    state["on"] = True
    with pytest.raises(NotImplementedYet):
        await _call(endpoint, _ctx())


PORTAL_STUBBED = [f for f in PORTAL if f[0] not in LIVE_PATHS]


@pytest.mark.parametrize(
    ("path", "endpoint"), PORTAL_STUBBED, ids=[e.__name__ for _p, e in PORTAL_STUBBED]
)
async def test_n01t02_portal_routes_firm_404_then_flag_then_501(
    path: str, endpoint: Endpoint, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Flag] = []
    state = {"on": False}

    async def flag_enabled(_tenant: object, f: Flag) -> bool:
        seen.append(f)
        return state["on"]

    monkeypatch.setattr(portal, "flag_enabled", flag_enabled)
    with pytest.raises(NotFound):
        await _call(endpoint, _ctx())
    assert seen == []
    with pytest.raises(NotFound):
        await _call(endpoint, _ctx(client=True))
    assert seen == [PORTAL_INTAKE_UPLOAD]
    state["on"] = True
    with pytest.raises(NotImplementedYet):
        await _call(endpoint, _ctx(client=True))


@pytest.mark.parametrize("model", MODELS, ids=[m.__name__ for m in MODELS])
def test_adr031_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


@pytest.mark.parametrize("action", HUMAN_ONLY)
def test_inv1_intake_writes_deny_the_agent_and_the_system(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"


@pytest.mark.parametrize(
    "action", ["portal_intake.upload", "portal_intake.read_own", "portal_intake.withdraw"]
)
def test_inv4_portal_intake_is_scope_only_and_never_third_parties(action: str) -> None:
    rule = RULES[action]
    assert rule.scope_only
    assert "third_party" not in rule.decisions
    assert rule.decisions.get("agent") == "deny"


def test_dv11_metadata_is_not_content_for_client_principals_and_agents() -> None:
    rule = RULES["evidence.read_metadata"]
    for role in ("client_admin", "client_contributor", "agent", "system"):
        assert rule.decisions.get(role) == "deny", role


# --- Consumers (N-01-T03) ------------------------------------------------------------------------


def test_r01_portal_upload_reads_in_client_words() -> None:
    """R-01 POR-03: Sent · Received by {firm} · Withdrawn; never an internal state."""
    assert {s.value for s in PortalIntakeUploadStatus} == {"sent", "received", "withdrawn"}
    assert portal.IntakeUploadOut.model_fields["status"].annotation is not None
    assert "note" in portal.IntakeUploadIn.model_fields


def test_t02_i01_waiting_counts_are_integers_from_the_summary() -> None:
    """T-02 TAX-03 "Waiting n" and I-01's `inbox_waiting` count read `waiting`."""
    fields = inbox.InboxSummaryOut.model_fields
    assert {"waiting", "unmatched", "by_source"} <= set(fields)
    assert fields["waiting"].annotation is int
    assert inbox.InboxThreadRow.model_fields["waiting"].annotation is int


def test_inbox_item_codes_cover_the_six_states() -> None:
    assert {s.value for s in InboxItemStatus} == {
        "new",
        "waiting",
        "filed",
        "ignored",
        "held",
        "withdrawn",
    }
    assert {s.value for s in InboxThreadStatus} == {"unmatched", "matched", "ignored"}


def test_a07_n02_folder_kinds_are_the_five_files_folders() -> None:
    kinds = {
        "source_documents",
        "workpapers",
        "correspondence",
        "deliverables",
        "signed_authorizations",
    }
    assert set(get_args(files.FolderKind)) == kinds
    assert set(get_args(inbox.FolderKind)) == kinds


def test_p11_flag_facts_are_identifiers_only_and_classifications_mask_the_tin() -> None:
    facts = inbox.AttachmentFlagOut.model_fields["facts"].annotation
    assert typing.get_origin(facts) is dict
    assert "taxpayer_tin" in inbox.ClassificationOut.model_fields
    assert not any(
        "tin" in f and f != "taxpayer_tin" and "matches" not in f
        for f in inbox.ClassificationOut.model_fields
    )


def test_files_statuses_and_drawer_are_read_only() -> None:
    assert {s.value for s in FileDocumentStatus} == {
        "processing",
        "needs_review",
        "accepted",
        "superseded",
        "on_hold",
    }
    assert "allowed_actions" in files.DrawerOut.model_fields


@pytest.mark.parametrize(("method", "path"), sorted(k for k in ROUTES if k[1] in LIVE_PATHS))
def test_n01t09_the_live_intake_routes_declare_their_action_and_no_501(
    method: str, path: str
) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)] == "inbox.log_intake"
    assert "501" not in set(cast(Json, op["responses"]))
