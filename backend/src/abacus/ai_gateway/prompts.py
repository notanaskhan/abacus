"""The prompt registry (ADR-019). PROTECTED. TASK-011 design §2.

Prompts are files: `prompts/<id>/<version>.txt`, referenced as `<id>@<version>` (for example
`evidence.screen@v0`). Never edited once used: a change is a new version. Inline prompt strings
elsewhere are banned (PROMPT-001).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).parent / "prompts"
_REF = re.compile(r"(?P<id>[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)@(?P<version>v[0-9]+)")


class UnknownPrompt(LookupError):
    """No registered prompt with this id and version."""


@dataclass(frozen=True)
class Prompt:
    id: str
    version: str
    text: str
    sha256: str

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"


@cache
def registry() -> dict[str, Prompt]:
    prompts: dict[str, Prompt] = {}
    for path in sorted(ROOT.glob("*/*.txt")):
        ref = f"{path.parent.name}@{path.stem}"
        match = _REF.fullmatch(ref)
        if match is None:
            raise ValueError(f"prompt file {path.name} in {path.parent.name} is not <id>@v<N>")
        text = path.read_text(encoding="utf-8")
        prompts[ref] = Prompt(
            match["id"], match["version"], text, hashlib.sha256(text.encode()).hexdigest()
        )
    return prompts


def prompt(ref: str) -> Prompt:
    found = registry().get(ref)
    if found is None:
        raise UnknownPrompt(ref)
    return found
