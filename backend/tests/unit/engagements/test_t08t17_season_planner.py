"""T-08-T17 (TASK-8840; T-08 §6; ENG-07; DEC-5842): `engagements.season_planner`.

Row acceptance: "The planner proposes the two-binder ask and reassignments only to eligible
staff, writes nothing, and a TRI-tagged input is refused by the gateway."
"""

from __future__ import annotations

import inspect
import uuid

from abacus.modules.engagements import season_planner as sp

ELIGIBLE = uuid.uuid4()
WALLED = uuid.uuid4()


def _rows() -> list[sp.FlaggedRow]:
    return [
        sp.FlaggedRow(
            uuid.uuid4(), uuid.uuid4(), ("binder_ambiguous",), "chicago", "entities_exempt"
        ),
        sp.FlaggedRow(uuid.uuid4(), uuid.uuid4(), ("assignee_walled_or_departed",), "chicago",
                      "individuals_trusts"),
    ]  # fmt: skip


def _given() -> sp.Given:
    rows = _rows()
    return sp.model_input(rows, {rows[1].row_id: [(ELIGIBLE, "Leo Wong")]})


def test_ac_two_binder_ask_from_code() -> None:
    given = _given()
    assert set(given.ask_rows) == {"binder_choice"}
    kept = sp.settle(None, given)  # a refused call: code's ask stands alone
    assert [k.question_code for k in kept] == ["binder_choice"]
    assert kept[0].phrase_key == "two_binders"


def test_ac_reassignment_only_to_eligible_staff() -> None:
    given = _given()
    ok = sp.SeasonPlannerOutput(
        asks=[sp.AskAnswer(ask_code="binder_choice", recommended_option="use_newer",
                           phrase_key="two_binders")],
        reassignments=[sp.Reassignment(row_id="r2", role="preparer", user_ref="u1"),
                       sp.Reassignment(row_id="r2", role="preparer", user_ref="u9")],
    )  # fmt: skip
    kept = sp.settle(ok, given)
    reassign = [k for k in kept if k.question_code == "reassign_preparer"]
    assert len(reassign) == 1 and reassign[0].recommended == str(ELIGIBLE)
    assert str(WALLED) not in {o for k in kept for o in k.options}


def test_invented_option_and_phrase_dropped() -> None:
    bad = sp.SeasonPlannerOutput(
        asks=[sp.AskAnswer(ask_code="binder_choice", recommended_option="approve_all",
                           phrase_key="free text")]
    )  # fmt: skip
    kept = sp.settle(bad, _given())
    assert kept[0].recommended is None and kept[0].phrase_key == "two_binders"


def test_ac_writes_nothing_and_no_tri() -> None:
    from abacus.modules.agents.specs._specs_v2 import SPECS_V2

    spec = SPECS_V2[sp.CAPABILITY]
    assert spec["tools"] == {} and "tri" not in spec["data_classes"]
    assert ".subjects(" not in inspect.getsource(sp._judge)
    for model in (sp.SeasonPlannerInput, sp.PlannerRow, sp.EligibleRef, sp.PlannerAsk):
        for f in model.model_fields.values():
            assert not any(getattr(m, "tri", False) for m in f.metadata)
