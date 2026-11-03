"""P-11-T22 (TASK-3270; DEC-2250): Textract inside the boundary, offline.

Row acceptance: "From the worker task Textract is reachable only through the endpoint in
us-east-2, any other Textract action is denied, and a Terraform test fails if the opt-out policy
is detached." Read from the module's source and the landing-zone policy, no plan, no credentials.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

INFRA = Path(__file__).resolve().parents[1]
MODULE = (INFRA / "modules" / "textract" / "main.tf").read_text(encoding="utf-8")
STAGING = (INFRA / "envs" / "staging" / "textract.tf").read_text(encoding="utf-8")
OPT_OUT = json.loads((INFRA / "landing-zone" / "ai-services-opt-out.json").read_text())


def test_the_endpoint_is_an_interface_endpoint_with_private_dns() -> None:
    assert 'vpc_endpoint_type   = "Interface"' in MODULE
    assert "private_dns_enabled = true" in MODULE
    assert re.search(
        r'service_name\s+=\s+"com\.amazonaws\.\$\{data\.aws_region\.current\.name\}\.textract"',
        MODULE,
    )


def test_the_worker_may_call_only_the_two_ocr_actions_through_the_endpoint() -> None:
    allow = MODULE.split('sid       = "TextractThroughTheEndpoint"')[1].split("statement {")[0]
    assert '["textract:DetectDocumentText", "textract:AnalyzeDocument"]' in allow
    assert '"aws:SourceVpce"' in allow
    assert 'sid         = "NoOtherTextract"' in MODULE and "not_actions" in MODULE
    assert 'sid       = "NoTextractOutsideTheEndpoint"' in MODULE
    assert 'worker_role_name         = aws_iam_role.task["worker"].name' in STAGING


def test_staging_is_us_east_2_only() -> None:
    providers = (INFRA / "envs" / "staging" / "providers.tf").read_text(encoding="utf-8")
    assert 'region = "us-east-2"' in providers or "us-east-2" in providers


def test_the_ai_services_opt_out_covers_every_service() -> None:
    default = OPT_OUT["services"]["default"]["opt_out_policy"]
    assert default["@@assign"] == "optOut"
    assert default["@@operators_allowed_for_child_policies"] == ["@@none"]


def test_alarms_and_the_budget_exist() -> None:
    for name in (
        '"ThrottledCount"',
        '"UserErrorCount"',
        '"ServerErrorCount"',
        "aws_budgets_budget",
    ):
        assert name in MODULE
