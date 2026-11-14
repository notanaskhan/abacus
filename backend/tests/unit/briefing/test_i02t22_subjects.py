"""I-02-T22 (TASK-7955; DEC-4945): the Today brief's model call names its §7216 subjects.

The gateway checks consent only for the subjects a call names (`enforce_tri_consent`), so the
call carries every TRI subject the facts collector found; a non-TRI subject is not a §7216 one.
"""

from __future__ import annotations

from uuid import uuid4

from abacus.ai_gateway import DataSubject
from abacus.modules.agents.briefing.facts import Subject
from abacus.modules.agents.briefing.today import tri_subjects


def test_every_tri_subject_goes_to_the_gateway() -> None:
    a, b = uuid4(), uuid4()
    found = tri_subjects([Subject(a, True, 2025), Subject(b, False, 2025)])
    assert found == [DataSubject(a, 2025)]


def test_a_tri_subject_without_a_year_still_goes_so_the_gateway_fails_closed() -> None:
    a = uuid4()
    assert tri_subjects([Subject(a, True, None)]) == [DataSubject(a, None)]


def test_the_call_site_passes_the_collected_subjects() -> None:
    from pathlib import Path

    from abacus.modules.agents.briefing import today

    body = Path(today.__file__).read_text(encoding="utf-8")
    assert "await _call(agent, given, (), facts.subjects)" in body
    assert "await _call(agent, given, codes, facts.subjects)" in body
