"""TASK-1207 security review, item 6 (DEC-52; G-01 AC9.4; SPEC-002 AC-20): no route returns an
unmasked TIN to an offshore reader.

Every served response model with a field tagged `pii_kind=tin` (nested models, lists and dicts
included) either belongs to a `not_offshore` action, which an offshore member is refused at the
condition layer, or passes its response through `identity.api.mask_tins_for`, the one central
mask. A new route that returns a TIN some other way fails here until it is wired. The mask itself
reaches TINs inside nested models, lists and dict values.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterator
from typing import Annotated, get_args

from fastapi.routing import iter_route_contexts
from pydantic import BaseModel

from abacus.api import create_app
from abacus.kernel.classification import classified, pii_paths
from abacus.modules.identity.api import AbacusRoute, declared_action, mask_tins
from abacus.modules.identity.authz.matrix import RULES

MASK_CALL = "mask_tins_for("


def _models(annotation: object) -> Iterator[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
    for arg in get_args(annotation):
        yield from _models(arg)


def _tin_routes() -> list[tuple[str, str, str, Callable[..., object]]]:
    found: list[tuple[str, str, str, Callable[..., object]]] = []
    for context in iter_route_contexts(create_app().routes):
        route = context.original_route
        if not isinstance(route, AbacusRoute):
            continue
        if not any(pii_paths(m, "tin") for m in _models(route.response_model)):
            continue
        for method in sorted(route.methods or set()):
            found.append((method, str(context.path), declared_action(route) or "", route.endpoint))
    return found


def test_review6_every_tin_response_is_refused_or_masked_for_an_offshore_reader() -> None:
    routes = _tin_routes()
    assert len(routes) >= 3  # the client record's GET and PATCH, and the TIN reveal
    unmasked = [
        f"{method} {path} ({action})"
        for method, path, action, endpoint in routes
        if not RULES[action].not_offshore and MASK_CALL not in inspect.getsource(endpoint)
    ]
    assert unmasked == []


def test_review6_a_reveal_is_the_only_tin_route_left_unmasked() -> None:
    refused = sorted(
        f"{method} {path}"
        for method, path, action, _ in _tin_routes()
        if RULES[action].not_offshore
    )
    assert refused == ["POST /v1/client-entities/{entity_id}/tin/reveal"]


class _Row(BaseModel):
    tin: Annotated[str, classified("restricted", pii_kind="tin")]
    last4: Annotated[str | None, classified("restricted", pii_kind="tin")] = None
    name: Annotated[str, classified("confidential")]


class _Out(BaseModel):
    one: _Row
    many: Annotated[list[_Row], classified("internal")]
    by_entity: Annotated[dict[str, _Row], classified("internal")]


def test_review6_the_mask_reaches_nested_models_lists_and_dict_values() -> None:
    row = _Row(tin="900-12-3456", last4="3456", name="Remy")
    masked = mask_tins(_Out(one=row, many=[row], by_entity={"a": row, "b": row}))
    for item in (masked.one, *masked.many, *masked.by_entity.values()):
        assert (item.tin, item.last4, item.name) == ("•••-••-3456", None, "Remy")
    assert sorted(masked.by_entity) == ["a", "b"]
