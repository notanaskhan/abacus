"""G-04-T22 (TASK-8759; the row's acceptance, offline half): the staff console's edge on staging is
reachable only from the allowlist. With CIDRs named, the console WebACL blocks every source outside
the IP set before any other rule; with none, no allowlist rule or IP set exists, so the firm and
portal WebACLs are unchanged. The console distribution serves console.html. Read as text."""

from __future__ import annotations

import re
from pathlib import Path

INFRA = Path(__file__).resolve().parents[1]
WAF = INFRA / "modules" / "waf"
FIRM = INFRA / "modules" / "cloudfront-firm"
STAGING = INFRA / "envs" / "staging"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ac1_allowlist_rule_blocks_every_source_outside_the_ip_set() -> None:
    main = text(WAF / "main.tf")
    rule = main[main.index('name     = "ip-allowlist"') :]
    rule = rule[: rule.index("visibility_config")]
    assert "block {}" in rule
    assert "not_statement" in rule
    assert "ip_set_reference_statement" in rule
    assert "aws_wafv2_ip_set.allow[0].arn" in rule


def test_ac2_allowlist_exists_only_when_cidrs_are_named() -> None:
    main = text(WAF / "main.tf")
    assert re.search(r'count\s+=\s+length\(var\.allow_ipv4_cidrs\) > 0 \? 1 : 0', main)
    assert re.search(r"for_each = length\(var\.allow_ipv4_cidrs\) > 0 \? \[1\] : \[\]", main)
    variables = text(WAF / "variables.tf")
    assert re.search(r'variable "allow_ipv4_cidrs" \{[^}]*default\s+=\s+\[\]', variables, re.S)


def test_ac3_no_rule_allows_around_the_allowlist() -> None:
    # The WebACL's default action is the only allow: every rule before or after the allowlist
    # blocks or counts, so a source outside the IP set cannot be let through by an earlier rule.
    assert text(WAF / "main.tf").count("allow {}") == 1


def test_ac4_console_edge_is_off_until_host_certificate_and_cidrs_are_set() -> None:
    edge = text(STAGING / "console_edge.tf")
    assert "var.console_host != null" in edge
    assert "var.console_certificate_arn != null" in edge
    assert "length(var.console_allow_ipv4_cidrs) > 0" in edge
    assert "allow_ipv4_cidrs     = var.console_allow_ipv4_cidrs" in edge
    assert 'default_root_object        = "console.html"' in edge


def test_ac5_no_cidr_is_committed() -> None:
    variables = text(STAGING / "variables.tf")
    block = variables[variables.index('variable "console_allow_ipv4_cidrs"') :]
    block = block[: block.index("}\n") + 2]
    assert re.search(r"default\s+=\s+\[\]", block)
    assert not re.search(r"\d+\.\d+\.\d+\.\d+/\d+", text(STAGING / "console_edge.tf"))


def test_ac6_the_firm_distribution_keeps_index_html() -> None:
    variables = text(FIRM / "variables.tf")
    assert re.search(r'variable "default_root_object" \{[^}]*default\s+=\s+"index.html"', variables, re.S)
    assert "default_root_object = var.default_root_object" in text(FIRM / "main.tf")
