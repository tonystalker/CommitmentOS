"""
CommitmentOS — Action Executor.

Rules:
  - Structured tool calls ONLY (never a freeform "do something" call)
  - Idempotency key per action: {commitment_id}:{action_type}
  - Check idempotency key before executing to prevent duplicates on retry
  - Bounded retry (max 3 attempts) with graceful partial-failure reporting
  - Every action record is written to DB before execution so the verifier can check it
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from agent.policy.engine import PolicyDecision, PolicyResult
from agent.planner.planner import ProposedAction
from commitments.models import ActionRecord, ActionStatus, ActionType, Commitment
from integrations.linear.client import LinearClient
from integrations.slack.client import SlackClient
from integrations.gmail.client import GmailClient
from config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class ExecutionResult:
    def __init__(
        self,
        action_record_id: str,
        success: bool,
        result: dict | None = None,
        error: str | None = None,
        awaiting_approval: bool = False,
    ) -> None:
        self.action_record_id = action_record_id
        self.success = success
        self.result = result or {}
        self.error = error
        self.awaiting_approval = awaiting_approval


class Executor:
    """
    Executes authorized actions via structured tool calls.
    Each action type dispatches to a specific integration method.
    """

    def __init__(
        self,
        db: AsyncSession,
        slack: SlackClient,
        linear: LinearClient,
        gmail: GmailClient,
    ) -> None:
        self.db = db
        self.slack = slack
        self.linear = linear
        self.gmail = gmail

    async def execute(
        self,
        action: ProposedAction,
        policy_result: PolicyResult,
        commitment: Commitment,
    ) -> ExecutionResult:
        """
        Execute a policy-authorized action.
        Creates an ActionRecord, checks idempotency, executes, updates record.
        """
        idempotency_key = f"{action.commitment_id}:{action.action_type.value}"

        # ── Idempotency check ──────────────────────────────────────────────
        existing_stmt = select(ActionRecord).where(ActionRecord.idempotency_key == idempotency_key)
        existing_result = await self.db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing and existing.status in (ActionStatus.COMPLETED, ActionStatus.VERIFIED):
            logger.info("Idempotency check: action %s already completed — skipping", idempotency_key)
            return ExecutionResult(
                action_record_id=existing.id, success=True, result=existing.result
            )

        # ── Create or reuse ActionRecord ───────────────────────────────────
        if existing:
            record = existing
        else:
            record = ActionRecord(
                commitment_id=action.commitment_id,
                idempotency_key=idempotency_key,
                action_type=action.action_type,
                risk_level=policy_result.risk_level,
                status=ActionStatus.PENDING,
                params=action.params,
                policy_decision=policy_result.decision.value,
                policy_reason=policy_result.reason,
            )
            self.db.add(record)
            await self.db.flush()

        # ── AWAITING_APPROVAL: don't execute yet ──────────────────────────
        if policy_result.decision == PolicyDecision.APPROVAL:
            record.status = ActionStatus.AWAITING_APPROVAL
            await self.db.flush()
            return ExecutionResult(
                action_record_id=record.id, success=False, awaiting_approval=True,
                error="Awaiting human approval"
            )

        # ── BLOCK: don't execute ───────────────────────────────────────────
        if policy_result.decision == PolicyDecision.BLOCK:
            record.status = ActionStatus.BLOCKED
            await self.db.flush()
            return ExecutionResult(
                action_record_id=record.id, success=False, error="Action blocked by policy"
            )

        # ── Execute with retry ─────────────────────────────────────────────
        record.status = ActionStatus.EXECUTING
        await self.db.flush()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = await self._dispatch(action)
                record.status = ActionStatus.COMPLETED
                record.result = result
                record.retry_count = attempt - 1
                await self.db.flush()
                logger.info("Action %s completed on attempt %d", idempotency_key, attempt)
                return ExecutionResult(action_record_id=record.id, success=True, result=result)

            except Exception as e:
                logger.warning("Action %s attempt %d failed: %s", idempotency_key, attempt, e)
                record.retry_count = attempt
                if attempt == MAX_RETRIES:
                    record.status = ActionStatus.FAILED
                    record.error = str(e)
                    await self.db.flush()
                    return ExecutionResult(action_record_id=record.id, success=False, error=str(e))

        return ExecutionResult(action_record_id=record.id, success=False, error="Max retries exhausted")

    async def execute_approved(self, action_record_id: str) -> ExecutionResult:
        """Execute an action that was AWAITING_APPROVAL and has now been approved by a human."""
        stmt = select(ActionRecord).where(ActionRecord.id == action_record_id)
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return ExecutionResult(action_record_id=action_record_id, success=False, error="ActionRecord not found")

        if record.status != ActionStatus.AWAITING_APPROVAL:
            return ExecutionResult(
                action_record_id=action_record_id, success=False,
                error=f"Expected AWAITING_APPROVAL, got {record.status}"
            )

        action = ProposedAction(
            action_type=ActionType(record.action_type),
            params=record.params or {},
            rationale="Approved by human",
            commitment_id=record.commitment_id,
        )

        record.status = ActionStatus.EXECUTING
        await self.db.flush()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                exec_result = await self._dispatch(action)
                record.status = ActionStatus.COMPLETED
                record.result = exec_result
                record.approved_at = datetime.now(timezone.utc)
                await self.db.flush()
                return ExecutionResult(action_record_id=record.id, success=True, result=exec_result)
            except Exception as e:
                logger.warning("Approved action %s attempt %d failed: %s", action_record_id, attempt, e)
                if attempt == MAX_RETRIES:
                    record.status = ActionStatus.FAILED
                    record.error = str(e)
                    await self.db.flush()
                    return ExecutionResult(action_record_id=action_record_id, success=False, error=str(e))

        return ExecutionResult(action_record_id=action_record_id, success=False, error="Exhausted")

    async def _dispatch(self, action: ProposedAction) -> dict:
        """Route an action to its integration method. All calls are structured."""
        p = action.params

        if action.action_type == ActionType.CREATE_LINEAR_TASK:
            issue = await self.linear.create_issue(
                title=p["title"],
                description=p.get("description"),
                team_id=p.get("team_id"),
                assignee_id=p.get("assignee_id"),
                commitment_id=action.commitment_id,
            )
            return {"linear_issue_id": issue.id, "url": issue.url}

        elif action.action_type == ActionType.UPDATE_LINEAR_STATUS:
            issue_id = p.get("issue_id")
            state_id = p.get("state_id")
            if not issue_id:
                # No existing issue — planner proposed updating something that doesn't exist yet.
                # Create it instead so the commitment is still tracked in Linear.
                issue = await self.linear.create_issue(
                    title=p.get("title", "Commitment follow-up"),
                    description=p.get("description"),
                    team_id=p.get("team_id"),
                    assignee_id=p.get("assignee_id"),
                    commitment_id=action.commitment_id,
                )
                return {"linear_issue_id": issue.id, "url": issue.url, "note": "created_instead_of_update"}
            success = await self.linear.update_issue_status(
                issue_id=issue_id, state_id=state_id or ""
            )
            return {"success": success}

        elif action.action_type == ActionType.POST_SLACK_MESSAGE:
            # Fall back to configured default channel if planner omitted channel_id
            channel = p.get("channel_id") or p.get("channel") or settings.slack_default_channel
            if not channel:
                raise ValueError("POST_SLACK_MESSAGE: no channel_id in params and no SLACK_DEFAULT_CHANNEL configured")
            ts = await self.slack.post_message(
                channel_id=channel,
                text=p["text"],
                thread_ts=p.get("thread_ts"),
            )
            return {"slack_ts": ts}

        elif action.action_type == ActionType.SEND_EXTERNAL_EMAIL:
            # Create a draft first — actual send only happens on approval
            draft_id = self.gmail.create_draft(
                to=p["to"],
                subject=p["subject"],
                body=p["body"],
                thread_id=p.get("thread_id"),
            )
            return {"gmail_draft_id": draft_id, "status": "draft_created"}

        elif action.action_type == ActionType.ASSIGN_TASK:
            success = await self.linear.update_issue_status(
                issue_id=p["issue_id"], state_id=p.get("state_id", "")
            )
            return {"success": success}

        elif action.action_type == ActionType.CREATE_REMINDER:
            # Implement reminders as a Slack DM or channel message
            reminder_text = p.get("text") or p.get("message") or "Reminder: you have a pending commitment due soon."
            # Try to DM the user; fall back to default channel
            target = p.get("user_id") or p.get("channel_id") or settings.slack_default_channel
            if not target:
                raise ValueError("CREATE_REMINDER: no user_id, channel_id, or SLACK_DEFAULT_CHANNEL configured")
            ts = await self.slack.post_message(
                channel_id=target,
                text=f"⏰ *Commitment Reminder*\n{reminder_text}",
            )
            return {"slack_ts": ts, "reminder_type": "slack_dm"}

        else:
            raise NotImplementedError(f"No executor for action_type={action.action_type}")
