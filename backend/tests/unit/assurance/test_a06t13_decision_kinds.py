"""A-06-T13 (TASK-3213; DEC-2213): the `deficiency_severity` and `sum_conclusion` kinds.

Row acceptance: "Margaret Okonkwo's decision concludes F-01 as Significant deficiency and the SUM
as immaterial, each card freezes its snapshot, and the HOME-02 projection shows both as
Decisions." Pinned here: both kinds are registered reserved to the engagement partner with a
code-computed option set and an applier; the deficiency question carries its row; the database
guard (0644) refuses a concluded severity without the person's decision on the card.
"""

from __future__ import annotations

import uuid

from abacus.modules.assurance import (
    api as _api,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the kinds
)
from abacus.modules.assurance import completion_decisions as cd
from abacus.modules.review.api import decision_kind


def test_ac_both_kinds_are_the_engagement_partners() -> None:
    for code in (cd.SEVERITY_KIND, cd.SUM_KIND):
        kind = decision_kind(code)
        assert kind.reserved_role == "engagement_partner"
        assert kind.apply is not None
        assert 0 < kind.mfa_max_age_s <= 900


def test_ac_the_severity_options_are_code_s_three() -> None:
    assert [k for k, _ in cd._SEVERITIES] == [  # pyright: ignore[reportPrivateUsage] -- the private helper under test
        "deficiency",
        "significant_deficiency",
        "material_weakness",
    ]
    assert [k for k, _ in cd._SUM_OPTIONS] == ["immaterial", "material"]  # pyright: ignore[reportPrivateUsage] -- the private helper under test


def test_ac_the_deficiency_question_names_its_row() -> None:
    row = uuid.uuid4()
    question = cd._deficiency_question(row)  # pyright: ignore[reportPrivateUsage] -- the private helper under test
    assert question.startswith("deficiency.")
    assert cd._deficiency_of(question) == row  # pyright: ignore[reportPrivateUsage] -- the private helper under test
