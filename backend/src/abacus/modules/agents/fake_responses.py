"""The fake model's screening answers (TASK-011 Q3). Local runs and tests only.

Reads the computed summary from the task layer and answers like a careful screener: ready for
review when debits equal credits, citing the total cells with their values. Tests replace it to
exercise invalid output, repair and fabricated citations.

P-06-T21 (F-04.26): the upload reviewer's answers are recorded, never computed. Its responder
serves the answer recorded for (prompt, SHA-256 of the request and the document as the reviewer
is shown it) and refuses anything else; the recorded answers are data files the caller passes in.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Final, cast

from abacus.ai_gateway import FakeModel, ModelRequest, ProviderError

SCREEN_PROMPT = "evidence.screen@v0"
UNTRUSTED_DOCUMENT: Final = '<untrusted name="document">'


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


def review_sha256(request: ModelRequest) -> str | None:
    """The SHA-256 of what a review is about, as the model is shown it: the request's wording and
    the untrusted document block (the extracted, masked text). An upload's bytes differ per
    attempt and the same document may answer another request; neither changes this."""
    if UNTRUSTED_DOCUMENT not in request.user or "## task\n" not in request.user:
        return None
    asked = _task(request).get("request")
    inside = request.user.split(UNTRUSTED_DOCUMENT, 1)[1].split("</untrusted>", 1)[0]
    content = json.dumps({"request": asked, "document": inside.strip("\n")}, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def review_responder(answers: Mapping[tuple[str, str], str]) -> Callable[[ModelRequest], str]:
    """The recorded answer for (prompt, `review_sha256`); anything else is refused."""

    def respond(request: ModelRequest) -> str:
        sha = review_sha256(request)
        found = answers.get((request.prompt_ref, sha)) if sha is not None else None
        if found is None:
            raise ProviderError(f"no recorded review for {request.prompt_ref} and {sha}")
        return found

    return respond


def install_review(fake: FakeModel, answers: Mapping[tuple[str, str], str]) -> FakeModel:
    """Register the reviewer's recorded answers for each prompt they name."""
    responder = review_responder(answers)
    for prompt in sorted({prompt for prompt, _ in answers}):
        fake.respond(prompt, responder)
    return fake


def install(fake: FakeModel) -> FakeModel:
    fake.respond(SCREEN_PROMPT, screening_responder)
    # K-01-T21: the methodology importer's answers are read from the document block by code.
    from abacus.modules.agents.methodology_import import PROMPT as IMPORT_PROMPT
    from abacus.modules.agents.methodology_import import fake_parse

    fake.respond(IMPORT_PROMPT, fake_parse)
    # A-04-T15: the materiality recommender's answer is read from the task by code.
    from abacus.modules.agents.decision_recommend import fake_recommend
    from abacus.modules.agents.spec import spec

    fake.respond(spec("decisions.recommender").prompt, fake_recommend)
    return fake
