"""DEC-453 (security review L4): the label indexer's run visits every firm once, starting at a
different firm each minute, so a run that spends its budget never leaves out the same firms."""

from __future__ import annotations

import uuid

from abacus.modules.audit_trail.jobs import label_run_order


def test_dec453_every_firm_once_from_a_rotating_start() -> None:
    firms = [uuid.uuid4() for _ in range(5)]
    orders = [label_run_order(firms, minute) for minute in range(5)]
    assert all(sorted(o, key=str) == sorted(firms, key=str) for o in orders)
    assert len({o[0] for o in orders}) == 5  # each firm goes first once in five minutes
    assert label_run_order([], 7) == []
