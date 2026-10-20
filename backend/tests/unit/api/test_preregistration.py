"""F-03-T08 (ADR-140): the 16 pre-registered modules import cleanly, the module graph is the
plan's and acyclic, and unregistered kinds, gates, scopes, consents and search projections fail
closed."""

from __future__ import annotations

import importlib
import uuid
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules import MODULES
from abacus.modules.engagements import api as engagements
from abacus.modules.identity import api as identity
from abacus.modules.platform import api as platform
from abacus_tools.quality.banned_patterns import MODULE_DEPENDENCIES

NEW = {
    "methodology",
    "review",
    "collaboration",
    "workpapers",
    "adjustments",
    "signatures",
    "integrations",
    "reporting",
    "assurance",
    "attest",
    "tax",
    "closes",
    "notices",
    "workbench",
    "practice",
    "portal",
}
TENANT = TenantContext(uuid.uuid4(), "system", "test")


def test_t08_every_new_module_imports_and_is_registered() -> None:
    assert set(MODULES) >= NEW
    for name in NEW:
        assert importlib.import_module(f"abacus.modules.{name}.api").ROUTERS == ()
        assert frozenset() == importlib.import_module(f"abacus.modules.{name}.registry").TABLES


def test_t08_the_graph_covers_every_module_and_is_acyclic() -> None:
    assert set(MODULE_DEPENDENCIES) == set(MODULES)
    done: set[str] = set()

    def visit(name: str, path: tuple[str, ...]) -> None:
        assert name not in path, f"cycle: {' -> '.join((*path, name))}"
        if name in done:
            return
        for dependency in MODULE_DEPENDENCIES[name]:
            visit(dependency, (*path, name))
        done.add(name)

    for name in MODULES:
        visit(name, ())


def test_t08_nothing_imports_the_edge_modules_and_engines_never_import_a_service_line() -> None:
    edge = {"portal", "notifications", "practice", "workbench", "audit_trail"}
    assert not any(edge & deps for deps in MODULE_DEPENDENCIES.values())
    lines = {"assurance", "attest", "tax", "closes", "notices"}
    for engine in ("review", "collaboration", "workpapers", "adjustments", "signatures"):
        assert not lines & MODULE_DEPENDENCIES[engine]


def test_t08_an_unregistered_work_item_kind_is_refused() -> None:
    with pytest.raises(engagements.UnknownWorkItemKind):
        engagements.work_item_provider("not_a_kind")


async def test_t08_an_unregistered_gate_is_unmet() -> None:
    fact = await engagements.gate_fact(TENANT, uuid.uuid4(), "G7")
    assert fact.met is False and fact.blockers == ("no_gate_provider",)


async def test_t08_an_unregistered_scope_and_consent_deny() -> None:
    assert await identity.resolve_scope(TENANT, "k1_package", uuid.uuid4()) is None
    assert (
        await identity.consent_given(TENANT, uuid.uuid4(), "tri_offshore", datetime.now(UTC))
        is False
    )


async def test_t08_an_unregistered_search_type_is_not_indexed() -> None:
    assert await platform.search_document(TENANT, "tax_return", uuid.uuid4()) is None


def test_t08_a_slot_takes_one_registration() -> None:
    async def gate(_t: TenantContext, _e: uuid.UUID) -> engagements.GateFact:
        return engagements.GateFact(met=True)

    with pytest.raises(ValueError, match="unknown"):
        engagements.register_gate_provider("G10", gate)
