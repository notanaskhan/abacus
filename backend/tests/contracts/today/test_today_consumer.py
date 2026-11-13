"""I-02-T05 (TASK-7613; `docs/contracts/today.md`; SPEC-654): the Today family's consumer suite,
written from the contract, in the providers' CI.

It asserts the six routes on the wire (one action each, 501 until their rows), that every field an
SHL-23 or HOME-05 artboard reads is in the schema, that every field is classified, that no count
field can be fed by model text (I-COUNT: the integer fields are typed integers and no blocks field
sits on a count model), that no schema names or counts a hidden or walled row (DEC-43), and that
client roles, support, the agent and the system are refused."""

from __future__ import annotations

import json
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import level_of, unclassified_fields
from abacus.modules.identity.api import RULES
from abacus.modules.practice.today import contract
from abacus.modules.workbench import today_questions_contract as questions

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])

T = "/v1/me/today"
ROUTES: list[tuple[str, str, str]] = [
    ("get", T, "briefing.read"),
    ("post", f"{T}/builds", "briefing.rebuild"),
    ("get", f"{T}/work-items/{{work_item_id}}", "briefing.read"),
    ("get", f"{T}/history", "briefing.read"),
    ("get", f"{T}/history/{{brief_id}}", "briefing.read"),
    ("post", f"{T}/questions", "briefing.ask"),
]
# Served by I-02-T10 (today, drill-in), T13 (builds), T16 (history), T14 (questions).
# S41 built the briefing reads (I-02); the rest stay stubs.
BUILT = {("get", "/v1/me/today"), ("get", "/v1/me/today/work-items/{work_item_id}")}
UNBUILT = {(m, p) for m, p, _ in ROUTES} - BUILT

ARTBOARD_FIELDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "SHL-23 1 / HOME-05 a (greeting, sub-line)": (
        "TodayVM",
        ("first_name", "items", "engagements", "brief_date", "built_at", "status"),
    ),
    "SHL-23 1 (cells)": ("CountCell", ("kind", "count", "href")),
    "SHL-23 1 (fact paragraph)": ("LeadFact", ("key", "values", "refs")),
    "SHL-23 1 (Needs you first)": (
        "GateRow",
        ("gate_id", "title", "due", "state", "deep_link", "context_line", "why_blocks", "folded"),
    ),
    "SHL-23 1 (due chips)": ("DueChip", ("due_on", "days", "tone")),
    "HOME-05 a (linked highlight)": ("GateRow", ("highlight_refs",)),
    "SHL-23 1, 4, 5 (groups)": ("Group", ("key", "count", "summary", "href", "items")),
    "SHL-23 1 (High risk card)": (
        "GroupItem",
        ("title", "detail", "detail_blocks", "pills", "deep_link", "assignable"),
    ),
    "SHL-23 4 (Running)": ("GroupItem", ("actor",)),
    "HOME-05 f (by_engagement)": ("TodayVM", ("layout", "cards")),
    "HOME-05 f (cards)": ("Card", ("label", "rows", "briefing_status", "summary_blocks")),
    "SHL-23 7 / HOME-05 e (building)": ("TodayVM", ("needs_build", "building_counts")),
    "DF-04 (unavailable)": (
        "Availability",
        ("narrative", "narrative_reason", "ask", "ask_reason"),
    ),
    "SHL-23 2 / HOME-05 b (drill-in)": (
        "DrillVM",
        ("title", "summary_blocks", "blockers", "downstream", "prefills", "not_assignable"),
    ),
    "HOME-05 b (selected rows)": ("DrillVM", ("select_refs", "open_href")),
    "SHL-23 2 (assign)": (
        "AssignPrefill",
        ("assignee_name", "title", "due_on", "anchor_label", "anchor_ref"),
    ),
    "SHL-23 2 (downstream)": ("DownstreamRow", ("title", "state_line", "deep_link")),
    "SHL-23 History": ("HistoryRow", ("brief_id", "brief_date", "built_at", "counts")),
    "SHL-23 3 (ask)": ("TodayQuestionAcceptedOut", ("session_id", "item_id")),
}
MODELS: list[type[BaseModel]] = [
    v
    for mod in (contract, questions)
    for v in vars(mod).values()
    if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == mod.__name__
]
REFUSED = (
    "client_admin",
    "client_contributor",
    "third_party",
    "platform_support",
    "platform_support_content",
    "agent",
    "system",
)
# The count-bearing models: none may hold a model-text (blocks) field (I-COUNT).
COUNT_MODELS = ("CountCell", "HistoryRow", "TodayBuildAcceptedOut")


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
    assert [f for f in fields if f not in properties] == [], artboard


@pytest.mark.parametrize("name", COUNT_MODELS)
def test_no_count_model_carries_model_text(name: str) -> None:
    for field in cast(Json, SCHEMAS[name].get("properties", {})):
        assert "blocks" not in field, (name, field)


def test_counts_are_integers_never_text() -> None:
    cell = cast(Json, cast(Json, SCHEMAS["CountCell"]["properties"])["count"])
    assert cell.get("type") == "integer" and cell.get("minimum") == 0
    for name, field in (("TodayVM", "items"), ("TodayVM", "engagements"), ("Group", "count")):
        prop = cast(Json, cast(Json, SCHEMAS[name]["properties"])[field])
        assert prop.get("type") == "integer", (name, field)


def test_no_schema_names_or_counts_a_hidden_or_walled_row() -> None:
    for model in MODELS:
        for field in model.model_fields:
            assert "hidden" not in field and "wall" not in field, (model.__name__, field)


def test_every_field_is_classified_and_question_text_is_restricted() -> None:
    assert MODELS
    for model in MODELS:
        assert unclassified_fields(model) == [], model.__name__
    assert level_of(questions.TodayQuestionIn.model_fields["text"]) == "restricted"
    assert level_of(contract.GateRow.model_fields["title"]) == "confidential"


@pytest.mark.parametrize("action", ["briefing.read", "briefing.rebuild", "briefing.ask"])
def test_client_support_agent_and_system_are_refused(action: str) -> None:
    decisions = RULES[action].decisions
    for role in REFUSED:
        assert decisions.get(role) != "allow", (action, role)


def test_a_question_is_at_most_1000_characters() -> None:
    text = cast(Json, cast(Json, SCHEMAS["TodayQuestionIn"]["properties"])["text"])
    assert text.get("maxLength") == 1000
