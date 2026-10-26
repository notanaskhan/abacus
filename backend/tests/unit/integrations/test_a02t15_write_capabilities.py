"""A-02-T15 (TASK-1415; SPEC-333 AC-50; A-02 AC-13.2; ADR-150, ADR-040): the write-capability
registry skeleton, without a database.

- The protected `write-capabilities.yaml` compiles to `_capabilities.py`; a hand edit of the
  generated module fails the drift check, and a source that would enable a write, name no
  decision, or let a reader write does not compile.
- The compiled registry enables nothing; every reserved write names its decision.
- Q-01's egress export is the registry's declared hosts; an adapter reaching an undeclared host
  is found, and start-up refuses while it is registered.
- A W1-shaped capability is refused for an attest client at registry level, even one a later
  schema might enable.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from abacus.modules.integrations.api import (
    UndeclaredEgress,
    WriteCapabilityRefused,
    assert_egress_declared,
    egress_allowlist,
    policy_refusal,
    register_adapter,
    registry,
    undeclared_egress,
    unregister_adapter,
    write_capability,
)
from abacus_tools.codegen import write_capabilities as compiler

SOURCE = compiler.SOURCE.read_text()


class Probe:
    """A read-only adapter whose host the registry does not declare."""

    key = "probe_egress"
    category = "ledger"
    connector_provider = "probe_egress"

    def read_scopes(self) -> tuple[str, ...]:
        return ("ledger.read",)

    def egress_hosts(self) -> tuple[str, ...]:
        return ("api.undeclared.example",)


@pytest.fixture
def probe() -> Iterator[None]:
    register_adapter(Probe())
    yield
    unregister_adapter(Probe.key)


def test_ac50_the_generated_module_matches_the_protected_file() -> None:
    assert compiler.main(["--check"]) == 0
    assert compiler.render(compiler.load(SOURCE)) == compiler.TARGET.read_text()


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('"enabled": False', '"enabled": True'),  # switching a write on by hand
        ("EGRESS_HOSTS: Final[frozenset[str]] = frozenset()", 'EGRESS_HOSTS = {"evil.example"}'),
        ('"shape": "W1"', '"shape": "W3"'),
    ],
)
def test_ac50_a_hand_edit_of_capabilities_fails_the_drift_check(
    before: str, after: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    edited = compiler.TARGET.read_text()
    assert before in edited
    target = tmp_path / "_capabilities.py"
    target.write_text(edited.replace(before, after, 1))
    monkeypatch.setattr(compiler, "TARGET", target)
    assert compiler.main(["--check"]) == 1


def test_ac50_a_missing_generated_module_fails_the_drift_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(compiler, "TARGET", tmp_path / "_capabilities.py")
    assert compiler.main(["--check"]) == 1


@pytest.mark.parametrize(
    ("before", "after", "rule"),
    [
        ("    enabled: false\n", "    enabled: true\n", "does not validate"),
        ("    decision: P-16\n", "", "names the decision"),
        ("version: 1", "version: 2", "does not validate"),
        ("    shape: W1\n", "    shape: W1\n    shape: W2\n", "appears twice"),
        (
            "    owner_epic: C-02\n",
            "    owner_epic: C-02\n    scope: write\n",
            "does not validate",
        ),
    ],
)
def test_a_source_that_would_enable_or_hide_a_write_does_not_compile(
    before: str, after: str, rule: str
) -> None:
    assert before in SOURCE
    with pytest.raises(compiler.RegistryInvalid, match=rule):
        compiler.load(SOURCE.replace(before, after, 1))


def test_a_read_connector_never_also_writes() -> None:
    reader = (
        "read_connectors:\n"
        "  - adapter_key: quickbooks_online\n"
        "    category: ledger\n"
        "    egress_hosts: [quickbooks.api.intuit.com]\n"
        "    read_scopes: [ledger.read]\n"
    )
    with pytest.raises(compiler.RegistryInvalid, match="never also writes"):
        compiler.load(SOURCE.replace("read_connectors: []\n", reader, 1))


def test_the_registry_enables_nothing_and_names_each_writes_decision() -> None:
    assert registry().version == 1
    assert registry().writes, "the reserved writes are declared"
    assert all(w.enabled is False for w in registry().writes)
    assert all(w.decision for w in registry().writes)
    shapes = {w.shape for w in registry().writes}
    assert "W1" in shapes  # posting is reserved, so the attest rule has an entry to refuse


def test_the_egress_export_is_the_declared_hosts(capsys: pytest.CaptureFixture[str]) -> None:
    assert egress_allowlist() == registry().egress_hosts()
    assert compiler.main(["--egress"]) == 0
    assert json.loads(capsys.readouterr().out) == sorted(registry().egress_hosts())
    with_reader = SOURCE.replace(
        "read_connectors: []\n",
        "read_connectors:\n"
        "  - adapter_key: probe_ledger\n"
        "    category: ledger\n"
        "    egress_hosts: [api.probe.example, auth.probe.example]\n"
        "    read_scopes: [ledger.read]\n",
        1,
    )
    rendered = compiler.render(compiler.load(with_reader))
    assert '"api.probe.example",' in rendered and '"auth.probe.example",' in rendered


@pytest.mark.usefixtures("probe")
def test_an_adapter_reaching_an_undeclared_host_is_found_and_blocks_start_up() -> None:
    assert undeclared_egress() == {"probe_egress": ("api.undeclared.example",)}
    with pytest.raises(UndeclaredEgress, match=r"api\.undeclared\.example"):
        assert_egress_declared()


def test_start_up_passes_with_no_undeclared_host() -> None:
    assert undeclared_egress() == {}
    assert_egress_declared()


def test_ac50_w1_is_refused_for_an_attest_client_at_registry_level() -> None:
    w1 = next(w for w in registry().writes if w.shape == "W1")
    assert policy_refusal(w1, attest_client=True) == "attest_client"
    assert policy_refusal(w1, attest_client=False) == "not_enabled"
    # A later schema that could enable W1 would still be refused for an attest client.
    enabled = w1.model_copy(update={"enabled": True})  # no validation: a future schema
    assert policy_refusal(enabled, attest_client=True) == "attest_client"
    assert policy_refusal(enabled, attest_client=False) is None
    other = next(w for w in registry().writes if w.shape != "W1")
    assert policy_refusal(other, attest_client=True) == "not_enabled"


def test_unknown_capabilities_are_not_found_and_the_refusal_has_its_code() -> None:
    assert write_capability("ledger_delete_everything") is None
    assert WriteCapabilityRefused.code == "write_capability_refused"
