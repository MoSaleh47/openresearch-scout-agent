from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator


class AgentRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Research topic or question")
    max_papers: int = Field(5, ge=1, le=10, description="Number of papers to return")
    year_from: int | None = Field(None, ge=1990, le=2100, description="Optional minimum publication year")
    include_cost: bool = Field(True, description="Whether to include a rough token/cost estimate")

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        return " ".join(value.strip().split())


class ToolCall(BaseModel):
    name: str
    input: dict[str, Any]
    output_summary: str
    latency_ms: float
    success: bool = True


class Paper(BaseModel):
    title: str
    authors: list[str]
    year: int | None = None
    published: str | None = None
    summary: str
    url: HttpUrl | str
    arxiv_id: str | None = None
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    matched_terms: list[str] = Field(default_factory=list)


class SafetyReport(BaseModel):
    allowed: bool
    reason: str = "ok"
    flags: list[str] = Field(default_factory=list)


class CostReport(BaseModel):
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    note: str


class AgentResponse(BaseModel):
    answer: str
    papers: list[Paper]
    tool_calls: list[ToolCall]
    safety: SafetyReport
    cost: CostReport | None = None
    monitoring_id: str
    created_at: datetime


class ErrorResponse(BaseModel):
    error: str
    safety: SafetyReport | None = None
    monitoring_id: str | None = None


class MetricsResponse(BaseModel):
    total_requests: int
    blocked_requests: int
    failed_requests: int
    average_latency_ms: float
    average_papers_returned: float
    recent_requests: list[dict[str, Any]]
