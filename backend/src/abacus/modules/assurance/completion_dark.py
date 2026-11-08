"""A-07's code-level kill constant (A-07-T22, T23; DEC-2806).

The completion projector and the bring-down workflow run only when this is True **and** the firm's
`assurance_release_mode` is `in_app`. No firm is `in_app` before M16 (Tue Mar 21, 2028), and this
stays False until the M16 flip PR sets it, so neither the subscriber nor the timer does anything in
any environment until then: a second key on top of the firm setting, so a mis-set firm setting
alone cannot start them. The A-07 rows place it at `assurance/completion/_dark.py`; `completion`
is already a module, so it lives beside it.
"""

from __future__ import annotations

from typing import Final

COMPLETION_LIVE: Final = False

__all__ = ["COMPLETION_LIVE"]
