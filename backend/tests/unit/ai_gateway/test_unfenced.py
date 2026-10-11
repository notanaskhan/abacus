"""SPEC-026 (TASK-049): some models wrap JSON answers in one Markdown code fence; the gateway
reads the JSON inside, and nothing else changes."""

from __future__ import annotations

import pytest

from abacus.ai_gateway import unfenced


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('```json\n{"ok": true}\n```', '{"ok": true}'),
        ('```\n{"ok": true}\n```', '{"ok": true}'),
        ('  ```json\n{"a": 1,\n "b": 2}\n```  ', '{"a": 1,\n "b": 2}'),
        ('{"ok": true}', '{"ok": true}'),  # bare JSON: unchanged
        ('Here you go: ```json\n{"ok": true}\n```', 'Here you go: ```json\n{"ok": true}\n```'),
        ('```json\n{"ok": true}\n```\n```json\n{}\n```', '{"ok": true}\n```\n```json\n{}'),
    ],
)
def test_one_surrounding_fence_is_removed(body: str, expected: str) -> None:
    assert unfenced(body) == expected
