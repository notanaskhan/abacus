"""N-01-T24 (pen-test delta #1 readiness): the WAF's file-route rules, checked offline.

- Rule 21's body-size block exempts every file route, so a staff-logged intake file and a raw-body
  import (both well over the common rule set's 8 KB body inspection) reach the API, which caps each
  route itself; JSON routes stay inside the block.
- Rule 3 rate-limits the same routes; rule 22 refuses a Content-Length of 64,000,000 bytes or more
  there with 413, above the scanner's 60 MiB stream limit, and nothing below it.

No plan and no credentials: the Terraform source is read as text and the variables' defaults are
exercised with Python's `re` (the patterns use only syntax RE2 shares).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WAF = REPO / "infra" / "modules" / "waf"


def _default(name: str) -> str:
    source = (WAF / "variables.tf").read_text(encoding="utf-8")
    block = source[source.index(f'variable "{name}"') :]
    found = re.search(r'default\s*=\s*"((?:[^"\\]|\\.)*)"', block)
    assert found, name
    return found.group(1).replace("\\\\", "\\")


UPLOADS = re.compile(_default("upload_path_regex"))
TOO_LARGE = re.compile(_default("upload_max_content_length_regex"))
SCANNER_STREAM_MAX = 60 * 1024 * 1024  # backend kernel.scanning.STREAM_MAX_BYTES (ADR-153)


@pytest.mark.parametrize(
    "path",
    [
        "/v1/inbox/intake/3f9a5e62-1c4d-4b8e-9f20-7a6b5c4d3e21/files",  # staff-logged intake
        "/v1/portal/intake-uploads",
        "/v1/portal/intake-uploads/3f9a5e62-1c4d-4b8e-9f20-7a6b5c4d3e21/files",
        "/v1/engagements/3f9a5e62/request-items/3f9a5e62/uploads",
        "/v1/tax-returns/3f9a5e62/engine-imports",
        "/v1/standards/imports",
        "/v1/questionnaire-templates:import",
        "/v1/report-templates/import",
        "/v1/envelopes/import/files",
    ],
)
def test_file_routes_are_file_routes(path: str) -> None:
    assert UPLOADS.match(path.lower()), path


@pytest.mark.parametrize(
    "path",
    [
        "/v1/inbox/threads",
        "/v1/inbox/messages/3f9a5e62/triage/apply",
        "/v1/portal/envelopes/3f9a5e62/signing-session",
        "/v1/auth/sign-in",
        "/v1/inbox/intake/3f9a5e62/files/extra",
        "/v1/inbox/intake",
    ],
)
def test_other_routes_keep_the_body_size_block(path: str) -> None:
    assert not UPLOADS.match(path.lower()), path


@pytest.mark.parametrize(
    "length",
    ["0", "8192", str(50 * 1024 * 1024), str(SCANNER_STREAM_MAX), "63999999"],
)
def test_a_legitimate_upload_size_passes_the_edge(length: str) -> None:
    assert not TOO_LARGE.match(length)


@pytest.mark.parametrize(
    "length", ["64000000", "69999999", "70000000", "99999999", "100000000", "21474836480"]
)
def test_an_oversized_upload_is_refused_at_the_edge(length: str) -> None:
    assert TOO_LARGE.match(length)


def test_the_rules_are_in_the_webacl_in_order_and_block() -> None:
    main = (WAF / "main.tf").read_text(encoding="utf-8")
    for name, priority in (("upload-rate", 3), ("upload-size-cap", 22)):
        at = main.index(f'name     = "{name}"')
        assert f"priority = {priority}" in main[at : at + 80], name
        rule = main[at : main.index("visibility_config", at)]
        assert "block {" in rule and "count {}" not in rule, name  # never count-only
    cap = main[main.index('name     = "upload-size-cap"') :]
    assert "response_code            = 413" in cap[:400]
    assert 'name = "content-length"' in cap
    assert '"too_large"' in main
