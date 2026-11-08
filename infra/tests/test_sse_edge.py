"""P-10-T15 (SPEC-647 AC-T1, AC-T5; P-10 §7): the SSE edge path. CloudFront sends every viewer
header to the API, `Last-Event-ID` included, and never caches or compresses a stream; the VPC
origin waits 60 s for bytes (heartbeats every 15 s); the internal ALB's idle timeout is 120 s; the
WAF's general rate rule does not count streams. Offline: the Terraform is read as text and the
WAF regex is exercised with Python's `re` (the pattern uses only syntax both engines share).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

INFRA = Path(__file__).resolve().parents[1]
FIRM = (INFRA / "modules" / "cloudfront-firm" / "main.tf").read_text(encoding="utf-8")
WAF = (INFRA / "modules" / "waf" / "main.tf").read_text(encoding="utf-8")
WAF_VARS = (INFRA / "modules" / "waf" / "variables.tf").read_text(encoding="utf-8")
STAGING = (INFRA / "envs" / "staging" / "compute.tf").read_text(encoding="utf-8")


def _block(text: str, start: str) -> str:
    """The `{ … }` block that opens on the first line containing `start`."""
    index = text.index(start)
    depth = 0
    for position in range(text.index("{", index), len(text)):
        depth += {"{": 1, "}": -1}.get(text[position], 0)
        if depth == 0:
            return text[index : position + 1]
    raise AssertionError(start)


def _stream_regex() -> re.Pattern[str]:
    block = _block(WAF_VARS, 'variable "stream_path_regex"')
    match = re.search(r'default\s*=\s*"(.*)"', block)
    assert match
    return re.compile(match.group(1).replace("\\\\", "\\"))


def test_the_stream_behavior_comes_before_v1_and_never_buffers() -> None:
    stream = FIRM.index('path_pattern               = "/v1/*events"')
    assert stream < FIRM.index('path_pattern               = "/v1/*"')
    behavior = FIRM[FIRM.rfind("ordered_cache_behavior", 0, stream) :]
    behavior = _block(behavior, "ordered_cache_behavior")
    assert (
        "cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id"
        in behavior
    )
    assert "compress                   = false" in behavior
    assert '"GET", "HEAD", "OPTIONS"' in behavior


def test_every_viewer_header_reaches_the_api_last_event_id_included() -> None:
    # AWS's managed "AllViewerExceptHostHeader" forwards all viewer headers but Host.
    assert 'name = "Managed-AllViewerExceptHostHeader"' in FIRM
    behavior = _block(
        FIRM[FIRM.index('"/v1/*events"') - 200 :], "ordered_cache_behavior"
    )
    assert "all_viewer_except_host.id" in behavior


def test_the_vpc_origin_waits_past_the_heartbeat() -> None:
    origin = _block(FIRM, "vpc_origin_config {")
    assert "origin_read_timeout      = 60" in origin
    assert "origin_keepalive_timeout = 60" in origin


def test_the_internal_alb_idle_timeout_is_120_seconds() -> None:
    alb = _block(STAGING, 'resource "aws_lb" "api"')
    assert "idle_timeout = 120" in alb


@pytest.mark.parametrize(
    "path",
    [
        "/v1/events",
        "/v1/me/agent-events",
        "/v1/agent-runs/3f1c0b7e-0000-4000-8000-000000000001/events",
        "/v1/workbench/sessions/3f1c0b7e-0000-4000-8000-000000000002/events",
    ],
)
def test_streams_are_not_counted_by_the_general_rate(path: str) -> None:
    assert _stream_regex().search(path.lower())


@pytest.mark.parametrize(
    "path",
    [
        "/v1/me",
        "/v1/agent-runs/abc",
        "/v1/agent-runs/abc/events/extra",
        "/v1/engagements/abc/runs",
        "/v1/events/123",
        "/v1/audit/events",
    ],
)
def test_everything_else_still_counts(path: str) -> None:
    assert not _stream_regex().search(path.lower())


def test_the_general_rule_scopes_streams_out() -> None:
    general = _block(WAF[WAF.index('name     = "general-rate"') - 20 :], "rule {")
    assert "not_statement" in general
    assert "regex_string = var.stream_path_regex" in general
