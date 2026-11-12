"""P-02-T01 (TASK-7504; C15 v1 stub): the registration fails closed, the contract carries no wall
signal and every field is classified, and the routes are declared with one action each."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from abacus.kernel.classification import unclassified_fields
from abacus.modules.platform.search import contract, spec
from abacus.modules.platform.search.routes import router


async def _build(tenant: object, object_id: object) -> None:
    del tenant, object_id


def _projection(**overrides: object) -> spec.SearchProjection:
    values: dict[str, object] = {
        "object_type": "p02_probe",
        "group": "clients",
        "read_action": "reference_set.read",
        "scope_kind": "firm",
        "build": _build,
        "target": "CLI-02",
    }
    values.update(overrides)
    return spec.SearchProjection(**values)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _clean_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spec, "_PROJECTIONS", {})


def test_ac1_registration_accepts_a_read_and_is_idempotent() -> None:
    spec.register_search_projection(_projection())
    spec.register_search_projection(_projection())  # a reloaded module: no-op
    assert spec.projection("p02_probe") is not None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"group": "actions"}, "unknown search group"),
        ({"scope_kind": "portal_scope"}, "unknown scope kind"),
        ({"read_action": "budget.manage"}, "not a read action"),
        ({"read_action": "nothing.read"}, "not in the permission matrix"),
        ({"target": "clients"}, "not a screen id"),
        ({"data_class": "restricted"}, "unknown data class"),
        ({"triggers": {"rename": lambda p: []}}, "not an event type"),
        ({"object_type": "Client"}, "snake_case"),
    ],
)
def test_ac1_registration_fails_closed(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(spec.SearchRegistrationInvalid, match=message):
        spec.register_search_projection(_projection(**overrides))


def test_ac1_a_different_projection_for_a_known_type_raises() -> None:
    spec.register_search_projection(_projection())

    async def other(tenant: object, object_id: object) -> None:
        del tenant, object_id

    with pytest.raises(spec.SearchRegistrationInvalid, match="already registered"):
        spec.register_search_projection(_projection(build=other))


def test_ac1_projections_list_in_canonical_group_order() -> None:
    spec.register_search_projection(_projection(object_type="b_todo", group="todos"))
    spec.register_search_projection(_projection(object_type="a_return", group="returns"))
    spec.register_search_projection(_projection(object_type="c_client", group="clients"))
    assert [p.group for p in spec.projections()] == ["clients", "returns", "todos"]


def test_ac1_documents_are_metadata_only() -> None:
    projection = _projection(scope_kind="client")
    doc = spec.SearchIndexDocument(
        object_id=uuid4(),
        title="Jonah & Claire Feld",
        source_updated_at=datetime(2026, 9, 14, tzinfo=UTC),
        target_params={"clientId": str(uuid4())},
        client_id=uuid4(),
    )
    spec.check_document(projection, doc)
    with pytest.raises(spec.SearchRegistrationInvalid, match="names a client"):
        spec.check_document(projection, doc.__class__(**{**doc.__dict__, "client_id": None}))
    with pytest.raises(spec.SearchRegistrationInvalid, match="identifiers only"):
        spec.check_document(
            projection, doc.__class__(**{**doc.__dict__, "target_params": {"q": "Jonah Feld"}})
        )
    with pytest.raises(spec.SearchRegistrationInvalid, match="title"):
        spec.check_document(projection, doc.__class__(**{**doc.__dict__, "title": "x" * 301}))


def test_ac1_v0_registrations_still_reach_the_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(spec.slots, "register_search_projection", lambda t, b: calls.append(t))
    spec.register_search_projection("legacy_type", _build)  # type: ignore[arg-type]
    assert calls == ["legacy_type"]


CONTRACT_MODELS = [
    contract.SearchContextIn,
    contract.SearchQueryIn,
    contract.SearchStatusOut,
    contract.SearchTargetOut,
    contract.SearchItemOut,
    contract.SearchGroupOut,
    contract.SearchSuggestionOut,
    contract.SearchResultsOut,
    contract.SearchRecentsOut,
    contract.SearchRecentIn,
    contract.SearchRecentRecordedOut,
]


@pytest.mark.parametrize("model", CONTRACT_MODELS)
def test_ac1_every_field_is_classified_and_none_is_a_wall_signal(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []
    for name in model.model_fields:
        assert "hidden" not in name and "wall" not in name, f"{model.__name__}.{name}"


def test_ac1_query_text_is_cleaned_and_bounded() -> None:
    q = contract.SearchQueryIn(q="  fe‮ld\u0000  \n").q
    assert q == "feld"
    with pytest.raises(ValidationError):
        contract.SearchQueryIn(q="x" * 101)
    with pytest.raises(ValidationError):
        contract.SearchQueryIn(q="feld", limit_per_group=11)


def test_ac1_total_visible_is_capped() -> None:
    with pytest.raises(ValidationError):
        contract.SearchResultsOut(groups=[], total_visible=100)


def test_ac1_routes_take_no_search_text_in_the_url() -> None:
    routes = {(r.path, tuple(sorted(r.methods))) for r in router.routes}  # type: ignore[attr-defined]
    assert routes == {
        ("/v1/search", ("POST",)),
        ("/v1/search/recents", ("GET",)),
        ("/v1/search/recents", ("POST",)),
    }
    for route in router.routes:
        names = {p.name for p in route.dependant.query_params}  # type: ignore[attr-defined]
        assert "q" not in names
