"""Upload processing activities (SPEC-029; TASK-054). PROTECTED.

Identifiers in, a status out. A bad file isn't an error (it's recorded `unreadable`); anything
else (storage or database unavailable) raises and the workflow retries.
"""

from __future__ import annotations

from temporalio import activity

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


@activity.defn(name="trust_layer.pending_words")
async def pending_words_activity(given: BackfillInput) -> list[UploadInput]:
    """P-03-T05: the backfill's next batch."""
    return await pending_words(given)


ACTIVITIES = (
    extract_activity,
    check_activity,
    preview_activity,
    words_activity,
    pending_words_activity,
)
