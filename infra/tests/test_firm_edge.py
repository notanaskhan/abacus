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


def run_edge(uri: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    node = shutil.which("node")
    assert node, "node runs the CloudFront Function under test"
    sent = {name: {"value": value} for name, value in (headers or {}).items()}
    event = {"request": {"uri": uri, "headers": sent}}
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
    # P-10-T15: the SSE stream behavior carries the headers policy too.
    assert main.count("response_headers_policy_id = aws_cloudfront_response_headers_policy.firm.id") == 3
    assert "content_security_policy" in main


# --- TASK-6990 (DEC-3990): the viewer's host reaches the API as X-Forwarded-Host -----------------
# Managed-AllViewerExceptHostHeader sends the ALB's name as `Host`, so the firm app's host reaches
# the API only through the function, and a value the viewer sent is never passed on (the API
# believes X-Forwarded-Host from the load balancer).


def test_v1_carries_the_viewer_host_as_x_forwarded_host_and_never_a_forged_one() -> None:
    result = run_edge(
        "/v1/me", {"host": "app.firm-domain.example.test", "x-forwarded-host": "evil.example.test"}
    )
    assert result["uri"] == "/v1/me"
    assert result["headers"]["x-forwarded-host"] == {"value": "app.firm-domain.example.test"}


def test_a_forged_x_forwarded_host_is_dropped_when_the_viewer_sent_no_host() -> None:
    result = run_edge("/v1/me", {"x-forwarded-host": "evil.example.test"})
    assert "x-forwarded-host" not in result["headers"]


def test_the_spa_passes_unchanged() -> None:
    result = run_edge("/home", {"host": "app.firm-domain.example.test"})
    assert result["uri"] == "/home"
    assert "x-forwarded-host" not in result["headers"]


def test_both_v1_behaviors_run_the_function() -> None:
    """The default behavior and both /v1 behaviors (the API and its event streams)."""
    main = (FIRM / "main.tf").read_text(encoding="utf-8")
    assert main.count("function_arn = aws_cloudfront_function.edge_block.arn") == 3
