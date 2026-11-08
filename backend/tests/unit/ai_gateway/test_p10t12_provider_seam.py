"""P-10-T12 (TASK-6103; ADR-234; chapter 05 §5.3.2): provider seam v2.

Row acceptance: "Every existing gateway, screener and matcher test passes unchanged and a scripted
two-turn tool_use trajectory replays deterministically on FakeModel." The first half is the
existing suites themselves plus the pins below on `ModelRequest`, `ModelResponse` and
`message_args`; the second half is `test_a_two_turn_tool_use_trajectory_replays_deterministically`.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.ai_gateway import FakeModel, ProviderError
from abacus.ai_gateway import providers as p
from abacus.ai_gateway.routes import _anthropic as a
from abacus.ai_gateway.routes.bedrock import AnthropicOnBedrock
from abacus.ai_gateway.routes.direct import AnthropicDirect

# The SDK's types, through the route adapter (only the adapters import the SDK, ADR-019).
Message = a.Message
TextBlock = a.TextBlock
ToolUseBlock = a.SdkToolUseBlock

pytestmark = pytest.mark.asyncio
PROMPT = "runtime.conformance@v1"
TOOLS = (
    p.ToolSpec(
        "requests.list_items",
        "List the request items on an engagement.",
        {"type": "object", "properties": {"engagement_id": {"type": "string"}}},
    ),
    p.ToolSpec(
        "evidence.read_version",
        "Read one evidence version's extracted text.",
        {"type": "object", "properties": {"version_id": {"type": "string"}}},
    ),
)
SYSTEM = (
    p.SystemBlock("You are the Accrued Agent. Propose; never decide.", cache=True),
    p.SystemBlock("Firm: Brightwater Hale.", cache=True),
    p.SystemBlock("Engagement: Northwind Robotics 401(k) Plan, PY2025."),
)


def _request(*messages: p.ConverseMessage, choice: p.ToolChoice = "auto") -> p.ConverseRequest:
    return p.ConverseRequest(
        model="fake",
        system_blocks=SYSTEM,
        messages=messages,
        max_output_tokens=4000,
        prompt_ref=PROMPT,
        tools=TOOLS,
        tool_choice=choice,
    )


def _user(text: str) -> p.ConverseMessage:
    return p.ConverseMessage("user", (p.TextBlock(text),))


def _script(fake: FakeModel) -> None:
    fake.script(
        PROMPT,
        [
            p.ToolCallTurn(
                (("requests.list_items", {"engagement_id": "northwind-py2025"}),),
                text="I'll list the open requests first.",
            ),
            p.FinalTurn('{"summary": "3 requests open", "items": []}'),
        ],
    )


async def _run(fake: FakeModel) -> list[p.ConverseResponse]:
    first_user = _user("What is still open on Northwind?")
    first = await fake.converse(_request(first_user))
    assistant = p.ConverseMessage("assistant", first.content_blocks)
    results = p.ConverseMessage(
        "user",
        tuple(
            p.ToolResultBlock(use.id, '{"items": ["R-1", "R-2", "R-3"]}')
            for use in first.tool_uses
        ),
    )
    second = await fake.converse(_request(first_user, assistant, results))
    return [first, second]


# --- the trajectory -------------------------------------------------------------------------


async def test_a_two_turn_tool_use_trajectory_replays_deterministically() -> None:
    fake = FakeModel()
    _script(fake)
    once = await _run(fake)
    again = await _run(fake)
    assert once == again  # same blocks, ids, stop reasons and token counts
    first, second = once
    assert first.stop_reason == "tool_use"
    assert first.text == "I'll list the open requests first."
    (use,) = first.tool_uses
    assert use.name == "requests.list_items"
    assert dict(use.input) == {"engagement_id": "northwind-py2025"}
    assert use.id.startswith("toolu_fake_")
    assert second.stop_reason == "end_turn"
    assert second.tool_uses == ()
    assert second.text == '{"summary": "3 requests open", "items": []}'


async def test_a_new_fake_replays_the_same_ids() -> None:
    a_fake, b_fake = FakeModel(), FakeModel()
    _script(a_fake)
    _script(b_fake)
    assert await _run(a_fake) == await _run(b_fake)


async def test_cached_system_layers_write_once_then_read() -> None:
    fake = FakeModel()
    _script(fake)
    first, second = await _run(fake)
    assert first.cache_write_tokens > 0 and first.cache_read_tokens == 0
    assert second.cache_read_tokens == first.cache_write_tokens
    assert second.cache_write_tokens == 0


async def test_the_fake_refuses_what_a_real_model_could_not_do() -> None:
    fake = FakeModel()
    with pytest.raises(ProviderError):  # no script for the prompt
        await fake.converse(_request(_user("hi")))
    _script(fake)
    with pytest.raises(ProviderError):  # the script asks for a tool while tools are off
        await fake.converse(_request(_user("hi"), choice="none"))
    fake.script(PROMPT, [p.ToolCallTurn((("ledger.post_entry", {}),))])
    with pytest.raises(ProviderError):  # a tool that was not offered
        await fake.converse(_request(_user("hi")))
    fake.script(PROMPT, [p.FinalTurn("done")])
    done = p.ConverseMessage("assistant", (p.TextBlock("done"),))
    with pytest.raises(ProviderError):  # past the script's last turn
        await fake.converse(_request(_user("hi"), done, _user("and?")))


async def test_scripted_stop_reasons_reach_the_caller() -> None:
    fake = FakeModel()
    fake.script(PROMPT, [p.FinalTurn("{", stop_reason="max_tokens")])
    reply = await fake.converse(_request(_user("hi")))
    assert reply.stop_reason == "max_tokens"


# --- complete() is untouched (AC-G6) --------------------------------------------------------


def test_model_request_and_response_are_unchanged() -> None:
    assert [f.name for f in dataclasses.fields(p.ModelRequest)] == [
        "model",
        "system",
        "user",
        "max_output_tokens",
        "prompt_ref",
        "temperature",
    ]
    assert [f.name for f in dataclasses.fields(p.ModelResponse)] == [
        "text",
        "input_tokens",
        "output_tokens",
        "model",
    ]


def test_complete_s_arguments_are_unchanged() -> None:
    request = p.ModelRequest("m", "sys", "usr", 100, "x@v1")
    assert a.message_args(request) == {
        "model": "m",
        "max_tokens": 100,
        "system": [{"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": "usr"}],
    }


# --- the Anthropic mapping (both routes) ----------------------------------------------------


def test_converse_args_layers_tools_and_blocks() -> None:
    use = p.ToolUseBlock("toolu_1", "requests.list_items", {"engagement_id": "e"})
    request = _request(
        p.ConverseMessage(
            "user", (p.TextBlock("read this"), p.DocumentBlock("JVBERi0=", title="Trust report"))
        ),
        p.ConverseMessage("assistant", (use,)),
        p.ConverseMessage("user", (p.ToolResultBlock("toolu_1", "[]", is_error=True),)),
        choice="any",
    )
    args = a.converse_args(request)
    assert args["system"] == [
        {"type": "text", "text": SYSTEM[0].text, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": SYSTEM[1].text, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": SYSTEM[2].text},
    ]
    assert [t["name"] for t in args["tools"]] == ["requests.list_items", "evidence.read_version"]
    assert "cache_control" not in args["tools"][0]
    assert args["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    assert args["tool_choice"] == {"type": "any"}
    user, assistant, results = args["messages"]
    assert user["content"][1] == {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": "JVBERi0="},
        "title": "Trust report",
    }
    assert assistant["content"] == [
        {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "requests.list_items",
            "input": {"engagement_id": "e"},
        }
    ]
    assert results["content"] == [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "[]", "is_error": True}
    ]
    assert "stream" not in args  # AC-G7: never streamed


def test_no_tools_sends_no_tool_choice_and_any_needs_a_tool() -> None:
    bare = dataclasses.replace(_request(_user("hi")), tools=())
    assert "tools" not in a.converse_args(bare)
    assert "tool_choice" not in a.converse_args(bare)
    with pytest.raises(ValueError):
        a.converse_args(dataclasses.replace(bare, tool_choice="any"))


def _message(stop: str, *content: object, read: int = 7, write: int = 11) -> Message:
    return Message.model_construct(
        id="msg_1",
        type="message",
        role="assistant",
        model="claude",
        content=list(content),
        stop_reason=stop,
        stop_sequence=None,
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=20,
            cache_read_input_tokens=read,
            cache_creation_input_tokens=write,
        ),
    )


def test_a_tool_use_reply_maps_to_blocks_and_counts_cache_apart() -> None:
    message = _message(
        "tool_use",
        TextBlock.model_construct(type="text", text="Checking."),
        ToolUseBlock.model_construct(
            type="tool_use", id="toolu_9", name="requests.list_items", input={"a": 1}
        ),
    )
    reply = a.to_converse_response(message, "claude-sonnet-5-5")
    assert reply.stop_reason == "tool_use"
    assert reply.content_blocks == (
        p.TextBlock("Checking."),
        p.ToolUseBlock("toolu_9", "requests.list_items", {"a": 1}),
    )
    assert (reply.input_tokens, reply.output_tokens) == (100, 20)
    assert (reply.cache_read_tokens, reply.cache_write_tokens) == (7, 11)
    assert reply.model == "claude-sonnet-5-5"


@pytest.mark.parametrize(
    ("stop", "expected"),
    [
        ("end_turn", "end_turn"),
        ("stop_sequence", "end_turn"),
        ("max_tokens", "max_tokens"),
        ("refusal", "refusal"),
    ],
)
def test_stop_reasons_map_to_the_gateway_s_words(stop: str, expected: str) -> None:
    reply = a.to_converse_response(_message(stop), "m")
    assert reply.stop_reason == expected


@pytest.mark.parametrize("stop", ["pause_turn", "model_context_window_exceeded"])
def test_other_stop_reasons_are_provider_errors(stop: str) -> None:
    with pytest.raises(ProviderError):
        a.to_converse_response(_message(stop), "m")


class _Messages:
    def __init__(self, reply: Message | Exception) -> None:
        self.reply = reply
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> Message:
        self.calls.append(kwargs)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.mark.parametrize("route", [AnthropicDirect, AnthropicOnBedrock])
async def test_both_routes_converse_through_one_mapping(route: type) -> None:
    messages = _Messages(_message("end_turn", TextBlock.model_construct(type="text", text="ok")))
    provider = route(cast(Any, SimpleNamespace(messages=messages)))  # SDK object or JSON
    reply = await provider.converse(_request(_user("hi")))
    assert reply.text == "ok"
    assert messages.calls == [a.converse_args(_request(_user("hi")))]
    assert isinstance(provider, p.ConversingProvider)


@pytest.mark.parametrize("route", [AnthropicDirect, AnthropicOnBedrock])
async def test_route_errors_carry_no_provider_message(route: type) -> None:
    messages = _Messages(RuntimeError("the prompt text echoed back"))
    provider = route(cast(Any, SimpleNamespace(messages=messages)))  # SDK object or JSON
    with pytest.raises(ProviderError) as caught:
        await provider.converse(_request(_user("hi")))
    assert "prompt" not in str(caught.value)


def test_a_provider_without_seam_v2_cannot_converse() -> None:
    class OnlyComplete:
        async def complete(self, request: p.ModelRequest) -> p.ModelResponse:
            raise NotImplementedError

    with pytest.raises(ProviderError):
        p.conversing(OnlyComplete())
    assert p.conversing(FakeModel()) is not None
