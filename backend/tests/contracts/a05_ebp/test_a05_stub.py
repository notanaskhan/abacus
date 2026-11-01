"""The A-05 ebp-workpapers v1 stub (A-05-T04; docs/contracts/ebp-workpapers.md; DEC-1859).

Row acceptance: "The stub merges dark behind ebp.modules with generated client types, and the
contract doc lists every human-only action (verify, adopt, record correction, evaluate
certification, conclude)." Each route exists with its one action and documents 404 (writes 501);
every model field is classified, SSN and DOB only as masks; the matrix denies the agent every
write and every client principal everything; the three flags default off; the examples foot.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel import _flags
from abacus.kernel.classification import unclassified_fields
from abacus.modules.assurance import ebp_contract as ebp
from abacus.modules.identity.authz import _matrix
from abacus.modules.organisations.api import MaskedTinOut

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
A = "/v1/audits/{work_item_id}"
REPO = Path(__file__).resolve().parents[4]
ROUTES: dict[tuple[str, str], str] = {
    ("get", f"{A}/ebp/plan"): "ebp.read",
    ("patch", f"{A}/ebp/plan"): "ebp_plan.edit",
    ("get", f"{A}/ebp/providers"): "ebp.read",
    ("post", f"{A}/ebp/providers"): "ebp_provider.manage",
    ("post", f"{A}/ebp/providers/{{provider_id}}/invite"): "ebp_provider.invite",
    ("get", f"{A}/ebp/plan-reviews/current"): "ebp.read",
    ("post", f"{A}/ebp/plan-reviews"): "workpaper.draft",
    ("get", f"{A}/ebp/participants"): "ebp.read",
    ("post", f"{A}/ebp/participants/{{participant_id}}/reveals"): "pii.reveal",
    ("post", f"{A}/ebp/imports"): "ebp_import.create",
    ("post", f"{A}/tests"): "test.create",
    ("put", f"{A}/tests/{{test_id}}/items/{{item_id}}/results/{{attribute}}"): "test.mark",
    ("get", f"{A}/ebp/eligibility"): "ebp.read",
    ("get", f"{A}/ebp/contributions/reconciliation"): "ebp.read",
    ("get", f"{A}/ebp/late-remittances"): "ebp.read",
    ("post", f"{A}/ebp/late-remittances/{{remittance_id}}/corrections"): "ebp_correction.record",
    ("get", f"{A}/ebp/loans/rollforward"): "ebp.read",
    ("get", f"{A}/ebp/investments"): "ebp.read",
    ("post", f"{A}/ebp/trust-tb/adopt"): "ledger_snapshot.create_from_document",
    ("put", f"{A}/ebp/certification/points/{{point_key}}"): "ebp_certification.evaluate",
    ("get", f"{A}/ebp/participant-accounts/rollforward"): "ebp.read",
    ("get", f"{A}/ebp/plan-expenses"): "ebp.read",
    ("get", f"{A}/ebp/form-5500"): "ebp_form5500.read",
    ("post", f"{A}/ebp/form-5500/lines/{{line_id}}/value"): "ebp_form5500.key",
    ("post", f"{A}/ebp/form-5500/reconciliation-note"): "ebp_form5500.send_note",
    ("get", f"{A}/estimates"): "estimate.read",
    ("put", f"{A}/estimates/{{estimate_id}}/method"): "estimate.evaluate",
    ("post", f"{A}/estimates/{{estimate_id}}/request-conclusion"): "estimate.request_conclusion",
    ("get", f"{A}/related-parties"): "related_party.read",
    ("post", f"{A}/related-parties"): "related_party.manage",
    ("post", f"{A}/related-parties/{{party_id}}/screen-out"): "related_party.screen_out",
    ("get", f"{A}/parties-in-interest"): "ebp.read",
    ("post", f"{A}/parties-in-interest"): "party_in_interest.manage",
}
READS = {"ebp.read", "ebp_form5500.read", "test.read", "estimate.read", "related_party.read"}
NEW_ACTIONS = sorted(
    {
        a
        for a in _matrix.ACTIONS
        if a.startswith(
            (
                "ebp",
                "test.",
                "estimate.",
                "related_party.",
                "party_in_interest.",
                "ledger_snapshot.",
            )
        )
    }
)
CLIENT_ROLES = ("client_admin", "client_contributor", "third_party", "client_service")


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_t04_each_route_declares_its_one_action_and_documents_404(method: str, path: str) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    responses = set(cast(Json, operation["responses"]))
    assert "404" in responses
    if method != "get":
        assert "501" in responses


def test_t04_every_write_takes_an_idempotency_key() -> None:
    for (method, path), _action in ROUTES.items():
        if method == "get":
            continue
        names = {p["name"] for p in cast(list[Json], PATHS[path][method].get("parameters", []))}
        assert "Idempotency-Key" in names, (method, path)


def test_t04_every_field_is_classified_and_pii_only_masked() -> None:
    models = [
        v
        for v in vars(ebp).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == ebp.__name__
    ]
    assert models
    for model in models:
        assert unclassified_fields(model) == [], model.__name__
    fields = ebp.ParticipantOut.model_fields
    # The census carries the SSN only as the platform's masked shape and the DOB masked (DEC-1858).
    assert fields["ssn"].annotation is MaskedTinOut
    assert "dob_masked" in fields and not set(fields) & {"dob", "date_of_birth"}


@pytest.mark.parametrize("action", NEW_ACTIONS)
def test_t04_clients_hold_nothing_and_the_agent_only_reads(action: str) -> None:
    cells = _matrix.ACTIONS[action]
    for role in CLIENT_ROLES:
        assert cells.get(role) == "deny", (action, role)
    assert cells.get("system") == "deny", action
    if action not in READS | {"ebp_population_query.run"}:
        assert cells.get("agent") == "deny", action


def test_t04_the_three_flags_exist_and_default_off() -> None:
    for name in ("ebp.modules", "ebp.form5500_tieout", "assurance.estimates_rp"):
        flag = _flags.FLAGS[name]
        assert flag.kind == "boolean"
        assert str(flag.default).lower() == "false", name


def test_t04_the_examples_foot() -> None:
    late = ebp.LateRemittanceOut.model_validate(ebp._LATE)  # pyright: ignore[reportPrivateUsage] -- the stub's own example
    assert late.amount == Decimal("33540.00")
    assert (late.business_days, late.calendar_days) == (9, 10)
    net = ebp.FiguresOut.model_validate(ebp._NET_ASSETS)  # pyright: ignore[reportPrivateUsage] -- the stub's own example
    assert (
        sum((r.amount or Decimal(0) for r in net.rows), Decimal(0))
        == net.total
        == Decimal("16861000.00")
    )
    assert Decimal("15060.00") + late.amount == Decimal("48600.00")
    assert Decimal("13640900.00") + Decimal("3171500.00") == Decimal("16812400.00")


def test_t04_the_contract_doc_lists_every_human_only_action() -> None:
    doc = (REPO / "docs/contracts/ebp-workpapers.md").read_text(encoding="utf-8")
    for act in ("verify", "adopt", "record correction", "evaluate certification", "conclude"):
        assert act in doc.casefold(), act
