"""Context assembly for model calls (ADR-050, ADR-051, ADR-052). PROTECTED. TASK-011 design §4.

The only way to build a gateway input. Five layers, always in this order: instructions, firm,
engagement, examples, task. Each has a token budget; text over budget is cut and the cut is
recorded, except the task layer, which is never cut mid-text (that could sever an `<untrusted>`
block): it drops items from the end of one named list until it fits (`trim`, recorded as
truncated), or is refused (`ContextTooLarge`). Untrusted values (client content, named by the
agent's spec) go into labelled `<untrusted>` blocks, JSON-encoded so they can't close the block
or pose as instructions. Task input is structured data: any list longer than `MAX_ROWS` is
refused (code computes, models judge: raw ledger data never reaches a model).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Literal, cast

LayerName = Literal["instructions", "firm", "engagement", "examples", "task"]
LAYERS: tuple[LayerName, ...] = ("instructions", "firm", "engagement", "examples", "task")
MAX_ROWS = 200
CHARS_PER_TOKEN = 4
DEFAULT_BUDGETS: dict[LayerName, int] = {
    "instructions": 1_000,
    "firm": 500,
    "engagement": 500,
    "examples": 1_000,
    "task": 4_000,
}


class DatasetTooLarge(ValueError):
    """Task input carried a list longer than MAX_ROWS (ADR-050)."""


class ContextTooLarge(ValueError):
    """The task layer doesn't fit its budget, even after trimming."""


def estimate_tokens(text: str) -> int:
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def _encode(value: object) -> str:
    # JSON with "<" escaped: an untrusted value can't open or close a delimiter block.
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).replace(
        "<", "\\u003c"
    )


def _longest_list(value: object) -> int:
    if isinstance(value, list | tuple):
        items = list(cast(Collection[object], value))
        return max([len(items), *(_longest_list(v) for v in items)])
    if isinstance(value, Mapping):
        return max([0, *(_longest_list(v) for v in cast(Mapping[object, object], value).values())])
    return 0


def _task_text(data: Mapping[str, object], untrusted: Collection[str]) -> str:
    trusted = {k: v for k, v in data.items() if k not in untrusted}
    blocks = [_encode(trusted)]
    for name in sorted(k for k in data if k in untrusted):
        blocks.append(f'<untrusted name="{name}">\n{_encode(data[name])}\n</untrusted>')
    return "\n".join(blocks)


@dataclass(frozen=True)
class Layer:
    name: LayerName
    text: str
    truncated: bool


@dataclass(frozen=True)
class AssembledContext:
    layers: tuple[Layer, ...]

    def render(self) -> str:
        return "\n\n".join(f"## {layer.name}\n{layer.text}" for layer in self.layers if layer.text)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.render().encode()).hexdigest()

    @property
    def truncated(self) -> tuple[LayerName, ...]:
        return tuple(layer.name for layer in self.layers if layer.truncated)


@dataclass
class ContextBuilder:
    budgets: Mapping[LayerName, int] = field(default_factory=lambda: dict(DEFAULT_BUDGETS))
    _texts: dict[LayerName, str] = field(default_factory=dict[LayerName, str])
    _trimmed: bool = False

    def text(self, layer: LayerName, text: str) -> ContextBuilder:
        if layer == "task":
            raise ValueError("task input is structured: use task()")
        if layer == "instructions":
            # Instructions are the registered prompt's (ADR-057), sent as the system message.
            raise ValueError("instructions come from the prompt registry")
        self._texts[layer] = text
        return self

    def task(
        self,
        data: Mapping[str, object],
        *,
        untrusted: Collection[str] = (),
        trim: str | None = None,
    ) -> ContextBuilder:
        """`untrusted` names the fields holding client content (from the agent's spec); `trim`
        names a list that may lose items from its end to fit the task budget."""
        if _longest_list(data) > MAX_ROWS:
            raise DatasetTooLarge(f"task input lists are limited to {MAX_ROWS} rows")
        limit = self.budgets.get("task", DEFAULT_BUDGETS["task"]) * CHARS_PER_TOKEN
        values = dict(data)
        trimmed = False
        text = _task_text(values, untrusted)
        while len(text) > limit:
            items = values.get(trim) if trim is not None else None
            if not isinstance(items, list) or not items:
                raise ContextTooLarge("task input exceeds its budget")
            values[cast(str, trim)] = cast(list[object], items)[:-1]
            trimmed = True
            text = _task_text(values, untrusted)
        self._texts["task"] = text
        self._trimmed = trimmed
        return self

    def build(self) -> AssembledContext:
        layers: list[Layer] = []
        for name in LAYERS:
            text = self._texts.get(name, "")
            if name == "task":
                layers.append(Layer(name, text, self._trimmed))
                continue
            limit = self.budgets.get(name, DEFAULT_BUDGETS[name]) * CHARS_PER_TOKEN
            layers.append(Layer(name, text[:limit], len(text) > limit))
        return AssembledContext(tuple(layers))
