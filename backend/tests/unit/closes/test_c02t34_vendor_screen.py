"""C-02-T34 (TASK-8906; C-02 §6; red): `close.agent` mode `vendor_screen`.

Row acceptance: "On the synthetic Copperleaf vendors the agent proposes Hartwell & Lowe as an
attorney with a verified W-9 citation, never adopts a value and never sees a TIN digit, and its
Bedrock run meets every T51 threshold with the run committed." Here: code settles the screen
(offered options, offered pages, no four-digit run anywhere), the W-9 text the model sees is
scrubbed, every quote must verify before anything is proposed, the proposal is a suggestion (the
applier writes only when a person adopts), the fake-model run over T51's frozen suite passes and
signs its report, and the tools and prompt are registered. The Bedrock run is the evaluation
account's (DEC-5901).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.modules.closes import agent as close_agent
from abacus.modules.closes import vendor_screen
from abacus_tools.evals import close_vendor_screen_run as screen_run

PROMPTS = Path(close_agent.__file__).resolve().parents[2] / "ai_gateway" / "prompts"


def _given(**over: object) -> close_agent.CloseAgentInput:
    base: dict[str, object] = {
        "mode": "vendor_screen",
        "close_id": uuid4(),
        "facts": [],
        "options": list(vendor_screen.ENTITY_TYPES),
        "pages": [1],
        "untrusted": ["W-9 page 1: Hartwell & Lowe LLP. Line 3a: Partnership."],
    }
    base.update(over)
    return close_agent.CloseAgentInput.model_validate(base)


def _answer(**screen: object) -> close_agent.CloseAgentOutput:
    base: dict[str, object] = {
        "entity_type": "partnership",
        "is_attorney": True,
        "quotes": [{"page": 1, "quote": "Partnership"}],
    }
    base.update(screen)
    return close_agent.CloseAgentOutput(
        blocks={"version": 1, "parts": [{"kind": "p", "segments": [
            {"kind": "text", "text": "Screened as an attorney."}]}]},
        screen=close_agent.VendorScreenOut.model_validate(base),
    )  # fmt: skip


def test_the_fake_answer_proposes_hartwell_and_lowe_as_an_attorney() -> None:
    settled = close_agent.settle(_given(), close_agent.FAKE_RESPONSES["vendor_screen"])
    assert settled.screen is not None
    assert (settled.screen.entity_type, settled.screen.is_attorney) == ("partnership", True)
    assert {q.quote for q in settled.screen.quotes} >= {"Hartwell & Lowe LLP"}


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        (_answer(entity_type="corporation"), "option_not_offered"),
        (_answer(exempt_reason="because_i_said"), "option_not_offered"),
        (_answer(quotes=[{"page": 2, "quote": "Partnership"}]), "page_not_offered"),
        (_answer(quotes=[{"page": 1, "quote": "TIN ending 4471"}]), "tin_in_output"),
    ],
)
def test_code_settles_the_screen(answer: close_agent.CloseAgentOutput, reason: str) -> None:
    with pytest.raises(close_agent.OutputRefused) as caught:
        close_agent.settle(_given(), answer)
    assert caught.value.facts == {"reason": reason}


def test_a_screen_outside_its_mode_is_refused() -> None:
    with pytest.raises(close_agent.OutputRefused) as caught:
        close_agent.settle(_given(mode="run"), _answer())
    assert caught.value.facts == {"reason": "screen_outside_vendor_screen"}


def test_the_vendor_screen_needs_its_screen() -> None:
    bare = close_agent.CloseAgentOutput(blocks={"version": 1, "parts": []})
    with pytest.raises(close_agent.OutputRefused):
        close_agent.settle(_given(), bare)


def test_no_tin_digit_reaches_the_model() -> None:
    page = "Hartwell & Lowe LLP Part I 98-1234471 ••-•••4471 suite 1200"
    scrubbed = vendor_screen.scrub_digits(page)
    assert "4471" not in scrubbed and "1234471" not in scrubbed and "1200" not in scrubbed
    assert "Hartwell & Lowe LLP" in scrubbed


async def test_an_unverified_quote_proposes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.evidence import api as evidence

    written: list[object] = []

    class _Session:
        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def scalar(self, *_: object) -> object:
            return uuid4()

    class _Tx(_Session):
        pass

    async def unverified(*_: object, **__: object) -> list[object]:
        return [SimpleNamespace(id=uuid4(), verified=False)]

    async def suggestion(*_: object, **kw: object) -> object:
        written.append(kw)
        return uuid4()

    from abacus.kernel import uow as uow_module
    from abacus.modules.agents import api as agents

    monkeypatch.setattr(vendor_screen, "tenant_session", lambda _t: _Session())  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]  -- a test double stands in
    monkeypatch.setattr(uow_module, "uow", lambda _t: _Tx())  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]  -- a test double stands in
    monkeypatch.setattr(evidence, "record_citations", unverified)
    monkeypatch.setattr(agents, "create_suggestion", suggestion)
    agent = SimpleNamespace(tenant=SimpleNamespace(tenant_id=uuid4()), engagement_id=uuid4())
    with pytest.raises(vendor_screen.UnverifiedQuote):
        await vendor_screen.propose_classification(
            agent,  # type: ignore[arg-type]  -- a test double stands in
            uuid4(),
            close_agent.VendorScreenOut(
                entity_type="partnership",
                is_attorney=True,
                quotes=[close_agent.W9QuoteOut(page=1, quote="Partnership")],
            ),
        )
    assert written == []


class _AdoptTx:
    def __init__(self) -> None:
        self.params: list[dict[str, object]] = []
        self.records: list[tuple[str, dict[str, object]]] = []
        self.session = self

    async def scalar(self, _sql: object, params: dict[str, object]) -> int:
        self.params.append(params)
        return 5

    def record(self, action: str, **kw: object) -> None:
        self.records.append((action, kw))


async def test_adopting_writes_the_vendor_as_the_person(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.agents.api import AdoptedValue
    from abacus.modules.engagements import api as engagements

    engagement = uuid4()

    async def where(*_: object) -> object:
        return engagement

    async def allowed(*_: object, **__: object) -> None:
        return None

    async def ref(*_: object) -> object:
        return SimpleNamespace(resource=lambda: object())

    monkeypatch.setattr(vendor_screen, "vendor_engagement", where)
    monkeypatch.setattr(vendor_screen, "authorise", allowed)
    monkeypatch.setattr(engagements, "get_ref", ref)
    tx, vendor, person = _AdoptTx(), uuid4(), uuid4()
    value = AdoptedValue(
        engagement_id=engagement, target_type=vendor_screen.TARGET, target_id=vendor,
        field_key="classification",
        value={"t": "json", "v": {"entity_type": "partnership", "is_attorney": True,
                                  "exempt_reason": None}},
        value_source="agent_suggested", cause="suggestion_adopted", suggestion_id=uuid4(),
        citation_ids=(uuid4(),), citation_note=None, checkpoint_id=None, proposal_id=None,
    )  # fmt: skip
    ctx = SimpleNamespace(tenant=SimpleNamespace(tenant_id=uuid4()), user_id=person)
    await vendor_screen.apply_vendor_classification(tx, ctx, value)  # type: ignore[arg-type]  -- a test double stands in
    assert tx.params == [
        {"entity_type": "partnership", "attorney": True, "exempt": None, "by": person,
         "v": vendor}
    ]  # fmt: skip
    assert [a for a, _ in tx.records] == ["vendor.updated"]


async def test_an_adopted_value_outside_the_closed_sets_is_refused() -> None:
    from abacus.modules.agents.api import AdoptedValue

    value = AdoptedValue(
        engagement_id=None, target_type=vendor_screen.TARGET, target_id=uuid4(),
        field_key="classification", value={"t": "json", "v": {"entity_type": "exempt_forever"}},
        value_source="human", cause="edit", suggestion_id=None, citation_ids=(),
        citation_note="edited", checkpoint_id=None, proposal_id=None,
    )  # fmt: skip
    with pytest.raises(close_agent.OutputRefused):
        await vendor_screen.apply_vendor_classification(_AdoptTx(), SimpleNamespace(), value)  # type: ignore[arg-type]  -- a test double stands in


def test_the_fake_model_run_passes_t51s_frozen_suite_and_signs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(screen_run.SIGNING_KEY_ENV, "test-key")
    assert screen_run.fake_main(tmp_path) == 0
    report = json.loads((tmp_path / "close_vendor_screen-fake.json").read_text())
    assert report["passed"] is True and report["route"] == "fake"
    assert report["clears_real_firms"] is False  # only a Bedrock run clears
    assert isinstance(report.get("signature"), str)
    assert report["prompt"] == "close.agent.vendor_screen@v1"


def test_the_mode_tools_and_prompts_are_registered() -> None:
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(close_agent.CAPABILITY)
    tools = {*spec.tools.read, *spec.tools.propose}
    assert {"close.read_vendor_facts", "close.read_vendor_document",
            "close.propose_vendor_classification"} <= tools  # fmt: skip
    assert tools <= close_agent.TOOLS | {"close.reconcile", "close.read_upload_table"}
    assert (PROMPTS / "close.agent.vendor_screen" / "v1.txt").exists()
    for tool in ("read_vendor_facts", "read_vendor_document", "propose_vendor_classification"):
        assert (PROMPTS / f"tool.close.{tool}" / "v1.txt").exists(), tool
    assert spec.client_data == "none"  # synthetic only until cleared
