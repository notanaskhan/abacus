"""Consumer tests for T-08's stubs and the contracts it reads (T-08-T08; SPEC-710 AC-36, AC-37;
DEC-5607).

Provider half: every SS-1, FD-1 and TP-1 model field carries a classification tag; every return
figure in TP-1 is TRI and FD-1 carries no TRI at all (metadata only, AC-14); every operation keeps
its action and its 501. Consumer half: the fields the 33 artboards read from C21 (due dates), C19
(consent status), C3 (issue links, decision cards, checkpoints), C7 (draft envelopes) and T-02's
engine summaries exist on the providers' models, so removing one fails here in the provider's CI.
The fixture half is `apps/web/src/fixtures/contracts/t08-practice.contract.test.ts`.
"""

from __future__ import annotations

import inspect
import json
from typing import cast

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import tri_paths, unclassified_fields
from abacus.modules.engagements import season_contract as ss1
from abacus.modules.organisations import consents_contract as c19
from abacus.modules.platform import filing_deadline_sources as slot
from abacus.modules.practice import due_dates_contract as c21
from abacus.modules.practice import filing_deadlines_contract as fd1
from abacus.modules.review import contract as c3
from abacus.modules.signatures import contract as c7
from abacus.modules.tax import practice_tools_contract as tp1
from abacus.modules.tax import returns_contract as t02

Json = dict[str, object]
PATHS = cast(dict[str, dict[str, Json]], json.loads(document())["paths"])


def _models(module: object) -> list[type[BaseModel]]:
    return [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, BaseModel) and obj.__module__ == getattr(module, "__name__", "")
    ]


@pytest.mark.parametrize(
    "model", [*_models(ss1), *_models(fd1), *_models(tp1)], ids=lambda m: m.__name__
)
def test_every_field_carries_a_classification_tag(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


@pytest.mark.parametrize(
    "model",
    [tp1.TaxPracticeTwoYearOut, tp1.TaxPracticeAmendmentOut, tp1.TaxPracticeAarOut,
     tp1.TaxPracticeOpportunityOut, tp1.TaxPracticePlanningSummaryOut],
    ids=lambda m: m.__name__,
)  # fmt: skip
def test_return_figures_are_tri(model: type[BaseModel]) -> None:
    assert tri_paths(model)


@pytest.mark.parametrize("model", [*_models(fd1), *_models(ss1)], ids=lambda m: m.__name__)
def test_deadlines_and_seasons_carry_no_tri(model: type[BaseModel]) -> None:
    """AC-14: deadline rows are metadata only; the season planner declares no `tri`."""
    assert tri_paths(model) == ()


def test_the_slot_kinds_are_the_read_models_check() -> None:
    kinds = frozenset(str(k) for k in fd1.SourceKind.__args__)
    assert kinds == slot.SOURCE_KINDS


def test_an_unknown_source_kind_fails_closed() -> None:
    async def provider(tenant: object, window: slot.FilingDeadlineWindow) -> list[object]:
        return []

    with pytest.raises(slot.UnknownFilingDeadlineSource):
        slot.register_filing_deadline_source("payroll_941", provider)  # type: ignore[arg-type]


# The fields T-08's screens read from the contracts it consumes (T-08 §8.2).
_READS: tuple[tuple[type[BaseModel], tuple[str, ...]], ...] = (
    (c21.DueDateOut, ("form", "tax_year", "original_due_on", "extension_form",
                      "extended_due_on", "postponement", "reference_set_version_ids",
                      "inputs_hash")),
    (c19.ConsentOut, ("client_id", "purpose", "tax_years", "status", "signed_count",
                      "signer_count", "envelope_id", "expires_at", "offshore")),
    (c19.ConsentSummaryOut, ("ai_use_signed", "blocked_clients")),
    (c3.IssueLinkOut, ("kind", "target_type", "target_id", "anchor")),
    (c3.DecisionCardOut, ("card", "question", "options", "recommendation", "decision")),
    (c3.CheckpointItemOut, ("id", "target_type", "target_id", "name", "status", "content_hash",
                            "author_kind")),
    (c7.EnvelopeOut, ("source_kind", "source_id", "engagement_id", "documents", "signers",
                      "expires_at")),
    (t02.EngineSummaryLineOut, ("line_key", "label", "amount", "line_ref", "total")),
)  # fmt: skip


@pytest.mark.parametrize(("model", "names"), _READS, ids=lambda x: getattr(x, "__name__", ""))
def test_the_consumed_fields_exist(model: type[BaseModel], names: tuple[str, ...]) -> None:
    missing = [n for n in names if n not in model.model_fields]
    assert missing == [], f"{model.__name__} lost fields T-08 reads: {missing}"


def _operations() -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    for router in (ss1.season_router, fd1.filing_deadlines_router, tp1.practice_tools_router):
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            extra = cast(dict[str, object], route.openapi_extra or {})
            for method in sorted(route.methods or set()):
                found.append((method.lower(), route.path, str(extra["x-abacus-action"])))
    return found


def test_the_three_stubs_declare_41_operations() -> None:
    assert len(_operations()) == 41


@pytest.mark.parametrize(("method", "path", "action"), _operations())
def test_every_operation_is_declared_with_its_action_and_501(
    method: str, path: str, action: str
) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == action
    assert "501" in cast(Json, operation["responses"])
