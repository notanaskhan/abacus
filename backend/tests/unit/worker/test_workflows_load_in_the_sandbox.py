"""Every workflow a worker registers loads in Temporal's sandbox (DEC-2363).

A real `Worker` validates each workflow when it is built, so one bad import stops all of them, and
tests that fake the worker never see it: T-03-T07's sweep imported `kernel.dispatch` at module
level and broke every worker on main until the integration shards ran.
"""

from __future__ import annotations

import importlib

import pytest
from temporalio import workflow
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner

_MAIN = importlib.import_module("abacus.worker.__main__")


def _registered() -> list[type]:
    found: list[type] = []
    for module in _MAIN.MODULES:
        found.extend(module.WORKFLOWS)
    return sorted(set(found), key=lambda w: w.__name__)


@pytest.mark.asyncio
@pytest.mark.parametrize("found", _registered(), ids=lambda w: w.__name__)
async def test_the_workflow_loads_in_the_sandbox(found: type) -> None:
    # The SDK's own check, as `Worker` runs it.
    definition = workflow._Definition.must_from_class(found)
    SandboxedWorkflowRunner().prepare_workflow(definition)
