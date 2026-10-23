"""Q-01-T56 (OPS-14 part; ADR-163): the portal edge, checked offline.

"The canary custom host serves the portal entry with its own certificate on the same /v1 origin,
and the 31st auth request in 5 minutes from one IP is blocked." No plan and no credentials: these
hold the Terraform source and the entry function to that sentence. The live half (a request to the
canary host, and 31 sign-in requests from one address) is the builder's, after the staging apply
(infra/README.md, "Portal edge").
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
INFRA = REPO / "infra"
PORTAL = INFRA / "modules" / "cloudfront-portal"
WAF = INFRA / "modules" / "waf"
STAGING = INFRA / "envs" / "staging"
ENTRY = PORTAL / "portal-entry.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def block(source: str, header: str) -> str:
    """The body of the first block whose opening line matches `header` (a regex)."""
    match = re.search(header + r"\s*\{", source)
    assert match, f"no block {header!r}"
    depth, index = 1, match.end()
    while depth and index < len(source):
        depth += {"{": 1, "}": -1}.get(source[index], 0)
        index += 1
    return source[match.end() : index - 1]


def enclosing(source: str, marker: str) -> str:
    """The body of the innermost block containing `marker` (a literal)."""
    at = source.index(marker)
    depth, start = 0, at
    while start > 0:
        start -= 1
        if source[start] == "}":
            depth += 1
        elif source[start] == "{":
            if depth == 0:
                break
            depth -= 1
    depth, index = 1, start + 1
    while depth and index < len(source):
        depth += {"{": 1, "}": -1}.get(source[index], 0)
        index += 1
    return source[start + 1 : index - 1]


def default(variables: str, name: str) -> Any:
    body = block(variables, rf'variable\s+"{name}"')
    found = re.search(r"^\s*default\s*=\s*(.+)$", body, re.M)
    assert found, f"variable {name} has no default"
    return json.loads(found.group(1))


# --- the auth and code rate rule ----------------------------------------------------------------


def auth_rule() -> str:
    return enclosing(text(WAF / "main.tf"), '"auth-and-code-rate"')


def auth_regex() -> re.Pattern[str]:
    paths = default(text(WAF / "variables.tf"), "auth_rate_limit_paths")
    # The module builds the same expression: "^(?:${join("|", var.auth_rate_limit_paths)})".
    assert 'auth_paths  = "^(?:${join("|", var.auth_rate_limit_paths)})"' in text(WAF / "main.tf")
    return re.compile("^(?:" + "|".join(paths) + ")")


def test_the_31st_auth_request_in_5_minutes_from_one_ip_is_blocked() -> None:
    variables = text(WAF / "variables.tf")
    assert default(variables, "auth_rate_limit") == 30
    assert default(variables, "rate_window_seconds") == 300
    rule = auth_rule()
    assert re.search(r"limit\s*=\s*var\.auth_rate_limit\b", rule)
    assert re.search(r"evaluation_window_sec\s*=\s*var\.rate_window_seconds\b", rule)
    assert re.search(r'aggregate_key_type\s*=\s*"IP"', rule)
    action = block(rule, r"action")
    assert "block" in action and "count" not in action, "the auth rule always blocks"
    assert re.search(r"response_code\s*=\s*429", action)


def test_the_auth_rate_rule_runs_first_and_never_in_count_mode() -> None:
    assert re.search(r"priority\s*=\s*0\b", auth_rule())
    assert "managed_rules_action" not in auth_rule()


@pytest.mark.parametrize(
    "path",
    [
        "/v1/auth/sign-in",
        "/v1/auth/callback",
        "/v1/auth/refresh",
        "/v1/portal/auth/start",
        "/v1/portal/auth/verify",
        "/v1/portal/auth/resend",
        "/v1/portal/auth/mfa",
    ],
)
def test_staff_and_portal_sign_in_and_code_paths_are_counted(path: str) -> None:
    assert auth_regex().match(path)


@pytest.mark.parametrize("path", ["/v1/portal/branding", "/v1/me", "/portal.html", "/sign-in"])
def test_other_paths_are_not_counted_by_the_auth_rule(path: str) -> None:
    assert not auth_regex().match(path)


def test_the_portal_contracts_code_entry_route_is_counted() -> None:
    contract = text(REPO / "docs" / "contracts" / "portal-identity.md")
    routes = set(re.findall(r"POST (/v1/portal/auth/[a-z-]+)", contract))
    assert routes, "the portal identity contract names no sign-in route"
    assert all(auth_regex().match(route) for route in routes)


def test_staging_attaches_the_webacl_to_the_portal_distribution() -> None:
    wiring = text(STAGING / "portal_edge.tf")
    assert re.search(r"web_acl_arn\s*=\s*module\.portal_waf\[0\]\.arn", wiring)
    assert re.search(r"web_acl_id\s*=\s*var\.web_acl_arn", text(PORTAL / "main.tf"))
    assert re.search(r'scope\s*=\s*"CLOUDFRONT"', text(WAF / "main.tf"))


def test_waf_logging_redacts_credentials_and_cookies() -> None:
    logging = block(
        text(WAF / "main.tf"), r'resource\s+"aws_wafv2_web_acl_logging_configuration"\s+"this"'
    )
    headers = re.findall(r'name\s*=\s*"([a-z-]+)"', logging)
    assert set(headers) == {"authorization", "cookie"}


# --- the distribution, its tenants and the same /v1 origin --------------------------------------


def distribution() -> str:
    return block(
        text(PORTAL / "main.tf"),
        r'resource\s+"aws_cloudfront_multitenant_distribution"\s+"portal"',
    )


def test_the_portal_is_one_multi_tenant_distribution_and_never_a_per_domain_one() -> None:
    main = text(PORTAL / "main.tf")
    assert 'resource "aws_cloudfront_multitenant_distribution" "portal"' in main
    assert 'resource "aws_cloudfront_distribution" ' not in main


def test_the_default_tenant_is_the_neutral_wildcard_host() -> None:
    tenant = block(
        text(PORTAL / "main.tf"), r'resource\s+"aws_cloudfront_distribution_tenant"\s+"default"'
    )
    assert re.search(r'domain\s*=\s*"\*\.\$\{var\.portal_base_domain\}"', tenant)
    assert re.search(
        r"distribution_id\s*=\s*aws_cloudfront_multitenant_distribution\.portal\.id", tenant
    )
    cert = block(text(PORTAL / "main.tf"), r'resource\s+"aws_acm_certificate"\s+"portal"')
    assert re.search(r'domain_name\s*=\s*"\*\.\$\{var\.portal_base_domain\}"', cert)
    assert re.search(r"region\s*=\s*local\.edge_region", cert)


def test_the_canary_tenant_has_its_own_managed_certificate_on_the_same_distribution() -> None:
    tenant = block(
        text(PORTAL / "main.tf"), r'resource\s+"aws_cloudfront_distribution_tenant"\s+"canary"'
    )
    assert re.search(
        r"distribution_id\s*=\s*aws_cloudfront_multitenant_distribution\.portal\.id", tenant
    )
    request = block(tenant, r"managed_certificate_request")
    assert re.search(r"primary_domain_name\s*=\s*var\.canary_custom_domain", request)
    assert re.search(r'validation_token_host\s*=\s*"cloudfront"', request)
    assert re.search(r"domain\s*=\s*var\.canary_custom_domain", block(tenant, r"domain"))
    # Tenants carry no origin or behaviour of their own: the canary serves the same entry and /v1.
    assert "origin" not in tenant and "cache_behavior" not in tenant


def test_v1_goes_same_origin_to_the_api_through_the_vpc_origin_uncached() -> None:
    dist = distribution()
    api = [
        b
        for b in re.split(r"\n  cache_behavior\s*\{", dist)
        if 'path_pattern               = "/v1/*"' in b
    ]
    assert api, "no /v1/* behaviour"
    assert "target_origin_id           = local.api_origin" in api[0]
    assert "data.aws_cloudfront_cache_policy.disabled.id" in api[0]
    assert "Managed-AllViewerExceptHostHeader" in text(PORTAL / "main.tf")
    assert re.search(r"vpc_origin_id\s*=\s*var\.api_vpc_origin_id", dist)


def test_the_edge_keeps_tls_1_2_and_the_portal_headers() -> None:
    dist = distribution()
    assert 'minimum_protocol_version = "TLSv1.2_2021"' in dist
    assert 'ssl_support_method       = "sni-only"' in dist
    headers = block(
        text(PORTAL / "main.tf"), r'resource\s+"aws_cloudfront_response_headers_policy"\s+"portal"'
    )
    assert 'referrer_policy = "no-referrer"' in headers
    assert "access_control_max_age_sec = 63072000" in headers
    assert "include_subdomains         = true" in headers
    assert "camera=(self), microphone=(), geolocation=()" in headers


def test_the_portal_csp_header_is_the_builds_csp() -> None:
    vite = text(REPO / "apps" / "web" / "vite.config.ts")
    policy = re.search(r"const policy = \[(.*?)\]\.join", vite, re.S)
    assert policy, "vite.config.ts no longer builds its CSP from a list"
    directives = re.findall(r'"([a-z-]+ [^"]+)"', policy.group(1))
    assert directives
    assert default(text(PORTAL / "variables.tf"), "content_security_policy") == "; ".join(
        directives
    )


# --- the portal entry function ------------------------------------------------------------------


def run_entry(uri: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    node = shutil.which("node")
    assert node, "node runs the CloudFront Function under test"
    event = {
        "request": {"uri": uri, "headers": {k: {"value": v} for k, v in (headers or {}).items()}}
    }
    script = (
        text(ENTRY) + f"\nprocess.stdout.write(JSON.stringify(handler({json.dumps(event)})));\n"
    )
    result = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True, timeout=30
    )  # noqa: S603 - our own function file, run by node
    return json.loads(result.stdout)


@pytest.mark.parametrize("uri", ["/", "/sign-in", "/accept", "/documents", "/documents/abc"])
def test_portal_routes_at_the_origin_root_are_served_the_portal_entry(uri: str) -> None:
    assert run_entry(uri)["uri"] == "/portal.html"


@pytest.mark.parametrize(
    "uri", ["/assets/index-3f9a.js", "/runtime-config.json", "/portal.html", "/favicon.svg"]
)
def test_files_pass_through_unchanged(uri: str) -> None:
    assert run_entry(uri)["uri"] == uri


@pytest.mark.parametrize("uri", ["/healthz", "/readyz", "/HEALTHZ", "/readyz/"])
def test_probes_answer_403_at_the_edge(uri: str) -> None:
    assert run_entry(uri)["statusCode"] == 403


def test_v1_carries_the_viewer_host_as_x_forwarded_host_and_never_a_forged_one() -> None:
    result = run_entry(
        "/v1/portal/branding",
        {
            "host": "firm-slug.portal-domain.example.test",
            "x-forwarded-host": "other-firm.example.test",
        },
    )
    assert result["uri"] == "/v1/portal/branding"
    assert result["headers"]["x-forwarded-host"] == {
        "value": "firm-slug.portal-domain.example.test"
    }


# --- ADR-163: a setting, never a literal; never the product name -------------------------------


def portal_edge_sources() -> list[Path]:
    return [*PORTAL.glob("*.tf"), *WAF.glob("*.tf"), *STAGING.glob("*.tf"), ENTRY]


def test_no_portal_edge_file_writes_a_domain_literal() -> None:
    for path in portal_edge_sources():
        source = re.sub(r"(?m)^\s*(#|//).*$", "", text(path))
        for literal in re.findall(
            r'"([^"\s$]*\.(?:com|net|org|io|app|co|cloud|dev|test))"', source
        ):
            assert literal.endswith(".amazonaws.com"), f"{path.relative_to(REPO)}: {literal}"


def test_the_product_name_appears_only_in_the_check_that_refuses_it() -> None:
    for path in portal_edge_sources():
        for line in text(path).splitlines():
            if "accrued" in line.lower():
                assert re.search(r'strcontains\(lower\(var\.\w+\), "accrued"\)', line), (
                    f"{path.relative_to(REPO)}: {line.strip()}"
                )


def test_the_portal_domain_variable_refuses_the_product_name() -> None:
    body = block(text(PORTAL / "variables.tf"), r'variable\s+"portal_base_domain"')
    assert 'strcontains(lower(var.portal_base_domain), "accrued")' in body
    assert not re.search(r"^\s*default\s*=", body, re.M), "no default: the domain is a setting"


def test_the_portal_edge_plans_to_nothing_until_its_settings_exist() -> None:
    variables = text(STAGING / "variables.tf")
    for name in (
        "portal_base_domain",
        "api_vpc_origin_id",
        "api_origin_domain_name",
        "portal_canary_custom_domain",
    ):
        assert re.search(r"default\s*=\s*null", block(variables, rf'variable\s+"{name}"')), name
    wiring = text(STAGING / "portal_edge.tf")
    assert wiring.count("count  = local.portal_edge ? 1 : 0") == 2


# --- the portal-entry deploy path and runtime config --------------------------------------------


def test_the_deploy_path_is_the_portal_builds_layout() -> None:
    vite = text(REPO / "apps" / "web" / "vite.config.ts")
    assert 'outDir: "dist/portal", rollupOptions: { input: "portal.html" }' in vite
    deploy = enclosing(text(PORTAL / "main.tf"), '"PutPortalBundle"')
    objects = re.findall(r'\$\{aws_s3_bucket\.portal\.arn\}/([^"]+)"', deploy)
    assert set(objects) == {"assets/*", "portal.html", "runtime-config.json"}
    assert "DeleteObject" not in text(PORTAL / "main.tf"), "old hashed assets stay for rollback"


def test_runtime_config_carries_portal_base_domain_from_the_setting() -> None:
    parameter = block(
        text(PORTAL / "main.tf"), r'resource\s+"aws_ssm_parameter"\s+"portal_base_domain"'
    )
    assert re.search(
        r'name\s*=\s*"/abacus/\$\{var\.environment\}/runtime-config/portal_base_domain"', parameter
    )
    assert re.search(r"value\s*=\s*var\.portal_base_domain", parameter)
    contract = text(REPO / "docs" / "contracts" / "platform-ops.md")
    assert "| `portal_base_domain` | hostname string | required | Public |" in contract
