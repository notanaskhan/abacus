# ac-test-author: ayushkbhatia
"""A-06-T06 (TASK-2919; SPEC-642 AC-3, AC-5; DEC-1965): AY's consumer tests for N's completion
stub. AUD-15 and AUD-16 a, e, f's operations exist with their one action and 404 and 501; every
field is classified; clients hold nothing; the agent may only read and propose a finding or a
candidate misstatement; passing on SUM is the EP's alone; severity and the SUM conclusion have no
endpoint of their own (they are C3 cards).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel import _flags
from abacus.kernel.classification import unclassified_fields
from abacus.modules.assurance import findings_contract as fc
from abacus.modules.identity.authz import _matrix

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
W = "/v1/work-items/{work_item_id}"
ROUTES: dict[tuple[str, str], str] = {
    ("get", f"{W}/findings"): "finding.read",
    ("post", f"{W}/findings"): "finding.create",
    ("get", "/v1/findings/{finding_id}"): "finding.read",
    ("post", "/v1/findings/{finding_id}/convert-to-deficiency"): "finding.convert",
    ("post", "/v1/findings/{finding_id}/convert-to-misstatement"): "finding.convert",
    ("post", "/v1/findings/{finding_id}/resolve"): "finding.resolve",
    ("post", "/v1/findings/{finding_id}/request-decision"): "finding.request_decision",
    ("get", f"{W}/misstatements"): "misstatement.read",
    ("post", "/v1/misstatements/{misstatement_id}/pass-to-sum"): "misstatement.pass_to_sum",
    ("get", f"{W}/sum"): "sum.read",
    ("put", f"{W}/sum/qualitative-factors/{{factor}}"): "sum.update_factors",
    ("post", f"{W}/sum/request-conclusion"): "sum.request_conclusion",
    ("post", f"{W}/sum/snapshots"): "sum.snapshot",
}
AGENT_MAY = {
    "finding.read",
    "finding.create",
    "misstatement.read",
    "misstatement.create",
    "sum.read",
}
CLIENT_ROLES = ("client_admin", "client_contributor", "third_party", "client_service")


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_action_and_documents_404_and_501(method: str, path: str) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, operation["responses"]))


def test_every_field_is_classified() -> None:
    models = [
        v
        for v in vars(fc).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == fc.__name__
    ]
    assert models
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


@pytest.mark.parametrize(
    "action",
    sorted(
        {
            a
            for a in _matrix.ACTIONS
            if a.startswith(("finding.", "misstatement.", "sum.", "consultation."))
        }
        - {
            "finding.raise",
            "finding.propose_severity",
            "finding.conclude_severity",
            "finding.communicate",
            "misstatement.set",
        }
    ),
)
def test_clients_hold_nothing_and_the_agent_only_reads_or_proposes(action: str) -> None:
    cells = _matrix.ACTIONS[action]
    for role in CLIENT_ROLES:
        assert cells.get(role, "deny") == "deny", (action, role)
    if action not in AGENT_MAY:
        assert cells.get("agent", "deny") == "deny", action


def test_passing_on_sum_is_the_eps_alone() -> None:
    cells = _matrix.ACTIONS["misstatement.pass_to_sum"]
    assert cells.get("engagement_partner") == "allow"
    for role in ("manager", "senior", "staff", "agent"):
        assert cells.get(role, "deny") == "deny", role


def test_severity_and_the_sum_conclusion_have_no_endpoint_of_their_own() -> None:
    for path in PATHS:
        assert not path.endswith(("/conclude-severity", "/sum/conclude", "/sum:conclude")), path


def test_the_sum_example_is_northwinds() -> None:
    example = cast(dict[str, object], fc.SumOut.model_json_schema()["examples"][0])
    found = fc.SumOut.model_validate(example)
    assert (found.rollover, found.iron_curtain) == (Decimal("34150.00"), Decimal("22250.00"))
    assert (found.pct_of_pm, found.fill_pct_of_overall) == (Decimal("18.1"), Decimal("13.5"))


def test_the_flag_defaults_off() -> None:
    flag = _flags.FLAGS["assurance.completion"]
    assert flag.kind == "boolean" and str(flag.default).lower() == "false"
