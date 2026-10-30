"""K-02-T12 (TASK-2311; SPEC-500 AC-49 to AC-51; K-02 §4.6): reference-set publication fan-out.

The row's acceptance: one publish yields exactly one audit event and one notification set per
active tenant, and a re-run is idempotent on tenant and version. The per-tenant announcement
checks the tenant's audit trail before writing (the database half runs at the end review with
the recorded replay history); here: the run's shape, the event and the C16 kind, and the CLI.
"""

from __future__ import annotations

import argparse
import inspect

import pytest

from abacus.modules.notifications.catalogue import CATALOGUE, TEMPLATES
from abacus.modules.platform import reference_fanout
from abacus.modules.platform.reference_fanout_workflow import (
    FanOutInput,
    ReferenceSetFanOutWorkflow,
    fanout_workflow_id,
)
from abacus_tools import refdata


def test_ac49_one_run_per_version_and_action() -> None:
    assert fanout_workflow_id("v1", "published") == "reference_fanout:published:v1"
    assert fanout_workflow_id("v1", "withdrawn") != fanout_workflow_id("v1", "published")
    names = {a.__temporal_activity_definition.name for a in reference_fanout.ACTIVITIES}  # type: ignore[attr-defined]  # temporalio's marker
    assert names == {"platform.reference_set_announce"}
    source = inspect.getsource(ReferenceSetFanOutWorkflow.run)
    assert "for tenant_id in request.tenant_ids" in source
    assert FanOutInput("v", "published").action == "published"


def test_ac50_an_announcement_is_written_once_per_tenant_and_version() -> None:
    source = inspect.getsource(reference_fanout.reference_set_announce)
    assert "audit_of_targets(" in source and "return False" in source
    assert source.index("audit_of_targets(") < source.index("tx.record(")
    assert reference_fanout.ReferenceSetPublished.event_type == "reference_set.published"
    fields = set(reference_fanout.ReferenceSetPublished.model_fields)
    assert fields >= {"version_id", "set_key"}  # identifiers only, never a rule's value


def test_ac51_firm_admins_hear_a_rules_table_was_updated() -> None:
    kind = CATALOGUE["reference_set.published"]
    assert kind.kind == "rules_table_updated" and kind.subject_key == "version_id"
    assert "reference_set.published" in TEMPLATES


async def test_ac49_a_publish_whose_fanout_failed_says_how_to_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def down(request: object) -> None:
        raise ConnectionError

    import abacus.modules.platform.api as platform_api

    class Conn:
        async def fetchrow(self, sql: str, *args: object) -> dict[str, str]:
            return {"set_key": "k", "operator": "a", "approver": "b"}

        async def fetch(self, sql: str) -> list[tuple[str]]:
            return [("t1",)]

        async def close(self) -> None:
            return None

    async def connect(dsn: str) -> Conn:
        return Conn()

    monkeypatch.setattr(platform_api, "start_reference_fanout", down)
    monkeypatch.setattr(refdata, "connect", connect)
    monkeypatch.setattr(refdata, "_owner_dsn", lambda: "postgresql://local")
    said = await refdata.fanout(
        argparse.Namespace(version="5c4e0b3c-0a0d-4c5c-9f9a-0e6c0d1d7a11", action="published")
    )
    assert "refdata fanout" in said and "ConnectionError" in said
