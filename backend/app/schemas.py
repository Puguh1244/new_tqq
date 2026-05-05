from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ApprovalItem(BaseModel):
    mapping_id: str
    approved: bool
    matched_name: str | None = None
    matched_class: str | None = None


class ApprovalPayload(BaseModel):
    session_id: str
    approvals: list[ApprovalItem] = Field(default_factory=list)


class GenerateExcelPayload(BaseModel):
    session_id: str
    approvals: list[ApprovalItem] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    mode: str
    summary: dict[str, Any]
    mapping: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    duplicates: list[dict[str, Any]]
    validation_scores: list[dict[str, Any]]
    validation_codes: list[dict[str, Any]]
    missing_scores: list[dict[str, Any]]
    preview: dict[str, Any]
    dashboard: dict[str, Any]

    def to_public_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
