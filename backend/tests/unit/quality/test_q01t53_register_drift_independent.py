"""Q-01-T53 (ADR-078): independent tests for the sub-processor register's drift check
(Q-01-T51), from the acceptance text: "a missing register row fails the check". The check is run
the way `make check-generated` runs it (`python -m abacus_tools.codegen.sub_processors --check`)
against a Terraform DNS Firewall allowlist holding the hosts the Q-01 epic names (F2), with the
real register and with one row taken out. Same-session authorship (TASK-1238): independence is
nominal."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from abacus_tools.codegen import sub_processors as sp

# Q-01 F2: the initial allowlist (AWS APIs resolve to VPC endpoints).
ALLOWLIST = (
    "acct.tmprl.cloud",
    "api.workos.com",
    "o0.ingest.us.sentry.io",
    "uptime.betterstack.com",
    "database.clamav.net",
    "api.anthropic.com",
)
OWNERS = {
    "acct.tmprl.cloud": "temporal",
    "api.workos.com": "workos",
    "o0.ingest.us.sentry.io": "sentry",
    "uptime.betterstack.com": "better-stack",
    "database.clamav.net": "clamav",
    "api.anthropic.com": "anthropic",
}


@pytest.fixture
def staged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository-shaped copy: the register, a staging allowlist, a generated table."""
    infra = tmp_path / "infra" / "envs" / "staging"
    infra.mkdir(parents=True)
    hosts = ", ".join(f'"{h}."' for h in ALLOWLIST)
    (infra / "dns_firewall.tf").write_text(
        'resource "aws_route53_resolver_firewall_domain_list" "allowed" {\n'
        '  name    = "abacus-staging-egress"\n'
        f"  domains = [{hosts}]\n"
        "}\n",
        encoding="utf-8",
    )
    register = tmp_path / "sub-processors.yaml"
    register.write_text(sp.SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(sp, "SOURCE", register)
    monkeypatch.setattr(sp, "INFRA", tmp_path / "infra")
    monkeypatch.setattr(sp, "TARGET", tmp_path / "sub-processors.md")
    monkeypatch.setattr(sp, "ROOT", tmp_path)
    assert sp.main([]) == 0  # the generated table for the full register
    return register


def test_ac_the_full_register_covers_the_epics_allowlist(staged: Path) -> None:
    assert sp.main(["--check"]) == 0


@pytest.mark.parametrize("host", ALLOWLIST)
def test_ac_a_missing_register_row_fails_the_check(
    staged: Path, host: str, capsys: pytest.CaptureFixture[str]
) -> None:
    document = yaml.safe_load(staged.read_text(encoding="utf-8"))
    document["rows"] = [r for r in document["rows"] if r["id"] != OWNERS[host]]
    staged.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    assert sp.main(["--check"]) == 1
    assert f"egress host {host} " in capsys.readouterr().err


def test_ac_a_row_that_lost_its_host_fails_the_check_too(
    staged: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = yaml.safe_load(staged.read_text(encoding="utf-8"))
    for row in document["rows"]:
        if row["id"] == "workos":
            row["egress_hosts"] = []
    staged.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    assert sp.main(["--check"]) == 1
    assert "api.workos.com" in capsys.readouterr().err
