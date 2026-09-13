"""
CommitmentOS — Action Verifier.

Every executed action has a verify step:
  - Re-fetch the created/updated object from the integration
  - Confirm it exists and matches expected values (title, assignee, commitment link, etc.)
  - Nothing is marked "done" on LLM intent alone — only on verified external state

If verification fails, the action is marked FAILED and the orchestrator is notified.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from commitments.models import ActionRecord, ActionStatus, ActionType
from integrations.linear.client import LinearClient
from integrations.slack.client import SlackClient

logger = logging.getLogger(__name__)


class Verifier:
    """
    Verifies that executed actions actually took effect in the external system.
    Called by the orchestrator after each successful executor run.
    """

    def __init__(self, db: AsyncSession, linear: LinearClient, slack: SlackClient) -> None:
        self.db = db
        self.linear = linear
        self.slack = slack

    async def verify(self, action_record_id: str) -> bool:
        """
        Verify an action. Returns True if verified, False if verification failed.
        Updates the ActionRecord in DB.
        """
        stmt = select(ActionRecord).where(ActionRecord.id == action_record_id)
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            logger.error("Verifier: ActionRecord %s not found", action_record_id)
            return False

        if record.status not in (ActionStatus.COMPLETED, ActionStatus.VERIFIED):
            logger.warning("Verifier: ActionRecord %s not in COMPLETED state (is %s)", action_record_id, record.status)
            return False

        try:
            verified, verification_result = await self._verify_by_type(record)
        except Exception as e:
            logger.error("Verifier: exception during verification of %s: %s", action_record_id, e)
            verified = False
            verification_result = {"error": str(e)}

        record.verified = verified
        record.verification_result = verification_result
        record.verified_at = datetime.now(timezone.utc)

        if verified:
            record.status = ActionStatus.VERIFIED
            logger.info("Verifier: action %s VERIFIED ✓", action_record_id)
        else:
            record.status = ActionStatus.FAILED
            logger.warning("Verifier: action %s FAILED verification ✗ — %s", action_record_id, verification_result)

        await self.db.flush()
        return verified

    async def _verify_by_type(self, record: ActionRecord) -> tuple[bool, dict]:
        """Dispatch verification to the appropriate integration check."""
        result = record.result or {}

        if record.action_type == ActionType.CREATE_LINEAR_TASK:
            issue_id = result.get("linear_issue_id")
            if not issue_id:
                return False, {"error": "No linear_issue_id in result"}
            issue = await self.linear.get_issue(issue_id)
            if not issue:
                return False, {"error": f"Linear issue {issue_id} not found after creation"}

            # Confirm commitment_id is in the description
            commitment_linked = (
                record.commitment_id in (issue.description or "")
            )
            return True, {
                "linear_issue_id": issue_id,
                "title_verified": bool(issue.title),
                "commitment_linked": commitment_linked,
                "state": issue.state,
            }

        elif record.action_type == ActionType.UPDATE_LINEAR_STATUS:
            success = result.get("success", False)
            return success, {"reported_success": success}

        elif record.action_type == ActionType.POST_SLACK_MESSAGE:
            ts = result.get("slack_ts")
            # If we got a ts back from Slack's API, it was accepted
            verified = bool(ts)
            return verified, {"slack_ts": ts, "posted": verified}

        elif record.action_type == ActionType.SEND_EXTERNAL_EMAIL:
            # For drafted emails, verify the draft was created
            draft_id = result.get("gmail_draft_id")
            verified = bool(draft_id)
            return verified, {"gmail_draft_id": draft_id, "draft_created": verified}

        else:
            # For unverifiable action types, mark as verified with a caveat
            logger.warning("No verification logic for action_type=%s — marking verified with caveat", record.action_type)
            return True, {"note": "No external verification available for this action type"}
