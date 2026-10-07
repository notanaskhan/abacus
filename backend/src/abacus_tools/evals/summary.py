"""A run's summary: the JSON the runner writes and `publish` loads (TASK-020 D3). Validated as a
frozen model; real-model summaries are signed (HMAC-SHA256 over the canonical JSON, keyed by
`ABACUS_EVAL_SIGNING_KEY`, a CI secret only), so a store accepts only runs CI actually made."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus_tools.evals.observation import Observation

SIGNING_KEY_ENV = "ABACUS_EVAL_SIGNING_KEY"


class GradeRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    grader: str
    passed: bool
    reason: str | None = None


class CaseRow(BaseModel):
    """One attempt: what was observed, and how it was graded."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")]
    attempt: Annotated[int, Field(ge=1)]
    stage: Literal["screened", "failed_validation", "failed", "errored"]
    action: str | None = None
    model_action: str | None = None
    confidence: float | None = None
    citations_verified: bool | None = None
    contained: bool | None = None
    cost_usd: Annotated[Decimal, Field(ge=0)]
    budget_usd: Annotated[Decimal, Field(ge=0)]
    error: str | None = None
    passed: bool
    grades: tuple[GradeRow, ...]

    def observation(self) -> Observation:
        return Observation(
            self.case_id,
            self.attempt,
            self.stage,
            self.action,
            self.model_action,
            self.confidence,
            self.citations_verified,
            self.contained,
            self.cost_usd,
            self.budget_usd,
            self.error,
        )


class Summary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    agent: str
    suite_version: Annotated[int, Field(ge=1)]
    prompt_version: str
    model: str
    tier: Literal["small", "medium", "large"]
    subset: Literal["fast", "full"]
    fake: bool
    route: str
    seeds: dict[str, int]
    sampling: dict[str, float]
    status: Literal["passed", "failed", "aborted_cost", "errored"]
    reasons: tuple[str, ...]
    metrics: dict[str, float]
    calibration: dict[str, object]
    total_cost_usd: Annotated[Decimal, Field(ge=0)]
    median_case_cost_usd: Annotated[Decimal, Field(ge=0)]
    started_at: datetime
    finished_at: datetime
    cases: tuple[CaseRow, ...]
    signature: str | None = None


def canonical(summary: Summary) -> bytes:
    """The bytes a signature covers: everything but the signature, sorted, compact."""
    data = summary.model_dump(mode="json", exclude={"signature"})
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def _key() -> bytes | None:
    key = os.environ.get(SIGNING_KEY_ENV)
    return key.encode() if key else None


def sign(summary: Summary) -> Summary:
    """The summary signed with the CI key, or as it is when no key is configured."""
    key = _key()
    if key is None:
        return summary
    digest = hmac.new(key, canonical(summary), hashlib.sha256).hexdigest()
    return summary.model_copy(update={"signature": digest})


def verified(summary: Summary) -> bool:
    key = _key()
    if key is None or summary.signature is None:
        return False
    digest = hmac.new(key, canonical(summary), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, summary.signature)
