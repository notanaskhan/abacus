"""A-06-T14 (TASK-3214; DEC-2214): AUD-17's re-review request and note bands.

Row acceptance: "Reopen returns a cleared note to Open and blocks L2+ again, re-review notifies
the stale signer, and the list returns 2 + 1 + 11 = 14 for Northwind." Reopen is C3's existing
note event (`reopened` returns a cleared note to `open`, P-04-T21); pinned here are the
re-review request's matrix row, its notification, and the bands.
"""

from __future__ import annotations

from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.notifications import catalogue
from abacus.modules.review import notes
from abacus.modules.review.re_review import bands_of


def test_ac_reopen_returns_a_cleared_note_to_open() -> None:
    assert notes.AFTER["reopened"] == "open"


def test_ac_re_review_is_a_persons_act_and_tells_the_signer() -> None:
    rule = RULES["sign_off.request_re_review"]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system", "deny") == "deny"
    kind = catalogue.CATALOGUE["sign_off.re_review_requested"]
    assert kind.kind == "sign_off_re_review"
    assert kind.recipients is catalogue._signer  # pyright: ignore[reportPrivateUsage] -- the private helper under test


def test_ac_northwind_bands_foot_to_fourteen() -> None:
    bands = bands_of({"open": 2, "responded": 1, "cleared": 11, "withdrawn": 3})
    assert (bands.open, bands.responded, bands.cleared, bands.total) == (2, 1, 11, 14)
