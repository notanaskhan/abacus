"""W-02-T05 (TASK-7606; `docs/contracts/workbench-sessions.md`; SPEC-653): the consumer suite for
the workbench-sessions family, written from the contract. It runs in the provider's CI.

It asserts the routes on the wire (one action each, 501 until their rows), that every field an
artboard reads is in the schema (removing one fails here), that every field is classified, that no
schema names or counts a hidden or walled row (DEC-43), that the agent, the system, support and
every portal principal are refused (INV-1, INV-4), and that the matrix refuses before
`workbench.enabled` is read and the flag off is 404."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import WORKBENCH_ENABLED
from abacus.kernel.classification import level_of, unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import Flag
from abacus.modules.agents import run_artifacts_contract
from abacus.modules.identity.api import RULES, AuthContext
from abacus.modules.workbench import list_contract, sessions_contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])

S = "/v1/workbench/sessions"
ROUTES: list[tuple[str, str, str]] = [
    ("get", S, "session.read"),
    ("post", S, "session.create"),
    ("patch", f"{S}/{{session_id}}", "session.manage"),
    ("delete", f"{S}/{{session_id}}", "session.manage"),
    ("get", "/v1/workbench/context-options", "session.create"),
    ("post", f"{S}/{{session_id}}/context", "session.manage"),
    ("delete", f"{S}/{{session_id}}/context/{{item_id}}", "session.manage"),
    ("post", f"{S}/{{session_id}}/drill", "session.manage"),
    ("get", "/v1/run-artifacts/{artifact_id}/preview", "run_content.read"),
    ("get", "/v1/run-artifacts/{artifact_id}/download", "run_artifact.download"),
]
# Served by W-02-T09 (list, create, rename, delete), T10 (context) and T20 (drill, preview,
# download); each row empties its entries and flips the 501 assertion with it.
UNBUILT = {(m, p) for m, p, _ in ROUTES}

# What each artboard reads (W-02 §2.1). Removing any of these fields fails this suite.
ARTBOARD_FIELDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "WB-01 a (rows, amber dot)": (
        "SessionSummaryOut",
        ("id", "title", "state", "last_item_at", "owner", "needs_answer"),
    ),
    "WB-01 a (via Agent meta)": ("SessionOwnerOut", ("name", "via_agent")),
    "WB-01 c (Running 3)": ("SessionListCountsOut", ("running", "needs_answer")),
    "WB-01 c (spinner rows)": ("SessionSummaryOut", ("running", "agent_label", "origin")),
    "WB-01 d (Ready for review)": ("SessionSummaryOut", ("ready_for_review",)),
    "WB-01 f (no results)": ("SessionListOut", ("items", "total", "counts", "next_cursor")),
    "WB-01 g (locked)": ("SessionSummaryOut", ("locked",)),
    "WB-01 rename": ("SessionSummaryOut", ("title_source", "version")),
    "WB-02 b (picker rows)": (
        "ContextOptionOut",
        ("kind", "ref_id", "title", "detail", "attached"),
    ),
    "WB-02 b (picker tab)": ("ContextOptionsOut", ("tab", "items")),
    "WB-02 c/d (stack and chips)": (
        "ContextItemOut",
        ("id", "kind", "ref_id", "card_title", "chip_label", "summary_lines"),
    ),
    "WB-02 a/f (firm-wide chip)": ("ContextItemsOut", ("session_id", "firm_wide", "items")),
    "WB-03 d (drill)": ("DrillOut", ("item_id", "group_key", "title", "total", "rows")),
    "WB-03 d (drill rows)": ("DrillRowOut", ("ref_type", "ref_id", "label", "detail", "href")),
    "WB-03 d2 (O4 preview)": (
        "ArtifactPreviewOut",
        ("artifact_id", "file_name", "sheets", "sheet", "columns", "rows", "footnote", "sha256"),
    ),
    "WB-03 d2 (cells)": ("PreviewCellOut", ("value", "kind", "bold")),
}

MODELS: list[type[BaseModel]] = [
    v
    for mod in (list_contract, sessions_contract, run_artifacts_contract)
    for v in vars(mod).values()
    if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == mod.__name__
]
REFUSED = (
    "agent",
    "system",
    "platform_support",
    "platform_support_content",
    "client_admin",
    "client_contributor",
    "third_party",
)


@pytest.mark.parametrize(("method", "path", "action"), ROUTES)
def test_every_route_declares_its_action_and_is_a_stub_until_built(
    method: str, path: str, action: str
) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == action
    assert ("501" in cast(Json, op["responses"])) is ((method, path) in UNBUILT)


@pytest.mark.parametrize("artboard", sorted(ARTBOARD_FIELDS))
def test_every_field_an_artboard_reads_is_on_the_wire(artboard: str) -> None:
    schema, fields = ARTBOARD_FIELDS[artboard]
    properties = cast(Json, SCHEMAS[schema].get("properties", {}))
    missing = [f for f in fields if f not in properties]
    assert missing == [], (artboard, missing)


def test_the_list_query_carries_filter_q_and_cursor_and_keeps_subject_ref() -> None:
    params = {str(p["name"]) for p in cast(list[Json], PATHS[S]["get"]["parameters"])}
    assert {"filter", "q", "cursor", "subject_ref"} <= params


def test_filters_are_the_five_menu_items() -> None:
    params = cast(list[Json], PATHS[S]["get"]["parameters"])
    schema = json.dumps(next(p for p in params if p["name"] == "filter"))
    for code in ("all", "mine", "via_agent", "running", "needs_answer"):
        assert f'"{code}"' in schema


def test_rename_needs_if_match() -> None:
    params = cast(list[Json], PATHS[f"{S}/{{session_id}}"]["patch"]["parameters"])
    header = next(p for p in params if p["name"] == "If-Match")
    assert header["in"] == "header" and header["required"] is True


def test_no_schema_names_or_counts_a_hidden_or_walled_row() -> None:
    names = {m.__name__ for m in MODELS}
    for name in names & set(SCHEMAS):
        for field in cast(Json, SCHEMAS[name].get("properties", {})):
            assert "hidden" not in field and "wall" not in field, (name, field)


def test_every_field_is_classified_and_titles_are_confidential() -> None:
    assert MODELS
    for model in MODELS:
        assert unclassified_fields(model) == [], model.__name__
    for model, field in (
        (sessions_contract.SessionSummaryOut, "title"),
        (list_contract.SessionRenameIn, "title"),
        (list_contract.ContextItemOut, "summary_lines"),
        (list_contract.ContextOptionOut, "title"),
        (run_artifacts_contract.PreviewCellOut, "value"),
    ):
        assert level_of(model.model_fields[field]) == "confidential", (model.__name__, field)


@pytest.mark.parametrize("action", sorted({a for _, _, a in ROUTES}))
def test_agent_system_support_and_portal_are_refused(action: str) -> None:
    decisions = RULES[action].decisions
    for role in REFUSED:
        assert decisions.get(role) != "allow", (action, role)


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        cast(Any, "manager"),
        None,
    )


@pytest.mark.parametrize("on", [False, True])
def test_the_flag_off_is_404_and_on_lets_the_request_through(
    monkeypatch: pytest.MonkeyPatch, on: bool
) -> None:
    import abacus.kernel.flags as flags

    async def enabled(_tenant: object, flag: Flag) -> bool:
        assert flag is WORKBENCH_ENABLED
        return on

    monkeypatch.setattr(flags, "flag_enabled", enabled)
    if on:
        assert asyncio.run(sessions_contract.workbench_gate(_ctx())) is None
    else:
        with pytest.raises(NotFound):
            asyncio.run(sessions_contract.workbench_gate(_ctx()))
