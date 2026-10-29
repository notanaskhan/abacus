"""Q-01-T15 (ADR-152; the row's acceptance): the firm distribution answers /readyz and /healthz with
403 at the edge, carries the security headers policy and sends /v1 to the internal ALB's VPC origin.
Offline: the CloudFront Function runs under node; the Terraform is read as text."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

INFRA = Path(__file__).resolve().parents[1]
FIRM = INFRA / "modules" / "cloudfront-firm"
FUNCTION = FIRM / "firm-edge.js"


def run_edge(uri: str) -> dict[str, Any]:
    node = shutil.which("node")
    assert node, "node runs the CloudFront Function under test"
    event = {"request": {"uri": uri, "headers": {}}}
    script = (
        FUNCTION.read_text(encoding="utf-8")
        + f"\nprocess.stdout.write(JSON.stringify(handler({json.dumps(event)})));\n"
    )
    result = subprocess.run(  # noqa: S603 - our own function file, run by node
        [node, "-e", script], capture_output=True, text=True, check=True, timeout=30
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("uri", ["/healthz", "/readyz", "/HEALTHZ", "/readyz/", "/ReadyZ"])
def test_probes_answer_403_at_the_edge(uri: str) -> None:
    assert run_edge(uri)["statusCode"] == 403


@pytest.mark.parametrize("uri", ["/", "/home", "/v1/me", "/assets/index-3f9a.js", "/readyzz"])
def test_everything_else_passes_unchanged(uri: str) -> None:
    assert run_edge(uri)["uri"] == uri


def test_v1_goes_to_the_vpc_origin_with_the_security_headers() -> None:
    main = (FIRM / "main.tf").read_text(encoding="utf-8")
    assert "vpc_origin_config" in main
    assert 'path_pattern               = "/v1/*"' in main
    assert main.count("response_headers_policy_id = aws_cloudfront_response_headers_policy.firm.id") == 2
    assert "content_security_policy" in main
