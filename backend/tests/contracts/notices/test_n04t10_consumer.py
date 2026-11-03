"""Notices v1 consumer contract suite (N-04-T10; docs/contracts/notices.md; chapter 10's rule:
the provider and the screens are AY's lane, this suite is the consumer's).

It fails on drift: the wire's status words are the registry's (`notice`, `notice_intake`), the
refusal codes the contract names are the codes the services raise, every amount and line stays
tax return information, the human-only writes deny the agent and system principals in the matrix,
and the field shapes the screens read (NOT-01, NOT-02) keep their keys.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import cast, get_args

import pytest
import yaml
from pydantic import BaseModel

from abacus.kernel.classification import tri_paths
from abacus.modules.notices import contract, intake, service

ROOT = Path(__file__).resolve().parents[4]
VOCAB = yaml.safe_load((ROOT / "docs/product/status-vocabulary.yaml").read_text())
MATRIX = yaml.safe_load((ROOT / "docs/architecture/permission-matrix/notices.yaml").read_text())
CONTRACT_DOC = (ROOT / "docs/contracts/notices.md").read_text()


def _codes(obj: str) -> set[str]:
    """The registry's codes for one status object (`objects.<obj>.codes`)."""
    objects = cast(dict[str, dict[str, dict[str, object]]], VOCAB["objects"])
    return set(objects[obj]["codes"])


def _raised(module: ModuleType) -> set[str]:
    """The refusal codes a module's error classes carry."""
    out: set[str] = set()
    for value in vars(module).values():
        code: object = getattr(value, "code", None) if isinstance(value, type) else None
        if isinstance(code, str):
            out.add(code)
    return out


@pytest.mark.parametrize(
    ("literal", "obj"),
    [(contract.NoticeStatus, "notice"), (contract.IntakeStatus, "notice_intake")],
)
def test_status_words_are_the_registry_codes(literal: object, obj: str) -> None:
    assert set(get_args(literal)) <= _codes(obj)


def test_intake_refusal_codes_are_the_ones_the_contract_names() -> None:
    raised = _raised(intake)
    assert {"low_confidence_unconfirmed", "duplicate_unresolved", "no_notice_engagement"} <= raised
    assert "not_ready" in raised
    assert "illegal_transition" in _raised(service)


@pytest.mark.parametrize(
    "code", ["decision_pending", "position_mismatch", "not_ready", "low_confidence_unconfirmed"]
)
def test_the_contract_document_names_each_refusal_code(code: str) -> None:
    assert f"`{code}`" in CONTRACT_DOC


def test_the_response_view_carries_position_mismatch() -> None:
    names = {
        name
        for model in vars(contract).values()
        if isinstance(model, type) and issubclass(model, BaseModel) and model is not BaseModel
        for name in model.model_fields
    }
    assert "position_mismatch" in names


def test_amounts_are_tax_return_information() -> None:
    assert set(tri_paths(contract.AmountsOut)) >= {"tax", "interest", "penalty", "total"}
    assert {"amounts.tax", "amounts.total"} <= set(tri_paths(contract.NoticeRowOut))


HUMAN_ONLY = (
    "notice_intake.confirm",
    "notice.agency_reply",
    "notice_response.send_for_signature",
    "notice_response.mark_sent",
)


@pytest.mark.parametrize("action", HUMAN_ONLY)
def test_human_only_writes_deny_agent_and_system(action: str) -> None:
    row = MATRIX["actions"][action]
    assert row["agent"] == "deny"
    assert row["system"] == "deny"
    assert all(row[p] == "deny" for p in ("client_admin", "client_contributor", "third_party"))


SHAPES: dict[type[BaseModel], frozenset[str]] = {
    contract.IntakeFieldOut: frozenset(
        {"key", "value_text", "confidence", "low_confidence", "confirmed", "tin", "origin"}
    ),
    contract.IntakeOut: frozenset({"id", "status", "fields", "match", "authorization", "version"}),
    contract.NoticeRowOut: frozenset(
        {"id", "status", "tile", "risk", "respond_by", "amounts", "position", "version"}
    ),
}


@pytest.mark.parametrize("model", list(SHAPES), ids=lambda m: m.__name__)
def test_the_screens_fields_keep_their_keys(model: type[BaseModel]) -> None:
    assert SHAPES[model] <= set(model.model_fields), sorted(
        SHAPES[model] - set(model.model_fields)
    )
