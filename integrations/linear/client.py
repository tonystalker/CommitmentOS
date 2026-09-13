"""
CommitmentOS — Linear integration client (GraphQL API).

Auth: Linear personal API key from .env (LINEAR_API_KEY).
No OAuth UI needed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"


@dataclass
class LinearIssue:
    id: str
    title: str
    description: str | None
    state: str
    assignee_name: str | None
    assignee_id: str | None
    url: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    raw: dict = field(default_factory=dict)


class LinearClient:
    """
    Thin GraphQL client for Linear.
    Operations: create issue, update status, fetch issue by ID, search issues.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": settings.linear_api_key,
                "Content-Type": "application/json",
            },
            timeout=20.0,
        )

    async def _query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = await self._client.post(LINEAR_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"Linear GraphQL error: {data['errors']}")
        return data.get("data", {})

    async def create_issue(
        self,
        title: str,
        description: str | None = None,
        team_id: str | None = None,
        assignee_id: str | None = None,
        commitment_id: str | None = None,
    ) -> LinearIssue:
        """Create a Linear issue. Returns the created issue."""
        # Append commitment_id to description for traceability
        full_description = description or ""
        if commitment_id:
            full_description += f"\n\n---\n*CommitmentOS commitment_id: {commitment_id}*"

        mutation = """
        mutation CreateIssue($title: String!, $description: String, $teamId: String, $assigneeId: String) {
          issueCreate(input: {
            title: $title,
            description: $description,
            teamId: $teamId,
            assigneeId: $assigneeId
          }) {
            success
            issue {
              id title description url state { name }
              assignee { id name }
              createdAt updatedAt
            }
          }
        }
        """
        vars: dict[str, Any] = {
            "title": title,
            "description": full_description or None,
            "teamId": team_id,
            "assigneeId": assignee_id,
        }
        data = await self._query(mutation, vars)
        issue_data = data["issueCreate"]["issue"]
        return self._parse_issue(issue_data)

    async def get_issue(self, issue_id: str) -> LinearIssue | None:
        """Fetch a single issue by Linear ID."""
        query = """
        query GetIssue($id: String!) {
          issue(id: $id) {
            id title description url state { name }
            assignee { id name }
            createdAt updatedAt
          }
        }
        """
        try:
            data = await self._query(query, {"id": issue_id})
            issue_data = data.get("issue")
            if not issue_data:
                return None
            return self._parse_issue(issue_data)
        except Exception as e:
            logger.error("Linear get_issue failed for id=%s: %s", issue_id, e)
            return None

    async def update_issue_status(self, issue_id: str, state_id: str) -> bool:
        """Update the status of an issue by workflow state ID."""
        mutation = """
        mutation UpdateIssue($id: String!, $stateId: String!) {
          issueUpdate(id: $id, input: { stateId: $stateId }) {
            success
          }
        }
        """
        try:
            data = await self._query(mutation, {"id": issue_id, "stateId": state_id})
            return data.get("issueUpdate", {}).get("success", False)
        except Exception as e:
            logger.error("Linear update_issue_status failed: %s", e)
            return False

    async def search_issues(self, query_text: str, *, limit: int = 20) -> list[LinearIssue]:
        """Search issues by text query."""
        query = """
        query SearchIssues($filter: IssueFilter, $first: Int) {
          issues(filter: $filter, first: $first) {
            nodes {
              id title description url state { name }
              assignee { id name }
              createdAt updatedAt
            }
          }
        }
        """
        variables = {
            "filter": {"title": {"containsIgnoreCase": query_text}},
            "first": limit,
        }
        try:
            data = await self._query(query, variables)
            nodes = data.get("issues", {}).get("nodes", [])
            return [self._parse_issue(n) for n in nodes]
        except Exception as e:
            logger.error("Linear search_issues failed: %s", e)
            return []

    async def get_teams(self) -> list[dict]:
        """Get all teams (for setup/seeding)."""
        query = "{ teams { nodes { id name } } }"
        try:
            data = await self._query(query)
            return data.get("teams", {}).get("nodes", [])
        except Exception as e:
            logger.error("Linear get_teams failed: %s", e)
            return []

    def _parse_issue(self, data: dict) -> LinearIssue:
        assignee = data.get("assignee") or {}
        return LinearIssue(
            id=data["id"],
            title=data.get("title", ""),
            description=data.get("description"),
            state=(data.get("state") or {}).get("name", "Unknown"),
            assignee_name=assignee.get("name"),
            assignee_id=assignee.get("id"),
            url=data.get("url", ""),
            raw=data,
        )

    async def close(self) -> None:
        await self._client.aclose()
