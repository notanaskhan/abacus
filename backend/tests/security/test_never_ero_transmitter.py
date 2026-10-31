# ac-test-author: ayushkbhatia
"""T-01-T42 (TASK-2525; T-01 §3.15; R-04; SPEC-501 AC-13, AC-14; DEC-1572): Accrued is never an
ERO or a transmitter. "The suite is a required check before Tue Aug 17, 2027 and fails on a
planted outbound call to an IRS host."

Written from the row, chapter T-01 §3.15, `docs/contracts/efile-record.md` and the human-only
register, not from the code:

- NEVER-ERO-001 holds on the whole product tree, and catches each transmitter identifier.
- No product file names an IRS or state revenue host, so no code path can call one (MeF, IRIS
  A2A for a 1099, a state DOR); the scanner here fails on a planted call to one.
- No egress allowlist (the connectors' and the VPC DNS Firewall's) holds such a host.
- The engine export is a file a person carries: no tax file imports a network client, and the
  tax-engine write is the file bridge (W2) with nothing to send.
- `transmission.record` is human-only at five layers: the matrix denies the agent and the
  system, a live person only, the status machine refuses the system, the human-only register
  and the database CHECK on `transmissions`.
- I-AGENT-NEVER: the agent and the system are denied `tax_return.approve`, `tax_return.export`,
  `engine_import.approve`, `transmission.record` and every `consent.*` action.
- No route offers to submit, transmit or file with a tax authority.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.modules.identity.authz._matrix import ACTIONS
from abacus.modules.integrations import _capabilities as caps
from abacus.modules.tax.status import actor_may
from abacus_tools.quality import banned_patterns as bp

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent
SRC = BACKEND / "src" / "abacus"
# An IRS host (irs.gov and its MeF / IRIS endpoints) or a state department of revenue's
# (`tax.<state>.gov`, `revenue.<state>.gov`, `dor.<state>.gov`, `<state>dor.gov`).
_TAX_HOST = re.compile(
    r"(?i)(?:^|[/.@\s\"'])(?:[a-z0-9-]+\.)*(?:irs\.gov|(?:tax|revenue|dor|dtf|ftb|cdor)"
    r"\.[a-z]{2,}\.gov|[a-z]{2}dor\.gov|tax\.ny\.gov|tax\.illinois\.gov|colorado\.gov/revenue)"
)
NEVER_AGENT = (
    "tax_return.approve",
    "tax_return.export",
    "engine_import.approve",
    "transmission.record",
)


def tax_host_literals(root: Path) -> Iterator[tuple[Path, int, str]]:
    """Every string constant under `root` naming an IRS or state revenue host."""
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            text = node.value if isinstance(node, ast.Constant) else None
            if isinstance(text, str) and _TAX_HOST.search(text):
                yield path, node.lineno, text


# --- NEVER-ERO-001 ------------------------------------------------------------------------------


def test_never_ero_001_holds_on_the_product_tree() -> None:
    found = [v for v in bp.scan(BACKEND) if v.rule_id == "NEVER-ERO-001"]
    assert found == [], found


@pytest.mark.parametrize(
    "planted",
    [
        'SUBMIT = "send through MeF"\n',
        'CHANNEL = "IRIS TCC"\n',
        "def a2a_submit() -> None: ...\n",
        "efin = '123456'\n",
        "class EtinStore: ...\n",
    ],
)
def test_never_ero_001_catches_a_planted_transmitter(tmp_path: Path, planted: str) -> None:
    rel = "src/abacus/modules/tax/planted.py"
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_text(planted, encoding="utf-8")
    assert [v for v in bp.scan(tmp_path) if v.rule_id == "NEVER-ERO-001"], planted


# --- no IRS or state revenue host anywhere ------------------------------------------------------


def test_no_product_file_names_an_irs_or_state_revenue_host() -> None:
    assert list(tax_host_literals(SRC)) == []


@pytest.mark.parametrize(
    "planted",
    [
        'import httpx\n\nhttpx.post("https://la.alt.mef.irs.gov/a2a/mef/submit")\n',
        'URL = "https://api.www4.irs.gov/iris/a2a"\n',
        'STATE = "https://www.tax.ny.gov/efile"\n',
        'HOST = "efile.revenue.ca.gov"\n',
    ],
)
def test_the_scan_fails_on_a_planted_outbound_call_to_a_tax_host(
    tmp_path: Path, planted: str
) -> None:
    (tmp_path / "planted.py").write_text(planted, encoding="utf-8")
    assert list(tax_host_literals(tmp_path)), planted


def test_no_egress_allowlist_holds_a_tax_host() -> None:
    hosts = [
        str(h) for c in caps.READ_CONNECTORS for h in cast(tuple[str, ...], c["egress_hosts"])
    ]
    dns = (ROOT / "infra/modules/dns-firewall/main.tf").read_text(encoding="utf-8")
    domains = re.findall(r'"([*a-z0-9.-]+\.[a-z]{2,})"', dns)
    assert domains, "the DNS Firewall allowlist moved"
    for host in [*hosts, *domains]:
        assert not _TAX_HOST.search(f"/{host}"), host
        assert "irs" not in host.split("."), host


# --- the export is a file a person carries -----------------------------------------------------


_NETWORK = re.compile(r"^(?:httpx|requests|aiohttp|urllib3|smtplib|paramiko|ftplib)\b")


def test_no_tax_file_imports_a_network_client() -> None:
    for path in sorted((SRC / "modules" / "tax").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            for name in names:
                assert not _NETWORK.match(name), f"{path.relative_to(BACKEND)} imports {name}"


def test_the_tax_engine_write_is_the_file_bridge_and_sends_nothing() -> None:
    bridges = [w for w in caps.WRITES if w["shape"] == "W2"]
    assert bridges, "the tax-engine file bridge is declared"
    for write in bridges:
        assert not cast(tuple[str, ...], write.get("egress_hosts", ())), write


# --- transmission.record is a person's, at five layers -----------------------------------------


def test_transmission_record_is_human_only_at_every_layer() -> None:
    row = ACTIONS["transmission.record"]
    assert (row.get("agent"), row.get("system")) == ("deny", "deny")  # 1: the matrix
    assert row.get("function_in") == "signer"  # 2: the signer on the return
    assert actor_may("transmission_recorded", "human")  # 4: the status machine
    for kind in ("system", "agent", "support"):
        assert not actor_may("transmission_recorded", kind), kind
    register = yaml.safe_load((ROOT / "docs/architecture/human-only-actions.yaml").read_text())
    listed = {a["action"] for a in register["actions"]}
    assert {"transmission.recorded", "efile_ack.recorded"} <= listed  # the audit trigger
    migration = next((BACKEND / "migrations" / "versions").glob("*_transmissions_acks.py"))
    assert "CHECK (actor_kind = 'human')" in migration.read_text()  # 5: the database


def test_the_service_refuses_anyone_but_a_live_designated_ero() -> None:
    """Layer 3: the service names its person check and the ERO designation before writing."""
    source = (SRC / "modules" / "tax" / "filing.py").read_text(encoding="utf-8")
    body = source[source.index("async def record_transmission(") :]
    body = body[: body.index("\nasync def ", 1)]
    assert "_person(ctx, TRANSMIT)" in body
    assert "ero_designated(ctx.tenant, ctx.user_id)" in body
    assert body.index("ero_designated(") < body.index("INSERT INTO transmissions")


# --- I-AGENT-NEVER ------------------------------------------------------------------------------


@pytest.mark.parametrize("action", NEVER_AGENT)
def test_the_agent_and_system_are_denied_the_tax_decisions(action: str) -> None:
    row = ACTIONS[action]
    assert (row.get("agent"), row.get("system")) == ("deny", "deny"), action


def test_the_agent_is_denied_every_consent_action() -> None:
    consent = sorted(a for a in ACTIONS if a.startswith("consent."))
    assert consent, "the consent actions moved"
    for action in consent:
        assert ACTIONS[action].get("agent") == "deny", action


# --- no route files with a tax authority -------------------------------------------------------


def test_no_route_submits_or_transmits_to_a_tax_authority() -> None:
    from abacus.api import create_app

    words = re.compile(
        r"(?i)(?:^|[/:_-])(?:submit|mef|a2a|iris|efin|etin|e-?file-submit)(?:$|[/:_-])"
    )
    for route in create_app().routes:
        path = str(getattr(route, "path", ""))
        assert not words.search(path), path
