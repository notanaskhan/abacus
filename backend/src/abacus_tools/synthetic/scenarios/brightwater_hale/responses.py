"""Load the scenario's recorded model responses into the fake model (F-04-T19; F-04.26).

Each `responses/*.json` file holds `{prompt_ref, content_sha256, response}`. `install(fake)`
records them on a `FakeModel`, which refuses to exist outside local runs and tests, so recorded
responses can only ever answer in a synthetic environment.

F-04-T25 adds the files, written by hand from the scenario documents (`documents.py`): every
citation resolves to one of the document's fixed regions and is verified by code, except the one
planted unsupported value, `PLANTED_UNSUPPORTED`, which verification marks unverified so that
SHL-10c and SHL-09e show "Uncited" with the approve control disabled (INV-2).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, cast

from abacus.ai_gateway import FakeModel

DIRECTORY: Final = Path(__file__).parent / "responses"
# (file, citation index): the screener cites the accrual-basis contributions, 1,366,900.00 (which
# include the 48,600 receivable fieldwork finds later), against the trust-basis trial balance's
# cell D11, which holds 1,318,300.00. Code finds the value mismatch: the value is "Uncited".
PLANTED_UNSUPPORTED: Final = ("northwind_trial_balance.screen.json", 3)


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
