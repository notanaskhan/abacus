# ac-test-author: ayushkbhatia
"""C-02-T57 (TASK-8945; ADR-040, CONN-001; ADR-078 suite 3): the vendor and payment read datasets
are read-only. A connections module that defines a write-shaped operation (create, update, post,
pay, delete …) for vendors or payments is a CONN-001 violation; a read is not."""

from __future__ import annotations

import textwrap
from pathlib import Path

from abacus_tools.quality import banned_patterns


def _module(tmp_path: Path, body: str) -> Path:
    backend = tmp_path / "backend"
    module = backend / "src" / "abacus" / "modules" / "connections"
    module.mkdir(parents=True)
    (module / "vendor_reads.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return backend


def test_ac_a_write_shaped_vendor_or_payment_method_is_refused(tmp_path: Path) -> None:
    backend = _module(
        tmp_path,
        """
        async def list_vendors(conn):
            return []

        async def create_vendor(conn, name):
            return None

        async def post_payment(conn, amount):
            return None
        """,
    )
    found = [v for v in banned_patterns.scan(backend) if v.rule_id == "CONN-001"]
    assert sorted(v.line for v in found) == [5, 8]


def test_ac_reads_alone_pass(tmp_path: Path) -> None:
    backend = _module(
        tmp_path,
        """
        async def list_vendors(conn):
            return []

        async def read_payments(conn, since):
            return []
        """,
    )
    assert [v for v in banned_patterns.scan(backend) if v.rule_id == "CONN-001"] == []
