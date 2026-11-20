"""S52 Q-05 sweep (TASK-8824; Q-05-T08 remainder; SPEC-711 AC-34): the register import parses and
refuses by code."""

from __future__ import annotations

import pytest

from abacus.modules.practice import quality_register as reg

GOOD = (
    "level,component,ref,parent_ref,title,frequency\n"
    "objective,resources,QO-01,,People are competent,\n"
    "risk,,QR-01,QO-01,Staff lack training,\n"
    "response,,QS-01,QO-01,Annual CPE review,annual\n"
).encode()


def test_a_register_file_parses() -> None:
    rows = reg.parse(GOOD)
    assert [r["level"] for r in rows] == ["objective", "risk", "response"]


@pytest.mark.parametrize(
    "bad",
    [
        b"level,component,ref,parent_ref,title\nobjective,unknown,QO-01,,X\n",
        b"level,component,ref,parent_ref,title\nrisk,,QR-01,QO-09,X\n",
        b"level,component,ref,parent_ref,title\nobjective,resources,QO-01,,X\nobjective,resources,QO-01,,Y\n",
    ],
)
def test_a_bad_file_is_refused(bad: bytes) -> None:
    with pytest.raises(reg.ImportInvalid):
        reg.parse(bad)
