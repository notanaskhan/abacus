"""`PackageAssemblyWorkflow` (C-02-T28; ADR-090; S52 end pass): its own module with no service
imports, so the workflow sandbox can load it (package_render imports the kernel's logging, which
the sandbox refuses). A change lands behind `workflow.patched(...)` so the v1 history replays."""

from __future__ import annotations

from datetime import timedelta
from typing import Final, cast

from temporalio import workflow
from temporalio.common import RetryPolicy

FINISH: Final = "closes.finish_package_assembly"


@workflow.defn(name="PackageAssemblyWorkflow")
class PackageAssemblyWorkflow:
    """`close_package:<tenant>:<close>:<version>`: wait for the render job, then end the DET run.
    The generate itself ran in the request (a person's act); this only finishes."""

    @workflow.run
    async def run(self, given: list[str]) -> str:
        return cast(
            str,
            await workflow.execute_activity(
                FINISH,
                given,
                result_type=str,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    backoff_coefficient=1.5,
                    maximum_interval=timedelta(seconds=20),
                    maximum_attempts=30,
                    non_retryable_error_types=["NotFound"],
                ),
            ),
        )
