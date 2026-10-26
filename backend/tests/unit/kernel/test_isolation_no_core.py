"""Security review M2 (P-03-T19): the isolated child never writes a core file, so a hostile file
that crashes a parser can't leave decrypted bytes or a password on disk."""

from __future__ import annotations

import resource

from abacus.kernel.isolation import run_isolated


def test_the_child_runs_with_no_core_dumps() -> None:
    assert run_isolated(resource.getrlimit, resource.RLIMIT_CORE) == (0, 0)
