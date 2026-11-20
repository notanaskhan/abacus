"""Q-05-T14 (DEC-5823): the records-destruction role, checked offline on the Terraform text.

"On staging a delete of an object with unexpired retention or legal hold on fails under the role,
an expired unheld object deletes, and an out-of-batch assumption pages on-call." The staging proof
itself is RB-100 (a person's). Here: only the worker task role may assume it, with a
destruction_batch session tag; it may delete versions and never bypass governance or change a
hold or retention; an untagged assumption pages; the SCP keeps every other principal out.
"""

from __future__ import annotations

import json
from pathlib import Path

INFRA = Path(__file__).resolve().parents[1]
MODULE = INFRA / "modules" / "destruction-role" / "main.tf"


def _text() -> str:
    return MODULE.read_text(encoding="utf-8")


def test_only_the_worker_role_with_a_batch_tag_assumes_it() -> None:
    trust = _text().split('data "aws_iam_policy_document" "trust"', 1)[1].split("\nlocals", 1)[0]
    assert "var.worker_task_role_arn" in trust
    assert '"aws:RequestTag/destruction_batch"' in trust
    assert '"sts:TagSession"' in trust


def test_it_deletes_versions_and_never_bypasses_or_changes_locks() -> None:
    text = _text()
    allow = text.split('sid       = "DeleteExpiredVersions"', 1)[1].split("statement", 1)[0]
    assert '"s3:DeleteObjectVersion"' in allow
    deny = text.split('sid    = "NeverBypassOrChangeLocks"', 1)[1].split("resource", 1)[0]
    for action in ("s3:BypassGovernanceRetention", "s3:PutObjectLegalHold", "s3:PutObjectRetention"):
        assert f'"{action}"' in deny
    assert "s3:BypassGovernanceRetention" not in allow


def test_an_untagged_assumption_pages_on_call() -> None:
    text = _text()
    assert 'resource "aws_cloudwatch_event_rule" "untagged_assume"' in text
    assert "exists = false" in text
    assert "var.oncall_topic_arn" in text


def test_the_scp_keeps_every_other_principal_out() -> None:
    scp = json.loads((INFRA / "landing-zone" / "scp-evidence-destruction.json").read_text())
    first = scp["Statement"][0]
    assert first["Effect"] == "Deny" and "s3:DeleteObjectVersion" in first["Action"]
    assert first["Condition"]["ArnNotLike"]["aws:PrincipalArn"] == ["arn:aws:iam::*:role/abacus-*-destruction"]


def test_staging_wires_it_off_by_default() -> None:
    env = (INFRA / "envs" / "staging" / "destruction.tf").read_text()
    assert "count  = var.destruction_role_enabled ? 1 : 0" in env
