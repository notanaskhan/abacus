"""Q-01-T24 / SPEC-050 AC-22 and AC-32: the plan assertions, and proof that they can fail.

Two kinds of test:

* `test_real_plan_*` read the plans of the environments (`terraform show -json plan.bin > <env>.json`)
  from the directory in `ABACUS_TF_PLANS`, and are skipped without it. Producing a plan needs the
  read-only plan role (infra.yml); no plan is made here.
* every other test runs the assertions on small hand-made plans in Terraform's JSON format: one
  compliant plan that must pass, and one flaw at a time that must be caught. Without these a
  broken assertion would pass every real plan.

Fake identifiers only: account 111111111111, no real ARN.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_assertions as pa  # noqa: E402

Plan = dict[str, Any]
KEY_ARN = "arn:aws:kms:us-east-2:111111111111:key/00000000-0000-4000-8000-000000000000"
TLS_POLICY = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DenyInsecureTransport",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": ["arn:aws:s3:::abacus-staging-evidence/*"],
                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
            }
        ],
    }
)


def change(
    type_: str,
    name: str,
    after: dict[str, Any],
    *,
    module: str | None = None,
    unknown: dict[str, Any] | None = None,
    provider: str = "aws",
) -> dict[str, Any]:
    prefix = f"module.{module}." if module else ""
    entry: dict[str, Any] = {
        "address": f"{prefix}{type_}.{name}",
        "mode": "managed",
        "type": type_,
        "name": name,
        "provider_name": "registry.terraform.io/hashicorp/aws",
        "provider_config_key": provider,
        "change": {"actions": ["create"], "before": None, "after": after, "after_unknown": unknown or {}},
    }
    if module:
        entry["module_address"] = f"module.{module}"
    return entry


def configured(type_: str, name: str, bucket: str | None = None) -> dict[str, Any]:
    expressions: dict[str, Any] = {}
    if bucket:
        expressions["bucket"] = {"references": [f"aws_s3_bucket.{bucket}.id", f"aws_s3_bucket.{bucket}"]}
    return {
        "address": f"{type_}.{name}",
        "mode": "managed",
        "type": type_,
        "name": name,
        "expressions": expressions,
    }


def bucket_group(
    name: str, bucket_name: str, *, module: str | None = None, lock: str | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """A bucket with everything AC-22 asks of it. `lock` is None (no Object Lock),
    `"GOVERNANCE"` (default retention) or `"records"` (lock on, no default retention)."""
    changes = [
        change("aws_s3_bucket", name, {"bucket": bucket_name, "object_lock_enabled": lock is not None}, module=module),
        change(
            "aws_s3_bucket_public_access_block",
            name,
            {
                "block_public_acls": True,
                "block_public_policy": True,
                "ignore_public_acls": True,
                "restrict_public_buckets": True,
            },
            module=module,
        ),
        change("aws_s3_bucket_versioning", name, {"versioning_configuration": [{"status": "Enabled"}]}, module=module),
        change(
            "aws_s3_bucket_server_side_encryption_configuration",
            name,
            {
                "rule": [
                    {
                        "apply_server_side_encryption_by_default": [
                            {"sse_algorithm": "aws:kms", "kms_master_key_id": KEY_ARN}
                        ]
                    }
                ]
            },
            module=module,
        ),
        change("aws_s3_bucket_policy", name, {"policy": TLS_POLICY}, module=module),
    ]
    resources = [
        configured("aws_s3_bucket", name),
        configured("aws_s3_bucket_public_access_block", name, name),
        configured("aws_s3_bucket_versioning", name, name),
        configured("aws_s3_bucket_server_side_encryption_configuration", name, name),
        configured("aws_s3_bucket_policy", name, name),
    ]
    if lock == "GOVERNANCE":
        changes.append(
            change(
                "aws_s3_bucket_object_lock_configuration",
                name,
                {
                    "object_lock_enabled": "Enabled",
                    "rule": [{"default_retention": [{"mode": "GOVERNANCE", "days": 30, "years": None}]}],
                },
                module=module,
            )
        )
        resources.append(configured("aws_s3_bucket_object_lock_configuration", name, name))
    elif lock == "records":
        changes.append(
            change(
                "aws_s3_bucket_object_lock_configuration",
                name,
                {"object_lock_enabled": "Enabled", "rule": []},
                module=module,
            )
        )
        resources.append(configured("aws_s3_bucket_object_lock_configuration", name, name))
    return changes, resources


def compliant_plan() -> Plan:
    evidence, evidence_config = bucket_group("evidence", "abacus-staging-evidence", lock="GOVERNANCE")
    records, records_config = bucket_group("records", "abacus-staging-records", module="storage", lock="records")
    logs, logs_config = bucket_group("logs", "abacus-staging-logs")
    changes = [
        *evidence,
        *records,
        *logs,
        change(
            "aws_db_instance",
            "main",
            {"publicly_accessible": False, "storage_encrypted": True, "db_subnet_group_name": "abacus-staging-data"},
        ),
        change(
            "aws_db_parameter_group",
            "main",
            {
                "parameter": [
                    {"name": "rds.force_ssl", "value": "1"},
                    {"name": "log_parameter_max_length", "value": "0"},
                    {"name": "log_parameter_max_length_on_error", "value": "0"},
                ]
            },
        ),
        change(
            "aws_security_group",
            "app",
            {
                "egress": [
                    {"from_port": 443, "to_port": 443, "protocol": "tcp", "cidr_blocks": ["0.0.0.0/0"]},
                    {"from_port": 3310, "to_port": 3310, "protocol": "tcp", "cidr_blocks": ["10.20.0.0/16"]},
                ]
            },
        ),
        change("aws_acm_certificate", "edge", {"domain_name": "app.example.test"}, provider="aws.edge"),
        change("aws_iam_role", "task", {"name": "abacus-staging-task"}),
    ]
    return {
        "format_version": "1.2",
        "resource_changes": changes,
        "configuration": {
            "provider_config": {
                "aws": {"name": "aws", "expressions": {"region": {"constant_value": "us-east-2"}}},
                "aws.edge": {
                    "name": "aws",
                    "alias": "edge",
                    "expressions": {"region": {"constant_value": "us-east-1"}},
                },
            },
            "root_module": {
                "resources": [*evidence_config, *logs_config],
                "module_calls": {"storage": {"module": {"resources": records_config}}},
            },
        },
    }


def find(plan: Plan, address: str) -> dict[str, Any]:
    (entry,) = [c for c in plan["resource_changes"] if c["address"] == address]
    return entry["change"]["after"]


def remove(plan: Plan, address: str) -> None:
    plan["resource_changes"] = [c for c in plan["resource_changes"] if c["address"] != address]


def add(plan: Plan, entry: dict[str, Any]) -> None:
    plan["resource_changes"].append(entry)


# --- the compliant plan passes ------------------------------------------------------------------


def test_a_compliant_plan_has_no_violations() -> None:
    assert pa.violations(compliant_plan()) == {}


def test_the_compliant_plan_is_not_vacuous() -> None:
    plan = compliant_plan()
    assert len(pa._buckets(plan)) == 3  # pyright: ignore[reportPrivateUsage]
    assert {r.module for r in pa.resources(plan)} == {"", "module.storage."}


# --- each flaw is caught ------------------------------------------------------------------------

Flaw = Callable[[Plan], None]


def _no_block(plan: Plan) -> None:
    remove(plan, "aws_s3_bucket_public_access_block.logs")


def _block_off(plan: Plan) -> None:
    find(plan, "aws_s3_bucket_public_access_block.evidence")["restrict_public_buckets"] = False


def _nested_block_off(plan: Plan) -> None:
    find(plan, "module.storage.aws_s3_bucket_public_access_block.records")["block_public_acls"] = False


def _public_acl(plan: Plan) -> None:
    add(plan, change("aws_s3_bucket_acl", "logs", {"bucket": "abacus-staging-logs", "acl": "public-read"}))


def _no_policy(plan: Plan) -> None:
    remove(plan, "aws_s3_bucket_policy.logs")


def _policy_without_tls(plan: Plan) -> None:
    find(plan, "aws_s3_bucket_policy.evidence")["policy"] = json.dumps(
        {"Statement": [{"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject", "Resource": "*"}]}
    )


def _unversioned(plan: Plan) -> None:
    find(plan, "aws_s3_bucket_versioning.logs")["versioning_configuration"] = [{"status": "Suspended"}]


def _aes256(plan: Plan) -> None:
    after = find(plan, "aws_s3_bucket_server_side_encryption_configuration.logs")
    after["rule"][0]["apply_server_side_encryption_by_default"][0]["sse_algorithm"] = "AES256"


def _aws_managed_key(plan: Plan) -> None:
    after = find(plan, "aws_s3_bucket_server_side_encryption_configuration.logs")
    after["rule"][0]["apply_server_side_encryption_by_default"][0]["kms_master_key_id"] = "alias/aws/s3"


def _evidence_unlocked(plan: Plan) -> None:
    find(plan, "aws_s3_bucket.evidence")["object_lock_enabled"] = False
    remove(plan, "aws_s3_bucket_object_lock_configuration.evidence")


def _evidence_compliance_mode(plan: Plan) -> None:
    after = find(plan, "aws_s3_bucket_object_lock_configuration.evidence")
    after["rule"][0]["default_retention"][0]["mode"] = "COMPLIANCE"


def _records_default_retention(plan: Plan) -> None:
    after = find(plan, "module.storage.aws_s3_bucket_object_lock_configuration.records")
    after["rule"] = [{"default_retention": [{"mode": "COMPLIANCE", "days": 30, "years": None}]}]


def _records_unlocked(plan: Plan) -> None:
    find(plan, "module.storage.aws_s3_bucket.records")["object_lock_enabled"] = False
    remove(plan, "module.storage.aws_s3_bucket_object_lock_configuration.records")


def _public_database(plan: Plan) -> None:
    find(plan, "aws_db_instance.main")["publicly_accessible"] = True


def _unencrypted_database(plan: Plan) -> None:
    find(plan, "aws_db_instance.main")["storage_encrypted"] = False


def _ssl_not_forced(plan: Plan) -> None:
    find(plan, "aws_db_parameter_group.main")["parameter"][0]["value"] = "0"


def _parameters_logged(plan: Plan) -> None:
    find(plan, "aws_db_parameter_group.main")["parameter"][1]["value"] = "-1"


def _no_parameter_group(plan: Plan) -> None:
    remove(plan, "aws_db_parameter_group.main")


def _egress_everywhere(plan: Plan) -> None:
    find(plan, "aws_security_group.app")["egress"].append(
        {"from_port": 0, "to_port": 0, "protocol": "-1", "cidr_blocks": ["0.0.0.0/0"]}
    )


def _egress_on_5432(plan: Plan) -> None:
    find(plan, "aws_security_group.app")["egress"].append(
        {"from_port": 5432, "to_port": 5432, "protocol": "tcp", "cidr_blocks": ["0.0.0.0/0"]}
    )


def _egress_rule_on_80(plan: Plan) -> None:
    add(
        plan,
        change(
            "aws_vpc_security_group_egress_rule",
            "http",
            {"ip_protocol": "tcp", "from_port": 80, "to_port": 80, "cidr_ipv4": "0.0.0.0/0"},
        ),
    )


def _iam_user(plan: Plan) -> None:
    add(plan, change("aws_iam_user", "deploy", {"name": "deploy"}))


def _access_key(plan: Plan) -> None:
    add(plan, change("aws_iam_access_key", "deploy", {"user": "deploy"}))


def _region_outside(plan: Plan) -> None:
    plan["configuration"]["provider_config"]["aws"]["expressions"]["region"]["constant_value"] = "eu-west-1"


def _region_from_variable(plan: Plan) -> None:
    plan["configuration"]["provider_config"]["aws"]["expressions"]["region"] = {"references": ["var.region"]}


def _edge_region_for_data(plan: Plan) -> None:
    add(plan, change("aws_ecs_cluster", "edge_compute", {"name": "abacus-staging"}, provider="aws.edge"))


FLAWS: dict[str, tuple[Flaw, str, str]] = {
    "no public access block": (_no_block, "buckets are private", "aws_s3_bucket.logs"),
    "public access block off": (_block_off, "buckets are private", "restrict_public_buckets"),
    "public access block off in a module": (_nested_block_off, "buckets are private", "block_public_acls"),
    "public ACL": (_public_acl, "buckets are private", "public ACL"),
    "no bucket policy": (_no_policy, "buckets are TLS-only", "aws_s3_bucket.logs"),
    "policy without a TLS deny": (_policy_without_tls, "buckets are TLS-only", "aws_s3_bucket.evidence"),
    "versioning suspended": (_unversioned, "buckets are versioned and SSE-KMS", "versioning"),
    "AES256 instead of KMS": (_aes256, "buckets are versioned and SSE-KMS", "aws:kms"),
    "AWS-managed key": (_aws_managed_key, "buckets are versioned and SSE-KMS", "AWS-managed"),
    "evidence without Object Lock": (_evidence_unlocked, "Object Lock", "aws_s3_bucket.evidence"),
    "evidence not GOVERNANCE": (_evidence_compliance_mode, "Object Lock", "GOVERNANCE"),
    "records with a default retention": (_records_default_retention, "Object Lock", "default retention"),
    "records without Object Lock": (_records_unlocked, "Object Lock", "records"),
    "public database": (_public_database, "database is private with forced SSL", "publicly accessible"),
    "unencrypted database": (_unencrypted_database, "database is private with forced SSL", "not encrypted"),
    "SSL not forced": (_ssl_not_forced, "database is private with forced SSL", "rds.force_ssl"),
    "parameters logged": (_parameters_logged, "database is private with forced SSL", "log_parameter"),
    "no parameter group": (_no_parameter_group, "database is private with forced SSL", "parameter group"),
    "egress on every port": (_egress_everywhere, "egress is 443 only", "every protocol"),
    "egress on 5432": (_egress_on_5432, "egress is 443 only", "5432"),
    "egress rule on 80": (_egress_rule_on_80, "egress is 443 only", "80"),
    "an IAM user": (_iam_user, "no IAM users", "aws_iam_user.deploy"),
    "an access key": (_access_key, "no IAM users", "aws_iam_access_key.deploy"),
    "a region outside the list": (_region_outside, "allowed regions", "eu-west-1"),
    "a region from a variable": (_region_from_variable, "allowed regions", "not a literal"),
    "us-east-1 for compute": (_edge_region_for_data, "allowed regions", "global edge"),
}


@pytest.mark.parametrize("flaw", sorted(FLAWS))
def test_each_flaw_is_caught(flaw: str) -> None:
    mutate, check, fragment = FLAWS[flaw]
    plan = copy.deepcopy(compliant_plan())
    mutate(plan)
    found = pa.violations(plan)
    assert check in found, f"{flaw}: not caught by '{check}'; got {found}"
    assert any(fragment in problem for problem in found[check]), found[check]


@pytest.mark.parametrize("flaw", sorted(FLAWS))
def test_a_flaw_is_reported_by_its_own_check_only(flaw: str) -> None:
    mutate, check, _ = FLAWS[flaw]
    plan = copy.deepcopy(compliant_plan())
    mutate(plan)
    assert set(pa.violations(plan)) <= {check}


def test_a_resource_the_plan_deletes_is_not_judged() -> None:
    plan = compliant_plan()
    add(plan, change("aws_iam_user", "old", {"name": "old"}))
    plan["resource_changes"][-1]["change"]["actions"] = ["delete"]
    assert pa.violations(plan) == {}


def test_a_bucket_is_judged_through_its_references_not_its_position() -> None:
    """A public access block for another bucket does not cover this one."""
    plan = compliant_plan()
    remove(plan, "aws_s3_bucket_public_access_block.logs")
    add(
        plan,
        change(
            "aws_s3_bucket_public_access_block",
            "other",
            {
                "block_public_acls": True,
                "block_public_policy": True,
                "ignore_public_acls": True,
                "restrict_public_buckets": True,
            },
        ),
    )
    plan["configuration"]["root_module"]["resources"].append(
        pa_config("aws_s3_bucket_public_access_block", "other", "evidence")
    )
    assert any("aws_s3_bucket.logs" in p for p in pa.violations(plan)["buckets are private"])


def pa_config(type_: str, name: str, bucket: str) -> dict[str, Any]:
    return configured(type_, name, bucket)


# --- the real plans -----------------------------------------------------------------------------

PLAN_DIR = os.environ.get("ABACUS_TF_PLANS")
REAL_PLANS = sorted(Path(PLAN_DIR).glob("*.json")) if PLAN_DIR else []


@pytest.mark.skipif(not REAL_PLANS, reason="set ABACUS_TF_PLANS to a directory of plan JSON files")
@pytest.mark.parametrize("plan_file", REAL_PLANS, ids=lambda p: p.stem)
def test_real_plan_meets_the_platform_assertions(plan_file: Path) -> None:
    assert pa.violations(pa.load(str(plan_file))) == {}
