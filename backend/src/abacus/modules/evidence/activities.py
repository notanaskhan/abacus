"""Upload processing activities (SPEC-029; TASK-054). PROTECTED.

Identifiers in, a status out. A bad file isn't an error (it's recorded `unreadable`); anything
else (storage or database unavailable) raises and the workflow retries.
"""

from __future__ import annotations

from temporalio import activity

from abacus.modules.evidence.processing import process_upload
from abacus.modules.evidence.workflow_types import UploadInput


@activity.defn(name="upload.extract")
async def extract_activity(given: UploadInput) -> str:
    return await process_upload(given)


ACTIVITIES = (extract_activity,)
