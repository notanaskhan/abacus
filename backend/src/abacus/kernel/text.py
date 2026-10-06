"""Text field types for request models: client content is hostile (AGENTS.md #8).

NUL can't be stored in Postgres (it would surface as a 500) and control characters have no place
in names; descriptions may keep newlines and tabs. Rejected values are 422s, never echoed.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_CONTROL_EXCEPT_LAYOUT = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _single_line(value: str) -> str:
    if _CONTROL.search(value):
        raise ValueError("must not contain control characters")
    return value


def _multi_line(value: str) -> str:
    if _CONTROL_EXCEPT_LAYOUT.search(value):
        raise ValueError("must not contain control characters other than newline and tab")
    return value


SingleLineText = Annotated[str, AfterValidator(_single_line)]
MultiLineText = Annotated[str, AfterValidator(_multi_line)]
