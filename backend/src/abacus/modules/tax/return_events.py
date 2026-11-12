"""The return's live counts, the rest (T-04-T29; T-04 §5; SPEC-649 §3.13; DEC-3419, DEC-4318).

TASK-6828 (DEC-3419) registers `document_approval.changed`, `issue.status_changed`, the
checkpoint events and `sign_off.recorded` onto the return's topics. Two of the review grammar's
events also move the workspace's counts and were not registered: a sign-off that goes stale and
an issue's reassignment. They invalidate the engagement topic, so a second tab refetches its
summary within the stream's poll; a tab without the stream polls (P-10-T30).
"""

from __future__ import annotations

from abacus.kernel import realtime


def register() -> None:
    """At the tax api's import: which topics each event invalidates."""
    for event, ref in (
        ("sign_off.went_stale", "sign_off_id"),
        ("issue.assigned", "issue_id"),
    ):
        if realtime.invalidation_of(event) is None:  # never replace another module's entry
            realtime.register_invalidation(
                event,
                realtime.Invalidation(
                    event.split(".")[0], ref, (("engagement", "engagement_id"),)
                ),
            )
