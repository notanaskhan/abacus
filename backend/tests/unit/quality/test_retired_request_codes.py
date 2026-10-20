"""F-03-T15 (REQ-002): the retired request status codes are refused in the request paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import banned_patterns as bp

REL = "src/abacus/modules/requests/service.py"


def _ids(root: Path, source: str, rel: str = REL) -> list[str]:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return [v.rule_id for v in bp.scan(root)]


@pytest.mark.parametrize(
    "source",
    [
        'if item.status == "open":\n    pass\n',
        'q = select(X).where(RequestItem.status.in_(("open", "needs_revision")))\n',
        'q = update(X).values(status="accepted")\n',
        'ok = locked.status not in ("ready_for_review",)\n',
    ],
)
def test_t15_retired_codes_are_flagged(tmp_path: Path, source: str) -> None:
    assert "REQ-002" in _ids(tmp_path, source)


@pytest.mark.parametrize(
    "source",
    [
        'if item.status in ("draft", "requested"):\n    pass\n',
        'action = "needs_revision"\n',  # the screener's proposal, not a status
        'if acceptance.decision == "accepted":\n    pass\n',
    ],
)
def test_t15_new_codes_and_other_words_pass(tmp_path: Path, source: str) -> None:
    assert "REQ-002" not in _ids(tmp_path, source)


def test_t15_other_modules_keep_their_own_open(tmp_path: Path) -> None:
    rel = "src/abacus/modules/fieldwork/notes.py"
    assert "REQ-002" not in _ids(tmp_path, 'if note.status == "open":\n    pass\n', rel)
