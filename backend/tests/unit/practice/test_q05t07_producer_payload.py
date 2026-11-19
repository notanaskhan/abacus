"""Q-05-T07 (S51 partials, TASK-8732; DEC-5726; DEC-96): `proposal.decided` carries what the
override projection reads (agent key, outcome in its words, source, decision time, decider), and
every outcome the producer writes is one the consumer accepts; an event without them is skipped,
never guessed."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from abacus.modules.agents import proposals
from abacus.modules.agents.events import ProposalDecided
from abacus.modules.practice import overrides


def test_ac_the_producer_outcomes_are_the_consumers_words() -> None:
    assert set(proposals._OUTCOME.values()) == overrides.OUTCOMES  # pyright: ignore[reportPrivateUsage] -- the mapping under test
    assert proposals._OUTCOME["approved_with_edits"] == "changed"  # pyright: ignore[reportPrivateUsage] -- the mapping under test


def test_ac_the_payload_has_every_field_the_projection_reads() -> None:
    decided = ProposalDecided(
        proposal_id=uuid4(),
        decision_id=uuid4(),
        engagement_id=uuid4(),
        decision="approved",
        by_user=uuid4(),
        agent_key="ebp_audit_workpapers",
        outcome="adopted",
        source_id=uuid4(),
        decided_at=datetime(2026, 9, 14, 14, 24, tzinfo=UTC).isoformat(),
        decided_by=uuid4(),
    )
    payload = decided.model_dump(mode="json")
    assert {"agent_key", "outcome", "source_id", "decided_at", "decided_by"} <= set(payload)
    assert overrides.SOURCE_KINDS["proposal.decided"] == "proposal"


def test_ac_an_older_event_without_them_still_validates() -> None:
    old = ProposalDecided(
        proposal_id=uuid4(),
        decision_id=uuid4(),
        engagement_id=None,
        decision="rejected",
        by_user=uuid4(),
    )
    assert old.agent_key is None and old.outcome is None
