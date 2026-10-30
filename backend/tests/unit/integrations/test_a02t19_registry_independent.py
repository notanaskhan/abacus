"""A-02-T19 (TASK-1419; ADR-078 independent AC suite): the integrations framework and the
write-capability registry, written from the acceptance criteria (A-02 AC-13.1 to AC-13.3, SPEC-333
AC-49 and AC-50, ADR-040, ADR-150, C20 v1 §2 and §3), not from the implementation's output.

The row's acceptance: the suite fails on each seeded violation (an undeclared host, a hand-edited
registry, an enabled capability without an ADR) and passes on main. Each violation is seeded here
on a temporary copy of the protected file or the generated module, or on the in-memory compiled
values, never on a tracked file; the same check is then shown to pass on what main holds.

- Fail-closed adapters: anything not a read-only adapter is refused, and a refusal leaves nothing
  registered; lookups of the unknown answer None.
- Catalogue honesty: a row whose adapter is not registered here, or is registered for another
  category or provider, is never listed as available on any surface.
- Drift: a hand edit of `_capabilities.py`, or an edit of the YAML without regenerating, fails
  the drift check `make check-generated` runs; a generated module edited to enable a write does
  not load and the API does not start.
- Enabled capability without an ADR: the protected file cannot enable a write in v1, cannot
  declare one without the decision that would enable it, and every decision main names exists.
- Write refusal and attest refusal at registry level; no principal holds the action.
- Outbound host allowlist: a registered adapter reaching a host the registry does not declare
  for it stops start-up, and the egress client refuses what the registry does not declare.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest
import yaml
from pydantic import ValidationError

from abacus.kernel.egress import EgressRefused, allowed_hosts, check_egress, configure_egress
from abacus.modules.integrations import _capabilities as compiled
from abacus.modules.integrations.api import (
    AdapterRefused,
    CatalogRow,
    IntegrationCategory,
    UndeclaredEgress,
    WriteCapabilityEntry,
    WriteCapabilityRegistry,
    assert_egress_declared,
    egress_allowlist,
    is_available,
    listed,
    listing_of,
    policy_refusal,
    register_adapter,
    registered_adapter,
    registered_keys,
    registry,
    undeclared_egress,
    unregister_adapter,
    write_capability,
)
from abacus_tools.codegen import write_capabilities as compiler

REPO: Final = compiler.BACKEND.parent
PROTECTED: Final = compiler.SOURCE.read_text()
GENERATED: Final = compiler.TARGET.read_text()
ADAPTER: Final = "probe_t19"
HOST: Final = "api.probe-t19.example"


# --- probes --------------------------------------------------------------------------------------


class Probe:
    """A read-only adapter built from the port alone (C20 §2): its machinery stays private."""

    def __init__(
        self,
        key: str = ADAPTER,
        *,
        category: str = "ledger",
        provider: str | None = ADAPTER,
        scopes: tuple[str, ...] = ("ledger.read",),
        hosts: tuple[str, ...] = (HOST,),
    ) -> None:
        self._key = key
        self._category = category
        self._provider = provider
        self._scopes = scopes
        self._hosts = hosts

    @property
    def key(self) -> str:
        return self._key

    @property
    def category(self) -> IntegrationCategory:
        return self._category  # pyright: ignore[reportReturnType] -- probes seed bad categories

    @property
    def connector_provider(self) -> str | None:
        return self._provider

    def read_scopes(self) -> tuple[str, ...]:
        return self._scopes

    def egress_hosts(self) -> tuple[str, ...]:
        return self._hosts


def _noop(_self: object) -> None:
    return None


def _with(name: str, value: object = _noop) -> Probe:
    """A probe with one more public attribute (a write method, an HTTP client …)."""
    return type(f"Probe_{name}", (Probe,), {name: value})()


@pytest.fixture(autouse=True)
def clean() -> Iterator[None]:
    """Nothing a test registers or seeds into the compiled registry outlives it."""
    before = registered_keys()
    registry.cache_clear()
    yield
    for key in registered_keys() - before:
        unregister_adapter(key)
    registry.cache_clear()
    configure_egress(frozenset())


def _row(**over: object) -> CatalogRow:
    fields: dict[str, object] = {
        "key": ADAPTER,
        "name": "Probe Ledger",
        "category": "ledger",
        "ownership_mode": "client_authorised",
        "surfaces": ("portal", "workbench"),
        "connector_provider": ADAPTER,
        "adapter_key": ADAPTER,
        "listing_status": "available",
        "consent_copy": None,
        "consent_version": None,
        "read_scopes": (("ledger.read", "Read ledger"),),
        "icon": "book-open",
        "tone": "olive",
        "sort_order": 1,
        "revision": 1,
        "loaded_at": datetime(2026, 9, 14, 14, 24, tzinfo=UTC),
    }
    fields.update(over)
    return CatalogRow(**fields)  # pyright: ignore[reportArgumentType] -- probe field values


# --- fail-closed adapters (AC-13.1, AC-49; ADR-040) ----------------------------------------------


def test_ac13_1_lookups_of_the_unknown_answer_none_never_a_default() -> None:
    assert registered_adapter(None) is None
    assert registered_adapter(ADAPTER) is None
    assert ADAPTER not in registered_keys()


def test_ac13_1_a_read_only_adapter_registers_and_is_found_under_its_key() -> None:
    register_adapter(Probe())
    adapter = registered_adapter(ADAPTER)
    assert adapter is not None and adapter.key == ADAPTER
    unregister_adapter(ADAPTER)
    assert registered_adapter(ADAPTER) is None


WRITE_SHAPED: Final = (
    "post_journal_entry",
    "create_invoice",
    "update_customer",
    "delete_account",
    "send_payment",
    "put_object",
    "patch_vendor",
    "write_back",
    "upload_attachment",
    "apply_payment",
    "commit",
    "sync",
    "execute",
)


@pytest.mark.parametrize("name", WRITE_SHAPED)
def test_ac13_1_an_adapter_with_any_write_shaped_method_is_refused(name: str) -> None:
    with pytest.raises(AdapterRefused):
        register_adapter(_with(name))
    assert ADAPTER not in registered_keys()


@pytest.mark.parametrize("name", ["http", "client", "session", "transport"])
def test_ac13_1_a_public_http_client_attribute_is_refused(name: str) -> None:
    """A caller could reach `.post` on an exposed client: the adapter keeps it private."""
    with pytest.raises(AdapterRefused):
        register_adapter(_with(name, object()))
    assert ADAPTER not in registered_keys()


@pytest.mark.parametrize(
    "declared",
    [
        ("post_entries",),  # a write name declared as a read
        ("read_trial_balance",),  # a read name that is not a method of the adapter
        ("key",),  # a port member passed off as a read method
        "read_trial_balance",  # not a tuple of names
    ],
)
def test_ac13_1_a_dishonest_read_method_declaration_is_refused(declared: object) -> None:
    probe = _with("read_methods", declared)
    with pytest.raises(AdapterRefused):
        register_adapter(probe)
    assert ADAPTER not in registered_keys()


def test_ac13_1_declared_read_methods_are_admitted() -> None:
    probe = type(
        "Reader",
        (Probe,),
        {"read_methods": ("read_trial_balance", "list_accounts"), "read_trial_balance": _noop}
        | {"list_accounts": _noop},
    )()
    register_adapter(probe)
    assert ADAPTER in registered_keys()


BAD_ADAPTERS: Final[dict[str, Callable[[], object]]] = {
    "not an adapter": lambda: object(),
    "key with capitals": lambda: Probe("Probe_T19", provider=None),
    "key too short": lambda: Probe("p", provider=None),
    "unknown category": lambda: Probe(category="general_ledger_writer"),
    "provider outside the grammar": lambda: Probe(provider="Probe-T19"),
    "no read scope": lambda: Probe(scopes=()),
    "scope outside the grammar": lambda: Probe(scopes=("Ledger Read",)),
    "host with a scheme": lambda: Probe(hosts=("https://api.probe-t19.example",)),
    "wildcard host": lambda: Probe(hosts=("*.probe-t19.example",)),
    "single-label host": lambda: Probe(hosts=("localhost",)),
    "IP address": lambda: Probe(hosts=("10.0.0.7",)),
    "host with a port": lambda: Probe(hosts=("api.probe-t19.example:443",)),
    "host with a path": lambda: Probe(hosts=("api.probe-t19.example/v3",)),
    "upper-case host": lambda: Probe(hosts=("API.PROBE-T19.EXAMPLE",)),
}


@pytest.mark.parametrize("build", BAD_ADAPTERS.values(), ids=list(BAD_ADAPTERS))
def test_ac13_1_registration_fails_closed(build: Callable[[], object]) -> None:
    before = registered_keys()
    with pytest.raises(AdapterRefused):
        register_adapter(build())
    assert registered_keys() == before


def test_ac13_1_one_adapter_per_key_and_per_connection_provider() -> None:
    register_adapter(Probe())
    with pytest.raises(AdapterRefused):
        register_adapter(Probe())  # the same key again
    with pytest.raises(AdapterRefused):
        register_adapter(Probe("probe_t19_two", provider=ADAPTER))  # the same provider again
    assert ADAPTER in registered_keys() and "probe_t19_two" not in registered_keys()
    adapter = registered_adapter(ADAPTER)
    assert adapter is not None and adapter.connector_provider == ADAPTER


# --- catalogue honesty (AC-13.1, AC-49) ----------------------------------------------------------


@pytest.mark.parametrize("surface", ["portal", "workbench"])
@pytest.mark.parametrize("ownership", ["client_authorised", "firm", "personal"])
def test_ac13_1_a_row_whose_adapter_is_not_registered_is_never_available(
    surface: str, ownership: str
) -> None:
    rows = [_row(ownership_mode=ownership), _row(key="probe_none", adapter_key=None)]
    entries = listed(rows, surface, ownership)  # pyright: ignore[reportArgumentType] -- probe surface
    assert entries, "the row is listed, only never as available"
    assert not any(is_available(e) for e in entries)
    assert {e.listing for e in entries} == {"coming_soon"}


@pytest.mark.parametrize(
    ("adapter", "why"),
    [
        (Probe(category="bank_feed"), "registered for another category"),
        (Probe(provider="probe_other"), "registered for another connection provider"),
        (Probe("probe_other", provider=ADAPTER), "registered under another key"),
    ],
)
def test_ac13_1_a_registered_adapter_that_does_not_match_the_row_is_not_available(
    adapter: Probe, why: str
) -> None:
    register_adapter(adapter)
    assert listing_of(_row()) == "coming_soon", why


def test_ac13_1_only_a_matching_registered_adapter_and_an_available_row_list_as_available() -> (
    None
):
    assert listing_of(_row()) == "coming_soon"
    register_adapter(Probe())
    assert listing_of(_row()) == "available"
    # The catalogue's own word still binds: coming soon stays coming soon, hidden is never listed.
    assert listing_of(_row(listing_status="coming_soon")) == "coming_soon"
    hidden = _row(listing_status="hidden")
    for surface in ("portal", "workbench"):
        assert listed([hidden], surface, "client_authorised") == []
    unregister_adapter(ADAPTER)  # a kill switch takes it off at once
    assert listing_of(_row()) == "coming_soon"


# --- drift: a hand-edited registry (AC-13.2) -----------------------------------------------------


@pytest.fixture
def scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """The compiler pointed at temporary copies of the protected file and the generated module."""
    source = tmp_path / "write-capabilities.yaml"
    target = tmp_path / "_capabilities.py"
    source.write_text(PROTECTED)
    target.write_text(GENERATED)
    monkeypatch.setattr(compiler, "SOURCE", source)
    monkeypatch.setattr(compiler, "TARGET", target)
    return source, target


def test_ac13_2_main_passes_the_drift_check() -> None:
    assert compiler.main(["--check"]) == 0


def test_ac13_2_the_drift_check_passes_on_untouched_copies(scratch: tuple[Path, Path]) -> None:
    assert compiler.main(["--check"]) == 0


HAND_EDITS: Final = {
    "enable a write": ('"enabled": False,', '"enabled": True,'),
    # A-02-T26 declared QuickBooks Online: each edit adds to what is generated, not to an empty
    # registry.
    "widen the egress allowlist": (
        "EGRESS_HOSTS: Final[frozenset[str]] = frozenset(\n    {\n",
        "EGRESS_HOSTS: Final[frozenset[str]] = frozenset(\n    {\n"
        '        "api.probe-t19.example",\n',
    ),
    "declare a read connector by hand": (
        "READ_CONNECTORS: Final[tuple[dict[str, object], ...]] = (\n",
        "READ_CONNECTORS: Final[tuple[dict[str, object], ...]] = (\n    "
        + repr(
            {
                "adapter_key": ADAPTER,
                "category": "ledger",
                "egress_hosts": (HOST,),
                "read_scopes": ("ledger.read",),
            }
        )
        + ",\n",
    ),
    "swap a write's decision": ('"decision": "P-16",', '"decision": "ADR-150",'),
    "drop the attest-relevant shape": ('"shape": "W1",', '"shape": "W3",'),
    "a comment only": ("from typing import Final\n", "from typing import Final  # tidy\n"),
}


@pytest.mark.parametrize(("before", "after"), HAND_EDITS.values(), ids=list(HAND_EDITS))
def test_ac13_2_a_hand_edit_of_the_generated_module_fails_the_drift_check(
    scratch: tuple[Path, Path], before: str, after: str
) -> None:
    _, target = scratch
    assert before in GENERATED, "the seed must apply to what main generates"
    target.write_text(GENERATED.replace(before, after, 1))
    assert compiler.main(["--check"]) == 1


def test_ac13_2_an_edit_of_the_protected_file_without_regenerating_fails_the_drift_check(
    scratch: tuple[Path, Path],
) -> None:
    source, _ = scratch
    source.write_text(
        PROTECTED.replace(
            "read_connectors:\n",
            "read_connectors:\n"
            f"  - adapter_key: {ADAPTER}\n"
            "    category: ledger\n"
            f"    egress_hosts: [{HOST}]\n"
            "    read_scopes: [ledger.read]\n",
            1,
        )
    )
    assert compiler.main(["--check"]) == 1
    # Regenerating is the only way back to green, and it carries the declared host.
    assert compiler.main([]) == 0
    assert compiler.main(["--check"]) == 0
    assert f'"{HOST}",' in scratch[1].read_text()


def test_ac13_2_the_drift_check_is_one_of_the_generated_file_gates() -> None:
    makefile = (REPO / "Makefile").read_text()
    generators = re.search(r"^GENERATORS = (.+)$", makefile, re.MULTILINE)
    assert generators is not None
    assert "write_capabilities" in generators.group(1).split()
    protected = (REPO / "docs" / "architecture" / "protected-paths.md").read_text()
    assert "integrations/_capabilities.py" in protected
    assert "docs/architecture/write-capabilities.yaml" in protected


def _seed_compiled(monkeypatch: pytest.MonkeyPatch, **values: object) -> None:
    """As if `_capabilities.py` had been edited by hand and loaded: the module's values only."""
    for name, value in values.items():
        monkeypatch.setattr(compiled, name, value)
    registry.cache_clear()


def test_ac13_2_a_generated_module_edited_to_enable_a_write_does_not_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edited = tuple({**w, "enabled": True} for w in compiled.WRITES)
    _seed_compiled(monkeypatch, WRITES=edited)
    with pytest.raises(ValidationError):
        registry()
    with pytest.raises(ValidationError):  # and start-up stops on it (fail closed)
        assert_egress_declared()


async def test_ac13_2_the_api_does_not_start_on_a_generated_module_that_enables_a_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.api import create_app

    app = create_app()
    _seed_compiled(monkeypatch, WRITES=tuple({**w, "enabled": True} for w in compiled.WRITES))
    with pytest.raises(ValidationError):
        async with app.router.lifespan_context(app):
            pass


def test_ac13_2_a_hand_widened_egress_constant_does_not_widen_what_may_be_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The allowlist is the declared read connectors' hosts; a stray constant adds nothing."""
    _seed_compiled(monkeypatch, EGRESS_HOSTS=frozenset({"evil.example"}))
    assert "evil.example" not in egress_allowlist()


def test_ac13_2_main_exports_one_allowlist_everywhere(capsys: pytest.CaptureFixture[str]) -> None:
    assert egress_allowlist() == compiled.EGRESS_HOSTS == registry().egress_hosts()
    assert compiler.main(["--egress"]) == 0
    assert json.loads(capsys.readouterr().out) == sorted(egress_allowlist())


# --- an enabled capability without an ADR (AC-13.2; ADR-150) -------------------------------------


def _reserved(**over: object) -> str:
    fields: dict[str, object] = {
        "key": "probe_write",
        "adapter_key": "probe_writer",
        "shape": "W3",
        "owner_epic": "C-02",
        "decision": "ADR-150",
    }
    fields.update(over)
    lines = [f"    {k}: {v}" for k, v in fields.items() if v is not None]
    return "  - " + "\n".join(lines)[4:] + "\n"


UNDECIDED: Final = {
    "enabled with its ADR": _reserved(enabled="true"),
    "enabled with no decision": _reserved(decision=None, enabled="true"),
    "reserved with no decision": _reserved(decision=None),
    "a decision that is no ADR or plan decision": _reserved(decision="DEC-46"),
    "a placeholder decision": _reserved(decision="TBD"),
    "a malformed ADR number": _reserved(decision="ADR-15"),
    "enabled by a field the schema does not know": _reserved(active="true"),
}


@pytest.mark.parametrize("entry", UNDECIDED.values(), ids=list(UNDECIDED))
def test_ac13_2_a_write_enabled_or_without_its_decision_does_not_compile(
    scratch: tuple[Path, Path], entry: str
) -> None:
    source, _ = scratch
    seeded = PROTECTED.replace("\nwrites:\n", "\nwrites:\n" + entry, 1)
    assert seeded != PROTECTED
    with pytest.raises(compiler.RegistryInvalid):
        compiler.load(seeded)
    source.write_text(seeded)
    assert compiler.main(["--check"]) == 1  # so `make check-generated` fails
    assert compiler.main([]) == 1  # and nothing is generated from it
    assert scratch[1].read_text() == GENERATED


def test_ac13_2_the_well_formed_reservation_the_seeds_start_from_compiles() -> None:
    """The control: the seed's entry, decided and not enabled, is a valid reservation."""
    seeded = PROTECTED.replace("\nwrites:\n", "\nwrites:\n" + _reserved(), 1)
    entry = next(w for w in compiler.load(seeded).writes if w.key == "probe_write")
    assert entry.enabled is False and entry.decision == "ADR-150"


def test_ac13_2_the_schema_cannot_express_an_enabled_write_into_a_client_system() -> None:
    with pytest.raises(ValidationError):
        WriteCapabilityEntry.model_validate(
            {
                "key": "probe_write",
                "adapter_key": "probe_writer",
                "shape": "W1",
                "owner_epic": "C-02",
                "decision": "P-16",
                "enabled": True,
            }
        )
    with pytest.raises(ValidationError):
        WriteCapabilityRegistry.model_validate({"version": 3, "read_connectors": [], "writes": []})


def test_ac13_2_main_enables_only_w7_and_every_decision_it_names_exists() -> None:
    # Version 2 (ADR-150 accepted, DEC-1280): the e-signature send under ADR-342, nothing else.
    raw = yaml.safe_load(PROTECTED)
    assert raw["version"] == 2
    assert [w["key"] for w in raw["writes"] if w.get("enabled")] == ["esignature_envelope_send"]
    assert {w.shape for w in registry().writes if w.enabled} == {"W7"}
    decisions = (REPO / "docs" / "plan" / "09-decisions-adrs.md").read_text()
    for write in registry().writes:
        assert write.decision is not None, write.key
        if write.decision.startswith("ADR-"):
            assert list((REPO / "docs" / "adr").glob(f"{write.decision}-*.md")), write.decision
        else:
            assert re.search(rf"^\| {re.escape(write.decision)} \|", decisions, re.MULTILINE), (
                write.decision
            )


# --- write and attest refusal at registry level (AC-13.2; I-POLICY-NOT-ATTEST) ------------------


@pytest.mark.parametrize("attest", [False, True])
def test_ac13_2_the_registry_refuses_every_declared_write_for_every_client(attest: bool) -> None:
    assert registry().writes
    for write in registry().writes:
        assert policy_refusal(write, attest_client=attest) is not None, write.key


def test_ac13_2_w1_is_refused_for_an_attest_client_whatever_the_file_says() -> None:
    w1 = [w for w in registry().writes if w.shape == "W1"]
    assert w1, "posting is reserved, so the attest rule has an entry to hold"
    for entry in w1:
        assert policy_refusal(entry, attest_client=True) == "attest_client"
        # A file a later schema could enable: still refused for the attest client.
        on = entry.model_copy(update={"enabled": True})  # unvalidated, as a later schema
        assert policy_refusal(on, attest_client=True) == "attest_client"
    # Any W1 the file might add, under any key or adapter, is refused the same way.
    other = WriteCapabilityEntry.model_construct(
        key="ledger_post_bills",
        adapter_key="probe_writer",
        shape="W1",
        owner_epic="C-02",
        decision="P-16",
        enabled=True,
    )
    assert policy_refusal(other, attest_client=True) == "attest_client"


def test_ac13_2_an_undeclared_capability_is_unknown() -> None:
    assert write_capability("ledger_delete_everything") is None
    assert write_capability("") is None


def test_ac13_2_no_principal_holds_write_capability_execute() -> None:
    matrix = yaml.safe_load(
        (REPO / "docs" / "architecture" / "permission-matrix" / "integrations.yaml").read_text()
    )
    cell = matrix["actions"]["write_capability.execute"]
    assert {k: v for k, v in cell.items() if v != "deny"} == {}
    assert cell.get("agent") == "deny" and cell.get("system") == "deny"


def test_ac13_2_no_code_outside_the_gate_reaches_a_writer_or_the_compiled_registry() -> None:
    """Writers are callable only through `execute_write` (ADR-150 enforcement): nothing else in
    the app imports `integrations.writers` or the generated module."""
    src = compiler.BACKEND / "src" / "abacus"
    gate = src / "modules" / "integrations"
    allowed = {gate / "api.py", gate / "writes.py", gate / "capabilities.py"}
    pattern = re.compile(r"integrations(\.|\s+import\s+)(writers|_capabilities)\b")
    offenders = [
        str(p.relative_to(src))
        for p in src.rglob("*.py")
        if p not in allowed and p.parent != gate / "writers" and pattern.search(p.read_text())
    ]
    assert offenders == []


# --- the outbound host allowlist (ADR-040; Q-01) -------------------------------------------------


def test_ac13_2_main_starts_with_no_undeclared_host() -> None:
    assert undeclared_egress() == {}
    assert_egress_declared()


def test_ac13_2_an_adapter_reaching_an_undeclared_host_stops_start_up() -> None:
    register_adapter(Probe())
    assert undeclared_egress() == {ADAPTER: (HOST,)}
    with pytest.raises(UndeclaredEgress, match=re.escape(HOST)):
        assert_egress_declared()


async def test_ac13_2_the_api_does_not_start_while_an_undeclared_host_is_registered() -> None:
    from abacus.api import create_app

    register_adapter(Probe())
    app = create_app()
    with pytest.raises(UndeclaredEgress):
        async with app.router.lifespan_context(app):
            pass


def _declare(monkeypatch: pytest.MonkeyPatch, adapter_key: str, *hosts: str) -> None:
    reader = {
        "adapter_key": adapter_key,
        "category": "ledger",
        "egress_hosts": hosts,
        "read_scopes": ("ledger.read",),
    }
    # Beside the declared connectors (A-02-T26's QuickBooks Online stays declared).
    _seed_compiled(
        monkeypatch,
        READ_CONNECTORS=(*compiled.READ_CONNECTORS, reader),
        EGRESS_HOSTS=compiled.EGRESS_HOSTS | frozenset(hosts),
    )


def test_ac13_2_hosts_are_declared_per_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    _declare(monkeypatch, ADAPTER, HOST)
    register_adapter(Probe())
    assert undeclared_egress() == {}
    assert_egress_declared()
    # One more host than declared is found, and so is another adapter borrowing these hosts.
    unregister_adapter(ADAPTER)
    register_adapter(Probe(hosts=(HOST, "auth.probe-t19.example")))
    register_adapter(Probe("probe_borrower", provider="probe_borrower"))
    found = undeclared_egress()
    assert found[ADAPTER] == ("auth.probe-t19.example",)
    assert found["probe_borrower"] == (HOST,)
    with pytest.raises(UndeclaredEgress):
        assert_egress_declared()


async def test_ac13_2_start_up_admits_exactly_the_declared_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.api import create_app

    _declare(monkeypatch, ADAPTER, HOST)
    register_adapter(Probe())
    # The lifespan's exit shuts the process-global tracer provider down; keep it running for the
    # rest of this worker's tests (CI: every later span end logged "Processor is already shutdown"
    # into the JSON log stream and the in-memory exporter stopped recording).
    monkeypatch.setattr("abacus.api.app.shutdown_tracing", lambda: None)
    monkeypatch.setattr("abacus.api.app.flush_errors", lambda: None)
    app = create_app()
    async with app.router.lifespan_context(app):
        assert allowed_hosts() == compiled.EGRESS_HOSTS | {HOST}  # the declared hosts, exactly
        check_egress(f"https://{HOST}/v3/reports/TrialBalance")
        for bad in (
            f"http://{HOST}/v3",  # not HTTPS
            "https://auth.probe-t19.example/",  # not declared
            f"https://{HOST}.evil.example/",  # a suffix trick
            f"https://user:pw@{HOST}/",  # credentials in the URL
        ):
            with pytest.raises(EgressRefused):
                check_egress(bad)


def test_ac13_2_an_adapter_registered_after_start_up_still_cannot_reach_its_host() -> None:
    """Start-up configures egress from the registry; a late registration widens nothing."""
    configure_egress(egress_allowlist())
    register_adapter(Probe())
    with pytest.raises(EgressRefused):
        check_egress(f"https://{HOST}/v3")
