"""P-10-T13 (TASK-6104; ADR-234 §7): route parity for tools and documents.

Row acceptance: "A Bedrock parity report under 90 days old covers tool use and documents, and a
route without it is refused for a loop spec." The refusal half is tested here; the committed
Bedrock report needs a real run (`make route-parity ROUTE=bedrock`), recorded as open on the PR.
"""

from __future__ import annotations

import base64
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.ai_gateway import providers as p
from abacus.ai_gateway import routes
from abacus.ai_gateway.routes import _anthropic as a
from abacus.ai_gateway.routes import parity
from abacus.kernel.config import ParityRecord

pytestmark = pytest.mark.asyncio
REPO = Path(__file__).resolve().parents[4]
TODAY = date(2027, 12, 14)
SHA = "b" * 64


def _settings(monkeypatch: pytest.MonkeyPatch, **records: ParityRecord) -> None:
    fake = SimpleNamespace(
        model_routes=("direct", "bedrock", "fake"),
        environment="local",
        route_parity=records,
    )
    monkeypatch.setattr(routes, "settings", lambda: fake)
    monkeypatch.setattr(routes, "system_now", lambda: datetime(2027, 12, 14, 15, tzinfo=UTC))


def test_a_loop_spec_is_refused_on_a_route_without_tool_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _settings(
        monkeypatch,
        bedrock=ParityRecord(checked_on=date(2027, 11, 30), report_sha256=SHA),
        direct=ParityRecord(checked_on=date(2027, 11, 30), report_sha256=SHA, tool_parity=True),
    )
    assert routes.route_enabled_for("bedrock", "single")
    assert not routes.route_enabled_for("bedrock", "loop")
    assert routes.route_enabled_for("direct", "loop")
    assert routes.loop_routes(("bedrock", "direct")) == ("direct",)


def test_a_stale_report_serves_neither_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    old = date(2027, 9, 1)  # 104 days before TODAY
    _settings(
        monkeypatch,
        bedrock=ParityRecord(checked_on=old, report_sha256=SHA, tool_parity=True),
    )
    assert not routes.route_enabled_for("bedrock", "single")
    assert not routes.route_enabled_for("bedrock", "loop")
    assert routes.loop_routes(("bedrock",)) == ()


def test_the_fake_route_serves_loops_only_where_it_serves_at_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _settings(monkeypatch)
    assert routes.route_enabled_for("fake", "loop")
    assert not routes.route_enabled_for("direct", "loop")  # no record at all


def test_an_older_record_reads_as_single_turn_only() -> None:
    record = ParityRecord.model_validate({"checked_on": "2026-10-11", "report_sha256": SHA})
    assert record.tool_parity is False


def test_the_committed_direct_report_predates_tool_parity() -> None:
    body = (REPO / "docs/operations/route-parity/direct-2026-10-11.json").read_text()
    report = parity.read_report(body)
    assert report.passed  # complete() still served
    assert not report.tool_parity  # no loop spec on it until a new report


def test_tool_parity_needs_every_model_and_the_base_checks() -> None:
    good = parity.ModelParity("small", "m1", True, True, True, tools=True, documents=True)
    no_docs = parity.ModelParity("large", "m2", True, True, True, tools=True, documents=False)
    no_cache = parity.ModelParity("medium", "m3", True, False, True, tools=True, documents=True)
    assert parity.ParityReport("bedrock", "2027-12-01", (good,)).tool_parity
    assert not parity.ParityReport("bedrock", "2027-12-01", (good, no_docs)).tool_parity
    assert not parity.ParityReport("bedrock", "2027-12-01", (no_cache,)).tool_parity
    assert '"tool_parity": true' in parity.ParityReport("b", "d", (good,)).to_json()


def _reply(stop: p.StopReason, *blocks: p.TextBlock | p.ToolUseBlock) -> p.ConverseResponse:
    return p.ConverseResponse(blocks, stop, 1, 1, 0, 0, "m")


def test_the_tool_check_wants_one_call_with_the_given_code() -> None:
    right = p.ToolUseBlock("t1", "parity.echo_code", {"code": "TOOLS-0917"})
    assert parity.tool_turn_ok(_reply("tool_use", right))
    wrong_code = p.ToolUseBlock("t1", "parity.echo_code", {"code": "TOOLS-0000"})
    assert not parity.tool_turn_ok(_reply("tool_use", wrong_code))
    assert not parity.tool_turn_ok(_reply("tool_use", right, right))
    assert not parity.tool_turn_ok(_reply("end_turn", p.TextBlock("TOOLS-0917")))


def test_the_document_check_reads_the_code_back() -> None:
    assert parity.document_turn_ok(_reply("end_turn", p.TextBlock('{"code": "PARITY-4217"}')))
    assert parity.document_turn_ok(
        _reply("end_turn", p.TextBlock('```json\n{"code": "PARITY-4217"}\n```'))
    )
    assert not parity.document_turn_ok(_reply("end_turn", p.TextBlock('{"code": "PARITY-1"}')))
    assert not parity.document_turn_ok(_reply("end_turn", p.TextBlock("PARITY-4217")))


def test_the_probe_pdf_is_synthetic_and_carries_the_code() -> None:
    raw = parity._PDF  # pyright: ignore[reportPrivateUsage]
    assert raw.startswith(b"%PDF-1.4") and raw.rstrip().endswith(b"%%EOF")
    assert b"(PARITY-4217)" in raw
    assert base64.b64decode(base64.b64encode(raw)) == raw


class _Client:
    """Answers the probes in order with SDK messages built through the route adapter."""

    def __init__(self, *replies: object) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, object]] = []
        self.messages = self

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.replies.pop(0)


def _message(stop: str, *content: object) -> object:
    return a.Message.model_construct(
        id="m",
        type="message",
        role="assistant",
        model="m",
        content=list(content),
        stop_reason=stop,
        stop_sequence=None,
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )


async def test_the_tools_probe_runs_a_tool_turn_and_a_result_turn() -> None:
    use = a.SdkToolUseBlock.model_construct(
        type="tool_use", id="toolu_1", name="parity.echo_code", input={"code": "TOOLS-0917"}
    )
    done = a.TextBlock.model_construct(type="text", text="Recorded.")
    client = _Client(_message("tool_use", use), _message("end_turn", done))
    assert await parity._tools(cast(Any, client), "m")  # pyright: ignore[reportPrivateUsage]
    first, second = client.calls
    assert first["tool_choice"] == {"type": "any"}
    assert second["tool_choice"] == {"type": "none"}
    messages = cast(list[dict[str, Any]], second["messages"])
    assert messages[-1]["content"][0]["type"] == "tool_result"


async def test_the_documents_probe_sends_a_document_block() -> None:
    answer = a.TextBlock.model_construct(type="text", text='{"code": "PARITY-4217"}')
    client = _Client(_message("end_turn", answer))
    assert await parity._documents(cast(Any, client), "m")  # pyright: ignore[reportPrivateUsage]
    (call,) = client.calls
    content = cast(list[dict[str, Any]], call["messages"])[0]["content"]
    assert content[0]["type"] == "document"
    assert content[0]["source"]["media_type"] == "application/pdf"


async def test_a_probe_that_errors_is_a_failed_check() -> None:
    class Broken:
        messages = SimpleNamespace(create=None)

    assert not await parity._tools(cast(Any, Broken()), "m")  # pyright: ignore[reportPrivateUsage]
    assert not await parity._documents(cast(Any, Broken()), "m")  # pyright: ignore[reportPrivateUsage]
