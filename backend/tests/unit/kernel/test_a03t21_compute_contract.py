"""A-03-T21 (SPEC-580 AC-6): the compute packages import only kernel.numeric and kernel.calendar.

Two checks: the import-linter contract is configured and switched on in pyproject.toml (the gate
`lint-imports` enforces it), and a direct scan of every import under the two packages, so a
violation fails in the unit suite too."""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest

BACKEND = Path(__file__).resolve().parents[3]
PACKAGES = ("sampling", "ledger")
ALLOWED = {"abacus.kernel.numeric", "abacus.kernel.calendar"}


def _contract() -> dict[str, Any]:
    config = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    contracts = cast(list[dict[str, Any]], config["tool"]["importlinter"]["contracts"])
    return next(c for c in contracts if str(c["name"]).startswith("Compute packages import only"))


def test_ac6_the_contract_covers_both_compute_packages_and_forbids_everything_else() -> None:
    contract = _contract()
    assert contract["type"] == "forbidden"
    assert set(contract["source_modules"]) == {
        "abacus.modules.sampling.compute",
        "abacus.modules.ledger.compute",
    }
    forbidden = set(contract["forbidden_modules"])
    assert {"abacus.kernel", "abacus.modules", "abacus_tools", "abacus.ai_gateway"} <= forbidden
    ignored = {str(i).split(" -> ")[1] for i in contract["ignore_imports"]}
    assert ignored >= ALLOWED
    assert not {i for i in ignored if i.startswith("abacus.kernel")} - ALLOWED


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


@pytest.mark.parametrize("package", PACKAGES)
def test_ac6_every_compute_import_is_stdlib_its_own_package_or_the_two_kernel_helpers(
    package: str,
) -> None:
    root = BACKEND / "src" / "abacus" / "modules" / package / "compute"
    own = f"abacus.modules.{package}.compute"
    for path in sorted(root.rglob("*.py")):
        for name in _imports(path):
            top = name.split(".")[0]
            if top in sys.stdlib_module_names or top == "__future__":
                continue
            assert name in ALLOWED or name == own or name.startswith(own + "."), (path, name)
