"""Upload processing activities (SPEC-029; TASK-054). PROTECTED.

Identifiers in, a status out. A bad file isn't an error (it's recorded `unreadable`); anything
else (storage or database unavailable) raises and the workflow retries.
"""

from __future__ import annotations

from temporalio import activity

from abacus.modules.evidence.processing import check_upload, process_upload
from abacus.modules.evidence.workflow_types import UploadInput


@activity.defn(name="upload.extract")
async def extract_activity(given: UploadInput) -> str:
    return await process_upload(given)


@activity.defn(name="upload.check")
async def check_activity(given: UploadInput) -> int:
    """SPEC-029 (TASK-055): the mechanical checks and ledger cross-checks."""
    return await check_upload(given)


ACTIVITIES = (extract_activity, check_activity)
