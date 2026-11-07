"""P-11-T29 (TASK-6018; DEC-2614): the OCR nightly role, checked offline.

The role `ocr-nightly.yml` assumes is trusted from one GitHub environment, may call only the two
synchronous OCR actions in staging's region, exists only with Textract on, and the workflow job
names the same environment. Read from the Terraform and workflow text, no plan, no credentials.
"""

from __future__ import annotations

from pathlib import Path

INFRA = Path(__file__).resolve().parents[1]
ROLE = (INFRA / "envs" / "staging" / "ocr_nightly.tf").read_text(encoding="utf-8")
WORKFLOW = (INFRA.parent / ".github" / "workflows" / "ocr-nightly.yml").read_text(encoding="utf-8")


def test_the_role_exists_only_with_textract_on() -> None:
    assert "count  = var.textract_enabled ? 1 : 0" in ROLE


def test_it_is_trusted_from_the_ocr_nightly_environment_alone() -> None:
    assert 'source = "../../modules/deploy-role"' in ROLE
    assert 'github_environment = "ocr-nightly"' in ROLE
    assert "environment: ocr-nightly" in WORKFLOW


def test_it_may_call_only_the_two_ocr_actions_in_the_region() -> None:
    allow = ROLE.split('sid       = "OcrSuiteOnRealTextract"')[1].split("statement {")[0]
    assert '["textract:DetectDocumentText", "textract:AnalyzeDocument"]' in allow
    assert '"aws:RequestedRegion"' in allow and "local.region" in allow
    deny = ROLE.split('sid         = "NothingElse"')[1]
    assert 'effect      = "Deny"' in deny
    assert 'not_actions = ["textract:DetectDocumentText", "textract:AnalyzeDocument"]' in deny


def test_no_account_id_is_written_in_git() -> None:
    assert "arn:aws:iam::" not in ROLE
