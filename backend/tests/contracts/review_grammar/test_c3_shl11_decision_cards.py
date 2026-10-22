"""C3 v1 consumer tests (P-04-T09), the SHL-11 a to h shapes: the decision card reads a question,
code-computed options, factors and the agent's recommendation as a tag; the reserved role decides
with a sealed rationale; history records reassessments. The Northwind planning-materiality example
foots as Decimal: 1.0% = 168,100; 1.5% = 252,200, PM 189,150, CT 12,610; v3 252,900, $700, no
change (`docs/contracts/review-grammar.md` §8 part 2; F-04 §3.6 F-04.27)."""

from __future__ import annotations

from decimal import Decimal
from typing import cast, get_args

import pytest
from pydantic import BaseModel

from abacus.kernel.classification import Classification
from abacus.kernel.listing import ListPage
from abacus.modules.review.contract import (
    ActorKind,
    AnalysisRequestIn,
    AnalysisRequestOut,
    CardDecideIn,
    CardDecisionOut,
    CardEvent,
    DecisionCardItemOut,
    DecisionCardOut,
    DecisionCardVersionOut,
    DecisionContextOut,
    DecisionFactorOut,
    DecisionNotifyOut,
    DecisionOptionOut,
    DecisionRecommendationOut,
    ReservedRole,
)

from ._c3 import (
    SCHEMAS,
    Json,
    conforms,
    dec,
    example,
    inline_example,
    level,
    restricted_anywhere,
    round_to,
)

NEEDS: dict[str, list[tuple[type[BaseModel], str, Classification]]] = {
    "a": [
        (DecisionCardOut, "question", "confidential"),
        (DecisionCardOut, "context", "confidential"),
        (DecisionCardOut, "options", "confidential"),
        (DecisionCardOut, "factors", "confidential"),
        (DecisionCardOut, "citation_ids", "internal"),
        (DecisionCardOut, "recommendation", "confidential"),
        (DecisionCardOut, "blocking_refs", "internal"),
        (DecisionOptionOut, "label", "confidential"),
        (DecisionOptionOut, "detail", "confidential"),
        (DecisionOptionOut, "recommended", "internal"),
        (DecisionFactorOut, "applicable", "internal"),
        (DecisionFactorOut, "checked", "internal"),
        (DecisionContextOut, "label", "internal"),
        (DecisionContextOut, "citation_id", "internal"),
        (CardDecideIn, "option_key", "internal"),
        (CardDecideIn, "factors", "internal"),
        (CardDecideIn, "seen_version", "internal"),
        # The rationale is sealed wherever it appears.
        (CardDecideIn, "rationale", "restricted"),
        (CardDecisionOut, "rationale", "restricted"),
        (DecisionCardOut, "decision", "restricted"),
    ],
    "b": [
        (DecisionCardItemOut, "reserved_user_name", "internal"),
        (DecisionCardItemOut, "requested_at", "internal"),
        (DecisionCardItemOut, "allowed_actions", "internal"),
        (AnalysisRequestIn, "text", "restricted"),
        (AnalysisRequestOut, "requested_at", "internal"),
        (DecisionNotifyOut, "notified_user_id", "internal"),
    ],
    "c": [
        (CardDecisionOut, "decided_by_name", "internal"),
        (CardDecisionOut, "decided_at", "internal"),
        (CardDecisionOut, "seen_card_version", "internal"),
        (DecisionCardItemOut, "version_no", "internal"),
        (DecisionCardItemOut, "status", "internal"),
    ],
    "d": [
        (DecisionCardOut, "history", "confidential"),
        (DecisionCardVersionOut, "version_no", "internal"),
        (DecisionCardVersionOut, "event", "internal"),
        (DecisionCardVersionOut, "actor_initials", "internal"),
        (DecisionCardVersionOut, "changed", "internal"),
        (DecisionCardVersionOut, "at", "internal"),
    ],
    "e": [
        (DecisionCardItemOut, "kind", "internal"),
        (DecisionCardItemOut, "blocking_count", "internal"),
        (DecisionCardItemOut, "reserved_role", "internal"),
    ],
    "f": [
        (DecisionOptionOut, "recommended", "internal"),
        (DecisionRecommendationOut, "option_key", "internal"),
    ],
    "g": [
        (DecisionCardOut, "note", "confidential"),
        (DecisionCardItemOut, "reserved_user_id", "internal"),
    ],
    "h": [
        (DecisionCardItemOut, "superseded_by_version", "internal"),
        (DecisionCardItemOut, "status", "internal"),
    ],
}
CASES = [(a, m, f, c) for a, rows in NEEDS.items() for m, f, c in rows]

CARD = example("card", "options", "recommendation")
PM_RATE = Decimal("0.75")  # performance materiality 75% (§8 SHL-11 a)
CT_RATE = Decimal("0.05")  # clearly trivial 5%
HUNDRED = Decimal(100)


@pytest.mark.parametrize(
    ("artboard", "model", "field", "classification"),
    CASES,
    ids=[f"SHL-11{a}-{m.__name__}.{f}" for a, m, f, _c in CASES],
)
def test_shl11_the_frame_reads_its_fields_with_their_tags(
    artboard: str, model: type[BaseModel], field: str, classification: Classification
) -> None:
    assert field in model.model_fields, f"SHL-11 {artboard} needs {model.__name__}.{field}"
    assert level(model, field) == classification


# --- a. Deciding: Northwind planning materiality ------------------------------------------------


def test_shl11a_the_card_example_is_the_wire_shape() -> None:
    card = conforms(DecisionCardOut, CARD)
    assert card.card.status == "awaiting_role" and card.card.reserved_role == "engagement_partner"
    assert card.card.reserved_user_name == "Margaret Okonkwo"
    assert card.decision is None and [h.event for h in card.history] == ["proposed"]
    assert card.history[0].actor_kind == "agent"  # the agent proposed; it never decides


def test_shl11a_the_options_foot_in_code() -> None:
    card = conforms(DecisionCardOut, CARD)
    amount = dec(next(c.value for c in card.context if c.key == "amount"))
    assert amount == dec("16,812,400")
    for option in card.options:
        f = {k: Decimal(v) for k, v in option.figures.items()}
        assert round_to(f["rate"] * amount, HUNDRED) == f["materiality"]
        assert f["materiality"] * PM_RATE == f["performance_materiality"]
        assert f["materiality"] * CT_RATE == f["clearly_trivial"]
        assert f"${f['materiality']:,}" in option.label
    by_key = {o.key: {k: Decimal(v) for k, v in o.figures.items()} for o in card.options}
    assert by_key["pct_1_0"]["materiality"] == dec("168,100")
    assert (
        by_key["pct_1_0"]["performance_materiality"],
        by_key["pct_1_0"]["clearly_trivial"],
    ) == (
        dec("126,075"),
        dec("8,405"),
    )
    chosen = by_key["pct_1_5"]
    assert (
        chosen["materiality"],
        chosen["performance_materiality"],
        chosen["clearly_trivial"],
    ) == (dec("252,200"), dec("189,150"), dec("12,610"))


def test_shl11a_the_agent_only_recommends() -> None:
    card = conforms(DecisionCardOut, CARD)
    assert card.recommendation is not None
    assert [o.key for o in card.options if o.recommended] == [card.recommendation.option_key]
    assert "decision.decide" in card.card.allowed_actions  # Margaret, the reserved role


# --- a to c. Decide; decided -------------------------------------------------------------------


def test_shl11a_to_c_decide_with_a_sealed_rationale() -> None:
    request = conforms(CardDecideIn, example("option_key", "rationale", "seen_version"))
    assert request.option_key == "pct_1_5" and request.rationale
    # Optional on the wire: the service answers the fixed 422 `rationale_required` (§6).
    assert (
        CardDecideIn.model_validate({"option_key": "pct_1_5", "seen_version": 1}).rationale is None
    )
    decided = conforms(CardDecisionOut, example("decided_by_name", "rationale"))
    assert decided.decided_by_name == "Margaret Okonkwo" and decided.seen_card_version == 1
    card = conforms(DecisionCardOut, CARD)
    f = next(o.figures for o in card.options if o.key == decided.option_key)
    line = "v2: 1.5% = ${:,} · PM ${:,} · CT ${:,}".format(
        *(Decimal(f[k]) for k in ("materiality", "performance_materiality", "clearly_trivial"))
    )
    assert line == "v2: 1.5% = $252,200 · PM $189,150 · CT $12,610"


# --- b. Awaiting role --------------------------------------------------------------------------


def test_shl11b_the_viewer_outside_the_role_has_notify_and_analysis_only() -> None:
    viewer = ["decision.notify", "decision.request_analysis"]
    hannah = {**CARD, "card": {**cast(Json, CARD["card"]), "allowed_actions": viewer}}
    card = conforms(DecisionCardOut, hannah)
    assert "decision.decide" not in card.card.allowed_actions
    assert card.card.status == "awaiting_role"


# --- d. History, reassessed; h. superseded -----------------------------------------------------


def test_shl11d_reassessed_on_final_net_assets_no_change() -> None:
    v3 = inline_example("History v3 is")
    assert set(v3) <= set(DecisionCardVersionOut.model_fields)
    assert v3["event"] == "reassessed" and v3["changed"] is False
    figures = {k: Decimal(str(v)) for k, v in cast(Json, v3["figures"]).items()}
    assert figures["benchmark"] == dec("16,812,400") + dec("48,600")
    assert round_to(Decimal("0.015") * figures["benchmark"], HUNDRED) == figures["materiality"]
    assert figures["materiality"] - dec("252,200") == figures["difference"] == Decimal(700)
    assert {"proposed", "decided", "reassessed"} == set(get_args(CardEvent))


def test_shl11h_superseded_by_a_later_version() -> None:
    assert SCHEMAS["DecisionCardStatus"]["enum"] == ["awaiting_role", "decided", "superseded"]
    item = DecisionCardItemOut.model_fields["superseded_by_version"]
    assert item.annotation == int | None


# --- e. Inline dock card; lists carry nothing sealed --------------------------------------------


def test_shl11e_the_list_row_carries_nothing_restricted() -> None:
    assert restricted_anywhere(DecisionCardItemOut) == []
    page = ListPage[DecisionCardItemOut].model_validate(
        {"items": [conforms(DecisionCardOut, CARD).card.model_dump()], "total": 1}
    )
    assert page.items[0].blocking_count == 3


# --- f. Deficiency severity; g. §754 -----------------------------------------------------------


def test_shl11f_g_the_reserved_roles_and_actors() -> None:
    assert set(get_args(ReservedRole)) == {
        "engagement_partner",
        "manager",
        "eqr_reviewer",
        "signer",
    }
    assert set(get_args(ActorKind)) == {"human", "agent", "system"}


def test_shl11g_client_figures_and_agent_reasons_are_restricted() -> None:
    assert level(DecisionContextOut, "value") == "restricted"
    assert level(DecisionOptionOut, "figures") == "restricted"
    assert level(DecisionCardVersionOut, "figures") == "restricted"
    assert level(DecisionRecommendationOut, "reasons") == "restricted"
