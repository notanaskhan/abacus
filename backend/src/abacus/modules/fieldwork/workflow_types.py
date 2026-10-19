"""Fieldwork workflow inputs (SPEC-037; TASK-083)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcedureSelectInput:
    tenant_id: str
    procedure_id: str
    requested_by: str
