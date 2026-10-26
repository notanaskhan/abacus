"""What a preview may show of a real client (DEC-379; C16 v1.1; R-01 Story 8.2).

Previews (POR-20's email preview and test send with `sample_contact_id`, ADM-10's portal preview
`?as=`) render a real contact's content: open request titles, work items, POR-02's to-dos. The
preview action (`email_template.read`, `email_template.test_send`, `portal.preview`) is a firm
setting action and grants no content. So a preview never widens access (ADR-024):

1. the contact must be one the viewer can see under `visible()` (else 404, and the picker never
   offers them; DEC-20);
2. every projected item (a request, a binder, a work item, a to-do) is kept only if the viewer
   could read it themselves: `engagement.read` and the item's own read action (`binder.read`,
   `request_item.read`) under `visible()`, with walls and independence as anywhere else;
3. items the viewer cannot read are dropped silently: no count, no placeholder, no "n hidden";
4. if nothing remains, the preview renders the sample client from the firm's published settings
   and fixed sample data, exactly as when no contact is chosen.

A firm admin walled off Copperleaf, or with no membership on its engagements, previews Tess
Moreno as the sample client. `viewer_scoped` is the rule; the implementing tasks (R-01-T23,
T26) feed it the viewer's own authorisation results.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PreviewSelection[T]:
    items: tuple[T, ...]
    use_sample: bool  # nothing the viewer may read: render the sample client instead


def viewer_scoped[T](
    items: Sequence[T], viewer_can_read: Callable[[T], bool], *, contact_visible: bool
) -> PreviewSelection[T]:
    """Keep the items the viewer could read themselves; fall back to the sample client when the
    contact is not visible or nothing is readable. Never reports what was dropped."""
    if not contact_visible:
        return PreviewSelection((), True)
    kept = tuple(item for item in items if viewer_can_read(item))
    return PreviewSelection(kept, not kept)
