"""C12 hand-off error codes (SPEC-702 F6; T-06-T03, DEC-5511). `handoff_not_available` is shared
with C-02's close hand-off and declared there too."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict


class HandoffNotAvailable(DomainConflict):
    """The source is not released (G8, a review's release or a locked close)."""

    code = "handoff_not_available"


class HandoffNeedsReview(DomainConflict):
    """Accounts marked for review have no choice yet (`facts.review_accounts`)."""

    code = "handoff_needs_review"


class PreviewChanged(DomainConflict):
    """The preview moved since it was read (`seen_preview_hash`): read it again."""

    code = "preview_changed"
