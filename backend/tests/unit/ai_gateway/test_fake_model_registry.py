"""F-04-T19 (F-04.26): "Responses load from data keyed by prompt and content hash in synthetic
environments only"."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from abacus.ai_gateway import FakeModel, ProviderError
from abacus.ai_gateway import providers as providers_module
from abacus.ai_gateway.providers import ModelRequest
from abacus_tools.synthetic.scenarios.brightwater_hale import responses

pytestmark = pytest.mark.asyncio
DOC_SHA = hashlib.sha256(b"Northwind 401(k) Plan certified trust report").hexdigest()
PROMPT = "evidence.screen@v0"


def _request(user: str, prompt: str = PROMPT) -> ModelRequest:
    return ModelRequest(
        model="fake", system="s", user=user, max_output_tokens=100, prompt_ref=prompt
    )


async def test_a_recorded_response_answers_its_prompt_and_document() -> None:
    fake = FakeModel()
    fake.record(PROMPT, DOC_SHA, '{"action": "ready_for_review"}')
    reply = await fake.complete(_request(f'## task\n{{"document": "{DOC_SHA}"}}'))
    assert reply.text == '{"action": "ready_for_review"}'
    with pytest.raises(ProviderError):  # same prompt, another document, no responder
        await fake.complete(_request("## task\n{}"))
    with pytest.raises(ProviderError):  # same document, another prompt
        await fake.complete(_request(f"names {DOC_SHA}", "evidence.match@v2"))


async def test_the_whole_input_hash_also_matches_and_responders_still_answer() -> None:
    fake = FakeModel({PROMPT: lambda _request: "responder"})
    user = "## task\n{}"
    fake.record(PROMPT, hashlib.sha256(user.encode()).hexdigest(), "recorded")
    assert (await fake.complete(_request(user))).text == "recorded"
    assert (await fake.complete(_request("other"))).text == "responder"


def test_a_recorded_key_is_a_sha256() -> None:
    with pytest.raises(ValueError, match="64-hex"):
        FakeModel().record(PROMPT, "not-a-hash", "x")


async def test_files_load_into_the_fake(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text(
        json.dumps({"prompt_ref": PROMPT, "content_sha256": DOC_SHA, "response": {"ok": True}})
    )
    fake = responses.install(FakeModel(), tmp_path)
    assert json.loads((await fake.complete(_request(DOC_SHA))).text) == {"ok": True}
    (tmp_path / "b.json").write_text(
        json.dumps({"prompt_ref": PROMPT, "content_sha256": DOC_SHA, "response": "again"})
    )
    with pytest.raises(responses.ResponseFileInvalid, match="second response"):
        responses.load(tmp_path)


def test_the_checked_in_responses_load() -> None:
    assert isinstance(responses.load(), list)


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_the_fake_and_its_recordings_are_refused_outside_synthetic_environments(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setattr(
        providers_module, "settings", lambda: SimpleNamespace(environment=environment)
    )
    with pytest.raises(RuntimeError, match="local runs and tests only"):
        FakeModel()
