# ac-test-author: ayushkbhatia
"""Q-05-T26 (TASK-8941; ADR P-43; A-07 F8): the archived-write kinds, `post_issuance` among them,
are settable only from the allowlisted services. A module file outside the allowlist that calls
`allow_archived_write` or names `app.archived_write` is an ARCHIVE-001 violation."""

from __future__ import annotations

import textwrap
from pathlib import Path

from abacus_tools.quality import banned_patterns


def test_ac_the_archived_write_kind_is_settable_only_from_allowlisted_files(
    tmp_path: Path,
) -> None:
    backend = tmp_path / "backend"
    module = backend / "src" / "abacus" / "modules" / "rogue"
    module.mkdir(parents=True)
    (module / "service.py").write_text(
        textwrap.dedent(
            """
            async def sneak(tx):
                await tx.allow_archived_write("post_issuance")

            SETTING = "app.archived_write"
            """
        ),
        encoding="utf-8",
    )
    found = [v for v in banned_patterns.scan(backend) if v.rule_id == "ARCHIVE-001"]
    assert {v.line for v in found} == {3, 5}
    assert all(v.path.endswith("modules/rogue/service.py") for v in found)
