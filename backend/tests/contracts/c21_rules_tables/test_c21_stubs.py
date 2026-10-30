"""K-02-T02 (TASK-2101; SPEC-500 AC-4 to AC-7): the C21 v1 stub on the wire, in the models and in
the module APIs (`docs/contracts/rules-tables.md`).

Every K-02 route declares its matrix action and answers 404 to a client principal, 404 with its
flag off and 501 with it on until its build task (the reference-set routes are live since
K-02-T05); every model field is classified; the payloads are discriminated by kind (seven
reference kinds, eight standard kinds); the module APIs exist with their frozen signatures and
raise `NotImplementedError` until their build tasks."""

from __future__ import annotations

import asyncio
import inspect
import json
import uuid
from collections.abc import Callable, Coroutine
from typing import cast, get_args

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import KNOWLEDGE_FIRM_STANDARDS, RULES_REFERENCE_SETS
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.identity.api import AuthContext
from abacus.modules.methodology import api as methodology_api
from abacus.modules.methodology import standards_contract
from abacus.modules.platform import api as platform_api
from abacus.modules.platform import reference_sets_contract, reference_sets_routes
from abacus.modules.practice import api as practice_api
from abacus.modules.practice import due_dates_contract, due_dates_routes

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
CONTRACTS = (standards_contract, reference_sets_contract, due_dates_contract)
MODELS: list[type[BaseModel]] = [
    v
    for module in CONTRACTS
    for v in vars(module).values()
    if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == module.__name__
]

ROUTES: list[tuple[str, str, str]] = [
    ("get", "/v1/reference-sets", "reference_set.read"),
    ("get", "/v1/reference-sets/{key}", "reference_set.read"),
    ("get", "/v1/reference-sets/{key}/versions", "reference_set.read"),
    ("get", "/v1/due-dates", "due_date.read"),
    ("get", "/v1/standards", "firm_standard.read"),
    ("post", "/v1/standards", "firm_standard.create"),
    ("get", "/v1/standards/{standard_id}", "firm_standard.read"),
    ("put", "/v1/standards/{standard_id}/owner", "firm_standard.assign_owner"),
    ("get", "/v1/standards/{standard_id}/versions/{version_id}", "firm_standard.read"),
    ("post", "/v1/standards/{standard_id}/versions", "firm_standard.draft"),
    ("patch", "/v1/standards/{standard_id}/versions/{version_id}", "firm_standard.draft"),
    ("delete", "/v1/standards/{standard_id}/versions/{version_id}", "firm_standard.draft"),
    (
        "post",
        "/v1/standards/{standard_id}/versions/{version_id}/publish",
        "firm_standard.publish",
    ),
    ("get", "/v1/standards/{standard_id}/versions/{version_id}/diff", "firm_standard.read"),
    (
        "get",
        "/v1/standards/{standard_id}/versions/{version_id}/export.xlsx",
        "firm_standard.read",
    ),
    ("get", "/v1/standards/{standard_id}/examples", "firm_standard.read"),
    ("post", "/v1/standards/{standard_id}/imports", "firm_standard.import"),
    ("post", "/v1/standards/imports", "firm_standard.import"),
]


# Built: K-02-T05 serves the reference sets, K-02-T07 the due dates.
LIVE = {
    path
    for _, path, _ in ROUTES
    if path.startswith("/v1/reference-sets") or path == "/v1/due-dates"
}


@pytest.mark.parametrize(("method", "path", "action"), ROUTES)
def test_ac5_every_route_declares_its_action_and_is_a_stub_until_built(
    method: str, path: str, action: str
) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == action
    assert ("501" in cast(Json, op["responses"])) is (path not in LIVE)


def test_ac5_there_is_no_reference_set_write_route() -> None:
    for path, ops in PATHS.items():
        if path.startswith("/v1/reference-sets"):
            assert set(ops) == {"get"}, path


def test_ac4_every_field_is_classified() -> None:
    assert MODELS
    for model in MODELS:
        assert unclassified_fields(model) == [], model.__name__


def test_ac4_seven_reference_kinds_and_eight_standard_kinds() -> None:
    assert len(get_args(reference_sets_contract.ReferenceSetKind)) == 7
    assert "standards_sets" in get_args(reference_sets_contract.ReferenceSetKind)
    assert len(get_args(standards_contract.StandardKind)) == 8
    assert set(get_args(standards_contract.StandardKind)) == set(
        get_args(standards_contract.FirmStandardKind)
    ) | set(get_args(standards_contract.ThresholdPolicyKind))


def test_ac4_payloads_are_discriminated_by_kind() -> None:
    payload = reference_sets_contract.ReferenceSetVersionOut.model_json_schema()
    assert "discriminator" in json.dumps(payload)
    standard = standards_contract.StandardVersionOut.model_json_schema()
    assert "discriminator" in json.dumps(standard)


def test_ac4_standards_families_exclude_issuer_and_pcaob() -> None:
    families = set(get_args(reference_sets_contract.StandardsFamily))
    assert families == {"gaas_nonissuer", "ssars", "sqms"}  # X-07, DEC-19


def test_ac4_document_confidence_auto_accept_stays_off() -> None:
    with pytest.raises(ValueError):
        standards_contract.DocumentConfidencePayload.model_validate(
            {
                "kind": "document_confidence",
                "hold_below_pct": "90",
                "auto_accept_above_pct": "98",
                "auto_accept_enabled": True,
            }
        )


def _ctx(*, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        "quality_partner",
        None,
        client=client,
    )


def test_inv4_a_client_principal_gets_404_before_anything() -> None:
    for stub in (
        standards_contract._stub(_ctx(client=True), "firm_standard.read"),  # pyright: ignore[reportPrivateUsage] -- the stub's order of checks, read directly
        reference_sets_routes._gate(_ctx(client=True)),  # pyright: ignore[reportPrivateUsage] -- the gate's order of checks, read directly
        due_dates_routes._gate(_ctx(client=True)),  # pyright: ignore[reportPrivateUsage] -- the gate's order of checks, read directly
    ):
        with pytest.raises(NotFound):
            asyncio.run(stub)


@pytest.mark.parametrize("module", [reference_sets_routes, due_dates_routes])
def test_ac5_part_as_gates_are_404_with_the_flag_off_and_open_with_it_on(
    monkeypatch: pytest.MonkeyPatch, module: object
) -> None:
    async def allowed(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(module, "authorise", allowed)
    for on in (False, True):

        async def enabled(_tenant: object, f: Flag, _on: bool = on) -> bool:
            assert f is RULES_REFERENCE_SETS
            return _on

        monkeypatch.setattr(module, "flag_enabled", enabled)
        gate = cast(
            "Callable[[AuthContext], Coroutine[None, None, None]]",
            module._gate,  # type: ignore[attr-defined] -- each routes module defines _gate
        )(_ctx())
        if on:
            assert asyncio.run(gate) is None
        else:
            with pytest.raises(NotFound):
                asyncio.run(gate)


def test_ac5_the_standards_flag_gates_the_standards_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def allowed(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(standards_contract, "authorise", allowed)
    for on, error in ((False, NotFound), (True, NotImplementedYet)):

        async def enabled(_tenant: object, f: Flag, _on: bool = on) -> bool:
            assert f is KNOWLEDGE_FIRM_STANDARDS
            return _on

        monkeypatch.setattr(standards_contract, "flag_enabled", enabled)
        with pytest.raises(error):
            asyncio.run(standards_contract._stub(_ctx(), "firm_standard.publish"))  # pyright: ignore[reportPrivateUsage] -- the stub's order of checks, read directly


PART_A = (
    "reference_value",
    "form_8879_for",
    "pub1345_tolerances",
    "information_return_threshold",
    "retention_minimum",
)
CALENDAR = ("due_dates_for", "add_business_days", "clock_due")
PART_B = (
    "current_version",
    "classify_entry",
    "variance_exceeded",
    "materiality_range_for",
    "validate_materiality",
    "confidence_hold",
    "required_review_levels",
    "return_approval_policy",
    "ssars_framework_for",
    "register_standard_examples",
)


def test_ac6_the_module_apis_are_exported() -> None:
    for name in PART_A:
        assert name in platform_api.__all__, name
    for name in CALENDAR:
        assert name in practice_api.__all__, name
    for name in PART_B:
        assert name in methodology_api.__all__, name


def test_ac6_part_bs_module_apis_raise_until_built() -> None:
    # Part A is built (K-02-T05 readers, K-02-T07 calendar; their integration suites).
    policy = methodology_api.PolicyRef("probe", uuid.uuid4(), 1, "Probe")
    with pytest.raises(NotImplementedError):
        methodology_api.classify_entry(
            cast(standards_contract.AjeThresholdsPayload, None),
            policy,
            account_class="probe",
            amount_usd=1,
            attest_client=False,
        )


def test_ac6_every_result_names_its_version() -> None:
    # INV-2: consumers store the version id a result came from.
    for cls in (
        platform_api.Form8879For,
        platform_api.TolerancesFor,
        platform_api.ThresholdFor,
        platform_api.RetentionFloor,
    ):
        assert "reference_set_version_id" in inspect.signature(cls).parameters, cls
    assert "reference_set_version_ids" in inspect.signature(practice_api.DueDates).parameters
    for cls in (
        methodology_api.EntryClassification,
        methodology_api.VarianceResult,
        methodology_api.MaterialityCheck,
        methodology_api.ConfidenceDecision,
        methodology_api.RequiredLevels,
        methodology_api.ReturnApproval,
        methodology_api.SsarsFramework,
    ):
        assert "policy" in inspect.signature(cls).parameters, cls
