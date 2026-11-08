"""Route parity checks (SPEC-010 AC-5, Q2). PROTECTED. Real credentials, real (small) cost.

Per catalog model on a route: a structured reply, prompt caching (a repeated long system prompt
must read from the cache), and batch processing access (direct: a message batch created and
cancelled; Bedrock: the model invocation jobs API answers). Results are identifiers and booleans
only; no prompt or reply is kept.

P-10-T13 (ADR-234 §7): two more checks per model, through seam v2's own mapping
(`converse_args`, `to_converse_response`): **tools** (offered one tool with `tool_choice: any`,
the model asks for it with schema-valid arguments, and a `tool_result` turn ends the
conversation) and **documents** (a one-page synthetic PDF is read back). `complete()`'s pass is
unchanged; a loop-shaped spec needs `tool_parity` as well (`routes.route_enabled_for`).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, cast

import anthropic
import boto3
from anthropic.lib.bedrock import AsyncAnthropicBedrock
from anthropic.types import Message, TextBlock

from abacus.ai_gateway import providers as p
from abacus.ai_gateway import unfenced
from abacus.ai_gateway.routes._anthropic import converse_args, to_converse_response
from abacus.kernel.clock import system_now
from abacus.kernel.config import Route, settings

_SYSTEM = 'You are a parity probe. Reply with the JSON object {"ok": true} only. ' + (
    # Past every model's minimum cacheable prompt (Haiku models need 2,048 tokens or more).
    "This sentence pads the system prompt so it is long enough to be cached. " * 320
)


# A one-page PDF whose only text is the code below: synthetic, no client data, built by hand so
# the probe needs no PDF library. The model must read the code back from the document block.
_DOC_CODE = "PARITY-4217"
_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>"
    b"/Contents 5 0 R>>endobj\n4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"5 0 obj<</Length 42>>stream\nBT /F1 24 Tf 72 700 Td (PARITY-4217) Tj ET\nendstream\n"
    b"endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
)
_TOOL = p.ToolSpec(
    "parity.echo_code",
    "Record a parity code. Call it exactly once with the code you were given.",
    {
        "type": "object",
        "properties": {"code": {"type": "string", "pattern": "^[A-Z]+-[0-9]+$"}},
        "required": ["code"],
        "additionalProperties": False,
    },
)
_TOOL_CODE = "TOOLS-0917"


@dataclass(frozen=True)
class ModelParity:
    tier: str
    model_id: str
    structured: bool
    cache: bool
    batch: bool
    tools: bool = False  # P-10-T13; reports before it read as no tool parity
    documents: bool = False


@dataclass(frozen=True)
class ParityReport:
    route: str
    checked_on: str
    models: tuple[ModelParity, ...]

    @property
    def passed(self) -> bool:
        return bool(self.models) and all(m.structured and m.cache and m.batch for m in self.models)

    @property
    def tool_parity(self) -> bool:
        """Tools and documents on every model, on top of `passed`: what a loop spec needs."""
        return self.passed and all(m.tools and m.documents for m in self.models)

    def to_json(self) -> str:
        return json.dumps(
            {**asdict(self), "passed": self.passed, "tool_parity": self.tool_parity},
            indent=2,
            sort_keys=True,
        )


def read_report(body: str) -> ParityReport:
    """A committed report, old or new (reports before P-10-T13 carry no tools or documents)."""
    raw = cast(dict[str, Any], json.loads(body))
    models = tuple(
        ModelParity(
            tier=str(m["tier"]),
            model_id=str(m["model_id"]),
            structured=bool(m["structured"]),
            cache=bool(m["cache"]),
            batch=bool(m["batch"]),
            tools=bool(m.get("tools", False)),
            documents=bool(m.get("documents", False)),
        )
        for m in cast(list[dict[str, Any]], raw["models"])
    )
    return ParityReport(str(raw["route"]), str(raw["checked_on"]), models)


def _client(route: Route) -> anthropic.AsyncAnthropic | AsyncAnthropicBedrock:
    s = settings()
    if route == "direct":
        if s.anthropic_api_key is None:
            raise RuntimeError("the direct route needs anthropic_api_key")
        return anthropic.AsyncAnthropic(api_key=s.anthropic_api_key.get_secret_value())
    return AsyncAnthropicBedrock(aws_region=s.bedrock_region)


async def _ask(client: anthropic.AsyncAnthropic | AsyncAnthropicBedrock, model: str) -> Message:
    return await client.messages.create(
        model=model,
        max_tokens=20,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": "probe"}],
    )


def _structured(message: Message) -> bool:
    text = "".join(b.text for b in message.content if isinstance(b, TextBlock)).strip()
    try:
        # As the gateway reads answers: one surrounding code fence is allowed.
        return cast(dict[str, object], json.loads(unfenced(text))).get("ok") is True
    except ValueError:
        return False


async def _batch(
    route: Route, client: anthropic.AsyncAnthropic | AsyncAnthropicBedrock, model: str
) -> bool:
    try:
        if route == "direct":
            if not isinstance(client, anthropic.AsyncAnthropic):
                return False
            batch = await client.messages.batches.create(
                requests=[
                    {
                        "custom_id": "parity",
                        "params": {
                            "model": model,
                            "max_tokens": 5,
                            "messages": [{"role": "user", "content": "probe"}],
                        },
                    }
                ]
            )
            await client.messages.batches.cancel(batch.id)
            return True
        bedrock = cast(
            Any,  # boto3 clients are untyped without the bedrock stubs (not on the allowlist)
            boto3.client(  # pyright: ignore[reportUnknownMemberType] -- untyped boto3 factory
                "bedrock", region_name=settings().bedrock_region
            ),
        )
        bedrock.list_model_invocation_jobs(maxResults=1)
        return True
    except Exception:
        return False


async def _converse(
    client: anthropic.AsyncAnthropic | AsyncAnthropicBedrock, request: p.ConverseRequest
) -> p.ConverseResponse:
    message = cast(Message, await client.messages.create(**converse_args(request)))
    return to_converse_response(message, request.model)


def tool_turn_ok(reply: p.ConverseResponse) -> bool:
    """The model asked for the one offered tool, once, with exactly the code it was given."""
    uses = reply.tool_uses
    return (
        reply.stop_reason == "tool_use"
        and len(uses) == 1
        and uses[0].name == _TOOL.name
        and dict(uses[0].input) == {"code": _TOOL_CODE}
    )


def document_turn_ok(reply: p.ConverseResponse) -> bool:
    try:
        answer = cast(dict[str, object], json.loads(unfenced(reply.text.strip())))
    except ValueError:
        return False
    return reply.stop_reason == "end_turn" and answer.get("code") == _DOC_CODE


async def _tools(client: anthropic.AsyncAnthropic | AsyncAnthropicBedrock, model: str) -> bool:
    try:
        ask = p.ConverseMessage("user", (p.TextBlock(f"The code is {_TOOL_CODE}."),))
        request = p.ConverseRequest(
            model=model,
            system_blocks=(p.SystemBlock("You are a parity probe."),),
            messages=(ask,),
            max_output_tokens=200,
            prompt_ref="parity.tools@v1",
            tools=(_TOOL,),
            tool_choice="any",
        )
        first = await _converse(client, request)
        if not tool_turn_ok(first):
            return False
        result = p.ConverseMessage(
            "user", (p.ToolResultBlock(first.tool_uses[0].id, '{"recorded": true}'),)
        )
        follow = p.ConverseRequest(
            model=model,
            system_blocks=request.system_blocks,
            messages=(ask, p.ConverseMessage("assistant", first.content_blocks), result),
            max_output_tokens=200,
            prompt_ref="parity.tools@v1",
            tools=(_TOOL,),
            tool_choice="none",
        )
        second = await _converse(client, follow)
        return second.stop_reason == "end_turn" and not second.tool_uses
    except Exception:
        return False


async def _documents(client: anthropic.AsyncAnthropic | AsyncAnthropicBedrock, model: str) -> bool:
    import base64

    try:
        request = p.ConverseRequest(
            model=model,
            system_blocks=(p.SystemBlock('Reply with the JSON object {"code": "<code>"} only.'),),
            messages=(
                p.ConverseMessage(
                    "user",
                    (
                        p.DocumentBlock(base64.b64encode(_PDF).decode(), title="Parity probe"),
                        p.TextBlock("What code is printed on the page?"),
                    ),
                ),
            ),
            max_output_tokens=50,
            prompt_ref="parity.documents@v1",
        )
        return document_turn_ok(await _converse(client, request))
    except Exception:
        return False


async def check_route(route: Route) -> ParityReport:
    client = _client(route)
    results: list[ModelParity] = []
    for tier, entry in sorted(settings().model_catalog.items()):
        model = entry.ids.get(route)
        if model is None:
            continue
        try:
            first = await _ask(client, model)
            second = await _ask(client, model)
            structured = _structured(first)
            cache = (getattr(second.usage, "cache_read_input_tokens", 0) or 0) > 0
        except Exception:
            structured = cache = False
        results.append(
            ModelParity(
                tier,
                model,
                structured,
                cache,
                await _batch(route, client, model),
                tools=await _tools(client, model),
                documents=await _documents(client, model),
            )
        )
    return ParityReport(route, system_now().date().isoformat(), tuple(results))
