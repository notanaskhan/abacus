"""Q-01-T51 (P-67, ADR-154): the sub-processor register and its Terraform drift check."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.codegen import sub_processors as sp


def register() -> list[sp.Row]:
    return sp.parse(sp.SOURCE.read_text(encoding="utf-8"))


def test_the_register_lists_the_platform_vendors_with_region_and_dpa_status() -> None:
    rows = {r.party: r for r in register() if r.kind == "sub-processor"}
    for party in ("Amazon Web Services", "Temporal Technologies", "WorkOS", "Better Stack"):
        assert party in rows
    assert any(r.service.startswith("Sentry") for r in rows.values())
    for row in rows.values():
        assert row.region.strip()
        assert row.dpa in sp.DPA_STATUSES


def test_the_register_and_its_markdown_are_current() -> None:
    assert sp.main(["--check"]) == 0


def write_tf(infra: Path, body: str) -> None:
    (infra / "envs" / "staging").mkdir(parents=True)
    (infra / "envs" / "staging" / "dns.tf").write_text(body, encoding="utf-8")


def test_an_egress_host_in_terraform_without_a_row_fails(tmp_path: Path) -> None:
    write_tf(
        tmp_path / "infra",
        'resource "aws_route53_resolver_firewall_domain_list" "allow" {\n'
        '  domains = ["api.workos.com.", "*.tmprl.cloud", "api.unknown-vendor.example"]\n'
        "}\n",
    )
    hosts = sp.terraform_egress_hosts(tmp_path / "infra")
    missing = sp.unregistered(register(), hosts)
    assert missing == ["api.unknown-vendor.example (infra/envs/staging/dns.tf)"]


def test_named_host_lists_count_and_comments_and_interpolations_do_not(tmp_path: Path) -> None:
    write_tf(
        tmp_path / "infra",
        "locals {\n"
        '  allowed_hosts = ["o1.ingest.us.sentry.io", "${var.extra}"]\n'
        '  # dns_domains = ["commented.example"]\n'
        '  scanner_domains = ["database.clamav.net"]\n'
        "}\n",
    )
    hosts = sp.terraform_egress_hosts(tmp_path / "infra")
    assert set(hosts) == {"o1.ingest.us.sentry.io", "database.clamav.net"}
    assert sp.unregistered(register(), hosts) == []


@pytest.mark.parametrize(
    ("pattern", "host", "covered"),
    [
        ("api.workos.com", "api.workos.com", True),
        ("*.tmprl.cloud", "acct.tmprl.cloud", True),
        ("*.tmprl.cloud", "*.tmprl.cloud", True),
        ("*.tmprl.cloud", "tmprl.cloud", False),
        ("*.tmprl.cloud", "eviltmprl.cloud", False),
        ("api.workos.com", "evil.api.workos.com", False),
    ],
)
def test_wildcard_rows_cover_subdomains_only(pattern: str, host: str, covered: bool) -> None:
    assert sp.covers(pattern, host) is covered


def test_a_malformed_row_is_refused() -> None:
    source = sp.SOURCE.read_text(encoding="utf-8")
    with pytest.raises(sp.RegisterError, match="dpa"):
        sp.parse(source.replace("\n    dpa: to-confirm", "\n    dpa: maybe", 1))
    with pytest.raises(sp.RegisterError, match="needs a DPA"):
        sp.parse(source.replace("\n    dpa: to-confirm", "\n    dpa: not-required", 1))
