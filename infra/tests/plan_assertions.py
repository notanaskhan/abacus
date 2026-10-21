"""Assertions over `terraform show -json` plans (SPEC-050 AC-22 and AC-32; epic Q-01 F2).

Each `check_*` takes the parsed plan and returns a list of violations, empty when the plan is
sound. They hold the properties the spec fixes for every environment:

* no public bucket; every bucket private, TLS-only, versioned and SSE-KMS with a platform key
* Object Lock on `abacus-<env>-evidence` (GOVERNANCE default mode) and `abacus-<env>-records`
  (Object Lock on, no default retention)
* RDS in private subnets, not publicly accessible, `rds.force_ssl=1`,
  `log_parameter_max_length=0` and `log_parameter_max_length_on_error=0`
* security-group egress on 443 (plus 3310 to the scanner) only
* no IAM users, no access keys
* only the allowed regions: us-east-2 and us-west-2, and us-east-1 for the global edge only

Standard library only, so the assertions run anywhere a plan can be read. The plan format is
Terraform's documented JSON representation: `resource_changes[].change.after` for values and
`configuration` for what references what.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

ALLOWED_REGIONS = frozenset({"us-east-2", "us-west-2"})
EDGE_REGION = "us-east-1"
# Resource types that may live in us-east-1: CloudFront, its certificates and its WAF.
EDGE_TYPES = ("aws_cloudfront_", "aws_acm_", "aws_wafv2_", "aws_route53_")
EGRESS_PORTS = frozenset({443, 3310})
IAM_USER_TYPES = frozenset(
    {
        "aws_iam_user",
        "aws_iam_access_key",
        "aws_iam_user_login_profile",
        "aws_iam_user_policy",
        "aws_iam_user_policy_attachment",
        "aws_iam_user_ssh_key",
        "aws_iam_service_specific_credential",
    }
)
PUBLIC_ACLS = frozenset({"public-read", "public-read-write", "authenticated-read"})
DEFAULT_AWS_KEYS = frozenset({"alias/aws/s3", "alias/aws/rds"})


@dataclass(frozen=True)
class Res:
    address: str
    module: str
    type: str
    name: str
    after: dict[str, Any]
    unknown: dict[str, Any]
    refs: dict[str, list[str]] = field(default_factory=lambda: {})
    provider_key: str = "aws"

    def references(self, target: "Res") -> bool:
        """Does this resource point at `target` through any attribute (`aws_s3_bucket.x.id`)?"""
        if self.module != target.module:
            return False  # references are written relative to the module they sit in
        for values in self.refs.values():
            for ref in values:
                parts = _strip_index(ref).split(".")
                if parts[0] not in {"data", "module", "var", "local"} and parts[:2] == [
                    target.type,
                    target.name,
                ]:
                    return True
        return False


def load(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _strip_index(address: str) -> str:
    return re.sub(r"\[[^\]]*\]", "", address)


def _configuration(module: dict[str, Any], prefix: str) -> Iterator[tuple[str, dict[str, Any]]]:
    for resource in module.get("resources", []):
        yield prefix + _strip_index(resource["address"]), resource
    for name, call in module.get("module_calls", {}).items():
        yield from _configuration(call.get("module", {}), f"{prefix}module.{name}.")


def _refs(expressions: dict[str, Any]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for key, value in expressions.items():
        collected: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                collected.extend(node.get("references", []))
                for child in node.values():
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)

        walk(value)
        if collected:
            found[key] = collected
    return found


def resources(plan: dict[str, Any]) -> list[Res]:
    """Managed resources that will exist after the plan (not the ones it deletes)."""
    config = {
        address: resource
        for address, resource in _configuration(
            plan.get("configuration", {}).get("root_module", {}), ""
        )
    }
    found: list[Res] = []
    for change in plan.get("resource_changes", []):
        if change.get("mode", "managed") != "managed":
            continue
        if change["change"].get("actions") == ["delete"]:
            continue
        module = change.get("module_address")
        prefix = f"{module}." if module else ""
        configured = config.get(prefix + _strip_index(f"{change['type']}.{change['name']}"), {})
        found.append(
            Res(
                address=change["address"],
                module=prefix,
                type=change["type"],
                name=change["name"],
                after=change["change"].get("after") or {},
                unknown=change["change"].get("after_unknown") or {},
                refs=_refs(configured.get("expressions", {})),
                provider_key=change.get("provider_config_key", change.get("provider_name", "aws")),
            )
        )
    return found


def _of(plan: dict[str, Any], *types: str) -> list[Res]:
    return [r for r in resources(plan) if r.type in types]


def _block(value: Any) -> dict[str, Any]:
    """Terraform renders a nested block as a one-item list."""
    if isinstance(value, list) and value:
        return value[0] if isinstance(value[0], dict) else {}
    return value if isinstance(value, dict) else {}


def _companions(plan: dict[str, Any], bucket: Res, *types: str) -> list[Res]:
    """Resources of `types` that belong to `bucket`: they reference it, or name it literally."""
    literal = bucket.after.get("bucket")
    return [
        r
        for r in _of(plan, *types)
        if r.references(bucket) or (literal is not None and r.after.get("bucket") == literal)
    ]


def _buckets(plan: dict[str, Any]) -> list[Res]:
    return _of(plan, "aws_s3_bucket")


# --- buckets ------------------------------------------------------------------------------------


def check_buckets_private(plan: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for bucket in _buckets(plan):
        blocks = _companions(plan, bucket, "aws_s3_bucket_public_access_block")
        if not blocks:
            problems.append(f"{bucket.address}: no public access block")
        for block in blocks:
            for setting in (
                "block_public_acls",
                "block_public_policy",
                "ignore_public_acls",
                "restrict_public_buckets",
            ):
                if block.after.get(setting) is not True:
                    problems.append(f"{bucket.address}: {setting} is not true")
        for acl in _companions(plan, bucket, "aws_s3_bucket_acl"):
            if acl.after.get("acl") in PUBLIC_ACLS:
                problems.append(f"{bucket.address}: public ACL {acl.after.get('acl')}")
        if bucket.after.get("acl") in PUBLIC_ACLS:
            problems.append(f"{bucket.address}: public ACL {bucket.after.get('acl')}")
    return problems


def _denies_insecure_transport(policy: Any) -> bool:
    try:
        document = json.loads(policy) if isinstance(policy, str) else policy
    except ValueError:
        return False
    statements = document.get("Statement", []) if isinstance(document, dict) else []
    if isinstance(statements, dict):
        statements = [statements]
    for statement in statements:
        if statement.get("Effect") != "Deny":
            continue
        condition = statement.get("Condition", {}).get("Bool", {})
        value = condition.get("aws:SecureTransport")
        if str(value).lower() == "false" or value == ["false"]:
            return True
    return False


def check_buckets_tls_only(plan: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for bucket in _buckets(plan):
        policies = _companions(plan, bucket, "aws_s3_bucket_policy")
        known = [p for p in policies if isinstance(p.after.get("policy"), (str, dict))]
        if not policies:
            problems.append(f"{bucket.address}: no bucket policy, so no TLS-only deny")
        elif known and not any(_denies_insecure_transport(p.after["policy"]) for p in known):
            problems.append(f"{bucket.address}: no Deny on aws:SecureTransport = false")
    return problems


def check_buckets_versioned_and_encrypted(plan: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for bucket in _buckets(plan):
        versioning = _companions(plan, bucket, "aws_s3_bucket_versioning")
        if not any(
            _block(v.after.get("versioning_configuration")).get("status") == "Enabled"
            for v in versioning
        ):
            problems.append(f"{bucket.address}: versioning is not Enabled")
        encryption = _companions(plan, bucket, "aws_s3_bucket_server_side_encryption_configuration")
        if not encryption:
            problems.append(f"{bucket.address}: no server-side encryption configuration")
        for config in encryption:
            default = _block(_block(config.after.get("rule")).get("apply_server_side_encryption_by_default"))
            if default.get("sse_algorithm") != "aws:kms":
                problems.append(f"{bucket.address}: default encryption is not aws:kms")
            key = default.get("kms_master_key_id")
            if key in (None, "") and "rule" not in config.unknown:
                problems.append(f"{bucket.address}: no platform KMS key named")
            if key in DEFAULT_AWS_KEYS:
                problems.append(f"{bucket.address}: the AWS-managed key is not a platform key")
    return problems


def _lock_enabled(plan: dict[str, Any], bucket: Res) -> bool:
    if bucket.after.get("object_lock_enabled") is True:
        return True
    return any(
        c.after.get("object_lock_enabled") in ("Enabled", True)
        for c in _companions(plan, bucket, "aws_s3_bucket_object_lock_configuration")
    )


def _default_retention(plan: dict[str, Any], bucket: Res) -> dict[str, Any] | None:
    for config in _companions(plan, bucket, "aws_s3_bucket_object_lock_configuration"):
        retention = _block(_block(config.after.get("rule")).get("default_retention"))
        if retention:
            return retention
    return None


def check_object_lock(plan: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for bucket in _buckets(plan):
        name = str(bucket.after.get("bucket", ""))
        if re.fullmatch(r"abacus-[a-z-]+-evidence", name):
            if not _lock_enabled(plan, bucket):
                problems.append(f"{bucket.address}: Object Lock is not enabled")
            retention = _default_retention(plan, bucket)
            if retention is None or retention.get("mode") != "GOVERNANCE":
                problems.append(f"{bucket.address}: default retention mode is not GOVERNANCE")
        elif re.fullmatch(r"abacus-[a-z-]+-records", name):
            if not _lock_enabled(plan, bucket):
                problems.append(f"{bucket.address}: Object Lock is not enabled")
            if _default_retention(plan, bucket) is not None:
                problems.append(
                    f"{bucket.address}: a default retention is set; retention is per object"
                )
    return problems


# --- the database -------------------------------------------------------------------------------


def _parameters(group: Res) -> dict[str, str]:
    raw = group.after.get("parameter") or []
    return {p["name"]: str(p["value"]) for p in raw if "name" in p and "value" in p}


def check_database_private_with_forced_ssl(plan: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    instances = _of(plan, "aws_db_instance", "aws_rds_cluster")
    for instance in instances:
        if instance.after.get("publicly_accessible") is True:
            problems.append(f"{instance.address}: publicly accessible")
        if instance.after.get("storage_encrypted") is not True:
            problems.append(f"{instance.address}: storage is not encrypted")
        if not instance.after.get("db_subnet_group_name") and "db_subnet_group_name" not in instance.unknown:
            problems.append(f"{instance.address}: not in a DB subnet group")
    if instances:
        groups = _of(plan, "aws_db_parameter_group", "aws_rds_cluster_parameter_group")
        wanted = {
            "rds.force_ssl": "1",
            "log_parameter_max_length": "0",
            "log_parameter_max_length_on_error": "0",
        }
        if not any(all(_parameters(g).get(k) == v for k, v in wanted.items()) for g in groups):
            problems.append(
                "no parameter group sets rds.force_ssl=1, log_parameter_max_length=0 and "
                "log_parameter_max_length_on_error=0"
            )
    return problems


# --- the network --------------------------------------------------------------------------------


def _egress_problem(owner: str, rule: dict[str, Any]) -> str | None:
    protocol = str(rule.get("protocol", rule.get("ip_protocol", "tcp")))
    low = rule.get("from_port")
    high = rule.get("to_port")
    if protocol in {"-1", "all"} or low is None or high is None:
        return f"{owner}: egress on every protocol or port"
    if protocol != "tcp":
        return f"{owner}: egress on {protocol}"
    if low != high or int(low) not in EGRESS_PORTS:
        return f"{owner}: egress on ports {low}-{high}; only 443 (and 3310 to the scanner)"
    return None


def check_egress_443_only(plan: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for group in _of(plan, "aws_security_group"):
        for rule in group.after.get("egress") or []:
            problem = _egress_problem(group.address, rule)
            if problem:
                problems.append(problem)
    for rule in _of(plan, "aws_vpc_security_group_egress_rule"):
        problem = _egress_problem(rule.address, rule.after)
        if problem:
            problems.append(problem)
    for rule in _of(plan, "aws_security_group_rule"):
        if rule.after.get("type") == "egress":
            problem = _egress_problem(rule.address, rule.after)
            if problem:
                problems.append(problem)
    return problems


# --- identities and regions ---------------------------------------------------------------------


def check_no_iam_users(plan: dict[str, Any]) -> list[str]:
    return [f"{r.address}: IAM users and access keys are not allowed" for r in resources(plan) if r.type in IAM_USER_TYPES]


def check_allowed_regions(plan: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    providers = plan.get("configuration", {}).get("provider_config", {})
    edge_keys: set[str] = set()
    for key, provider in providers.items():
        if not key.split(".")[0] == "aws":
            continue
        region = provider.get("expressions", {}).get("region", {}).get("constant_value")
        if region is None:
            problems.append(f"provider {key}: region is not a literal")
        elif region == EDGE_REGION:
            edge_keys.add(key)
        elif region not in ALLOWED_REGIONS:
            problems.append(f"provider {key}: region {region} is not allowed")
    for resource in resources(plan):
        if resource.provider_key in edge_keys and not resource.type.startswith(EDGE_TYPES):
            problems.append(f"{resource.address}: {EDGE_REGION} is for the global edge only")
        region = resource.after.get("region")
        if isinstance(region, str) and region not in ALLOWED_REGIONS | {EDGE_REGION}:
            problems.append(f"{resource.address}: region {region} is not allowed")
    return problems


CHECKS = {
    "buckets are private": check_buckets_private,
    "buckets are TLS-only": check_buckets_tls_only,
    "buckets are versioned and SSE-KMS": check_buckets_versioned_and_encrypted,
    "Object Lock": check_object_lock,
    "database is private with forced SSL": check_database_private_with_forced_ssl,
    "egress is 443 only": check_egress_443_only,
    "no IAM users": check_no_iam_users,
    "allowed regions": check_allowed_regions,
}


def violations(plan: dict[str, Any]) -> dict[str, list[str]]:
    """Every check's violations, keyed by check; checks with none are omitted."""
    found = {name: check(plan) for name, check in CHECKS.items()}
    return {name: problems for name, problems in found.items() if problems}
