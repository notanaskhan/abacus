"""The fake model's screening answers (TASK-011 Q3). Local runs and tests only.

Reads the computed summary from the task layer and answers like a careful screener: ready for
review when debits equal credits, citing the total cells with their values. Tests replace it to
exercise invalid output, repair and fabricated citations.
"""

from __future__ import annotations

import json
from typing import cast

from abacus.ai_gateway import FakeModel, ModelRequest

SCREEN_PROMPT = "evidence.screen@v0"


def _task(request: ModelRequest) -> dict[str, object]:
    section = request.user.split("## task\n", 1)[1]
    return cast(dict[str, object], json.loads(section.split("\n", 1)[0]))


def screening_responder(request: ModelRequest) -> str:
    task = _task(request)
    totals = cast(dict[str, str], task["totals"])
    cells = cast(dict[str, str], task["cells"])
    balanced = totals["debit"] == totals["credit"]
    return json.dumps(
        {
            "action": "ready_for_review" if balanced else "needs_revision",
            "confidence": 0.9 if balanced else 0.6,
            "rationale": (
                "Debits equal credits and the trial balance covers the requested period."
                if balanced
                else "Debits and credits differ; the trial balance needs review."
            ),
            "citations": [
                {"cell": cells["total_debit"], "value": totals["debit"]},
                {"cell": cells["total_credit"], "value": totals["credit"]},
            ],
            "unverified": [],
        }
    )


def install(fake: FakeModel) -> FakeModel:
    fake.respond(SCREEN_PROMPT, screening_responder)
    return fake
