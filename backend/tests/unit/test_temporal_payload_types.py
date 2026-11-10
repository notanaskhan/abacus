"""Temporal payloads never carry `object` (S35 end pass; the S34 lesson, made twice).

Temporal's payload converter cannot decode a value typed `object`: an activity whose argument or
result dataclass holds `dict[str, object]` fails "Failed decoding arguments" at runtime and the
workflow task retries for ever (`AgentRunWorkflow` in S34, `RunFacts.plan` in S35). Unit tests
that call the activity directly never see it. This walks every activity, and every workflow's run,
signal, query and update handler, through their type hints and nested dataclasses, and fails on
`object`. Use `Any` with a `# Any: JSON` comment instead.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
import typing
from collections.abc import Callable, Iterator

import abacus.modules as modules

_HANDLERS = (
    "__temporal_workflow_run",
    "__temporal_signal_definition",
    "__temporal_query_definition",
    "__temporal_update_definition",
)


def _temporal_callables() -> Iterator[tuple[str, Callable[..., typing.Any]]]:  # Any: any handler
    for info in pkgutil.walk_packages(modules.__path__, modules.__name__ + "."):
        try:
            module = importlib.import_module(info.name)
        except (ImportError, OSError):
            continue  # a native library (WeasyPrint's) missing on this machine
        for value in vars(module).values():
            if getattr(value, "__module__", None) != info.name:
                continue
            if callable(value) and hasattr(value, "__temporal_activity_definition"):
                yield f"{info.name}.{value.__qualname__}", value
            elif inspect.isclass(value) and hasattr(value, "__temporal_workflow_definition"):
                for member in vars(value).values():
                    if callable(member) and any(hasattr(member, h) for h in _HANDLERS):
                        yield f"{info.name}.{member.__qualname__}", member


def _objects(hint: object, where: str, seen: set[type]) -> Iterator[str]:
    if hint is object:
        yield where
        return
    if isinstance(hint, type) and dataclasses.is_dataclass(hint):
        if hint in seen:
            return
        seen.add(hint)
        for name, field_hint in typing.get_type_hints(hint).items():
            yield from _objects(field_hint, f"{where}.{hint.__name__}.{name}", seen)
        return
    for arg in typing.get_args(hint):
        yield from _objects(arg, where, seen)


def test_no_temporal_activity_or_handler_carries_object() -> None:
    found: list[str] = []
    checked = 0
    seen: set[type] = set()
    for name, fn in _temporal_callables():
        checked += 1
        for param, hint in typing.get_type_hints(fn).items():
            found.extend(_objects(hint, f"{name}:{param}", seen))
    assert checked > 50, checked
    assert found == [], "Temporal cannot decode `object`; use `Any  # Any: JSON`:\n" + "\n".join(
        sorted(set(found))
    )
