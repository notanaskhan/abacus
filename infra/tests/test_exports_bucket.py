"""DEC-454 (TASK-1361): the engagement export bucket, checked offline.

The module is written and never planned by a session, so what it promises is held on the
Terraform text: the bucket is wired into staging and production, it carries no Object Lock and
expires every object after 7 days, the worker may build and prune segments under `exports/`, the
API may only read them, the key is used only through S3 for this bucket, and the task environment
names the setting `kernel/config.py` reads. The general bucket rules (public access block,
versioning, SSE-KMS, TLS-only) are `test_repository_files.py`'s and apply here too.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

INFRA = Path(__file__).resolve().parents[1]
REPO = INFRA.parent
MODULE = INFRA / "modules" / "s3-exports"
CONFIG = REPO / "backend" / "src" / "abacus" / "kernel" / "config.py"
STORAGE = REPO / "backend" / "src" / "abacus" / "modules" / "evidence" / "export_storage.py"
ROOTS = ("staging", "production")


def main() -> str:
    return (MODULE / "main.tf").read_text(encoding="utf-8")


def document(name: str) -> str:
    """The body of `data "aws_iam_policy_document" "<name>"`, up to the next top-level block."""
    text = main()
    start = text.index(f'data "aws_iam_policy_document" "{name}"')
    following = re.search(r"\n(?:data|resource) ", text[start + 1 :])
    return text[start : start + 1 + following.start()] if following else text[start:]


def statements(body: str) -> list[str]:
    return [s for s in re.split(r"\n  statement \{", body)[1:]]


def actions_of(statement: str) -> set[str]:
    found = re.search(r"actions\s*=\s*\[([^\]]*)\]", statement)
    assert found, statement
    return set(re.findall(r'"([^"]+)"', found.group(1)))


def allowed(body: str) -> dict[str, str]:
    """action -> the statement's resources line, for every Allow statement."""
    result: dict[str, str] = {}
    for statement in statements(body):
        if re.search(r'effect\s*=\s*"Deny"', statement):
            continue
        resources = re.search(r"resources\s*=\s*\[([^\]]*)\]", statement)
        assert resources, statement
        for action in actions_of(statement):
            result[action] = resources.group(1).strip()
    return result


@pytest.mark.parametrize("root", ROOTS)
def test_every_environment_wires_the_module_with_its_own_name(root: str) -> None:
    text = (INFRA / "envs" / root / "exports.tf").read_text(encoding="utf-8")
    assert '"../../modules/s3-exports"' in text
    assert re.search(rf'environment\s*=\s*"{root}"', text)
    variables = (INFRA / "envs" / root / "variables.tf").read_text(encoding="utf-8")
    for name in ("worker_task_role_name", "api_task_role_name"):
        block = variables.split(f'variable "{name}"', 1)[1].split("}", 1)[0]
        assert re.search(r"default\s*=\s*null", block), f"{root}: {name} must default to null"
    outputs = (INFRA / "envs" / root / "outputs.tf").read_text(encoding="utf-8")
    assert "module.exports.task_environment" in outputs


def test_the_bucket_is_named_for_its_environment_and_never_takes_object_lock() -> None:
    text = main()
    assert 'bucket_name  = "abacus-${var.environment}-exports"' in text
    assert "object_lock" not in text.replace("PutBucketObjectLockConfiguration", "")
    deny = [s for s in statements(document("bucket")) if re.search(r'effect\s*=\s*"Deny"', s)]
    denied = set().union(*(actions_of(s) for s in deny))
    assert {
        "s3:PutBucketObjectLockConfiguration",
        "s3:PutObjectRetention",
        "s3:PutObjectLegalHold",
    } <= denied
    assert any("aws:SecureTransport" in s and '"false"' in s for s in deny)


def test_every_object_is_gone_within_seven_days_and_uploads_are_aborted() -> None:
    """Versioning keeps an expired object as a noncurrent copy for a day: current versions go
    after 6 days, so the data is gone within 7 (security review, DEC-454)."""
    variables = (MODULE / "variables.tf").read_text(encoding="utf-8")
    assert re.search(r'variable "expiry_days" \{[^}]*default\s*=\s*6\b', variables)
    assert "var.expiry_days <= 6" in variables
    lifecycle = main().split('resource "aws_s3_bucket_lifecycle_configuration" "exports"', 1)[1]
    lifecycle = lifecycle.split("\nresource ", 1)[0]
    assert re.search(r"expiration \{\s*days\s*=\s*var\.expiry_days", lifecycle)
    assert re.search(r"noncurrent_version_expiration \{\s*noncurrent_days\s*=\s*1\b", lifecycle)
    assert re.search(
        r"abort_incomplete_multipart_upload \{\s*days_after_initiation\s*=\s*1\b", lifecycle
    )
    assert "expired_object_delete_marker = true" in lifecycle
    assert re.search(r"filter \{\}", lifecycle)  # the whole bucket, not a prefix


def test_the_bucket_is_encrypted_with_its_own_rotating_key() -> None:
    text = main()
    key = text.split('resource "aws_kms_key" "exports" {', 1)[1].split("\nresource ", 1)[0]
    assert re.search(r"enable_key_rotation\s*=\s*true", key)
    assert "kms_master_key_id = aws_kms_key.exports.arn" in text
    assert "bucket_key_enabled = true" in text


def test_the_worker_builds_reads_and_prunes_segments_under_exports_only() -> None:
    worker = allowed(document("worker"))
    assert set(worker) == {
        "s3:ListBucket",
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "kms:GenerateDataKey",
        "kms:Decrypt",
    }
    for action in ("s3:PutObject", "s3:GetObject", "s3:DeleteObject"):
        assert worker[action] == '"${aws_s3_bucket.exports.arn}/${local.prefix}*"'
    assert worker["s3:ListBucket"] == "aws_s3_bucket.exports.arn"
    listing = next(s for s in statements(document("worker")) if "s3:ListBucket" in s)
    assert re.search(r'variable\s*=\s*"s3:prefix"', listing)
    assert re.search(r'prefix\s*=\s*"exports/"', main())


def test_the_prefix_is_the_one_the_export_store_writes() -> None:
    assert 'return f"exports/{tenant_id}/{export_id}/"' in STORAGE.read_text(encoding="utf-8")


def test_the_api_only_reads() -> None:
    api = allowed(document("api"))
    assert set(api) == {"s3:GetObject", "kms:Decrypt"}
    assert api["s3:GetObject"] == '"${aws_s3_bucket.exports.arn}/${local.prefix}*"'


@pytest.mark.parametrize("name", ["worker", "api"])
def test_the_key_is_used_only_through_s3_for_this_bucket(name: str) -> None:
    for statement in statements(document(name)):
        if any(a.startswith("kms:") for a in actions_of(statement)):
            assert "aws_kms_key.exports.arn" in statement
            assert 'variable = "kms:ViaService"' in statement
            assert 'variable = "kms:EncryptionContext:aws:s3:arn"' in statement


def test_no_wildcard_action_or_resource_is_granted_to_a_task_role() -> None:
    for name in ("worker", "api"):
        for action, resources in allowed(document(name)).items():
            assert "*" not in action, f"{name}: {action}"
            assert resources not in {'"*"', ""}, f"{name}: {action} on {resources}"


def test_policies_attach_only_to_the_task_roles_named() -> None:
    text = main()
    for role in ("worker", "api"):
        assert re.search(
            rf'resource "aws_iam_role_policy_attachment" "{role}" \{{\s*count = var\.{role}_task_role_name == null \? 0 : 1',
            text,
        )
    assert 'aws_iam_role"' not in text  # the module creates no role of its own


def test_the_task_environment_names_the_setting_the_app_reads() -> None:
    config = CONFIG.read_text(encoding="utf-8")
    assert re.search(r"^\s*exports_bucket: Annotated\[str \| None", config, re.M)
    assert 'env_prefix="ABACUS_"' in config
    outputs = (MODULE / "outputs.tf").read_text(encoding="utf-8")
    assert re.search(r"ABACUS_EXPORTS_BUCKET\s*=\s*aws_s3_bucket\.exports\.id", outputs)
    assert not re.search(r"\b\d{12}\b", outputs + main())  # no account ID anywhere


def test_the_account_administers_the_key_but_only_the_task_roles_use_it() -> None:
    key = document("key")
    admin = next(st for st in statements(key) if 'sid = "KeyAdministration"' in st)
    admin_actions = actions_of(admin)
    assert "kms:*" not in admin_actions
    assert (
        not {"kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey*", "kms:ReEncrypt*"}
        & admin_actions
    )
    use = key.split('sid       = "TaskRolesUseThroughS3"', 1)[1]
    assert re.search(
        r'actions\s*=\s*\["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey\*"\]', use
    )
    assert "identifiers = local.key_users" in use
    assert 'variable = "kms:ViaService"' in use
    assert 'variable = "kms:EncryptionContext:aws:s3:arn"' in use
    assert re.search(
        r"for name in compact\(\[var\.worker_task_role_name, var\.api_task_role_name\]\)", main()
    )


def test_a_put_naming_another_key_or_encryption_is_refused() -> None:
    bucket = document("bucket")
    other_key = bucket.split('sid       = "DenyOtherKeys"', 1)[1].split("statement {", 1)[0]
    assert 'variable = "s3:x-amz-server-side-encryption-aws-kms-key-id"' in other_key
    assert "values   = [aws_kms_key.exports.arn]" in other_key
    assert '"s3:PutObject"' in other_key and 'effect    = "Deny"' in other_key
    other_kind = bucket.split('sid       = "DenyOtherEncryption"', 1)[1].split("statement {", 1)[0]
    assert 'variable = "s3:x-amz-server-side-encryption"' in other_kind
    assert 'values   = ["aws:kms"]' in other_kind


@pytest.mark.parametrize("name", ["worker", "api"])
def test_every_s3_grant_requires_this_account_to_own_the_bucket(name: str) -> None:
    for statement in statements(document(name)):
        if any(a.startswith("s3:") for a in actions_of(statement)):
            assert 'variable = "aws:ResourceAccount"' in statement
            assert "values   = [local.account]" in statement
    assert re.search(r"account\s*=\s*data\.aws_caller_identity\.current\.account_id", main())
