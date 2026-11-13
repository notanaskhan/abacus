"""Every workflow a module's api declares in `WORKFLOWS` has a work class, so `dispatch` can route
it (ADR-071; TASK-7811). notices declared four and registered none: each dispatch raised
LookupError, and the outbox relay held the firm's every later event behind the first
`notice.created`.
"""

from __future__ import annotations

from importlib import import_module

import pytest

from abacus.kernel.dispatch import work_class_of
from abacus.worker.__main__ import MODULES


def _declared() -> list[tuple[str, type]]:
    out: list[tuple[str, type]] = []
    for module in MODULES:
        workflows = getattr(module, "WORKFLOWS", None)
        if isinstance(workflows, dict):
            out += [(module.__name__, w) for w in workflows]  # pyright: ignore[reportUnknownVariableType] -- a module's registry
    return out


def test_the_worker_loads_the_notices_registry() -> None:
    import_module("abacus.modules.notices.api")
    assert any(name == "abacus.modules.notices.api" for name, _ in _declared())


@pytest.mark.parametrize(
    ("module", "workflow"), _declared(), ids=lambda x: getattr(x, "__name__", x)
)
def test_ac_each_declared_workflow_has_a_work_class(module: str, workflow: type) -> None:
    assert work_class_of(workflow), f"{module}: {workflow.__name__}"
