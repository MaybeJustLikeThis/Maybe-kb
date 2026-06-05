"""Pydantic schemas for the normalized /api/v1 contract."""
from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel, Generic[T]):
    data: T | None
    meta: dict[str, Any] = Field(default_factory=dict)
    error: ApiError | None = None


class PaginationMeta(BaseModel):
    limit: int
    offset: int
    total: int


class NoteBase(BaseModel):
    file_id: str
    title: str
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    status: str = "published"
    source_project: str | None = None
    source_path: str | None = None
    source_context: str | None = None
    content_type: str = "markdown"


class NoteSummary(NoteBase):
    pass


class NoteDetail(NoteBase):
    content: str = ""
    attachments: list[str] = Field(default_factory=list)


class OpenTarget(BaseModel):
    obsidian_uri: str
    file_path: str
    relative_path: str


class RAGSource(BaseModel):
    file_id: str
    title: str
    snippet: str
    source_project: str | None = None
    source_path: str | None = None
    content_type: str = "markdown"
    attachments: list[str] = Field(default_factory=list)


class NoteCreateRequest(BaseModel):
    title: str = Field(..., max_length=300)
    content: str = Field(default="", max_length=500_000)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    source_project: str | None = Field(default=None, max_length=200)
    source_path: str | None = Field(default=None, max_length=500)
    source_context: str | None = Field(default=None, max_length=500)
    content_type: str = Field(default="markdown", max_length=50)


class NoteUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    content: str | None = Field(default=None, max_length=500_000)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=20)
    source_project: str | None = Field(default=None, max_length=200)
    source_path: str | None = Field(default=None, max_length=500)
    source_context: str | None = Field(default=None, max_length=500)
    content_type: str | None = Field(default=None, max_length=50)


SearchMode = Literal["fulltext", "semantic", "hybrid"]


class SearchResult(BaseModel):
    note: NoteSummary
    score: float | None = None
    source: str
    chunk_text: str | None = None


class CountItem(BaseModel):
    name: str
    count: int
    label: str | None = None


class TaxonomyResponse(BaseModel):
    tags: list[str] = Field(default_factory=list)
    categories: list[CountItem] = Field(default_factory=list)
    source_projects: list[CountItem] = Field(default_factory=list)
    content_types: list[CountItem] = Field(default_factory=list)


class IndexHealth(BaseModel):
    notes_count: int
    vectors_count: int
    coverage: float


class HealthCheck(BaseModel):
    id: str
    label: str
    status: Literal["ready", "warning", "error"]
    message: str
    action: str | None = None


class HealthSummary(BaseModel):
    notes_count: int
    vectors_count: int
    coverage: float


class SystemHealth(BaseModel):
    status: Literal["ready", "warning", "error"]
    checks: list[HealthCheck] = Field(default_factory=list)
    summary: HealthSummary


class DashboardStats(BaseModel):
    notes_count: int
    attachments_count: int
    source_projects: list[CountItem] = Field(default_factory=list)
    content_types: list[CountItem] = Field(default_factory=list)
    index_health: IndexHealth


class IndexRebuildResult(BaseModel):
    indexed: int
    vectors: int


class AttachmentUploadResult(BaseModel):
    path: str


class DeleteResult(BaseModel):
    ok: bool


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class ChatAnswer(BaseModel):
    answer: str
    model: str
    tokens_used: int | None = None
    sources: list[RAGSource] = Field(default_factory=list)


class ChatStreamEvent(BaseModel):
    text: str | None = None
    done: bool = False
