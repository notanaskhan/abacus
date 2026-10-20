"""F-03-T07 (P-39): one sorted MODULES tuple, in step with the packages; every module declares a
registry and its routers; no table is claimed twice."""

from __future__ import annotations

import importlib
from pathlib import Path

import abacus.modules as modules_package
from abacus.modules import MODULES
from abacus_tools.quality import schema_check

PACKAGES = Path(modules_package.__file__).parent


def test_t07_modules_is_sorted_unique_and_matches_the_packages() -> None:
    on_disk = sorted(p.name for p in PACKAGES.iterdir() if (p / "__init__.py").exists())
    assert list(MODULES) == sorted(set(MODULES)) == on_disk


def test_t07_every_module_has_a_registry_and_routers() -> None:
    for name in MODULES:
        registry = importlib.import_module(f"abacus.modules.{name}.registry")
        assert registry.INSERT_ONLY <= registry.TABLES
        assert set(registry.INSERT_COLUMNS) <= registry.TABLES
        assert set(registry.UPDATE_COLUMNS) <= registry.TABLES
        assert isinstance(importlib.import_module(f"abacus.modules.{name}.api").ROUTERS, tuple)


def test_t07_the_gate_collects_every_module_table() -> None:
    for name in MODULES:
        registry = importlib.import_module(f"abacus.modules.{name}.registry")
        assert all(schema_check.TABLE_OWNERS[t] == name for t in registry.TABLES)
