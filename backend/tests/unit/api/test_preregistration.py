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
from abacus.modules.engagements import slots
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
# Pre-registered modules whose first epic has landed: they still import and register, but now
# own tables and routes (SPEC-308, TASK-319; assurance SPEC-309, TASK-320).
# F-03-T22 (TASK-385, migration 0089): tax, closes and notices hold their work-item subtypes.
# P-08-T01 (TASK-431): the portal module serves the C5 v1.1 home and preferences stubs.
# A-02-T06 (TASK-1262): the integrations module serves the C20 v1 stub (no tables yet).
# I-01-T02 (TASK-1303): practice serves the C13 home-half stub. K-01-T01/T02 (TASK-1305,
# TASK-1306, migration 0180): methodology serves its stubs and re-owns its tables.
LANDED = {
    "assurance",
    "review",
    "workpapers",
    "tax",
    "closes",
    "notices",
    "portal",
    "integrations",
    "practice",
    "methodology",
}
TENANT = TenantContext(uuid.uuid4(), "system", "test")


def test_t08_every_new_module_imports_and_is_registered() -> None:
    assert set(MODULES) >= NEW
    for name in NEW:
        api = importlib.import_module(f"abacus.modules.{name}.api")
        registry = importlib.import_module(f"abacus.modules.{name}.registry")
        routers: object = api.ROUTERS
        tables: object = registry.TABLES
        assert isinstance(routers, tuple) and isinstance(tables, frozenset)
        if name not in LANDED:
            assert routers == ()
            assert frozenset() == tables


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
    fact = await engagements.gate_fact(TENANT, uuid.uuid4(), "G4")  # G6-G9 registered by SPEC-314
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


async def test_t08_registering_the_same_gate_provider_again_is_a_no_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-executing a module (importlib.reload of engagements.api) registers the identical
    provider again; that must not raise, or one test's reload breaks the import for the rest."""
    monkeypatch.setattr(slots, "_GATES", {})

    async def gate(_t: TenantContext, _e: uuid.UUID) -> engagements.GateFact:
        return engagements.GateFact(met=True)

    engagements.register_gate_provider("G4", gate)
    engagements.register_gate_provider("G4", gate)
    assert (await engagements.gate_fact(TENANT, uuid.uuid4(), "G4")).met is True


async def test_t08_a_different_provider_for_a_registered_gate_is_still_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(slots, "_GATES", {})

    async def first(_t: TenantContext, _e: uuid.UUID) -> engagements.GateFact:
        return engagements.GateFact(met=True)

    async def other(_t: TenantContext, _e: uuid.UUID) -> engagements.GateFact:
        return engagements.GateFact(met=False)

    engagements.register_gate_provider("G4", first)
    with pytest.raises(ValueError, match="already registered"):
        engagements.register_gate_provider("G4", other)
    assert (await engagements.gate_fact(TENANT, uuid.uuid4(), "G4")).met is True  # the first stays
