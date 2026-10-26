"""Upload processing activities (SPEC-029; TASK-054). PROTECTED.

Identifiers in, a status out. A bad file isn't an error (it's recorded `unreadable`); anything
else (storage or database unavailable) raises and the workflow retries.
"""

from __future__ import annotations

from temporalio import activity

from abacus.modules.evidence.drops import sort_drop
from abacus.modules.evidence.masked_previews import masked_preview_upload, pending_masks
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.processing import check_upload, preview_upload, process_upload
from abacus.modules.evidence.words import pending_words, words_upload
from abacus.modules.evidence.workflow_types import BackfillInput, UploadInput


@activity.defn(name="upload.extract")
async def extract_activity(given: UploadInput) -> str:
    return await process_upload(given)


@activity.defn(name="upload.check")
async def check_activity(given: UploadInput) -> int:
    """SPEC-029 (TASK-055): the mechanical checks and ledger cross-checks."""
    return await check_upload(given)


@activity.defn(name="upload.preview")
async def preview_activity(given: UploadInput) -> str:
    """SPEC-029 (TASK-056): server-made previews."""
    return await preview_upload(given)


@activity.defn(name="upload.words")
async def words_activity(given: UploadInput) -> int:
    """P-03-T05: the word layer."""
    return await words_upload(given)


@activity.defn(name="upload.pii_scan")
async def pii_scan_activity(given: UploadInput) -> int:
    """P-03-T13: PII detection over the word layer."""
    return await pii_scan_upload(given)


@activity.defn(name="upload.masked_preview")
async def masked_preview_activity(given: UploadInput) -> str:
    """P-03-T15: the masked rendition, burned in the isolated child."""
    return await masked_preview_upload(given)


@activity.defn(name="upload.portal_drop_sort")
async def portal_drop_sort_activity(given: UploadInput) -> str:
    """R-01-T09: a portal drop's code-rule sort."""
    return await sort_drop(given)


@activity.defn(name="trust_layer.pending_words")
async def pending_words_activity(given: BackfillInput) -> list[UploadInput]:
    """P-03-T05: the backfill's next batch."""
    return await pending_words(given)


@activity.defn(name="trust_layer.pending_masks")
async def pending_masks_activity(given: BackfillInput) -> list[UploadInput]:
    """P-03-T15: the masking backfill's next batch."""
    return await pending_masks(given)


ACTIVITIES = (
    extract_activity,
    check_activity,
    preview_activity,
    words_activity,
    pii_scan_activity,
    masked_preview_activity,
    portal_drop_sort_activity,
    pending_words_activity,
    pending_masks_activity,
)
