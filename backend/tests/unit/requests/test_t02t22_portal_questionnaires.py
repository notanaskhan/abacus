"""T-02-T22 (TASK-2324; T-02 §3.5; POR-05; DEC-1370): an answer is checked against its question's
type by code and stored as given (client content, never markup), and the client sees only the
questions a person has sent, counted as such; a firm principal never reaches the portal's
questionnaires."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests import portal_questionnaires as portal
from abacus.modules.requests.questionnaires import QuestionnaireView, QuestionView


@pytest.mark.parametrize(
    ("kind", "value", "stored"),
    [
        ("yes_no", True, True),
        ("upload_if_yes", False, False),
        ("long_text", "<b>not markup</b>", "<b>not markup</b>"),
        ("choice", "Single", "Single"),
        ("amount_group", {"Federal": 19990, "NY": "7824"}, {"Federal": "19990", "NY": "7824"}),
        ("long_text", None, None),
    ],
)
def test_an_answer_is_checked_by_its_type(kind: str, value: object, stored: object) -> None:
    assert portal._checked(kind, value) == stored  # pyright: ignore[reportPrivateUsage] -- the check itself


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("yes_no", "yes"),
        ("long_text", "x" * 4001),
        ("amount_group", {"Federal": "NaN"}),
        ("amount_group", ["19990"]),
        ("choice", 3),
    ],
)
def test_a_wrong_answer_is_refused(kind: str, value: object) -> None:
    with pytest.raises(portal.AnswerInvalid):
        portal._checked(kind, value)  # pyright: ignore[reportPrivateUsage] -- the check itself


def _q(sent: bool, answered: bool) -> QuestionView:
    return QuestionView(
        uuid.uuid4(),
        "Income",
        "yes_no",
        "Synthetic question",
        None,
        None,
        None,
        True if answered else None,
        1 if answered else None,
        None,
        datetime(2026, 9, 1, tzinfo=UTC) if sent else None,
    )


def test_the_client_sees_only_sent_questions() -> None:
    view = QuestionnaireView(
        uuid.uuid4(),
        "team_questions",
        "Questions from Kevin",
        "open",
        date(2026, 9, 30),
        2,
        3,
        None,
        (_q(True, True), _q(True, False), _q(False, True)),
    )
    shown = portal._client_view(view)  # pyright: ignore[reportPrivateUsage] -- the filter itself
    assert (shown.total, shown.answered, len(shown.questions)) == (2, 1, 2)


async def test_a_firm_principal_is_404() -> None:
    user = uuid.uuid4()
    firm = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), "firm_manager", None
    )
    with pytest.raises(NotFound):
        await portal.portal_questionnaires(firm)
