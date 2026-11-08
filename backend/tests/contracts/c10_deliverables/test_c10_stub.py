"""R-02-T02 (TASK-5102; SPEC-646 AC-7, AC-17): C10's stub. Every route exists under exactly one
matrix action and answers 501; every field is classified; no client DTO carries a field the pack
rule bans; A-06 and A-07 can bind to `publish_deliverable`'s signature."""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.kernel.uow import UnitOfWork
from abacus.modules.reporting.api import (
    DeliverableAudience,
    DeliverableInvalid,
    DeliverableSpec,
    deliverables_for_work_item,
    publish_deliverable,
)

REPO = Path(__file__).resolve().parents[4]
ROUTES = {
    ("get", "/v1/portal/deliverables"): "deliverable.read",
    ("get", "/v1/portal/deliverables/{deliverable_id}"): "deliverable.read",
    ("get", "/v1/portal/deliverables/{deliverable_id}/versions/{version_no}"): "deliverable.read",
    (
        "get",
        "/v1/portal/deliverables/{deliverable_id}/versions/{version_no}/pages/{page}",
    ): "deliverable.read",
    (
        "get",
        "/v1/portal/deliverables/{deliverable_id}/versions/{version_no}/download",
    ): "deliverable.download",
    (
        "post",
        "/v1/portal/deliverables/{deliverable_id}/versions/{version_no}/approve",
    ): "statement.client_approve",
    (
        "get",
        "/v1/portal/deliverables/{deliverable_id}/versions/{version_no}/comments",
    ): "deliverable.comment",
    (
        "post",
        "/v1/portal/deliverables/{deliverable_id}/versions/{version_no}/comments",
    ): "deliverable.comment",
    ("get", "/v1/portal/governance/rooms"): "tcwg.read",
    ("get", "/v1/portal/governance/rooms/{room_id}/communications"): "tcwg.read",
    ("get", "/v1/portal/governance/rooms/{room_id}/inquiries"): "tcwg.read",
    ("get", "/v1/portal/governance/rooms/{room_id}/reports"): "tcwg.read",
    ("get", "/v1/portal/governance/communications/{communication_id}"): "tcwg.read",
    ("get", "/v1/portal/governance/communications/{communication_id}/pdf"): "tcwg.read",
    (
        "post",
        "/v1/portal/governance/communications/{communication_id}/acknowledge",
    ): "tcwg.acknowledge",
    ("get", "/v1/portal/governance/communications/{communication_id}/questions"): "tcwg.ask",
    ("post", "/v1/portal/governance/communications/{communication_id}/questions"): "tcwg.ask",
}
BANNED = re.compile(
    r"materiality|threshold|policy|review_note|sign_off|signoff|agent|confidence|internal_status",
    re.I,
)


def _doc() -> dict[str, object]:
    return cast(dict[str, object], json.loads(document()))


def _operation(method: str, path: str) -> dict[str, object]:
    paths = cast(dict[str, dict[str, dict[str, object]]], _doc()["paths"])
    return paths[path][method]


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_every_route_exists_with_its_501(method: str, path: str) -> None:
    responses = cast(dict[str, object], _operation(method, path)["responses"])
    assert "501" in responses


@pytest.mark.parametrize("action", sorted(set(ROUTES.values())))
def test_clients_only_agent_and_system_denied(action: str) -> None:
    matrix = yaml.safe_load((REPO / "docs/architecture/permission-matrix/portal.yaml").read_text())
    row = matrix["actions"][action]
    assert row["agent"] == "deny"
    assert row["system"] == "deny"
    firm = {"firm_admin", "engagement_partner", "manager", "senior", "staff", "client_service"}
    assert not firm & set(row)
    assert row["scope_only"] == "required"


def test_no_client_dto_carries_a_banned_field() -> None:
    schemas = cast(dict[str, dict[str, object]], _doc()["components"])["schemas"]
    used: set[str] = set()
    for method, path in ROUTES:
        used |= set(
            re.findall(r"#/components/schemas/(\w+)", json.dumps(_operation(method, path)))
        )
    for name in used:
        schema = cast(dict[str, object], schemas[name])
        for field in cast(dict[str, object], schema.get("properties", {})):
            assert not BANNED.search(field), f"{name}.{field}"


async def test_consumers_bind_to_the_publish_signature() -> None:
    assert list(inspect.signature(publish_deliverable).parameters) == ["tx", "spec"]
    assert list(inspect.signature(deliverables_for_work_item).parameters) == [
        "tenant",
        "work_item_id",
    ]
    spec = DeliverableSpec(
        client_id=uuid4(),
        kind="fs_draft",
        title="Financial statements and supplemental schedules",
        source_module="reporting",
        source_ref="statement_version:v3",
        evidence_version_id=uuid4(),
        render_hash="h",
        page_count=14,
        audiences=[DeliverableAudience("work_item", uuid4())],
        published_by_user_id=uuid4(),
        is_draft=True,
        page_comments=True,
    )
    # R-02-T09 made the service live (S31 end pass): a spec C10 can't publish is refused before
    # the provider's transaction is touched.
    with pytest.raises(DeliverableInvalid):
        await publish_deliverable(cast("UnitOfWork", None), replace(spec, page_count=0))
