"""Payloads of `RequestPublishWorkflow` (C-01-T19). Identifiers only (ADR-090)."""

from __future__ import annotations

from dataclasses import dataclass

SECONDS_UNTIL = "closes.requests_seconds_until"
PUBLISH = "closes.publish_requests"
RECOMPUTE = "recompute"


@dataclass(frozen=True)
class PublishInput:
    tenant_id: str
    close_id: str


@dataclass(frozen=True)
class PublishResult:
    created: int
    plan_version: int | None = None
