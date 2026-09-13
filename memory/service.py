"""
CommitmentOS — MemoryService interface.

All semantic memory operations go through this interface so the implementation
(Supermemory today, anything else tomorrow) is swappable without touching the agent.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemorySearchResult:
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    doc_id: str = ""


@dataclass
class UserProfile:
    person_id: str
    static_context: dict[str, Any] = field(default_factory=dict)
    dynamic_context: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class MemoryService(ABC):
    """Abstract interface for semantic memory operations."""

    @abstractmethod
    async def store(
        self,
        content: str,
        *,
        person_id: str | None = None,
        commitment_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        task_type: str = "memory",
    ) -> str:
        """Ingest content. Returns the document ID."""

    @abstractmethod
    async def search(self, query: str, *, limit: int = 5) -> list[MemorySearchResult]:
        """Semantic search over memories. Returns ranked results."""

    @abstractmethod
    async def search_documents(self, query: str, *, limit: int = 5) -> list[MemorySearchResult]:
        """Raw chunk search (for RAG grounding over reference material)."""

    @abstractmethod
    async def get_profile(self, person_id: str) -> UserProfile:
        """Retrieve static + dynamic context for a person."""

    @abstractmethod
    async def forget(self, *, doc_id: str | None = None, content: str | None = None) -> None:
        """Soft-delete a memory by doc_id or exact content."""

    @abstractmethod
    async def forget_matching(self, query: str, *, dry_run: bool = False) -> list[str]:
        """Soft-delete all memories matching a query. Returns affected IDs."""
