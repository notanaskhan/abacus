"""Q-03-T259 (TASK-7523; P-05 §2.3 CL-1; ADR-236 decision 1): the CL-1 consolidation's independent
equivalence suite, written from P-05 §2.3 and ADR-236 before the consolidation runs.

CL-1 re-owns SPEC-032's `comments`, `comment_mentions`, `comment_redactions` and `comment_reads`
in `collaboration` as `request_item` and `evidence_version` threads, after every firm has
`collaboration.v2` on (P-05-T16's canary flip and rollout). Row acceptance: "The equivalence suite
passes on a copy of the canary's threads." Until CL-1 lands, the parts that need it are strict
expected failures naming Q-03-T258: red now, and an XPASS fails the suite the day it lands, so the
marks come off in that PR. What already holds (the window's guards) is asserted plainly.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

from abacus.modules.collaboration import anchors
from abacus.modules.requests import registry as requests_registry

LEGACY: tuple[str, ...] = ("comments", "comment_mentions", "comment_redactions", "comment_reads")


def test_in_the_window_the_live_kinds_are_never_v2_anchors() -> None:
    """ADR-236 decision 2: until CL-1, v2 refuses the live SPEC-032 kinds."""
    assert frozenset({"request_item", "evidence_version"}) == anchors.LIVE_SPEC032_KINDS


def test_in_the_window_requests_still_owns_the_legacy_tables() -> None:
    assert set(LEGACY) <= set(requests_registry.TABLES)


@pytest.mark.xfail(reason="TASK-7522: CL-1 waits for collaboration.v2 (P-05-T16)", strict=True)
def test_cl1_collaboration_owns_the_legacy_tables() -> None:
    from abacus.modules.collaboration import registry as collaboration_registry

    assert set(LEGACY) <= set(collaboration_registry.TABLES)
    assert not set(LEGACY) & set(requests_registry.TABLES)


@pytest.mark.xfail(reason="TASK-7522: CL-1 waits for collaboration.v2 (P-05-T16)", strict=True)
def test_cl1_request_items_and_evidence_versions_are_registered_anchor_kinds() -> None:
    assert not anchors.LIVE_SPEC032_KINDS
    registered_kinds: Any = getattr(anchors, "registered_kinds")  # noqa: B009 -- Any: absent until CL-1

    assert {"request_item", "evidence_version"} <= set(registered_kinds())


@pytest.mark.xfail(reason="TASK-7522: CL-1 waits for collaboration.v2 (P-05-T16)", strict=True)
def test_cl1_a_thread_reads_identically_before_and_after() -> None:
    """On a copy of the canary's threads: each legacy thread's comments, authors, times,
    mentions, redaction markers and read state equal the consolidated thread's, in order, and no
    comment row was updated in place (ids and sealed bytes preserved; insert-only events only)."""
    name = "abacus.modules.collaboration.cl1"
    cl1: Any = importlib.import_module(name)  # Any: absent until CL-1

    report: Any = cl1.equivalence_report()  # Any: the CL-1 report is not built yet
    assert report.threads_compared > 0
    assert report.differences == []
    assert report.rows_updated_in_place == 0


@pytest.mark.xfail(reason="TASK-7522: CL-1 waits for collaboration.v2 (P-05-T16)", strict=True)
def test_cl1_the_comment_mentioned_event_is_retired_for_mention_created() -> None:
    from abacus.modules.collaboration import events

    assert hasattr(events, "MentionCreated")
    from abacus.modules.requests import events as request_events

    assert not hasattr(request_events, "CommentMentioned")
