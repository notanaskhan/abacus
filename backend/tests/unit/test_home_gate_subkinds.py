"""I-01-T23: every gate subkind a source registers renders in words on HOME-01 and HOME-02, and no
retired flag is left behind (the row's check)."""

from __future__ import annotations

from pathlib import Path

from abacus.kernel import _flags
from abacus.modules.notices import api as _notices  # noqa: F401
from abacus.modules.review.gates import _SOURCES
from abacus.modules.signatures import api as _signatures  # noqa: F401

MESSAGES = Path(__file__).parents[3] / "apps/web/src/domain/home/messages.ts"


def test_the_gates_landing_s13_to_s29_have_words() -> None:
    words = MESSAGES.read_text()
    for name in ("envelope_send", "envelope_countersign", "notice_response_send"):
        assert name in _SOURCES
        assert name in words


def test_the_home_flags_are_retired() -> None:
    assert not hasattr(_flags, "HOME_DASHBOARD")
    assert not hasattr(_flags, "HOME_APPROVALS")
