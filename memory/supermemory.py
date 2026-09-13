"""
CommitmentOS — Supermemory implementation of MemoryService.

Container tag: commitment-os (project-scoped for hackathon).
Every call is scoped to this tag — strict isolation.

API reference: https://docs.supermemory.ai/llms.txt
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config import settings
from memory.service import MemorySearchResult, MemoryService, UserProfile

logger = logging.getLogger(__name__)

BASE_URL = "https://api.supermemory.ai"


class SupermemoryService(MemoryService):
    """
    Supermemory-backed implementation of MemoryService.

    Endpoints used:
      POST /v3/documents      → store()
      POST /v4/search         → search()
      POST /v3/search         → search_documents()
      POST /v4/profile        → get_profile()
      DELETE /v4/memories     → forget()
      POST /v4/memories/forget-matching → forget_matching()
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.supermemory_api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._container_tag = settings.supermemory_container_tag

    def _tag(self) -> str:
        return self._container_tag

    async def store(
        self,
        content: str,
        *,
        person_id: str | None = None,
        commitment_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        task_type: str = "memory",
    ) -> str:
        """Ingest a conversation, evidence, or document into Supermemory."""
        payload: dict[str, Any] = {
            "content": content,
            "containerTag": self._tag(),
            "taskType": task_type,
            "metadata": {
                **(metadata or {}),
                **({"person_id": person_id} if person_id else {}),
                **({"commitment_id": commitment_id} if commitment_id else {}),
            },
        }
        try:
            resp = await self._client.post("/v3/documents", json=payload)
            resp.raise_for_status()
            data = resp.json()
            doc_id = data.get("id", "")
            logger.debug("Supermemory stored doc_id=%s", doc_id)
            return doc_id
        except httpx.HTTPStatusError as e:
            logger.error("Supermemory store failed: %s — %s", e.response.status_code, e.response.text)
            return ""
        except Exception as e:
            logger.error("Supermemory store error: %s", e)
            return ""

    async def search(self, query: str, *, limit: int = 5) -> list[MemorySearchResult]:
        """Semantic search over memories (facts, profiles, graph context)."""
        payload = {
            "query": query,
            "containerTag": self._tag(),
            "limit": limit,
        }
        try:
            resp = await self._client.post("/v4/search", json=payload)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("memories", []):
                results.append(
                    MemorySearchResult(
                        content=item.get("content", ""),
                        score=item.get("score", 0.0),
                        metadata=item.get("metadata", {}),
                        doc_id=item.get("id", ""),
                    )
                )
            return results
        except Exception as e:
            logger.error("Supermemory search error: %s", e)
            return []

    async def search_documents(self, query: str, *, limit: int = 5) -> list[MemorySearchResult]:
        """Raw chunk search for RAG grounding."""
        payload = {
            "query": query,
            "containerTag": self._tag(),
            "limit": limit,
            "searchMode": "documents",
        }
        try:
            resp = await self._client.post("/v3/search", json=payload)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("documents", []):
                results.append(
                    MemorySearchResult(
                        content=item.get("content", ""),
                        score=item.get("score", 0.0),
                        metadata=item.get("metadata", {}),
                        doc_id=item.get("id", ""),
                    )
                )
            return results
        except Exception as e:
            logger.error("Supermemory document search error: %s", e)
            return []

    async def get_profile(self, person_id: str) -> UserProfile:
        """Retrieve static + dynamic context for a person (episodic history)."""
        payload = {
            "containerTag": self._tag(),
            "userId": person_id,
        }
        try:
            resp = await self._client.post("/v4/profile", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return UserProfile(
                person_id=person_id,
                static_context=data.get("staticContext", {}),
                dynamic_context=data.get("dynamicContext", {}),
                raw=data,
            )
        except Exception as e:
            logger.error("Supermemory get_profile error: %s", e)
            return UserProfile(person_id=person_id)

    async def forget(self, *, doc_id: str | None = None, content: str | None = None) -> None:
        """Soft-delete one memory by doc_id or exact content."""
        payload: dict[str, Any] = {"containerTag": self._tag()}
        if doc_id:
            payload["id"] = doc_id
        elif content:
            payload["content"] = content
        else:
            raise ValueError("Must provide either doc_id or content")
        try:
            resp = await self._client.request("DELETE", "/v4/memories", json=payload)
            resp.raise_for_status()
        except Exception as e:
            logger.error("Supermemory forget error: %s", e)

    async def forget_matching(self, query: str, *, dry_run: bool = False) -> list[str]:
        """Soft-delete all memories matching a query. Returns affected IDs."""
        payload = {
            "containerTag": self._tag(),
            "query": query,
            "dryRun": dry_run,
        }
        try:
            resp = await self._client.post("/v4/memories/forget-matching", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("deletedIds", [])
        except Exception as e:
            logger.error("Supermemory forget_matching error: %s", e)
            return []

    async def close(self) -> None:
        await self._client.aclose()
