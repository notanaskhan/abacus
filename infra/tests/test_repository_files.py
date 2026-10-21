"""Q-01-T24 / SPEC-050 AC-1, AC-2, AC-22 and AC-32: what can be asserted about `infra/` offline.

No plan, no credentials: these read the policy documents in `infra/landing-zone/` and the Terraform
source files, and hold them to the spec. They apply to every environment as it lands (T14 onward):
a bucket added to `infra/` without a public access block, an IAM user, or a provider in another
region fails here before any plan is made.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

INFRA = Path(__file__).resolve().parents[1]
LANDING_ZONE = INFRA / "landing-zone"
TF_FILES = sorted(p for p in INFRA.rglob("*.tf") if ".terraform" not in p.parts)
ALLOWED_REGIONS = {"us-east-2", "us-west-2"}
# Services the spec lets run outside the two US regions (epic Q-01 F1): the global edge and Bedrock
# US Geo inference, plus IAM, Organizations and billing, which are global.
EDGE_SERVICES = {"acm", "bedrock", "cloudfront", "waf", "wafv2", "shield"}
DATA_SERVICES = {
    "s3", "rds", "kms", "ec2", "ecs", "ecr", "lambda", "ses", "sesv2", "dynamodb", "sqs", "sns",
    "secretsmanager", "ssm", "logs", "elasticloadbalancing", "backup", "states", "events",
}  # fmt: skip


def policy(name: str) -> dict[str, Any]:
    return json.loads((LANDING_ZONE / name).read_text(encoding="utf-8"))


def statements(document: dict[str, Any]) -> list[dict[str, Any]]:
    found = document["Statement"]
    return [found] if isinstance(found, dict) else found


def as_list(value: Any) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


# --- the service control policies ---------------------------------------------------------------


def test_the_baseline_policy_denies_iam_users_and_access_keys_everywhere() -> None:
    denied: set[str] = set()
    for statement in statements(policy("scp-baseline-guards.json")):
        if statement["Effect"] == "Deny" and statement["Resource"] == "*":
            denied |= set(as_list(statement.get("Action", [])))
    assert {"iam:CreateUser", "iam:CreateAccessKey"} <= denied


def test_the_baseline_policy_has_no_allow_statement_that_could_grant_iam_users() -> None:
    for statement in statements(policy("scp-baseline-guards.json")):
        if statement["Effect"] == "Allow":
            actions = as_list(statement.get("Action", []))
            assert not any(a in {"*", "iam:*", "iam:CreateUser"} for a in actions)


def region_condition(statement: dict[str, Any]) -> list[str]:
    condition = statement.get("Condition", {}).get("StringNotEquals", {})
    return as_list(condition.get("aws:RequestedRegion", []))


def test_regional_apis_outside_us_east_2_and_us_west_2_are_denied() -> None:
    guards = [
        s
        for s in statements(policy("scp-region-guard.json"))
        if s["Effect"] == "Deny" and "NotAction" in s
    ]
    assert len(guards) == 1
    assert set(region_condition(guards[0])) == ALLOWED_REGIONS


def test_the_global_exemptions_do_not_cover_data_services() -> None:
    (guard,) = [s for s in statements(policy("scp-region-guard.json")) if "NotAction" in s]
    exempt = {a.split(":")[0] for a in as_list(guard["NotAction"])}
    assert exempt & DATA_SERVICES == set()


def test_us_east_1_is_open_to_the_global_edge_and_bedrock_only() -> None:
    edge = [
        s
        for s in statements(policy("scp-region-guard.json"))
        if s["Effect"] == "Deny" and "Action" in s and region_condition(s)
    ]
    assert edge, "the policy has no statement that limits what us-east-1 may host"
    for statement in edge:
        assert set(region_condition(statement)) == ALLOWED_REGIONS | {"us-east-1"}
        assert {a.split(":")[0] for a in as_list(statement["Action"])} <= EDGE_SERVICES


def test_the_policies_name_no_account_or_key() -> None:
    for name in ("scp-baseline-guards.json", "scp-region-guard.json", "ai-services-opt-out.json"):
        text = (LANDING_ZONE / name).read_text(encoding="utf-8")
        assert not re.search(r"\b\d{12}\b", text), f"{name} carries a 12-digit account ID"
        assert not re.search(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", text)


# --- the Terraform source -----------------------------------------------------------------------

BLOCK = re.compile(r'^\s*(resource|data|provider|variable)\s+"([^"]+)"(?:\s+"([^"]+)")?\s*\{', re.M)


def blocks(text: str) -> list[tuple[str, str, str, str]]:
    """(kind, type, name, body) for each top-level resource, data and provider block."""
    found: list[tuple[str, str, str, str]] = []
    for match in BLOCK.finditer(text):
        depth, index = 1, match.end()
        while depth and index < len(text):
            depth += {"{": 1, "}": -1}.get(text[index], 0)
            index += 1
        found.append((match.group(1), match.group(2), match.group(3) or "", text[match.end() : index - 1]))
    return found


def all_blocks() -> list[tuple[Path, str, str, str, str]]:
    return [
        (path, kind, type_, name, body)
        for path in TF_FILES
        for kind, type_, name, body in blocks(path.read_text(encoding="utf-8"))
    ]


def test_there_is_terraform_to_check() -> None:
    assert TF_FILES
    assert any(kind == "resource" for _, kind, *_ in all_blocks())


def test_no_iam_user_or_access_key_is_declared() -> None:
    declared = [
        f"{path.relative_to(INFRA)}: {type_}.{name}"
        for path, kind, type_, name, _ in all_blocks()
        if kind == "resource"
        and type_
        in {"aws_iam_user", "aws_iam_access_key", "aws_iam_user_login_profile", "aws_iam_user_policy_attachment"}
    ]
    assert declared == []


def provider_region(path: Path, body: str) -> str:
    """The provider's region: a literal, or the default of the variable it names."""
    match = re.search(r'^\s*region\s*=\s*(?:"([a-z0-9-]+)"|var\.(\w+))', body, re.M)
    assert match, f"{path.relative_to(INFRA)}: the provider region is neither a literal nor a variable"
    if match.group(1):
        return match.group(1)
    declared = [
        variable
        for p, kind, type_, name, variable in all_blocks()
        if p.parent == path.parent and kind == "variable" and type_ == match.group(2)
    ]
    default = re.search(r'default\s*=\s*"([a-z0-9-]+)"', declared[0]) if declared else None
    assert default, f"{path.relative_to(INFRA)}: variable {match.group(2)} has no literal default"
    return default.group(1)


def test_every_aws_provider_is_in_an_allowed_region() -> None:
    providers = [(p, body) for p, kind, type_, _, body in all_blocks() if kind == "provider" and type_ == "aws"]
    assert providers
    for path, body in providers:
        region = provider_region(path, body)
        edge = "us-east-1" if re.search(r'alias\s*=\s*"(?:edge|us_east_1|cloudfront)"', body) else None
        assert region in ALLOWED_REGIONS or region == edge, f"{path.relative_to(INFRA)}: {region}"


def test_no_literal_region_outside_the_allowed_ones() -> None:
    for path in TF_FILES:
        for region in re.findall(r'"((?:us|eu|ap|sa|ca|me|af|il|mx)-[a-z]+-\d)"', path.read_text(encoding="utf-8")):
            assert region in ALLOWED_REGIONS | {"us-east-1"}, f"{path.relative_to(INFRA)}: {region}"


def sibling_bodies(path: Path, type_: str) -> list[str]:
    return [body for p, kind, t, _, body in all_blocks() if p.parent == path.parent and kind == "resource" and t == type_]


def test_every_bucket_declared_has_a_complete_public_access_block() -> None:
    buckets = [(p, n) for p, kind, t, n, _ in all_blocks() if kind == "resource" and t == "aws_s3_bucket"]
    assert buckets
    for path, name in buckets:
        mine = [b for b in sibling_bodies(path, "aws_s3_bucket_public_access_block") if f"aws_s3_bucket.{name}." in b]
        assert mine, f"{path.relative_to(INFRA)}: bucket {name} has no public access block"
        for setting in ("block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"):
            assert re.search(rf"{setting}\s*=\s*true\b", mine[0]), f"{name}: {setting}"


def test_every_bucket_declared_is_versioned_and_encrypted_with_kms() -> None:
    buckets = [(p, n) for p, kind, t, n, _ in all_blocks() if kind == "resource" and t == "aws_s3_bucket"]
    for path, name in buckets:
        versioning = [b for b in sibling_bodies(path, "aws_s3_bucket_versioning") if f"aws_s3_bucket.{name}." in b]
        assert versioning and re.search(r'status\s*=\s*"Enabled"', versioning[0]), f"{name}: versioning"
        encryption = [
            b
            for b in sibling_bodies(path, "aws_s3_bucket_server_side_encryption_configuration")
            if f"aws_s3_bucket.{name}." in b
        ]
        assert encryption, f"{name}: no encryption configuration"
        assert 'sse_algorithm     = "aws:kms"' in encryption[0] or re.search(r'sse_algorithm\s*=\s*"aws:kms"', encryption[0])
        assert re.search(r"kms_master_key_id\s*=", encryption[0]), f"{name}: no platform key named"


def test_every_bucket_declared_denies_plain_http() -> None:
    buckets = [(p, n) for p, kind, t, n, _ in all_blocks() if kind == "resource" and t == "aws_s3_bucket"]
    for path, name in buckets:
        texts = [
            body
            for p, kind, t, _, body in all_blocks()
            if p.parent == path.parent and t in {"aws_iam_policy_document", "aws_s3_bucket_policy"} and f"aws_s3_bucket.{name}." in body
        ]
        assert any("aws:SecureTransport" in text and re.search(r'"false"', text) for text in texts), (
            f"{path.relative_to(INFRA)}: bucket {name} has no aws:SecureTransport deny"
        )


def test_the_state_bucket_is_never_public_and_never_hand_removed() -> None:
    text = (INFRA / "bootstrap" / "state.tf").read_text(encoding="utf-8")
    assert re.search(r"prevent_destroy\s*=\s*true", text)
    assert "public-read" not in text
