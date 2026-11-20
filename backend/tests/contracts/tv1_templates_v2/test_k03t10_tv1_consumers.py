"""TV-1 v1 consumer tests (K-03-T10; TASK-8854; SPEC-720; C22; DEC-5851). Each operation is
declared under its one matrix action with its 501, every write is denied to the agent and the
system, and the fields the KNW-06, KNW-07, SHL-22 and SHT-03 artboards read are present. The
fixture half is `apps/web/src/fixtures/contracts/tv1-templates-v2.contract.test.ts`."""

from __future__ import annotations

import json
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.modules.engagements.templates_v2_contract import TemplateLinkOut, TemplateUpdateOut
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.methodology.templates_v2_contract import (
    ChangeListOut,
    EngagementTemplateVersionOut,
    RolloutOut,
    ScopingPreviewOut,
    TemplateCheckListOut,
)

Json = dict[str, object]
PATHS = cast(dict[str, dict[str, Json]], json.loads(document())["paths"])
V = "/v1/template-versions/{version_id}"
E = "/v1/engagements/{engagement_id}"
OPERATIONS = {
    ("get", "/v1/engagement-templates"): "template.read",
    ("get", "/v1/engagement-templates/{template_id}"): "template.read",
    ("post", "/v1/engagement-templates/{template_id}/versions"): "template.edit",
    ("get", "/v1/template-versions"): "template.read",
    ("get", V): "template.read",
    ("get", f"{V}/components/{{kind}}"): "template.read",
    ("put", f"{V}/components/{{kind}}"): "template.edit",
    ("get", f"{V}/checks"): "template.read",
    ("get", f"{V}/changes"): "template.read",
    ("post", f"{V}/preview"): "template.read",
    ("get", f"{V}/scoping-rules"): "template.read",
    ("put", f"{V}/scoping-rules"): "scoping_rule.edit",
    ("post", f"{V}/scoping-rules/preview"): "template.read",
    ("get", f"{V}/scoping-sources"): "template.read",
    ("post", f"{V}/publish"): "template.publish",
    ("post", f"{V}/deprecate"): "template.publish",
    ("get", f"{V}/used-by"): "template.read",
    ("get", f"{V}/rollout"): "template.rollout",
    ("put", f"{V}/rollout/actions/{{engagement_id}}"): "template.rollout",
    ("post", f"{V}/rollout/start"): "template.rollout",
    ("get", f"{E}/template-link"): "template_update.read",
    ("get", f"{E}/template-update"): "template_update.read",
    ("get", f"{E}/template-update/{{update_id}}"): "template_update.read",
    ("post", f"{E}/template-update"): "template.apply_update",
    ("post", f"{E}/template-hold"): "template.apply_update",
    ("post", f"{E}/template-hold/release"): "template.apply_update",
    ("get", f"{E}/scoping"): "scoping.read",
    ("post", "/v1/skills/import"): "skill.import",
    ("get", "/v1/skills"): "knowledge.read",
    ("get", "/v1/skill-versions/{skill_version_id}"): "knowledge.read",
}
WRITES = ("template.edit", "template.publish", "template.rollout", "scoping_rule.edit",
          "template.apply_update", "skill.import")  # fmt: skip


@pytest.mark.parametrize(("op", "action"), sorted(OPERATIONS.items()), ids=str)
def test_every_operation_is_declared_with_its_action_and_501(
    op: tuple[str, str], action: str
) -> None:
    method, path = op
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == action
    assert "501" in cast(Json, operation["responses"])


@pytest.mark.parametrize("action", WRITES)
def test_every_write_is_denied_to_the_agent_and_the_system(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny" and rule.decisions.get("system") == "deny"


def test_publish_and_import_need_fresh_mfa() -> None:
    assert RULES["template.publish"].mfa_recent and RULES["skill.import"].mfa_recent


@pytest.mark.parametrize(
    ("model", "fields"),
    [
        (
            EngagementTemplateVersionOut,
            {"label", "status", "retired", "rail", "used_by", "draft_etag"},
        ),
        (TemplateCheckListOut, {"items", "errors", "warnings"}),
        (ChangeListOut, {"items", "added", "changed", "removed"}),
        (RolloutOut, {"rows", "live", "update_now", "on_rollover", "hold", "updated"}),
        (ScopingPreviewOut, {"rows", "shows_steps", "shows_sheets", "hides", "adds_requests"}),
        (TemplateLinkOut, {"state", "available_label", "held_reason", "updated_by", "updated_at"}),
        (TemplateUpdateOut, {"status", "changes", "added", "changed", "removed", "applied"}),
    ],
    ids=lambda v: getattr(v, "__name__", ""),
)
def test_the_artboards_fields_are_present(model: type, fields: set[str]) -> None:
    assert fields <= set(model.model_fields)  # type: ignore[attr-defined] -- a pydantic model
