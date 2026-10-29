# ac-test-author: ayushkbhatia
"""T-01-T03 (TASK-2110; SPEC-501 AC-9): C19 as its consumers read it (T-02's consent chip,
CLI-05, ADM-05, the AI gateway). Written against the stub; holds as the routes go live.

- Return and transcript figures are TRI; nothing serves a TIN or a bank number in plaintext.
- A consent row names exactly one purpose; a request can't merge purposes into one document.
- The consent and authorization codes the contract serves are the status registry's.
- No agent can hold an action that records, exports or approves (I-AGENT-NEVER)."""

from __future__ import annotations

import json
from typing import get_args

from pydantic import BaseModel

from abacus.kernel._statuses import ConsentStatus as RegistryConsent
from abacus.kernel._statuses import TaxAuthorizationStatus as RegistryAuthorization
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.organisations import consents_contract as c19

PLAINTEXT = {"tin", "ssn", "ein", "itin", "account_number", "routing_number", "caf"}


def _models() -> list[type[BaseModel]]:
    return [
        v
        for v in vars(c19).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == c19.__name__
    ]


def test_ac9_no_plaintext_tin_bank_or_caf_field() -> None:
    for model in _models():
        assert not (set(model.model_fields) & PLAINTEXT), model.__name__


def test_ac9_figures_from_returns_and_transcripts_are_tri() -> None:
    for model, field in (
        (c19.TaxElectionOut, "amount"),
        (c19.TranscriptLineDiffOut, "transcript_amount"),
        (c19.TranscriptLineDiffOut, "return_amount"),
        (c19.TranscriptComparisonOut, "lines"),
    ):
        schema = model.model_json_schema()["properties"][field]
        assert schema.get("x-tri") is True, (model.__name__, field)


def test_ac9_one_purpose_per_consent_document() -> None:
    assert c19.ConsentOut.model_fields["purpose"].annotation is not list
    schema = json.dumps(c19.ConsentDocumentOut.model_json_schema()["properties"]["purpose"])
    assert '"type": "array"' not in schema
    assert set(get_args(c19.Purpose)) == {
        "use",
        "ai_disclosure",
        "offshore_disclosure",
        "third_party_disclosure",
        "other_services_use",
        "firm_defined",
    }


def test_ac9_consent_and_authorization_codes_are_the_registrys() -> None:
    served = set(get_args(c19.ConsentStatus))
    assert served <= {s.value for s in RegistryConsent}
    authorizations = set(get_args(c19.AuthorizationStatus))
    assert authorizations <= {s.value for s in RegistryAuthorization}


def test_ac9_no_agent_task_scope_on_a_c19_write() -> None:
    for action, rule in RULES.items():
        if action.split(".", 1)[0] in {"consent", "consent_template", "tax_election"}:
            assert rule.decisions.get("agent", "deny") == "deny", action
