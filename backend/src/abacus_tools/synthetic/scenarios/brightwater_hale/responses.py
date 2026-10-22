"""Load the scenario's recorded model responses into the fake model (F-04-T19; F-04.26).

Each `responses/*.json` file holds `{prompt_ref, content_sha256, response}`. `install(fake)`
records them on a `FakeModel`, which refuses to exist outside local runs and tests, so recorded
responses can only ever answer in a synthetic environment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, cast

from abacus.ai_gateway import FakeModel

DIRECTORY: Final = Path(__file__).parent / "responses"


class ResponseFileInvalid(ValueError):
    pass


def load(directory: Path = DIRECTORY) -> list[tuple[str, str, str]]:
    """(prompt_ref, content_sha256, text) for every response file, in file-name order."""
    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(directory.glob("*.json")):
        raw = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
        prompt, sha, response = (
            raw.get("prompt_ref"),
            raw.get("content_sha256"),
            raw.get("response"),
        )
        if not isinstance(prompt, str) or not isinstance(sha, str) or response is None:
            raise ResponseFileInvalid(f"{path.name}: prompt_ref, content_sha256, response")
        if (prompt, sha) in seen:
            raise ResponseFileInvalid(f"{path.name}: a second response for {prompt} and {sha}")
        seen.add((prompt, sha))
        out.append((prompt, sha, response if isinstance(response, str) else json.dumps(response)))
    return out


def install(fake: FakeModel, directory: Path = DIRECTORY) -> FakeModel:
    for prompt, sha, text in load(directory):
        fake.record(prompt, sha, text)
    return fake
