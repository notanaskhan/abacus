"""Route parity checks (SPEC-010 AC-5, Q2). PROTECTED. Real credentials, real (small) cost.

Per catalog model on a route: a structured reply, prompt caching (a repeated long system prompt
must read from the cache), and batch processing access (direct: a message batch created and
cancelled; Bedrock: the model invocation jobs API answers). Results are identifiers and booleans
only; no prompt or reply is kept.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, cast

import anthropic
import boto3
from anthropic.lib.bedrock import AsyncAnthropicBedrock
from anthropic.types import Message, TextBlock

from abacus.kernel.config import Route, settings

_SYSTEM = 'You are a parity probe. Reply with the JSON object {"ok": true} only. ' + (
    "This sentence pads the system prompt so it is long enough to be cached. " * 120
)


@dataclass(frozen=True)
class ModelParity:
    tier: str
    model_id: str
    structured: bool
    cache: bool
    batch: bool


@dataclass(frozen=True)
class ParityReport:
    route: str
    checked_on: str
    models: tuple[ModelParity, ...]

    @property
    def passed(self) -> bool:
        return bool(self.models) and all(m.structured and m.cache and m.batch for m in self.models)

    def to_json(self) -> str:
        return json.dumps({**asdict(self), "passed": self.passed}, indent=2, sort_keys=True)


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
        return cast(dict[str, object], json.loads(text)).get("ok") is True
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
            ModelParity(tier, model, structured, cache, await _batch(route, client, model))
        )
    return ParityReport(route, datetime.now(UTC).date().isoformat(), tuple(results))
