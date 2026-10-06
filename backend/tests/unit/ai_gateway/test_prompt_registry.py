"""AC-14: the prompt registry (TASK-011a interface contract, "Prompt registry"; ADR-019).

Prompts are files `prompts/<id>/<version>.txt`, referenced as `<id>@<version>`. Expectations come
from the contract: the reference names the file, the hash is the text's, anything else is unknown.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest

import abacus.ai_gateway
from abacus.ai_gateway import Prompt, UnknownPrompt, prompt, registry

PROMPTS = Path(abacus.ai_gateway.__file__).parent / "prompts"
SCREEN = "evidence.screen@v0"


def _files() -> list[Path]:
    return sorted(PROMPTS.glob("*/*.txt"))


def test_ac14_a_registered_prompt_has_its_id_version_text_and_hash() -> None:
    found = prompt(SCREEN)
    assert isinstance(found, Prompt)
    assert (found.id, found.version) == ("evidence.screen", "v0")
    assert found.ref == SCREEN
    assert found.text == (PROMPTS / "evidence.screen" / "v0.txt").read_text(encoding="utf-8")
    assert found.sha256 == hashlib.sha256(found.text.encode()).hexdigest()
    assert len(found.sha256) == 64


def test_ac14_the_registry_lists_every_prompt_file_and_nothing_else() -> None:
    expected = {f"{path.parent.name}@{path.stem}" for path in _files()}
    assert expected  # the screener's prompt at least
    assert set(registry()) == expected


def test_ac14_every_registry_entry_is_keyed_by_its_own_reference() -> None:
    for ref, found in registry().items():
        assert found.ref == ref
        assert found.text.strip()
        assert found.sha256 == hashlib.sha256(found.text.encode()).hexdigest()


def test_ac14_a_lookup_returns_the_registered_object() -> None:
    assert prompt(SCREEN) == registry()[SCREEN]


@pytest.mark.parametrize(
    "ref",
    [
        "evidence.screen@v1",
        "evidence.screen@v99",
        "evidence.nothing@v0",
        "other.screen@v0",
        "evidence.screen",
        "evidence.screen@",
        "@v0",
        "",
        " ",
        "evidence.screen@V0",
        "Evidence.Screen@v0",
        "evidence.screen@v0 ",
        " evidence.screen@v0",
        "evidence.screen@v0\n",
        "evidence.screen@0",
        "evidence.screen@v",
        "evidence.screen@v-1",
        "evidence.screen@v0@v0",
        "../evidence.screen@v0",
        "evidence/screen@v0",
        "evidence.screen/v0",
        "evidence.screen@v0.txt",
        "You are a helpful assistant. Screen this trial balance.",
    ],
)
def test_ac14_an_unknown_or_malformed_reference_is_unknown_prompt(ref: str) -> None:
    with pytest.raises(UnknownPrompt):
        prompt(ref)


def test_ac14_unknown_prompt_is_a_lookup_error() -> None:
    assert issubclass(UnknownPrompt, LookupError)


def test_ac14_a_prompt_cannot_be_edited_after_the_fact() -> None:
    found = prompt(SCREEN)
    with pytest.raises(dataclasses.FrozenInstanceError):
        Prompt.__setattr__(found, "text", "changed")


def test_ac14_the_screening_prompt_treats_untrusted_blocks_as_data() -> None:
    text = prompt(SCREEN).text
    assert "<untrusted" in text
    assert "JSON" in text
